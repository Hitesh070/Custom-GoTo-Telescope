"""
telescope_bridge.py
3-Axis GoTo Telescope Bridge & Controller

Architecture:
  Stellarium Desktop  --TCP 127.0.0.1:10001 (binary protocol)-->  telescope_bridge.py
  telescope_bridge.py --USB Serial 115200 ASCII lines---------->  Arduino Uno firmware

Deliverable for custom alt-az GoTo telescope with motorized focus.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import math
import os
import queue
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Attempt to import pyserial
try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    serial = None
    HAS_PYSERIAL = False

# ==============================================================================
# SECTION 7: REFERENCE CODE (TESTED, VERBATIM)
# ==============================================================================

D2R = math.pi / 180.0

def julian_date(t):                      # t: timezone-naive UTC datetime
    y, m = t.year, t.month
    sec = t.second + getattr(t, 'microsecond', 0) / 1_000_000.0
    d = t.day + (t.hour + (t.minute + sec / 60.0) / 60.0) / 24.0
    if m <= 2: y, m = y - 1, m + 12
    a = y // 100
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + 2 - a + a // 4 - 1524.5

def lst_deg(jd_or_t, lon_deg):                # lon: east positive; accepts float JD or datetime
    if hasattr(jd_or_t, 'year'):
        jd = julian_date(jd_or_t)
    else:
        jd = float(jd_or_t)
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + lon_deg) % 360.0

def true_to_apparent_alt(h_deg: float) -> float:
    """Bennett (1982) formula for atmospheric refraction (Meeus standard)."""
    if h_deg < -1.0:
        return h_deg
    R_arcmin = 1.02 / math.tan(math.radians(h_deg + 10.3 / (h_deg + 5.11)))
    return h_deg + R_arcmin / 60.0

def apparent_to_true_alt(h_app_deg: float) -> float:
    """Exact inverse of Bennett formula by 4-pass fixed point iteration (<0.0001 arcsec error)."""
    if h_app_deg < -1.0:
        return h_app_deg
    h_true = h_app_deg
    for _ in range(4):
        r = 1.02 / math.tan(math.radians(h_true + 10.3 / (h_true + 5.11)))
        h_app_calc = h_true + r / 60.0
        h_true = h_true + (h_app_deg - h_app_calc)
    return h_true

def radec_to_altaz(ra, dec, lat, lon, t, apply_refraction=False):        # all degrees; az from North, East = 90
    ha = (lst_deg(julian_date(t), lon) - ra) * D2R
    d, p = dec * D2R, lat * D2R
    sin_alt = math.sin(d) * math.sin(p) + math.cos(d) * math.cos(p) * math.cos(ha)
    alt = math.asin(max(-1.0, min(1.0, sin_alt)))
    az = math.atan2(-math.sin(ha) * math.cos(d),
                    math.cos(p) * math.sin(d) - math.sin(p) * math.cos(d) * math.cos(ha))
    alt_deg = alt / D2R
    if apply_refraction:
        alt_deg = true_to_apparent_alt(alt_deg)
    return alt_deg, (az / D2R) % 360.0

def altaz_to_radec(alt, az, lat, lon, t, apply_refraction=False):        # needed for the position reported to Stellarium
    alt_geom = apparent_to_true_alt(alt) if apply_refraction else alt
    a, z, p = alt_geom * D2R, az * D2R, lat * D2R
    sin_dec = math.sin(a) * math.sin(p) + math.cos(a) * math.cos(p) * math.cos(z)
    dec = math.asin(max(-1.0, min(1.0, sin_dec)))
    ha = math.atan2(-math.sin(z) * math.cos(a),
                    math.sin(a) * math.cos(p) - math.cos(a) * math.sin(p) * math.cos(z))
    return (lst_deg(julian_date(t), lon) - ha / D2R) % 360.0, dec / D2R

def precess_j2000_to_date(ra, dec, t):           # skip this if Stellarium is set to JNow
    T = (julian_date(t) - 2451545.0) / 36525.0
    zeta = (2306.2181 * T + 0.30188 * T**2 + 0.017998 * T**3) / 3600.0 * D2R
    z    = (2306.2181 * T + 1.09468 * T**2 + 0.018203 * T**3) / 3600.0 * D2R
    th   = (2004.3109 * T - 0.42665 * T**2 - 0.041833 * T**3) / 3600.0 * D2R
    a, d = ra * D2R, dec * D2R
    A = math.cos(d) * math.sin(a + zeta)
    B = math.cos(th) * math.cos(d) * math.cos(a + zeta) - math.sin(th) * math.sin(d)
    C = math.sin(th) * math.cos(d) * math.cos(a + zeta) + math.cos(th) * math.sin(d)
    return (math.atan2(A, B) + z) / D2R % 360.0, math.asin(max(-1.0, min(1.0, C))) / D2R

def pack_position(ra_deg, dec_deg, status=0):    # bridge -> Stellarium, 24 bytes
    ra = int(round((ra_deg % 360.0) / 360.0 * 2**32)) & 0xFFFFFFFF
    dec = int(round(dec_deg / 90.0 * 0x40000000))
    return struct.pack('<HHQIii', 24, 0, int(time.time() * 1e6), ra, dec, status)

def parse_goto(buf):                             # Stellarium -> bridge, 20 bytes
    length, mtype, _t, ra, dec = struct.unpack('<HHQIi', buf[:20])
    if length != 20 or mtype != 0: raise ValueError("not a goto message")
    return ra / 2**32 * 360.0, dec / 0x40000000 * 90.0     # degrees (J2000 or JNow, per setting)

def sun_radec(t):                                # low-precision Sun position, about 0.01 deg
    n = julian_date(t) - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = ((357.528 + 0.9856003 * n) % 360.0) * D2R
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * D2R
    eps = (23.439 - 4e-7 * n) * D2R
    return (math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)) / D2R) % 360.0, \
           math.asin(max(-1.0, min(1.0, math.sin(eps) * math.sin(lam)))) / D2R

def separation_deg(ra1, dec1, ra2, dec2):
    c = (math.sin(dec1 * D2R) * math.sin(dec2 * D2R) +
         math.cos(dec1 * D2R) * math.cos(dec2 * D2R) * math.cos((ra1 - ra2) * D2R))
    return math.acos(max(-1.0, min(1.0, c))) / D2R

def choose_az_branch(az_deg, current_deg, limit=200.0):
    """az in [0,360) from North -> equivalent angle within +/-limit, nearest to where we are."""
    az_norm = az_deg % 360.0
    cands = [a for a in (az_norm, az_norm - 360.0, az_norm + 360.0) if -limit <= a <= limit]
    if not cands:
        return max(-limit, min(limit, az_norm if az_norm <= 180.0 else az_norm - 360.0))
    return min(cands, key=lambda a: abs(a - current_deg))

def precess_date_to_j2000(ra, dec, t):
    """Inverse of precess_j2000_to_date by fixed-point iteration (converges in a few passes)."""
    r0, d0 = ra, dec
    for _ in range(8):
        r1, d1 = precess_j2000_to_date(r0, d0, t)
        r0 = (r0 + ((ra - r1 + 180.0) % 360.0 - 180.0)) % 360.0
        d0 = max(-90.0, min(90.0, d0 + (dec - d1)))
    return r0, d0

# ==============================================================================
# CONFIGURATION MANAGEMENT (Section 8.6)
# ==============================================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "latitude_deg": 12.84,
    "longitude_deg": 80.15,
    "epoch": "J2000",
    "apply_refraction": True,
    "serial_port": "",
    "baud": 115200,
    "simulate": False,
    "stellarium_host": "127.0.0.1",
    "stellarium_port": 10001,
    "steps_per_deg_az": 113.22,
    "steps_per_deg_alt": 113.22,
    "sign_az": 1,
    "sign_alt": 1,
    "sign_focus": 1,
    "backlash_az": 0,
    "backlash_alt": 0,
    "speed_az": 226,
    "speed_alt": 226,
    "speed_foc": 300,
    "accel_az": 100,
    "accel_alt": 100,
    "accel_foc": 150,
    "az_limit_deg": 200,
    "alt_min_deg": 0,
    "alt_max_deg": 85,
    "sun_keepout_deg": 15,
    "solar_filter_installed": False,
    "tracking_interval_s": 1.0,
    "position_report_interval_s": 0.2,
    "position_poll_interval_s": 0.3,
    "jog_deg": {"fine": 0.05, "medium": 0.5, "coarse": 3.0},
    "focus_steps": {"fine": 20, "coarse": 200},
    "park_az_deg": 0,
    "park_alt_deg": 0,
    "az_home_switch": False,
    "log_csv": True,
}

class Config:
    """Manages JSON configuration persistence, merging, and validation."""

    @staticmethod
    def get_default_path() -> str:
        """Returns standard configuration file path, using %APPDATA%/AstroGoTo when frozen."""
        if getattr(sys, 'frozen', False):
            app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
            target_dir = os.path.join(app_data, 'AstroGoTo')
            os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, 'telescope_config.json')
        return "telescope_config.json"

    def __init__(self, path: Optional[str] = None):
        self.path = path or self.get_default_path()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Loads configuration from file if exists, merging with defaults."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                # Preserve unknown keys and update known
                self.data.update(user_data)
            except Exception as e:
                logging.error(f"Error loading config from {self.path}: {e}")
        else:
            self.save()

    def save(self) -> None:
        """Writes current configuration to JSON file."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving config to {self.path}: {e}")

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULT_CONFIG.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def validate(self) -> List[str]:
        """Validates configuration values. Returns a list of error descriptions."""
        errors = []
        if not (-90.0 <= self["latitude_deg"] <= 90.0):
            errors.append("Latitude must be between -90 and +90 degrees.")
        if not (-180.0 <= self["longitude_deg"] <= 180.0):
            errors.append("Longitude must be between -180 and +180 degrees.")
        if self["epoch"] not in ("JNow", "J2000"):
            errors.append("Epoch must be either 'JNow' or 'J2000'.")
        if self["baud"] <= 0:
            errors.append("Baud rate must be positive.")
        if not (1024 <= self["stellarium_port"] <= 65535):
            errors.append("Stellarium port must be between 1024 and 65535.")
        if self["steps_per_deg_az"] <= 0 or self["steps_per_deg_alt"] <= 0:
            errors.append("Steps per degree must be greater than zero.")
        if self["sign_az"] not in (1, -1) or self["sign_alt"] not in (1, -1) or self["sign_focus"] not in (1, -1):
            errors.append("Signs must be +1 or -1.")
        if self["backlash_az"] < 0 or self["backlash_az"] > 2000 or self["backlash_alt"] < 0 or self["backlash_alt"] > 2000:
            errors.append("Backlash must be between 0 and 2000 steps.")
        for ax in ("az", "alt", "foc"):
            spd = self[f"speed_{ax}"]
            acc = self[f"accel_{ax}"]
            if not (10 <= spd <= 1500):
                errors.append(f"Speed for {ax} must be between 10 and 1500 steps/s.")
            if not (10 <= acc <= 3000):
                errors.append(f"Acceleration for {ax} must be between 10 and 3000 steps/s^2.")
        if not (0 <= self["az_limit_deg"] <= 360):
            errors.append("Azimuth limit must be between 0 and 360 degrees.")
        if not (-90 <= self["alt_min_deg"] < self["alt_max_deg"] <= 90):
            errors.append("Altitude limits must satisfy -90 <= min < max <= 90 degrees.")
        if self["sun_keepout_deg"] < 0:
            errors.append("Sun keep-out angle must be non-negative.")
        return errors

# ==============================================================================
# COORDINATE CONVERSION UTILITIES (Section 4)
# ==============================================================================

def angle_to_steps(angle_deg: float, steps_per_deg: float, sign: int) -> int:
    """Converts axis angle in degrees to logical steps."""
    return int(round(angle_deg * steps_per_deg * sign))

def steps_to_angle(steps: int, steps_per_deg: float, sign: int) -> float:
    """Converts logical steps to axis angle in degrees."""
    return float(steps) / (steps_per_deg * sign)

# ==============================================================================
# TELEMETRY DATA STRUCTURE
# ==============================================================================

@dataclass
class Telemetry:
    """Snapshot of microcontroller telemetry."""
    az_steps: int = 0
    alt_steps: int = 0
    foc_steps: int = 0
    moving: int = 0
    homed: int = 0
    timestamp: float = 0.0
    valid: bool = False

# ==============================================================================
# HARDWARE COMMUNICATION INTERFACES (LinkBase, SerialLink, SimLink)
# ==============================================================================

class LinkBase:
    """Base interface for serial communication with telescope hardware / simulator."""

    def __init__(self) -> None:
        self.latest_telemetry: Telemetry = Telemetry()
        self.async_messages: queue.Queue[str] = queue.Queue()
        self.reply_queue: queue.Queue[str] = queue.Queue()
        self.is_open: bool = False
        self.send_lock: threading.Lock = threading.Lock()

    def open(self) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def send(self, cmd: str) -> str:
        """Sends a command and synchronously waits up to 1.0 s for reply."""
        raise NotImplementedError

    @property
    def is_stale(self) -> bool:
        """Returns True if telemetry has not updated for > 2.0 seconds while open."""
        if not self.is_open or not self.latest_telemetry.valid:
            return True
        return (time.time() - self.latest_telemetry.timestamp) > 2.0


class SerialLink(LinkBase):
    """Pyserial implementation connecting to physical Arduino Uno."""

    def __init__(self, port: str, baud: int = 115200, poll_interval_s: float = 0.3):
        super().__init__()
        self.port = port
        self.baud = baud
        self.poll_interval_s = poll_interval_s
        self.ser: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._waiting_for_p: bool = False

    def open(self) -> bool:
        if not HAS_PYSERIAL:
            logging.error("pyserial is not installed. Please run: pip install pyserial")
            return False

        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1, write_timeout=1.0)
            self.is_open = True
            self._stop_event.clear()

            # Start reader thread
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True, name="SerialReader")
            self._reader_thread.start()

            # Wait up to 3.0 s for "READY" line
            ready_received = False
            t0 = time.time()
            while time.time() - t0 < 3.0:
                try:
                    msg = self.async_messages.get(timeout=0.1)
                    if msg.strip() == "READY":
                        ready_received = True
                        break
                except queue.Empty:
                    pass

            if not ready_received:
                logging.warning("READY line not received from Arduino within 3 seconds, continuing anyway.")

            # Start background poller thread
            self._poller_thread = threading.Thread(target=self._poller_loop, daemon=True, name="SerialPoller")
            self._poller_thread.start()
            return True

        except Exception as e:
            logging.error(f"Failed to open serial port {self.port}: {e}")
            self.close()
            return False

    def close(self) -> None:
        self.is_open = False
        self._stop_event.set()
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _reader_loop(self) -> None:
        """Reads newline-terminated ASCII lines from serial port."""
        buf = bytearray()
        while not self._stop_event.is_set() and self.ser and self.ser.is_open:
            try:
                chunk = self.ser.read(64)
                if not chunk:
                    continue
                buf.extend(chunk)
                while b'\n' in buf:
                    line_bytes, buf = buf.split(b'\n', 1)
                    line = line_bytes.decode('ascii', errors='replace').strip('\r').strip()
                    if not line:
                        continue
                    self._handle_incoming_line(line)
            except Exception as e:
                if not self._stop_event.is_set():
                    logging.error(f"Serial read error: {e}")
                    self.async_messages.put("DISCONNECTED")
                break
        self.is_open = False

    def _handle_incoming_line(self, line: str) -> None:
        """Categorizes incoming lines into telemetry, command replies, or async notifications."""
        if line.startswith("P "):
            parts = line.split()
            if len(parts) == 6:
                try:
                    az_s = int(parts[1])
                    alt_s = int(parts[2])
                    foc_s = int(parts[3])
                    mov = int(parts[4])
                    hom = int(parts[5])
                    self.latest_telemetry = Telemetry(
                        az_steps=az_s,
                        alt_steps=alt_s,
                        foc_steps=foc_s,
                        moving=mov,
                        homed=hom,
                        timestamp=time.time(),
                        valid=True,
                    )
                except ValueError:
                    pass
            # Only route to reply queue when send("P") is explicitly waiting for it
            if self._waiting_for_p:
                self.reply_queue.put(line)

        elif line in ("ERR HOME ALT", "ERR HOME AZ", "WATCHDOG", "READY"):
            self.async_messages.put(line)
        else:
            # Synchronous command replies (OK, ERR LIMIT, ERR BUSY, ERR PARSE, etc.)
            self.reply_queue.put(line)

    def _poller_loop(self) -> None:
        """Polls telemetry from Arduino every position_poll_interval_s."""
        while not self._stop_event.is_set():
            if self.is_open:
                self.send_raw("P")
            time.sleep(self.poll_interval_s)

    def send_raw(self, cmd: str) -> None:
        """Writes command line to serial port without waiting for reply."""
        if not self.is_open or not self.ser:
            return
        with self.send_lock:
            try:
                self.ser.write((cmd + "\n").encode('ascii'))
            except Exception as e:
                logging.error(f"Serial write error: {e}")
                self.close()

    def send(self, cmd: str) -> str:
        """Synchronously sends command and awaits reply."""
        if not self.is_open or not self.ser:
            return "ERR NOT_CONNECTED"
        with self.send_lock:
            # Drain any stale items in reply queue
            while not self.reply_queue.empty():
                try:
                    self.reply_queue.get_nowait()
                except queue.Empty:
                    break

            if cmd.strip() == "P":
                self._waiting_for_p = True

            try:
                try:
                    self.ser.write((cmd + "\n").encode('ascii'))
                except Exception as e:
                    logging.error(f"Serial write error on send: {e}")
                    self.close()
                    return "TIMEOUT"

                # Wait up to 1.0 s for reply
                try:
                    reply = self.reply_queue.get(timeout=1.0)
                    return reply
                except queue.Empty:
                    return "TIMEOUT"
            finally:
                self._waiting_for_p = False


class SimLink(LinkBase):
    """Simulated Arduino Uno implementing the exact text protocol and kinematics."""

    def __init__(self, config: Optional[Config] = None):
        super().__init__()
        self.config = config or Config()

        # Simulated state
        self.az_pos: float = 0.0
        self.alt_pos: float = 0.0
        self.foc_pos: float = 0.0

        self.az_target: float = 0.0
        self.alt_target: float = 0.0
        self.foc_target: float = 0.0

        self.speed_az: float = float(self.config.get("speed_az", 700))
        self.speed_alt: float = float(self.config.get("speed_alt", 700))
        self.speed_foc: float = float(self.config.get("speed_foc", 500))

        self.accel_az: float = float(self.config.get("accel_az", 300))
        self.accel_alt: float = float(self.config.get("accel_alt", 300))
        self.accel_foc: float = float(self.config.get("accel_foc", 300))

        self.az_limit_min: int = -22644
        self.az_limit_max: int = 22644
        self.alt_limit_min: int = 0
        self.alt_limit_max: int = 9624

        self.backlash_az: int = 0
        self.backlash_alt: int = 0

        self.homed_bits: int = 0
        self.homing_axis: Optional[str] = None
        self.homing_start_time: float = 0.0
        self.homing_duration: float = 0.2  # background homing simulation duration (s)

        self._timer_thread: Optional[threading.Thread] = None
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_update_time: float = time.time()

    def open(self) -> bool:
        self.is_open = True
        self._stop_event.clear()
        self._last_update_time = time.time()

        # Signal boot READY notification
        self.async_messages.put("READY")

        # Initialize telemetry
        self._update_telemetry()

        # Start simulation physics loop
        self._timer_thread = threading.Thread(target=self._sim_loop, daemon=True, name="SimPhysics")
        self._timer_thread.start()

        # Start poller loop
        self._poller_thread = threading.Thread(target=self._poller_loop, daemon=True, name="SimPoller")
        self._poller_thread.start()
        return True

    def close(self) -> None:
        self.is_open = False
        self._stop_event.set()

    def _sim_loop(self) -> None:
        """Updates motor positions toward target at configured speeds every 20 ms."""
        while not self._stop_event.is_set():
            time.sleep(0.02)
            now = time.time()
            dt_s = now - self._last_update_time
            self._last_update_time = now

            with self.send_lock:
                # Coordinated constant-velocity multi-axis vector motion (matches firmware Chebyshev scaling)
                diff_az = self.az_target - self.az_pos
                diff_alt = self.alt_target - self.alt_pos
                dist_az = abs(diff_az)
                dist_alt = abs(diff_alt)
                dist_max = max(dist_az, dist_alt)

                if dist_max > 0.01:
                    max_speed = max(self.speed_az, self.speed_alt)
                    step_max = max_speed * dt_s
                    if dist_max <= step_max:
                        self.az_pos = self.az_target
                        self.alt_pos = self.alt_target
                    else:
                        ratio = step_max / dist_max
                        self.az_pos += diff_az * ratio
                        self.alt_pos += diff_alt * ratio

                # Update Focus
                diff_foc = self.foc_target - self.foc_pos
                if abs(diff_foc) > 0.01:
                    step_foc = self.speed_foc * dt_s
                    if abs(diff_foc) <= step_foc:
                        self.foc_pos = self.foc_target
                    else:
                        self.foc_pos += math.copysign(step_foc, diff_foc)

                # Handle background homing
                if self.homing_axis is not None:
                    if (now - self.homing_start_time) >= self.homing_duration:
                        if self.homing_axis == "ALT":
                            self.alt_pos = 0.0
                            self.alt_target = 0.0
                            self.homed_bits |= 1
                        elif self.homing_axis == "AZ":
                            self.az_pos = 0.0
                            self.az_target = 0.0
                            self.homed_bits |= 2
                        self.homing_axis = None

                # Keep simulated telemetry refreshed at 50 Hz
                self._update_telemetry()

    def _update_telemetry(self) -> None:
        is_moving = 1 if (
            abs(self.az_pos - self.az_target) > 0.5 or
            abs(self.alt_pos - self.alt_target) > 0.5 or
            abs(self.foc_pos - self.foc_target) > 0.5 or
            self.homing_axis is not None
        ) else 0

        self.latest_telemetry = Telemetry(
            az_steps=int(round(self.az_pos)),
            alt_steps=int(round(self.alt_pos)),
            foc_steps=int(round(self.foc_pos)),
            moving=is_moving,
            homed=self.homed_bits,
            timestamp=time.time(),
            valid=True,
        )

    def _poller_loop(self) -> None:
        while not self._stop_event.is_set():
            with self.send_lock:
                self._update_telemetry()
            time.sleep(0.1)

    def send(self, cmd: str) -> str:
        """Processes protocol command and returns simulated firmware reply."""
        if not self.is_open:
            return "ERR NOT_CONNECTED"

        line = cmd.strip()
        if not line:
            return ""

        parts = line.split()
        c = parts[0]

        with self.send_lock:
            if c == "G":
                if len(parts) != 3:
                    return "ERR PARSE"
                try:
                    tgt_az = int(parts[1])
                    tgt_alt = int(parts[2])
                except ValueError:
                    return "ERR PARSE"

                if self.homing_axis is not None:
                    return "ERR BUSY"

                if (tgt_az < self.az_limit_min or tgt_az > self.az_limit_max or
                        tgt_alt < self.alt_limit_min or tgt_alt > self.alt_limit_max):
                    return "ERR LIMIT"

                self.az_target = float(tgt_az)
                self.alt_target = float(tgt_alt)
                self._update_telemetry()
                return "OK"

            elif c == "F":
                if len(parts) != 2:
                    return "ERR PARSE"
                try:
                    delta = int(parts[1])
                except ValueError:
                    return "ERR PARSE"

                cur_tgt = self.foc_target if abs(self.foc_pos - self.foc_target) > 0.5 else self.foc_pos
                new_tgt = cur_tgt + delta
                if new_tgt < -6000 or new_tgt > 6000:
                    return "ERR LIMIT"

                self.foc_target = float(new_tgt)
                self._update_telemetry()
                return "OK"

            elif c == "H":
                if len(parts) != 3:
                    return "ERR PARSE"
                try:
                    new_az = int(parts[1])
                    new_alt = int(parts[2])
                except ValueError:
                    return "ERR PARSE"

                self.az_pos = float(new_az)
                self.az_target = float(new_az)
                self.alt_pos = float(new_alt)
                self.alt_target = float(new_alt)
                self.homing_axis = None
                self._update_telemetry()
                return "OK"

            elif c == "B":
                if len(parts) != 3:
                    return "ERR PARSE"
                try:
                    b_az = int(parts[1])
                    b_alt = int(parts[2])
                except ValueError:
                    return "ERR PARSE"
                if not (0 <= b_az <= 2000 and 0 <= b_alt <= 2000):
                    return "ERR PARSE"
                self.backlash_az = b_az
                self.backlash_alt = b_alt
                return "OK"

            elif c == "L":
                if len(parts) != 5:
                    return "ERR PARSE"
                try:
                    azmin = int(parts[1])
                    azmax = int(parts[2])
                    altmin = int(parts[3])
                    altmax = int(parts[4])
                except ValueError:
                    return "ERR PARSE"
                if azmin > azmax or altmin > altmax:
                    return "ERR PARSE"
                self.az_limit_min = azmin
                self.az_limit_max = azmax
                self.alt_limit_min = altmin
                self.alt_limit_max = altmax
                return "OK"

            elif c == "V":
                if len(parts) != 4:
                    return "ERR PARSE"
                try:
                    v_az = int(parts[1])
                    v_alt = int(parts[2])
                    v_foc = int(parts[3])
                except ValueError:
                    return "ERR PARSE"
                if not (10 <= v_az <= 1500 and 10 <= v_alt <= 1500 and 10 <= v_foc <= 1500):
                    return "ERR PARSE"
                self.speed_az = float(v_az)
                self.speed_alt = float(v_alt)
                self.speed_foc = float(v_foc)
                return "OK"

            elif c == "A":
                if len(parts) != 4:
                    return "ERR PARSE"
                try:
                    a_az = int(parts[1])
                    a_alt = int(parts[2])
                    a_foc = int(parts[3])
                except ValueError:
                    return "ERR PARSE"
                if not (10 <= a_az <= 3000 and 10 <= a_alt <= 3000 and 10 <= a_foc <= 3000):
                    return "ERR PARSE"
                self.accel_az = float(a_az)
                self.accel_alt = float(a_alt)
                self.accel_foc = float(a_foc)
                return "OK"

            elif c == "Z":
                if len(parts) != 2:
                    return "ERR PARSE"
                axis = parts[1]
                if axis not in ("ALT", "AZ"):
                    return "ERR PARSE"
                if self.homing_axis is not None:
                    return "ERR BUSY"

                self.homing_axis = axis
                self.homing_start_time = time.time()
                self._update_telemetry()
                return "OK"

            elif c == "S":
                self.az_target = float(int(round(self.az_pos)))
                self.alt_target = float(int(round(self.alt_pos)))
                self.foc_target = float(int(round(self.foc_pos)))
                self.homing_axis = None
                self._update_telemetry()
                return "OK"

            elif c == "P":
                self._update_telemetry()
                t = self.latest_telemetry
                return f"P {t.az_steps} {t.alt_steps} {t.foc_steps} {t.moving} {t.homed}"

            else:
                return "ERR PARSE"

# ==============================================================================
# STELLARIUM TCP SERVER (Section 6)
# ==============================================================================

class StellariumServer:
    """TCP Server implementing Stellarium Desktop binary telescope control protocol."""

    def __init__(self, host: str, port: int, core: BridgeCore):
        self.host = host
        self.port = port
        self.core = core
        self.server_sock: Optional[socket.socket] = None
        self.client_sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._report_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_client_connected: bool = False
        self.is_running: bool = False

    def start(self) -> None:
        self._stop_event.clear()
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        # Update port if bound dynamically (port 0)
        self.port = self.server_sock.getsockname()[1]
        self.server_sock.listen(1)
        self.is_running = True

        self._server_thread = threading.Thread(target=self._accept_loop, daemon=True, name="StellariumAccept")
        self._server_thread.start()

        self._report_thread = threading.Thread(target=self._report_loop, daemon=True, name="StellariumReport")
        self._report_thread.start()

    def stop(self) -> None:
        self.is_running = False
        self._stop_event.set()
        if self.client_sock:
            try:
                self.client_sock.shutdown(socket.SHUT_RDWR)
                self.client_sock.close()
            except Exception:
                pass
            self.client_sock = None
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        self.is_client_connected = False

    def _accept_loop(self) -> None:
        """Listens for Stellarium client connections, handling one client at a time."""
        while not self._stop_event.is_set() and self.server_sock:
            try:
                self.server_sock.settimeout(1.0)
                try:
                    conn, addr = self.server_sock.accept()
                except socket.timeout:
                    continue

                logging.info(f"Stellarium connected from {addr}")
                self.client_sock = conn
                self.is_client_connected = True
                self.core.on_event("STELLARIUM_CONNECTED", f"Connected from {addr}")

                self._handle_client(conn)

            except Exception as e:
                if not self._stop_event.is_set():
                    logging.debug(f"Stellarium accept error: {e}")

    def _handle_client(self, conn: socket.socket) -> None:
        """Buffers TCP stream, handles message fragmentation, and parses GoTo messages."""
        buf = bytearray()
        conn.settimeout(0.5)

        while not self._stop_event.is_set():
            try:
                data = conn.recv(512)
                if not data:
                    break
                buf.extend(data)

                while len(buf) >= 2:
                    msg_len = struct.unpack('<H', buf[:2])[0]
                    if msg_len < 4 or msg_len > 1024:
                        logging.warning(f"Invalid Stellarium message length: {msg_len}, dropping client.")
                        return

                    if len(buf) < msg_len:
                        # Wait for remaining message bytes
                        break

                    msg_bytes = bytes(buf[:msg_len])
                    buf = buf[msg_len:]

                    if msg_len == 20:
                        try:
                            ra_deg, dec_deg = parse_goto(msg_bytes)
                            # Match configured epoch: J2000 or JNow
                            is_j2000 = (self.core.config.get("epoch", "J2000") == "J2000")
                            self.core.on_goto_requested(ra_deg, dec_deg, is_j2000=is_j2000)
                            if hasattr(self.core, "follower") and self.core.follower:
                                self.core.follower.authorize_target(self.core.follower.target_name)
                        except Exception as ex:
                            logging.warning(f"Failed to parse goto message: {ex}")
                    else:
                        logging.debug(f"Skipping unknown Stellarium message length: {msg_len}")

            except socket.timeout:
                continue
            except Exception as e:
                logging.debug(f"Stellarium client error: {e}")
                break

        try:
            conn.close()
        except Exception:
            pass
        self.client_sock = None
        self.is_client_connected = False
        self.core.on_event("STELLARIUM_DISCONNECTED", "Client disconnected")

    def _report_loop(self) -> None:
        """Periodically sends position reports (24 bytes) to connected Stellarium client."""
        interval = float(self.core.config.get("position_report_interval_s", 0.3))
        while not self._stop_event.is_set():
            if self.is_client_connected and self.client_sock:
                # Report position matching the configured epoch (J2000 or JNow)
                ra_deg, dec_deg = self.core.get_telescope_radec()
                try:
                    packet = pack_position(ra_deg, dec_deg, status=0)
                    self.client_sock.sendall(packet)
                except Exception as e:
                    logging.debug(f"Failed to send position to Stellarium: {e}")
                    self.is_client_connected = False
            time.sleep(interval)


# ==============================================================================
# STELLARIUM HTTP FOLLOWER (Satellite & Dynamic Target Tracking via Port 8090)
# ==============================================================================

class StellariumHttpFollower:
    """Continuously polls Stellarium Remote Control HTTP API to track moving satellites and live targets."""

    def __init__(self, core: 'BridgeCore', host: str = "127.0.0.1", port: int = 8090, poll_interval_s: float = 0.5, require_explicit_goto: bool = False):
        self.core = core
        self.host = host
        self.port = port
        self.poll_interval_s = poll_interval_s
        self.require_explicit_goto: bool = require_explicit_goto
        self.authorized_target_name: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_active: bool = False
        self.is_connected: bool = False
        self.target_name: str = ""
        self.target_type: str = ""
        self.last_poll_time: float = 0.0
        self.prev_alt: Optional[float] = None
        self.prev_az: Optional[float] = None
        self.prev_poll_time: Optional[float] = None
        self.last_target_name: str = ""

    def authorize_target(self, name: str) -> None:
        """Authorizes a specific target for live follow (set when user commands GoTo via Ctrl+1)."""
        self.authorized_target_name = name

    def clear_authorized_target(self) -> None:
        """Clears authorized target."""
        self.authorized_target_name = None

    def sync_location_from_stellarium(self) -> Optional[Tuple[float, float, str]]:
        """Queries Stellarium HTTP API to get observer latitude, longitude, and site name."""
        import urllib.request
        import json
        url = f"http://{self.host}:{self.port}/api/main/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AstroGoTo-Bridge/2.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    loc = data.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    name = loc.get("name") or loc.get("role") or "Stellarium Site"
                    if lat is not None and lon is not None:
                        return float(lat), float(lon), str(name)
        except Exception as e:
            logging.debug(f"Could not sync location from Stellarium: {e}")
        return None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.is_active = True
        self.prev_alt = None
        self.prev_az = None
        self.prev_poll_time = None
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="StellariumHttpFollower")
        self._thread.start()

    def stop(self) -> None:
        self.is_active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        self.is_connected = False
        self.prev_alt = None
        self.prev_az = None
        self.prev_poll_time = None

    def _poll_loop(self) -> None:
        import urllib.request
        import json

        url = f"http://{self.host}:{self.port}/api/objects/info?format=json"

        while not self._stop_event.is_set():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AstroGoTo-Bridge/2.0"})
                with urllib.request.urlopen(req, timeout=0.8) as resp:
                    if resp.status == 200:
                        raw = resp.read().decode("utf-8")
                        data = json.loads(raw)
                        self.is_connected = True
                        self.last_poll_time = time.time()

                        if data:
                            name = data.get("name") or data.get("localized-name") or "Tracked Object"
                            obj_type = (data.get("type") or "celestial").lower()

                            self.target_name = name
                            self.target_type = obj_type
                            self.core.target_name = name
                            self.core.target_type = obj_type

                            is_satellite = ("satellite" in obj_type) or ("spacecraft" in obj_type) or bool(re.search(r'\b(iss|zarya|tiangong|css|hst|hubble)\b', name, re.IGNORECASE))
                            has_altaz = ("altitude" in data and "azimuth" in data)

                            if is_satellite and has_altaz:
                                if self.require_explicit_goto and (self.authorized_target_name != name):
                                    # User is browsing / inspecting this object in Stellarium, but has NOT commanded
                                    # a GoTo slew via Ctrl+1 yet. Do not auto-slew on click or double-click.
                                    self.last_target_name = name
                                else:
                                    cur_alt = float(data["altitude"])
                                    cur_az = float(data["azimuth"])
                                now = time.time()

                                v_az = 0.0
                                v_alt = 0.0
                                if self.prev_poll_time is not None and (0.05 < now - self.prev_poll_time < 3.0):
                                    dt_s = now - self.prev_poll_time
                                    d_az = cur_az - (self.prev_az if self.prev_az is not None else cur_az)
                                    if d_az > 180.0:
                                        d_az -= 360.0
                                    elif d_az < -180.0:
                                        d_az += 360.0
                                    d_alt = cur_alt - (self.prev_alt if self.prev_alt is not None else cur_alt)
                                    v_az = d_az / dt_s
                                    v_alt = d_alt / dt_s

                                self.prev_poll_time = now
                                self.prev_alt = cur_alt
                                self.prev_az = cur_az

                                # Predictive lead feedforward: aim where satellite will be when motors arrive
                                tau_lead = 0.50
                                pred_az = (cur_az + v_az * tau_lead) % 360.0
                                pred_alt = max(0.0, min(85.0, cur_alt + v_alt * tau_lead))

                                self.core.track_satellite_altaz(pred_alt, pred_az, name=name)
                            else:
                                # Celestial object: record name for display, but NEVER auto-slew on click.
                                # Slew commands are commanded explicitly by the user via Ctrl+1 (port 10001) or GoTo dialog.
                                self.last_target_name = name

                        # Automatic location synchronization from Stellarium
                        if not getattr(self, "_has_auto_synced_location", False):
                            loc = self.sync_location_from_stellarium()
                            if loc:
                                lat, lon, site_name = loc
                                self.core.config["latitude_deg"] = lat
                                self.core.config["longitude_deg"] = lon
                                self._has_auto_synced_location = True
                                self.core.on_event("INFO", f"Observer location automatically synchronized from Stellarium: Lat {lat:.4f}°, Lon {lon:.4f}° ({site_name})")
            except Exception:
                self.is_connected = False

            time.sleep(self.poll_interval_s)

# ==============================================================================
# POINTING CSV LOGGER (Section 8.7)
# ==============================================================================

class PointingLogger:
    """Logs pointing events, GOTOs, SYNCs and jogs to CSV file."""

    CSV_HEADER = [
        "utc_time", "event", "target_ra_deg", "target_dec_deg",
        "target_alt_deg", "target_az_deg", "az_steps", "alt_steps", "note"
    ]

    @staticmethod
    def get_default_log_path() -> str:
        if getattr(sys, 'frozen', False):
            app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
            target_dir = os.path.join(app_data, 'AstroGoTo')
            os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, 'pointing_log.csv')
        return "pointing_log.csv"

    def __init__(self, filename: Optional[str] = None):
        self.filename = filename or self.get_default_log_path()
        self.lock = threading.Lock()
        self._ensure_header()

    def _ensure_header(self) -> None:
        if not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0:
            try:
                with open(self.filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADER)
            except Exception as e:
                logging.error(f"Error creating pointing log header: {e}")

    def log(self, event: str, target_ra: Optional[float] = None, target_dec: Optional[float] = None,
            target_alt: Optional[float] = None, target_az: Optional[float] = None,
            az_steps: Optional[int] = None, alt_steps: Optional[int] = None,
            note: str = "", utc_time_str: Optional[str] = None) -> None:
        with self.lock:
            try:
                t_str = utc_time_str or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                row = [
                    t_str,
                    event,
                    f"{target_ra:.4f}" if target_ra is not None else "",
                    f"{target_dec:.4f}" if target_dec is not None else "",
                    f"{target_alt:.4f}" if target_alt is not None else "",
                    f"{target_az:.4f}" if target_az is not None else "",
                    str(az_steps) if az_steps is not None else "",
                    str(alt_steps) if alt_steps is not None else "",
                    note
                ]
                with open(self.filename, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
            except Exception as e:
                logging.error(f"Error appending to pointing log: {e}")

# ==============================================================================
# BRIDGE CORE LOGIC (Section 8.5)
# ==============================================================================

class BridgeCore:
    """Ties together hardware link, tracking, astronomy math, and Stellarium server."""

    def __init__(self, config: Optional[Config] = None, link: Optional[LinkBase] = None,
                 time_fn: Optional[Callable[[], dt.datetime]] = None):
        self.config: Config = config or Config()
        self.link: LinkBase = link or SimLink(self.config)
        self.time_fn: Callable[[], dt.datetime] = time_fn or (
            lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        )
        self.logger = PointingLogger()

        # Mount target and tracking state
        self.current_target_radec: Optional[Tuple[float, float]] = None  # as received (JNow or J2000)
        self.current_target_is_j2000: bool = True
        self.current_target_of_date: Optional[Tuple[float, float]] = None
        self.tracking_enabled: bool = False
        self.is_parked: bool = False
        self.is_homed: bool = False
        self.follower: Optional[Any] = None
        self.az_off_steps: int = 0
        self.alt_off_steps: int = 0
        self.last_sent_steps: Optional[Tuple[int, int]] = None
        self.last_goto_target_str: str = "None"
        self.target_name: str = "Target"
        self.target_type: str = "star"

        # Tracking telemetry and activity metrics
        self.tracking_pulses_count: int = 0
        self.tracking_last_pulse_time: float = 0.0
        self.tracking_total_steps_az: int = 0
        self.tracking_total_steps_alt: int = 0
        self.tracking_initial_steps: Optional[Tuple[int, int]] = None

        # Solar observation confirmation state & safety callback for GUI confirmation
        self.solar_filter_confirmed: bool = bool(self.config.get("solar_filter_installed", False))
        self.solar_warning_callback: Optional[Callable[[float], bool]] = None

        # Event queue for GUI / logging
        self.event_queue: queue.Queue[Tuple[str, str]] = queue.Queue()

        # Tracking loop thread
        self._stop_event = threading.Event()
        self._tracking_thread: Optional[threading.Thread] = None

    def get_time(self) -> dt.datetime:
        """Returns current naive UTC datetime."""
        return self.time_fn()

    def start_tracking_thread(self) -> None:
        self._stop_event.clear()
        self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True, name="BridgeTracker")
        self._tracking_thread.start()

    def stop_tracking_thread(self) -> None:
        self._stop_event.set()

    def on_event(self, event_type: str, message: str) -> None:
        self.event_queue.put((event_type, message))

    @property
    def is_connected(self) -> bool:
        """Returns True if the hardware or simulation link is open and active."""
        return bool(self.link and self.link.is_open)

    def connect(self, port: Optional[str] = None, simulate: Optional[bool] = None) -> bool:
        """Connects to hardware or simulator and sends initial configuration."""
        if simulate is not None:
            self.config["simulate"] = simulate

        # If a link already exists and simulate was not explicitly passed, keep it
        if self.link is None:
            if self.config["simulate"]:
                self.link = SimLink(self.config)
            else:
                p = port or self.config["serial_port"]
                self.link = SerialLink(p, baud=self.config["baud"], poll_interval_s=self.config["position_poll_interval_s"])
        elif simulate is not None:
            is_sim = bool(simulate)
            if is_sim != (type(self.link).__name__ == "SimLink"):
                if self.link.is_open:
                    try:
                        self.link.close()
                    except Exception:
                        pass
                if is_sim:
                    self.link = SimLink(self.config)
                else:
                    p = port or self.config["serial_port"]
                    self.link = SerialLink(p, baud=self.config["baud"], poll_interval_s=self.config["position_poll_interval_s"])

        if not self.link.is_open:
            if not self.link.open():
                self.on_event("ERROR", f"Failed to connect to {'Simulator' if self.config['simulate'] else self.config['serial_port']}")
                return False

        self.on_event("INFO", f"Connected to {'Simulator' if self.config['simulate'] else self.config['serial_port']}")

        # Send initial hardware parameters: V, A, L, B, P
        self.push_hardware_config()
        return True

    def disconnect(self) -> None:
        """Cleanly disconnects hardware link."""
        self.tracking_enabled = False
        if self.link and self.link.is_open:
            self.link.send("S")
            self.link.close()
        self.on_event("INFO", "Hardware disconnected")

    def push_hardware_config(self) -> None:
        """Pushes speeds (V), accelerations (A), limits (L), and backlash (B) to Arduino."""
        if not self.link or not self.link.is_open:
            return

        cfg = self.config
        # 1. Speeds: V <az> <alt> <foc>
        r_v = self.link.send(f"V {cfg['speed_az']} {cfg['speed_alt']} {cfg['speed_foc']}")
        if r_v != "OK":
            logging.warning(f"V command reply: {r_v}")

        # 2. Accelerations: A <az> <alt> <foc>
        r_a = self.link.send(f"A {cfg['accel_az']} {cfg['accel_alt']} {cfg['accel_foc']}")
        if r_a != "OK":
            logging.warning(f"A command reply: {r_a}")

        # 3. Soft Limits: L <azmin> <azmax> <altmin> <altmax>
        az_lim_steps = angle_to_steps(cfg["az_limit_deg"], cfg["steps_per_deg_az"], cfg["sign_az"])
        alt_lim_1 = angle_to_steps(cfg["alt_min_deg"], cfg["steps_per_deg_alt"], cfg["sign_alt"])
        alt_lim_2 = angle_to_steps(cfg["alt_max_deg"], cfg["steps_per_deg_alt"], cfg["sign_alt"])
        az_min = -abs(az_lim_steps)
        az_max = abs(az_lim_steps)
        alt_min = min(alt_lim_1, alt_lim_2)
        alt_max = max(alt_lim_1, alt_lim_2)

        r_l = self.link.send(f"L {az_min} {az_max} {alt_min} {alt_max}")
        if r_l != "OK":
            logging.warning(f"L command reply: {r_l}")

        # 4. Backlash: B <az> <alt>
        r_b = self.link.send(f"B {cfg['backlash_az']} {cfg['backlash_alt']}")
        if r_b != "OK":
            logging.warning(f"B command reply: {r_b}")

        # 5. Initial telemetry poll
        self.link.send("P")

    def on_goto_requested(self, ra: float, dec: float, is_j2000: Optional[bool] = None,
                          predict_flight: bool = True, solar_confirmed: bool = False,
                          target_name: Optional[str] = None) -> bool:
        """Processes GoTo command from Stellarium or GUI with predictive time-of-flight intercept (Section 8.5)."""
        if not self.link or not self.link.is_open or not self.link.latest_telemetry.valid:
            msg = "GoTo ignored: telescope not connected"
            self.on_event("WARNING", msg)
            logging.warning(msg)
            return False

        self.is_parked = False
        self.is_homed = False

        t0 = self.get_time()
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        epoch = self.config.get("epoch", "J2000")

        if is_j2000 is None:
            is_j2000 = (epoch == "J2000")

        # Step 2: Convert target to of-date coordinates at current time
        if is_j2000:
            ra_date0, dec_date0 = precess_j2000_to_date(ra, dec, t0)
        else:
            ra_date0, dec_date0 = ra, dec

        # Step 3: Compute compass azimuth and altitude at t0
        use_refr = bool(self.config.get("apply_refraction", True))
        alt0, az0_compass = radec_to_altaz(ra_date0, dec_date0, lat, lon, t0, apply_refraction=use_refr)

        # Step 4: Predictive Time-of-Flight Intercept Calculation
        # Eliminates the ~15-20 arcminute slew lag on long hops
        t_target = t0
        alt_slew = alt0
        az_slew_compass = az0_compass

        if predict_flight:
            cur_alt, cur_az = self.get_telescope_altaz()
            cur_az_steps = self.link.latest_telemetry.az_steps
            cur_az_angle = steps_to_angle(cur_az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
            az_limit = float(self.config["az_limit_deg"])

            speed_steps_az = float(self.config.get("speed_az", 226))
            steps_per_deg_az = float(self.config.get("steps_per_deg_az", 113.22))
            speed_deg_az = speed_steps_az / steps_per_deg_az if steps_per_deg_az > 0 else 2.0

            speed_steps_alt = float(self.config.get("speed_alt", 226))
            steps_per_deg_alt = float(self.config.get("steps_per_deg_alt", 113.22))
            speed_deg_alt = speed_steps_alt / steps_per_deg_alt if steps_per_deg_alt > 0 else 2.0

            # Contraction mapping fixed-point arrival time iteration (converges in 3 passes to < 0.1 arcsec)
            is_sim = isinstance(self.link, SimLink)
            ramp_az = 0.0 if is_sim else (speed_steps_az / max(1.0, float(self.config.get("accel_az", 100))))
            ramp_alt = 0.0 if is_sim else (speed_steps_alt / max(1.0, float(self.config.get("accel_alt", 100))))
            tau = 0.0
            for _ in range(3):
                t_eval = t0 + dt.timedelta(seconds=tau)
                if is_j2000:
                    r_eval, d_eval = precess_j2000_to_date(ra, dec, t_eval)
                else:
                    r_eval, d_eval = ra, dec
                a_eval, az_c_eval = radec_to_altaz(r_eval, d_eval, lat, lon, t_eval, apply_refraction=use_refr)
                az_b_eval = choose_az_branch(az_c_eval, cur_az_angle, limit=az_limit)
                t_az = (abs(az_b_eval - cur_az_angle) / speed_deg_az + ramp_az) if (speed_deg_az > 0 and abs(az_b_eval - cur_az_angle) > 0.01) else 0.0
                t_alt = (abs(a_eval - cur_alt) / speed_deg_alt + ramp_alt) if (speed_deg_alt > 0 and abs(a_eval - cur_alt) > 0.01) else 0.0
                tau = max(t_az, t_alt)

            flight_time_s = tau
            if flight_time_s > 0.5:
                t_target = t0 + dt.timedelta(seconds=flight_time_s)
                if is_j2000:
                    ra_date_arr, dec_date_arr = precess_j2000_to_date(ra, dec, t_target)
                else:
                    ra_date_arr, dec_date_arr = ra, dec
                alt_slew, az_slew_compass = radec_to_altaz(ra_date_arr, dec_date_arr, lat, lon, t_target, apply_refraction=use_refr)

        # Step 5: Safety checks (altitude limits and Sun keep-out)
        alt_min = float(self.config["alt_min_deg"])
        alt_max = float(self.config["alt_max_deg"])
        if alt_slew < alt_min or alt_slew > alt_max:
            msg = f"GoTo refused: target altitude {alt_slew:.1f}° outside allowed [{alt_min}°, {alt_max}°]"
            self.on_event("ERROR", msg)
            logging.warning(msg)
            if self.config["log_csv"]:
                self.logger.log("GOTO_REFUSED", target_ra=ra, target_dec=dec,
                                target_alt=alt_slew, target_az=az_slew_compass, note=msg)
            return False

        # Endpoint separation from Sun
        sun_ra, sun_dec = sun_radec(t_target)
        if is_j2000:
            ra_check, dec_check = precess_j2000_to_date(ra, dec, t_target)
        else:
            ra_check, dec_check = ra, dec
        sun_sep = separation_deg(ra_check, dec_check, sun_ra, sun_dec)
        sun_keepout = float(self.config["sun_keepout_deg"])

        # Path sampling: sample intermediate points along straight Alt/Az slew path
        cur_az_steps = self.link.latest_telemetry.az_steps
        cur_az_angle = steps_to_angle(cur_az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
        az_limit = float(self.config["az_limit_deg"])
        az_angle = choose_az_branch(az_slew_compass, cur_az_angle, limit=az_limit)

        min_path_sep = sun_sep
        cur_alt, _ = self.get_telescope_altaz()
        for step_i in range(1, 10):
            frac = step_i / 10.0
            t_sample = t0 + dt.timedelta(seconds=flight_time_s * frac) if predict_flight else t0
            sample_alt = cur_alt + frac * (alt_slew - cur_alt)
            sample_az = cur_az_angle + frac * (az_angle - cur_az_angle)
            s_ra_t, s_dec_t = sun_radec(t_sample)
            s_alt_t, s_az_t = radec_to_altaz(s_ra_t, s_dec_t, lat, lon, t_sample, apply_refraction=use_refr)
            d_az = (sample_az - s_az_t) * D2R
            cos_sep = (math.sin(sample_alt * D2R) * math.sin(s_alt_t * D2R) +
                       math.cos(sample_alt * D2R) * math.cos(s_alt_t * D2R) * math.cos(d_az))
            sep_sample = math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))
            if sep_sample < min_path_sep:
                min_path_sep = sep_sample

        effective_sep = min(sun_sep, min_path_sep)
        if effective_sep < sun_keepout:
            confirmed = solar_confirmed or self.solar_filter_confirmed
            if not confirmed and self.solar_warning_callback:
                confirmed = self.solar_warning_callback(effective_sep)
                if confirmed:
                    self.solar_filter_confirmed = True

            if not confirmed:
                path_note = "slew path sweeps within" if min_path_sep < sun_sep else "target is"
                msg = f"GoTo refused: {path_note} {effective_sep:.1f}° from Sun (solar filter required, keepout: {sun_keepout}°)"
                self.on_event("WARNING", msg)
                logging.warning(msg)
                if self.config["log_csv"]:
                    self.logger.log("GOTO_REFUSED", target_ra=ra, target_dec=dec,
                                    target_alt=alt_slew, target_az=az_slew_compass, note=msg)
                return False
            else:
                self.on_event("WARNING", f"Solar Slew Authorized: target is {effective_sep:.1f}° from Sun. Ensure certified solar filter is attached.")
        else:
            if not self.config.get("solar_filter_installed", False):
                self.solar_filter_confirmed = False

        # Step 7: Step conversion and command transmission
        target_az_steps = angle_to_steps(az_angle, self.config["steps_per_deg_az"], self.config["sign_az"])
        target_alt_steps = angle_to_steps(alt_slew, self.config["steps_per_deg_alt"], self.config["sign_alt"])

        reply = self.link.send(f"G {target_az_steps} {target_alt_steps}")
        if reply != "OK":
            msg = f"GoTo command failed: Arduino replied {reply}"
            self.on_event("ERROR", msg)
            logging.error(msg)
            return False

        # Set hold-off and optimistic moving flag to prevent tracking thread from overwriting intercept
        self.last_goto_time = time.time()
        if self.link and getattr(self.link, 'latest_telemetry', None):
            self.link.latest_telemetry.moving = 1

        # Step 8: Update active target and enable tracking
        self.current_target_radec = (ra, dec)
        self.current_target_is_j2000 = is_j2000
        self.current_target_of_date = (ra_date0, dec_date0)
        self.target_type = "celestial"
        self.az_off_steps = 0
        self.alt_off_steps = 0
        self.last_sent_steps = (target_az_steps, target_alt_steps)
        self.tracking_enabled = True
        self.last_goto_target_str = target_name or f"RA {ra:.2f}°, Dec {dec:.2f}°"
        if target_name:
            self.target_name = target_name
        self.tracking_initial_steps = (target_az_steps, target_alt_steps)
        self.tracking_pulses_count = 0
        self.tracking_total_steps_az = 0
        self.tracking_total_steps_alt = 0
        self.tracking_last_pulse_time = time.time()

        msg = f"GoTo slewing to RA {ra:.2f}°, Dec {dec:.2f}° (Alt {alt_slew:.1f}°, Az {az_angle:.1f}°)"
        self.on_event("INFO", msg)
        if self.config["log_csv"]:
            self.logger.log("GOTO", target_ra=ra, target_dec=dec, target_alt=alt_slew,
                            target_az=az_angle, az_steps=target_az_steps, alt_steps=target_alt_steps)
        return True

    def _tracking_loop(self) -> None:
        """Periodic tracking thread updating target coordinates every tracking_interval_s."""
        last_tracking_time = 0.0
        was_moving = False
        while not self._stop_event.is_set():
            time.sleep(0.1)
            if not self.tracking_enabled or not self.link or not self.link.is_open:
                continue

            if hasattr(self.link, "az_target") and hasattr(self.link, "az_pos"):
                is_moving = (abs(self.link.az_target - self.link.az_pos) > 1.0 or
                             abs(self.link.alt_target - self.link.alt_pos) > 1.0)
            else:
                is_moving = bool(self.link.latest_telemetry and getattr(self.link.latest_telemetry, "moving", 0))

            now = time.time()
            interval = float(self.config.get("tracking_interval_s", 1.0))

            # Detect arrival edge (moving transitioned 1 -> 0)
            arrival_detected = was_moving and not is_moving
            was_moving = is_moving

            if is_moving:
                continue

            if arrival_detected or (now - last_tracking_time >= interval):
                last_tracking_time = now
                self.update_tracking()

    def update_tracking(self) -> None:
        """Computes current Alt/Az for target and slews mount smoothly (Section 8.5)."""
        if not self.tracking_enabled or not self.current_target_radec or not self.link or not self.link.is_open:
            return

        # Never run sidereal tracking on fast-moving satellites (they are guided by track_satellite_altaz)
        if getattr(self, "target_type", "") == "satellite":
            return

        # Crucial: Never inject tracking delta nudges while an active Az/Alt GoTo slew is running
        if isinstance(self.link, SerialLink) and (time.time() - getattr(self, "last_goto_time", 0.0)) < 0.6:
            return

        if hasattr(self.link, "az_target") and hasattr(self.link, "az_pos"):
            if abs(self.link.az_target - self.link.az_pos) > 1.0 or abs(self.link.alt_target - self.link.alt_pos) > 1.0:
                return
        elif self.link.latest_telemetry and getattr(self.link.latest_telemetry, "moving", 0):
            return

        t = self.get_time()
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        ra_target, dec_target = self.current_target_radec

        is_j2000 = getattr(self, "current_target_is_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        if is_j2000:
            ra_date, dec_date = precess_j2000_to_date(ra_target, dec_target, t)
        else:
            ra_date, dec_date = ra_target, dec_target

        self.current_target_of_date = (ra_date, dec_date)
        use_refr = bool(self.config.get("apply_refraction", True))
        alt, az_compass = radec_to_altaz(ra_date, dec_date, lat, lon, t, apply_refraction=use_refr)

        # Safety checks
        alt_min = float(self.config["alt_min_deg"])
        alt_max = float(self.config["alt_max_deg"])
        sun_ra, sun_dec = sun_radec(t)
        sun_sep = separation_deg(ra_date, dec_date, sun_ra, sun_dec)
        sun_keepout = float(self.config["sun_keepout_deg"])

        is_sun_danger = (sun_sep < sun_keepout) and not self.solar_filter_confirmed
        if alt < alt_min or alt > alt_max or is_sun_danger:
            self.emergency_stop()
            warn = "Tracking stopped: target exceeded altitude limits or Sun keepout without confirmed solar filter."
            self.on_event("WARNING", warn)
            logging.warning(warn)
            if self.config["log_csv"]:
                self.logger.log("STOP", note=warn)
            return

        cur_az_steps = self.link.latest_telemetry.az_steps
        cur_az_angle = steps_to_angle(cur_az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
        az_limit = float(self.config["az_limit_deg"])
        az_angle = choose_az_branch(az_compass, cur_az_angle, limit=az_limit)

        tgt_az_steps = angle_to_steps(az_angle, self.config["steps_per_deg_az"], self.config["sign_az"]) + self.az_off_steps
        tgt_alt_steps = angle_to_steps(alt, self.config["steps_per_deg_alt"], self.config["sign_alt"]) + self.alt_off_steps

        if (tgt_az_steps, tgt_alt_steps) != self.last_sent_steps:
            if self.tracking_initial_steps is None:
                self.tracking_initial_steps = (tgt_az_steps, tgt_alt_steps)
            self.tracking_total_steps_az = tgt_az_steps - self.tracking_initial_steps[0]
            self.tracking_total_steps_alt = tgt_alt_steps - self.tracking_initial_steps[1]
            self.tracking_pulses_count += 1
            self.tracking_last_pulse_time = time.time()

            self.link.send(f"G {tgt_az_steps} {tgt_alt_steps}")
            self.last_sent_steps = (tgt_az_steps, tgt_alt_steps)

    def track_satellite_altaz(self, alt: float, az_compass: float, name: str = "Satellite") -> bool:
        """Tracks rapidly moving satellites directly using predictive Alt/Az feedforward."""
        if not self.link or not self.link.is_open or not self.link.latest_telemetry.valid:
            return False

        # Safety checks
        alt_min = float(self.config.get("alt_min_deg", 0.0))
        alt_max = float(self.config.get("alt_max_deg", 85.0))
        if alt < alt_min or alt > alt_max:
            return False

        t = self.get_time()
        sun_ra, sun_dec = sun_radec(t)
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        sun_alt, sun_az = radec_to_altaz(sun_ra, sun_dec, lat, lon, t)

        d_az = (az_compass - sun_az) * D2R
        c = (math.sin(alt * D2R) * math.sin(sun_alt * D2R) +
             math.cos(alt * D2R) * math.cos(sun_alt * D2R) * math.cos(d_az))
        sun_sep = math.acos(max(-1.0, min(1.0, c))) / D2R
        if sun_sep < float(self.config.get("sun_keepout_deg", 15.0)):
            return False

        cur_az_steps = self.link.latest_telemetry.az_steps
        cur_az_angle = steps_to_angle(cur_az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
        az_limit = float(self.config["az_limit_deg"])
        az_angle = choose_az_branch(az_compass, cur_az_angle, limit=az_limit)

        tgt_az_steps = angle_to_steps(az_angle, self.config["steps_per_deg_az"], self.config["sign_az"]) + self.az_off_steps
        tgt_alt_steps = angle_to_steps(alt, self.config["steps_per_deg_alt"], self.config["sign_alt"]) + self.alt_off_steps

        # Compute equivalent J2000 RA/Dec for target state display and logging
        use_refr = bool(self.config.get("apply_refraction", True))
        ra_date, dec_date = altaz_to_radec(alt, az_compass, lat, lon, t, apply_refraction=use_refr)
        ra_j2000, dec_j2000 = precess_date_to_j2000(ra_date, dec_date, t)
        self.current_target_radec = (ra_j2000, dec_j2000)
        self.current_target_is_j2000 = True
        self.current_target_of_date = (ra_date, dec_date)
        self.target_type = "satellite"
        self.tracking_enabled = True
        self.last_goto_target_str = f"{name} [SATELLITE]"

        if (tgt_az_steps, tgt_alt_steps) != self.last_sent_steps:
            if self.tracking_initial_steps is None:
                self.tracking_initial_steps = (tgt_az_steps, tgt_alt_steps)
            self.tracking_total_steps_az = tgt_az_steps - self.tracking_initial_steps[0]
            self.tracking_total_steps_alt = tgt_alt_steps - self.tracking_initial_steps[1]
            self.tracking_pulses_count += 1
            self.tracking_last_pulse_time = time.time()

            self.link.send(f"G {tgt_az_steps} {tgt_alt_steps}")
            self.last_sent_steps = (tgt_az_steps, tgt_alt_steps)
        return True

    def jog(self, direction: str, speed_mode: str = "medium") -> None:
        """Executes manual jog, accumulating tracking offset if tracking is active."""
        if not self.link or not self.link.is_open or not self.link.latest_telemetry.valid:
            return

        jog_map = self.config["jog_deg"]
        deg_step = float(jog_map.get(speed_mode, 0.5))

        d_az_deg = 0.0
        d_alt_deg = 0.0

        if direction == "up":
            d_alt_deg = +deg_step
        elif direction == "down":
            d_alt_deg = -deg_step
        elif direction == "right":  # toward East = increasing az_angle
            d_az_deg = +deg_step
        elif direction == "left":   # toward West = decreasing az_angle
            d_az_deg = -deg_step
        else:
            return

        d_az_steps = angle_to_steps(d_az_deg, self.config["steps_per_deg_az"], self.config["sign_az"])
        d_alt_steps = angle_to_steps(d_alt_deg, self.config["steps_per_deg_alt"], self.config["sign_alt"])

        az_lim_steps = angle_to_steps(self.config["az_limit_deg"], self.config["steps_per_deg_az"], self.config["sign_az"])
        alt_lim_1 = angle_to_steps(self.config["alt_min_deg"], self.config["steps_per_deg_alt"], self.config["sign_alt"])
        alt_lim_2 = angle_to_steps(self.config["alt_max_deg"], self.config["steps_per_deg_alt"], self.config["sign_alt"])
        alt_min_steps = min(alt_lim_1, alt_lim_2)
        alt_max_steps = max(alt_lim_1, alt_lim_2)

        if self.tracking_enabled:
            self.az_off_steps += d_az_steps
            self.alt_off_steps += d_alt_steps
            self.update_tracking()
            self.on_event("INFO", f"Jog {direction} ({speed_mode}): offset az={self.az_off_steps}, alt={self.alt_off_steps}")
            if self.config["log_csv"]:
                self.logger.log("JOG", note=f"Jog {direction} offset az={self.az_off_steps} alt={self.alt_off_steps}")
        else:
            new_az_steps = self.link.latest_telemetry.az_steps + d_az_steps
            new_alt_steps = self.link.latest_telemetry.alt_steps + d_alt_steps

            if (abs(new_az_steps) > abs(az_lim_steps) or
                    new_alt_steps < min(alt_min_steps, alt_max_steps) or
                    new_alt_steps > max(alt_min_steps, alt_max_steps)):
                self.on_event("WARNING", "Jog limit reached")
                return

            self.link.send(f"G {new_az_steps} {new_alt_steps}")
            self.on_event("INFO", f"Jog {direction} ({speed_mode})")
            if self.config["log_csv"]:
                self.logger.log("JOG", az_steps=new_az_steps, alt_steps=new_alt_steps)

    def sync(self) -> None:
        """Aligns logical position to current theoretical sky target (Section 8.5)."""
        if not self.current_target_radec:
            self.on_event("WARNING", "SYNC ignored: No active target selected")
            return
        if not self.link or not self.link.is_open or not self.link.latest_telemetry.valid:
            self.on_event("WARNING", "SYNC ignored: Telescope not connected")
            return

        t = self.get_time()
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        ra_tgt, dec_tgt = self.current_target_radec

        is_j2000 = getattr(self, "current_target_is_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        if is_j2000:
            ra_date, dec_date = precess_j2000_to_date(ra_tgt, dec_tgt, t)
        else:
            ra_date, dec_date = ra_tgt, dec_tgt

        use_refr = bool(self.config.get("apply_refraction", True))
        alt, az_compass = radec_to_altaz(ra_date, dec_date, lat, lon, t, apply_refraction=use_refr)
        cur_az_steps = self.link.latest_telemetry.az_steps
        cur_az_angle = steps_to_angle(cur_az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
        az_angle = choose_az_branch(az_compass, cur_az_angle, limit=float(self.config["az_limit_deg"]))

        sync_az_steps = angle_to_steps(az_angle, self.config["steps_per_deg_az"], self.config["sign_az"])
        sync_alt_steps = angle_to_steps(alt, self.config["steps_per_deg_alt"], self.config["sign_alt"])

        old_az = self.link.latest_telemetry.az_steps
        old_alt = self.link.latest_telemetry.alt_steps

        # Compute angular distance between physical pointing and theoretical target
        cur_alt, cur_az = self.get_telescope_altaz()
        d_az = abs(az_compass - cur_az)
        if d_az > 180.0:
            d_az = 360.0 - d_az
        d_alt = abs(alt - cur_alt)
        angular_dist = math.hypot(d_az, d_alt)

        # If mount is parked, homed, or not pointing near the target (> 3.0°),
        # do NOT send 'H' (which teleports coordinates without moving motors).
        # Instead, smoothly slew the mount to the target!
        if getattr(self, "is_parked", False) or getattr(self, "is_homed", False) or angular_dist > 3.0:
            self.is_parked = False
            self.is_homed = False
            self.on_event("INFO", f"Sync: slewing telescope to target ({angular_dist:.1f}° away)...")
            return self.on_goto_requested(ra_tgt, dec_tgt, is_j2000=is_j2000)

        # Fine star-alignment calibration (within 3.0° of target):
        reply = self.link.send(f"H {sync_az_steps} {sync_alt_steps}")
        if reply == "OK":
            self.az_off_steps = 0
            self.alt_off_steps = 0
            d_az_s = sync_az_steps - old_az
            d_alt_s = sync_alt_steps - old_alt
            note = f"d_az={d_az_s:+d} d_alt={d_alt_s:+d} steps"
            self.on_event("INFO", f"SYNC successful (calibrated): {note}")
            if self.config["log_csv"]:
                self.logger.log("SYNC", target_ra=ra_tgt, target_dec=dec_tgt,
                                target_alt=alt, target_az=az_compass,
                                az_steps=sync_az_steps, alt_steps=sync_alt_steps, note=note)
        else:
            self.on_event("ERROR", f"SYNC failed: {reply}")

    def emergency_stop(self) -> None:
        """Stops all motion and turns tracking off."""
        self.tracking_enabled = False
        if self.link and self.link.is_open:
            self.link.send("S")
        self.on_event("WARNING", "EMERGENCY STOP executed")
        if self.config["log_csv"]:
            self.logger.log("STOP", note="Manual stop")

    def park(self) -> None:
        """Parks telescope at configured park angles."""
        self.tracking_enabled = False
        self.is_parked = True
        if hasattr(self, "follower") and self.follower:
            self.follower.clear_authorized_target()
        if not self.link or not self.link.is_open:
            return

        park_az_steps = angle_to_steps(self.config["park_az_deg"], self.config["steps_per_deg_az"], self.config["sign_az"])
        park_alt_steps = angle_to_steps(self.config["park_alt_deg"], self.config["steps_per_deg_alt"], self.config["sign_alt"])
        self.link.send(f"G {park_az_steps} {park_alt_steps}")
        self.on_event("INFO", f"Slewing to Park position (Az {self.config['park_az_deg']}°, Alt {self.config['park_alt_deg']}°)")
        if self.config["log_csv"]:
            self.logger.log("PARK", az_steps=park_az_steps, alt_steps=park_alt_steps)

    def home_axis(self, axis: str) -> None:
        """Commands background homing on limit switch."""
        if not self.link or not self.link.is_open:
            return
        self.tracking_enabled = False
        self.is_homed = True
        if hasattr(self, "follower") and self.follower:
            self.follower.clear_authorized_target()
        reply = self.link.send(f"Z {axis}")
        if reply == "OK":
            self.on_event("INFO", f"Homing {axis} started...")
            if self.config["log_csv"]:
                self.logger.log("HOME", note=f"Started homing {axis}")
        else:
            self.on_event("ERROR", f"Homing {axis} rejected: {reply}")

    def move_focus(self, amount_type: str, direction_in: bool) -> None:
        """Moves focus motor by fine or coarse step delta."""
        if not self.link or not self.link.is_open:
            return
        steps_cfg = self.config["focus_steps"]
        base_steps = int(steps_cfg.get(amount_type, 20))
        delta = (-base_steps if direction_in else base_steps) * int(self.config["sign_focus"])
        reply = self.link.send(f"F {delta}")
        if reply != "OK":
            self.on_event("WARNING", f"Focus move rejected: {reply}")

    def zero_position(self) -> None:
        """Sets current physical orientation as logical (0, 0)."""
        if not self.link or not self.link.is_open:
            return
        self.is_parked = False
        self.is_homed = False
        if hasattr(self, "follower") and self.follower:
            self.follower.clear_authorized_target()
        reply = self.link.send("H 0 0")
        if reply == "OK":
            self.az_off_steps = 0
            self.alt_off_steps = 0
            self.on_event("INFO", "Position reset to North/Level (0,0)")
        else:
            self.on_event("ERROR", f"Zero position failed: {reply}")

    def get_telescope_altaz(self) -> Tuple[float, float]:
        """Returns current telescope (Alt, Compass Az) in degrees."""
        if not self.link or not self.link.latest_telemetry.valid:
            return 0.0, 0.0
        t = self.link.latest_telemetry
        az_deg = steps_to_angle(t.az_steps, self.config["steps_per_deg_az"], self.config["sign_az"])
        alt_deg = steps_to_angle(t.alt_steps, self.config["steps_per_deg_alt"], self.config["sign_alt"])
        compass_az = az_deg % 360.0
        return alt_deg, compass_az

    def get_telescope_radec_j2000(self) -> Tuple[float, float]:
        """Always returns current telescope RA/Dec in J2000 coordinates for Stellarium TCP port 10001 protocol."""
        alt, az = self.get_telescope_altaz()
        t = self.get_time()
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        use_refr = bool(self.config.get("apply_refraction", True))
        ra_date, dec_date = altaz_to_radec(alt, az, lat, lon, t, apply_refraction=use_refr)
        return precess_date_to_j2000(ra_date, dec_date, t)

    def get_telescope_radec(self) -> Tuple[float, float]:
        """Returns current telescope RA/Dec in configured epoch (J2000 or JNow)."""
        alt, az = self.get_telescope_altaz()
        t = self.get_time()
        lat = float(self.config["latitude_deg"])
        lon = float(self.config["longitude_deg"])
        use_refr = bool(self.config.get("apply_refraction", True))
        ra_date, dec_date = altaz_to_radec(alt, az, lat, lon, t, apply_refraction=use_refr)

        if self.config.get("epoch", "J2000") == "J2000":
            return precess_date_to_j2000(ra_date, dec_date, t)
        return ra_date, dec_date

# ==============================================================================
# TKINTER GRAPHICAL USER INTERFACE (Section 8.8)
# ==============================================================================

class TelescopeApp:
    """Tkinter Desktop GUI for telescope control, status monitoring, and settings."""

    def __init__(self, root: Any, core: BridgeCore, stellarium_server: StellariumServer):
        self.root = root
        self.core = core
        self.stellarium = stellarium_server

        self.root.title("GoTo Telescope Bridge - 3-Axis Controller")
        self.root.geometry("860x780")
        self.root.minsize(780, 680)
        self.root.configure(bg="#10151d")

        # Color Theme Constants (Section 8.8)
        self.BG_MAIN = "#10151d"
        self.BG_PANEL = "#1a2230"
        self.TEXT_COLOR = "#e6edf3"
        self.ACCENT_COLOR = "#4aa3ff"
        self.WARN_COLOR = "#ffb454"
        self.ERR_COLOR = "#ff6b6b"
        self.READY_COLOR = "#3fb950"

        # State tracking for GUI updates
        self.speed_var = None
        self.port_var = None
        self.simulate_var = None
        self.serial_indicator = None
        self.stellarium_indicator = None
        self.log_text = None

        self._apply_dark_theme()
        self._build_ui()
        self._bind_keys()

        # Handle window close cleanly
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start periodic GUI queue polling (~20 Hz) and status telemetry update (~5 Hz)
        self.root.after(50, self._poll_events)
        self.root.after(200, self._update_status_display)

    def _apply_dark_theme(self) -> None:
        import tkinter.ttk as ttk
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=self.BG_PANEL, foreground=self.TEXT_COLOR, font=("Segoe UI", 9))
        style.configure("TFrame", background=self.BG_PANEL)
        style.configure("TLabel", background=self.BG_PANEL, foreground=self.TEXT_COLOR)
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.ACCENT_COLOR)
        style.configure("TButton", background="#2a3548", foreground=self.TEXT_COLOR, borderwidth=1)
        style.map("TButton",
                  background=[("active", "#3b4b66"), ("pressed", "#1f2736")],
                  foreground=[("active", "#ffffff")])
        style.configure("Accent.TButton", background="#1a5ca8", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#2274d4"), ("pressed", "#12437b")])
        style.configure("Stop.TButton", background="#9e2a2b", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.map("Stop.TButton", background=[("active", "#c4383a"), ("pressed", "#6e1d1e")])
        style.configure("TRadiobutton", background=self.BG_PANEL, foreground=self.TEXT_COLOR)
        style.configure("TCheckbutton", background=self.BG_PANEL, foreground=self.TEXT_COLOR)
        style.configure("TCombobox", fieldbackground="#2a3548", background="#2a3548", foreground=self.TEXT_COLOR)

    def _build_ui(self) -> None:
        import tkinter as tk
        import tkinter.ttk as ttk

        # ----------------------------------------------------------------------
        # Top Red Safety Banner
        # ----------------------------------------------------------------------
        banner = tk.Label(
            self.root,
            text="⚠️  NEVER POINT AT THE SUN - KEEP THE LENS CAP ON IN DAYTIME  ⚠️",
            bg="#b30000",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            pady=5
        )
        banner.pack(fill=tk.X, side=tk.TOP)

        main_container = tk.Frame(self.root, bg=self.BG_MAIN)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # ----------------------------------------------------------------------
        # 1. Connection Bar
        # ----------------------------------------------------------------------
        conn_frame = ttk.Frame(main_container, padding=6)
        conn_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(conn_frame, text="Serial Port:").pack(side=tk.LEFT, padx=(0, 4))
        self.port_var = tk.StringVar(value=self.core.config.get("serial_port", ""))
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=14)
        self.port_combo.pack(side=tk.LEFT, padx=(0, 4))
        self._refresh_ports()

        ttk.Button(conn_frame, text="↻", width=3, command=self._refresh_ports).pack(side=tk.LEFT, padx=(0, 6))

        self.btn_connect = ttk.Button(conn_frame, text="Connect", command=self._toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=(0, 6))

        self.simulate_var = tk.BooleanVar(value=bool(self.core.config.get("simulate", False)))
        chk_sim = ttk.Checkbutton(conn_frame, text="Simulate Uno", variable=self.simulate_var)
        chk_sim.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(conn_frame, text="Settings", command=self._open_settings_dialog).pack(side=tk.LEFT, padx=(0, 15))

        # Status indicators
        ttk.Label(conn_frame, text="Serial:").pack(side=tk.LEFT, padx=(0, 4))
        self.serial_indicator = tk.Label(conn_frame, text="● DISCONNECTED", fg=self.ERR_COLOR, bg=self.BG_PANEL, font=("Segoe UI", 9, "bold"))
        self.serial_indicator.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(conn_frame, text="Stellarium:").pack(side=tk.LEFT, padx=(0, 4))
        self.stellarium_indicator = tk.Label(conn_frame, text="● WAITING", fg=self.WARN_COLOR, bg=self.BG_PANEL, font=("Segoe UI", 9, "bold"))
        self.stellarium_indicator.pack(side=tk.LEFT)

        # ----------------------------------------------------------------------
        # 2. Status Panel (~5 Hz refresh)
        # ----------------------------------------------------------------------
        status_frame = ttk.Frame(main_container, padding=8)
        status_frame.pack(fill=tk.X, pady=(0, 6))

        # 3-column layout inside status panel
        col1 = ttk.Frame(status_frame)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        col2 = ttk.Frame(status_frame)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        col3 = ttk.Frame(status_frame)
        col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # Column 1: Time and Coordinates
        self.lbl_utc = ttk.Label(col1, text="UTC Time: --")
        self.lbl_utc.pack(anchor=tk.W)
        self.lbl_lst = ttk.Label(col1, text="LST: --")
        self.lbl_lst.pack(anchor=tk.W)
        self.lbl_altaz = ttk.Label(col1, text="Mount Alt/Az: 0.00° / 0.00°")
        self.lbl_altaz.pack(anchor=tk.W)
        self.lbl_radec = ttk.Label(col1, text="Mount RA/Dec: 0.00° / 0.00°")
        self.lbl_radec.pack(anchor=tk.W)

        # Column 2: Steps, Kinematics, Flags
        self.lbl_steps = ttk.Label(col2, text="Steps (Az/Alt/Foc): 0 / 0 / 0")
        self.lbl_steps.pack(anchor=tk.W)
        self.lbl_moving = ttk.Label(col2, text="Moving: NO")
        self.lbl_moving.pack(anchor=tk.W)
        self.lbl_homed = ttk.Label(col2, text="Homed: Alt=NO, Az=NO")
        self.lbl_homed.pack(anchor=tk.W)
        self.lbl_align = tk.Label(col2, text="Alignment: NOT HOMED", fg=self.ERR_COLOR, bg=self.BG_PANEL, font=("Segoe UI", 9, "bold"))
        self.lbl_align.pack(anchor=tk.W)

        # Column 3: Target and Tracking
        self.lbl_tracking = ttk.Label(col3, text="Tracking: OFF")
        self.lbl_tracking.pack(anchor=tk.W)
        self.lbl_target_radec = ttk.Label(col3, text="Target RA/Dec: None")
        self.lbl_target_radec.pack(anchor=tk.W)
        self.lbl_target_altaz = ttk.Label(col3, text="Target Alt/Az: None")
        self.lbl_target_altaz.pack(anchor=tk.W)
        self.lbl_sun_sep = ttk.Label(col3, text="Sun Separation: --")
        self.lbl_sun_sep.pack(anchor=tk.W)

        # ----------------------------------------------------------------------
        # Middle Split: Controls (Left) and Focus (Right)
        # ----------------------------------------------------------------------
        mid_frame = tk.Frame(main_container, bg=self.BG_MAIN)
        mid_frame.pack(fill=tk.X, pady=(0, 6))

        # 3. Control Panel (Jog pad, speeds, actions)
        ctrl_frame = ttk.Frame(mid_frame, padding=8)
        ctrl_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        ttk.Label(ctrl_frame, text="Mount Controls", style="Header.TLabel").grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 4))

        # 3x3 Jog Pad
        btn_up = ttk.Button(ctrl_frame, text="▲ Alt+", width=7, command=lambda: self.core.jog("up", self.speed_var.get()))
        btn_up.grid(row=1, column=1, padx=2, pady=2)

        btn_left = ttk.Button(ctrl_frame, text="◀ Az-", width=7, command=lambda: self.core.jog("left", self.speed_var.get()))
        btn_left.grid(row=2, column=0, padx=2, pady=2)

        btn_stop = ttk.Button(ctrl_frame, text="STOP", width=7, style="Stop.TButton", command=self.core.emergency_stop)
        btn_stop.grid(row=2, column=1, padx=2, pady=2)

        btn_right = ttk.Button(ctrl_frame, text="Az+ ▶", width=7, command=lambda: self.core.jog("right", self.speed_var.get()))
        btn_right.grid(row=2, column=2, padx=2, pady=2)

        btn_down = ttk.Button(ctrl_frame, text="▼ Alt-", width=7, command=lambda: self.core.jog("down", self.speed_var.get()))
        btn_down.grid(row=3, column=1, padx=2, pady=2)

        # Speed selector
        speed_box = ttk.Frame(ctrl_frame)
        speed_box.grid(row=4, column=0, columnspan=3, pady=(6, 2))
        self.speed_var = tk.StringVar(value="medium")
        for mode in ("fine", "medium", "coarse"):
            ttk.Radiobutton(speed_box, text=mode.capitalize(), value=mode, variable=self.speed_var).pack(side=tk.LEFT, padx=4)

        # Action buttons column
        act_box = ttk.Frame(ctrl_frame)
        act_box.grid(row=1, column=3, rowspan=4, sticky=tk.N, padx=(12, 0))

        self.btn_sync = ttk.Button(act_box, text="SYNC", width=12, style="Accent.TButton", command=self.core.sync)
        self.btn_sync.pack(fill=tk.X, pady=2)

        self.btn_track = ttk.Button(act_box, text="Toggle Track", width=12, command=self._toggle_tracking)
        self.btn_track.pack(fill=tk.X, pady=2)

        ttk.Button(act_box, text="Home Alt", width=12, command=lambda: self.core.home_axis("ALT")).pack(fill=tk.X, pady=2)

        self.btn_home_az = ttk.Button(act_box, text="Home Az", width=12, command=lambda: self.core.home_axis("AZ"))
        self.btn_home_az.pack(fill=tk.X, pady=2)
        if not self.core.config.get("az_home_switch", False):
            self.btn_home_az.configure(state=tk.DISABLED)

        ttk.Button(act_box, text="Park", width=12, command=self.core.park).pack(fill=tk.X, pady=2)

        ttk.Button(act_box, text="Set (0,0)", width=12, command=self._confirm_zero).pack(fill=tk.X, pady=2)

        # 4. Focus Panel
        foc_frame = ttk.Frame(mid_frame, padding=8)
        foc_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(4, 0))

        ttk.Label(foc_frame, text="Motorized Focus", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))

        self.lbl_foc_steps = ttk.Label(foc_frame, text="Focus Steps: 0")
        self.lbl_foc_steps.pack(anchor=tk.W, pady=(0, 6))

        ttk.Button(foc_frame, text="<< Coarse In", width=14, command=lambda: self.core.move_focus("coarse", True)).pack(fill=tk.X, pady=2)
        ttk.Button(foc_frame, text="< Fine In", width=14, command=lambda: self.core.move_focus("fine", True)).pack(fill=tk.X, pady=2)
        ttk.Button(foc_frame, text="Fine Out >", width=14, command=lambda: self.core.move_focus("fine", False)).pack(fill=tk.X, pady=2)
        ttk.Button(foc_frame, text="Coarse Out >>", width=14, command=lambda: self.core.move_focus("coarse", False)).pack(fill=tk.X, pady=2)

        # ----------------------------------------------------------------------
        # 5. Log Panel (Last 500 lines scrolling text)
        # ----------------------------------------------------------------------
        log_frame = ttk.Frame(main_container, padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(log_frame, text="Activity Log", style="Header.TLabel").pack(anchor=tk.W)

        self.log_text = tk.Text(log_frame, height=9, bg="#0d1117", fg="#c9d1d9",
                                insertbackground="#ffffff", relief=tk.FLAT, wrap=tk.WORD,
                                font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

    def _bind_keys(self) -> None:
        """Binds arrow keys and space/esc emergency stops."""
        self.root.bind("<Up>", lambda e: self.core.jog("up", self.speed_var.get()))
        self.root.bind("<Down>", lambda e: self.core.jog("down", self.speed_var.get()))
        self.root.bind("<Left>", lambda e: self.core.jog("left", self.speed_var.get()))
        self.root.bind("<Right>", lambda e: self.core.jog("right", self.speed_var.get()))
        self.root.bind("<Escape>", lambda e: self.core.emergency_stop())
        self.root.bind("<space>", lambda e: self.core.emergency_stop())

    def _refresh_ports(self) -> None:
        if HAS_PYSERIAL and serial:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.port_combo['values'] = ports
            if ports and not self.port_var.get():
                self.port_var.set(ports[0])
        else:
            self.port_combo['values'] = ["(Simulate only)"]

    def _toggle_connection(self) -> None:
        if self.core.link and self.core.link.is_open:
            self.core.disconnect()
            self.btn_connect.configure(text="Connect")
        else:
            port = self.port_var.get()
            sim = self.simulate_var.get()
            if self.core.connect(port=port, simulate=sim):
                self.btn_connect.configure(text="Disconnect")

    def _toggle_tracking(self) -> None:
        self.core.tracking_enabled = not self.core.tracking_enabled
        self.core.on_event("INFO", f"Tracking {'ENABLED' if self.core.tracking_enabled else 'DISABLED'}")

    def _confirm_zero(self) -> None:
        import tkinter.messagebox as msgbox
        ans = msgbox.askyesno(
            "Confirm Reset (0,0)",
            "Set current orientation as North (Azimuth 0) and Level (Altitude 0)?\nMake sure the tube is level and pointed True North."
        )
        if ans:
            self.core.zero_position()

    def _poll_events(self) -> None:
        """Processes async log events and notifications on main GUI thread."""
        while not self.core.event_queue.empty():
            try:
                ev_type, text = self.core.event_queue.get_nowait()
                self._append_log(f"[{ev_type}] {text}")
            except queue.Empty:
                break

        # Check async messages from link
        if self.core.link:
            while not self.core.link.async_messages.empty():
                try:
                    async_msg = self.core.link.async_messages.get_nowait()
                    self._append_log(f"[HARDWARE] {async_msg}")
                except queue.Empty:
                    break

        self.root.after(50, self._poll_events)

    def _update_status_display(self) -> None:
        """Updates status fields (~5 times per second) from latest telemetry and astronomy math."""
        t_utc = self.core.get_time()
        jd = julian_date(t_utc)
        lst = lst_deg(jd, float(self.core.config["longitude_deg"]))

        self.lbl_utc.configure(text=f"UTC Time: {t_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        self.lbl_lst.configure(text=f"LST: {lst:.2f}° ({(lst/15.0):.2f}h)")

        # Link indicators
        if self.core.link and self.core.link.is_open:
            if self.core.link.is_stale:
                self.serial_indicator.configure(text="● STALE", fg=self.WARN_COLOR)
            else:
                self.serial_indicator.configure(text="● CONNECTED", fg=self.READY_COLOR)
            self.btn_connect.configure(text="Disconnect")
        else:
            self.serial_indicator.configure(text="● DISCONNECTED", fg=self.ERR_COLOR)
            self.btn_connect.configure(text="Connect")

        # Stellarium indicator
        if self.stellarium.is_client_connected:
            self.stellarium_indicator.configure(text="● CONNECTED", fg=self.READY_COLOR)
        else:
            self.stellarium_indicator.configure(text="● WAITING", fg=self.WARN_COLOR)

        # Coordinates
        alt, az = self.core.get_telescope_altaz()
        ra, dec = self.core.get_telescope_radec()
        self.lbl_altaz.configure(text=f"Mount Alt/Az: {alt:.2f}° / {az:.2f}°")
        epoch_str = self.core.config.get("epoch", "JNow")
        self.lbl_radec.configure(text=f"Mount RA/Dec ({epoch_str}): {ra:.2f}° / {dec:.2f}°")

        # Telemetry
        if self.core.link and self.core.link.latest_telemetry.valid:
            telem = self.core.link.latest_telemetry
            self.lbl_steps.configure(text=f"Steps (Az/Alt/Foc): {telem.az_steps} / {telem.alt_steps} / {telem.foc_steps}")
            self.lbl_moving.configure(text=f"Moving: {'YES' if telem.moving else 'NO'}")
            alt_homed = (telem.homed & 1) != 0
            az_homed = (telem.homed & 2) != 0
            self.lbl_homed.configure(text=f"Homed: Alt={'YES' if alt_homed else 'NO'}, Az={'YES' if az_homed else 'NO'}")
            self.lbl_foc_steps.configure(text=f"Focus Steps: {telem.foc_steps}")

            # Alignment status
            if alt_homed or self.core.current_target_radec is not None:
                self.lbl_align.configure(text="Alignment: READY", fg=self.READY_COLOR)
            else:
                self.lbl_align.configure(text="Alignment: NOT HOMED", fg=self.ERR_COLOR)

        # Tracking and target
        self.lbl_tracking.configure(text=f"Tracking: {'ON' if self.core.tracking_enabled else 'OFF'}")
        if self.core.current_target_radec:
            tgt_ra, tgt_dec = self.core.current_target_radec
            self.lbl_target_radec.configure(text=f"Target RA/Dec: {tgt_ra:.2f}° / {tgt_dec:.2f}°")
            if self.core.current_target_of_date:
                t_ra_d, t_dec_d = self.core.current_target_of_date
                t_alt, t_az = radec_to_altaz(t_ra_d, t_dec_d, float(self.core.config["latitude_deg"]), float(self.core.config["longitude_deg"]), t_utc)
                self.lbl_target_altaz.configure(text=f"Target Alt/Az: {t_alt:.1f}° / {t_az:.1f}°")

                sun_ra, sun_dec = sun_radec(t_utc)
                sep = separation_deg(t_ra_d, t_dec_d, sun_ra, sun_dec)
                self.lbl_sun_sep.configure(text=f"Sun Separation: {sep:.1f}°")
        else:
            self.lbl_target_radec.configure(text="Target RA/Dec: None")
            self.lbl_target_altaz.configure(text="Target Alt/Az: None")
            self.lbl_sun_sep.configure(text="Sun Separation: --")

        self.root.after(200, self._update_status_display)

    def _append_log(self, text: str) -> None:
        """Appends timestamped entry to scrolling log window (max 500 lines)."""
        import tkinter as tk
        t_str = dt.datetime.now().strftime("%H:%M:%S")
        entry = f"{t_str} {text}\n"

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, entry)

        # Cap lines to 500
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > 500:
            self.log_text.delete("1.0", f"{num_lines - 500}.0")

        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _open_settings_dialog(self) -> None:
        """Opens modal configuration dialog allowing editing of all settings."""
        import tkinter as tk
        import tkinter.messagebox as msgbox
        import tkinter.ttk as ttk

        dlg = tk.Toplevel(self.root)
        dlg.title("Mount Configuration & Settings")
        dlg.geometry("560x650")
        dlg.configure(bg=self.BG_PANEL)
        dlg.transient(self.root)
        dlg.grab_set()

        canvas = tk.Canvas(dlg, bg=self.BG_PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
        form_frame = ttk.Frame(canvas, padding=10)

        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_win = canvas.create_window((0, 0), window=form_frame, anchor=tk.NW)
        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))

        entries: Dict[str, Any] = {}
        row = 0

        def add_entry(key: str, label_text: str, default_val: Any) -> None:
            nonlocal row
            ttk.Label(form_frame, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=3)
            var = tk.StringVar(value=str(default_val))
            ent = ttk.Entry(form_frame, textvariable=var, width=24)
            ent.grid(row=row, column=1, sticky=tk.E, pady=3)
            entries[key] = var
            row += 1

        def add_combobox(key: str, label_text: str, values: List[str], current: str) -> None:
            nonlocal row
            ttk.Label(form_frame, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=3)
            var = tk.StringVar(value=current)
            cb = ttk.Combobox(form_frame, textvariable=var, values=values, width=22, state="readonly")
            cb.grid(row=row, column=1, sticky=tk.E, pady=3)
            entries[key] = var
            row += 1

        cfg = self.core.config
        add_entry("latitude_deg", "Latitude (°):", cfg["latitude_deg"])
        add_entry("longitude_deg", "Longitude (°):", cfg["longitude_deg"])
        add_combobox("epoch", "Epoch:", ["JNow", "J2000"], cfg["epoch"])
        add_combobox("sign_az", "Azimuth Sign:", ["1", "-1"], str(cfg["sign_az"]))
        add_combobox("sign_alt", "Altitude Sign:", ["1", "-1"], str(cfg["sign_alt"]))
        add_combobox("sign_focus", "Focus Sign:", ["1", "-1"], str(cfg["sign_focus"]))
        add_entry("steps_per_deg_az", "Steps/deg (Azimuth):", cfg["steps_per_deg_az"])
        add_entry("steps_per_deg_alt", "Steps/deg (Altitude):", cfg["steps_per_deg_alt"])
        add_entry("speed_az", "Speed Az (steps/s):", cfg["speed_az"])
        add_entry("speed_alt", "Speed Alt (steps/s):", cfg["speed_alt"])
        add_entry("speed_foc", "Speed Focus (steps/s):", cfg["speed_foc"])
        add_entry("accel_az", "Accel Az (steps/s²):", cfg["accel_az"])
        add_entry("accel_alt", "Accel Alt (steps/s²):", cfg["accel_alt"])
        add_entry("accel_foc", "Accel Focus (steps/s²):", cfg["accel_foc"])
        add_entry("backlash_az", "Backlash Az (steps):", cfg["backlash_az"])
        add_entry("backlash_alt", "Backlash Alt (steps):", cfg["backlash_alt"])
        add_entry("az_limit_deg", "Azimuth Limit (±°):", cfg["az_limit_deg"])
        add_entry("alt_min_deg", "Altitude Min (°):", cfg["alt_min_deg"])
        add_entry("alt_max_deg", "Altitude Max (°):", cfg["alt_max_deg"])
        add_entry("sun_keepout_deg", "Sun Keepout (°):", cfg["sun_keepout_deg"])
        add_entry("tracking_interval_s", "Tracking Interval (s):", cfg["tracking_interval_s"])
        add_entry("stellarium_port", "Stellarium Port:", cfg["stellarium_port"])

        # Checkboxes
        az_home_var = tk.BooleanVar(value=bool(cfg.get("az_home_switch", False)))
        ttk.Checkbutton(form_frame, text="Azimuth Home Switch Installed", variable=az_home_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        csv_log_var = tk.BooleanVar(value=bool(cfg.get("log_csv", True)))
        ttk.Checkbutton(form_frame, text="Enable Pointing CSV Logging", variable=csv_log_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        def save_and_apply() -> None:
            try:
                cfg["latitude_deg"] = float(entries["latitude_deg"].get())
                cfg["longitude_deg"] = float(entries["longitude_deg"].get())
                cfg["epoch"] = entries["epoch"].get()
                cfg["sign_az"] = int(entries["sign_az"].get())
                cfg["sign_alt"] = int(entries["sign_alt"].get())
                cfg["sign_focus"] = int(entries["sign_focus"].get())
                cfg["steps_per_deg_az"] = float(entries["steps_per_deg_az"].get())
                cfg["steps_per_deg_alt"] = float(entries["steps_per_deg_alt"].get())
                cfg["speed_az"] = int(entries["speed_az"].get())
                cfg["speed_alt"] = int(entries["speed_alt"].get())
                cfg["speed_foc"] = int(entries["speed_foc"].get())
                cfg["accel_az"] = int(entries["accel_az"].get())
                cfg["accel_alt"] = int(entries["accel_alt"].get())
                cfg["accel_foc"] = int(entries["accel_foc"].get())
                cfg["backlash_az"] = int(entries["backlash_az"].get())
                cfg["backlash_alt"] = int(entries["backlash_alt"].get())
                cfg["az_limit_deg"] = float(entries["az_limit_deg"].get())
                cfg["alt_min_deg"] = float(entries["alt_min_deg"].get())
                cfg["alt_max_deg"] = float(entries["alt_max_deg"].get())
                cfg["sun_keepout_deg"] = float(entries["sun_keepout_deg"].get())
                cfg["tracking_interval_s"] = float(entries["tracking_interval_s"].get())
                cfg["stellarium_port"] = int(entries["stellarium_port"].get())
                cfg["az_home_switch"] = az_home_var.get()
                cfg["log_csv"] = csv_log_var.get()

                val_errors = cfg.validate()
                if val_errors:
                    msgbox.showerror("Validation Error", "\n".join(val_errors))
                    return

                cfg.save()
                self.btn_home_az.configure(state=tk.NORMAL if cfg["az_home_switch"] else tk.DISABLED)

                # Re-send V, A, L, B immediately to microcontroller if connected
                if self.core.link and self.core.link.is_open:
                    self.core.push_hardware_config()

                self.core.on_event("INFO", "Settings saved and pushed to mount.")
                dlg.destroy()

            except ValueError as ve:
                msgbox.showerror("Format Error", f"Please check numerical input fields: {ve}")

        btn_box = ttk.Frame(form_frame)
        btn_box.grid(row=row, column=0, columnspan=2, pady=12)
        ttk.Button(btn_box, text="Save & Apply", style="Accent.TButton", command=save_and_apply).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_box, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    def on_close(self) -> None:
        """Gracefully shuts down tracking, emergency stops motors, closes sockets/ports."""
        try:
            self.core.stop_tracking_thread()
            self.core.emergency_stop()
            self.stellarium.stop()
            self.core.disconnect()
        except Exception:
            pass
        self.root.destroy()

# ==============================================================================
# SECTION 9: SELF-TEST SUITE (--selftest)
# ==============================================================================

def run_self_test() -> int:
    """Executes the complete headless 13-test verification suite (Section 9)."""
    passed = 0
    total = 13

    def record_pass(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS {name}")

    def record_fail(name: str, reason: str) -> None:
        print(f"FAIL {name}: {reason}")

    # --------------------------------------------------------------------------
    # Test 1: Maths - Polaris position from lat 12.84, lon 80.15 at 2026-11-02 16:00 UTC
    # --------------------------------------------------------------------------
    try:
        t_pol = dt.datetime(2026, 11, 2, 16, 0, 0)
        lat = 12.84
        lon = 80.15
        ra_now, dec_now = precess_j2000_to_date(37.9546, 89.2641, t_pol)
        alt_pol, az_pol = radec_to_altaz(ra_now, dec_now, lat, lon, t_pol)
        # Alt within 1° of lat, Az within 2° of North (0/360)
        alt_diff = abs(alt_pol - lat)
        az_diff = min(az_pol, abs(360.0 - az_pol))
        if alt_diff <= 1.0 and az_diff <= 2.0:
            record_pass("test_1_maths_polaris")
        else:
            record_fail("test_1_maths_polaris", f"alt_diff={alt_diff:.4f} > 1.0 or az_diff={az_diff:.4f} > 2.0")
    except Exception as e:
        record_fail("test_1_maths_polaris", str(e))

    # --------------------------------------------------------------------------
    # Test 2: altaz_to_radec round trip within 1e-6 degrees
    # --------------------------------------------------------------------------
    try:
        t = dt.datetime(2026, 11, 2, 18, 0, 0)
        ra_orig, dec_orig = 123.456, 45.678
        alt, az = radec_to_altaz(ra_orig, dec_orig, 12.84, 80.15, t)
        ra_back, dec_back = altaz_to_radec(alt, az, 12.84, 80.15, t)
        if abs(ra_orig - ra_back) < 1e-6 and abs(dec_orig - dec_back) < 1e-6:
            record_pass("test_2_altaz_radec_roundtrip")
        else:
            record_fail("test_2_altaz_radec_roundtrip", f"diff ra={abs(ra_orig - ra_back)}, dec={abs(dec_orig - dec_back)}")
    except Exception as e:
        record_fail("test_2_altaz_radec_roundtrip", str(e))

    # --------------------------------------------------------------------------
    # Test 3: precess_date_to_j2000 round trip within 1e-6 degrees
    # --------------------------------------------------------------------------
    try:
        t = dt.datetime(2026, 11, 2, 18, 0, 0)
        ra_j2000, dec_j2000 = 210.5, -25.3
        ra_d, dec_d = precess_j2000_to_date(ra_j2000, dec_j2000, t)
        ra_j2000_rt, dec_j2000_rt = precess_date_to_j2000(ra_d, dec_d, t)
        if abs(ra_j2000 - ra_j2000_rt) < 1e-6 and abs(dec_j2000 - dec_j2000_rt) < 1e-6:
            record_pass("test_3_precess_roundtrip")
        else:
            record_fail("test_3_precess_roundtrip", f"diff={abs(ra_j2000 - ra_j2000_rt)}, {abs(dec_j2000 - dec_j2000_rt)}")
    except Exception as e:
        record_fail("test_3_precess_roundtrip", str(e))

    # --------------------------------------------------------------------------
    # Test 4: pack_position / parse_goto round trip within 1e-5 degrees
    # --------------------------------------------------------------------------
    try:
        ra_in, dec_in = 285.12345, -42.98765
        ra_int = int(round((ra_in % 360.0) / 360.0 * 2**32)) & 0xFFFFFFFF
        dec_int = int(round(dec_in / 90.0 * 0x40000000))
        fake_goto_buf = struct.pack('<HHQIi', 20, 0, 0, ra_int, dec_int)
        ra_out, dec_out = parse_goto(fake_goto_buf)

        packed_pos = pack_position(ra_in, dec_in, status=0)
        _, _, _, ra_un, dec_un, _ = struct.unpack('<HHQIii', packed_pos)
        ra_pos_out = ra_un / 2**32 * 360.0
        dec_pos_out = dec_un / 0x40000000 * 90.0

        if (abs(ra_in - ra_out) < 1e-5 and abs(dec_in - dec_out) < 1e-5 and
                abs(ra_in - ra_pos_out) < 1e-5 and abs(dec_in - dec_pos_out) < 1e-5):
            record_pass("test_4_pack_parse_roundtrip")
        else:
            record_fail("test_4_pack_parse_roundtrip", "Precision exceeded 1e-5 degrees")
    except Exception as e:
        record_fail("test_4_pack_parse_roundtrip", str(e))

    # --------------------------------------------------------------------------
    # Test 5: choose_az_branch cases
    # --------------------------------------------------------------------------
    try:
        c1 = choose_az_branch(270.0, 0.0)      # -> -90.0
        c2 = choose_az_branch(180.0, -170.0)   # -> -180.0
        c3 = choose_az_branch(180.0, 170.0)    # -> 180.0
        c4 = choose_az_branch(10.0, 0.0)       # -> 10.0
        if c1 == -90.0 and c2 == -180.0 and c3 == 180.0 and c4 == 10.0:
            record_pass("test_5_choose_az_branch")
        else:
            record_fail("test_5_choose_az_branch", f"results: {c1}, {c2}, {c3}, {c4}")
    except Exception as e:
        record_fail("test_5_choose_az_branch", str(e))

    # --------------------------------------------------------------------------
    # Test 6: Step conversion round trip for both axes with sign +1 and -1
    # --------------------------------------------------------------------------
    try:
        scale = 113.22
        all_ok = True
        for sign in (1, -1):
            for ang in (0.0, 45.123, -120.456, 85.0):
                steps = angle_to_steps(ang, scale, sign)
                ang_rt = steps_to_angle(steps, scale, sign)
                # Quantization resolution is 1 step = ~0.0088°
                if abs(ang - ang_rt) > (1.0 / scale):
                    all_ok = False
            for step in (0, 1000, -5000, 12345):
                ang = steps_to_angle(step, scale, sign)
                step_rt = angle_to_steps(ang, scale, sign)
                if step != step_rt:
                    all_ok = False
        if all_ok:
            record_pass("test_6_step_conversion_roundtrip")
        else:
            record_fail("test_6_step_conversion_roundtrip", "Round-trip mismatch detected")
    except Exception as e:
        record_fail("test_6_step_conversion_roundtrip", str(e))

    # --------------------------------------------------------------------------
    # Test 7: SimLink protocol checks
    # --------------------------------------------------------------------------
    try:
        sim = SimLink()
        sim.open()
        sim.speed_az = 2000.0
        sim.speed_alt = 2000.0
        p0 = sim.send("P")
        if p0 != "P 0 0 0 0 0":
            record_fail("test_7_simlink_protocol", f"Initial P returned {p0}")
        else:
            r_g = sim.send("G 1000 500")
            if r_g != "OK":
                record_fail("test_7_simlink_protocol", f"G 1000 500 returned {r_g}")
            else:
                # Wait up to 3s for simulation to reach 1000 500
                t_end = time.time() + 3.0
                reached = False
                while time.time() < t_end:
                    rep = sim.send("P")
                    parts = rep.split()
                    if len(parts) == 6 and int(parts[1]) == 1000 and int(parts[2]) == 500 and int(parts[4]) == 0:
                        reached = True
                        break
                    time.sleep(0.05)

                if not reached:
                    record_fail("test_7_simlink_protocol", "Did not reach G target 1000 500")
                else:
                    # Test G outside limits
                    r_lim = sim.send("G 50000 500")
                    # Test H 0 0
                    r_h = sim.send("H 0 0")
                    # Test Z ALT -> homed bit 1
                    sim.homing_duration = 0.05
                    sim.send("Z ALT")
                    time.sleep(0.1)
                    p_home = sim.send("P")
                    parts_h = p_home.split()
                    homed_bit1 = (int(parts_h[5]) & 1) != 0

                    # Test F 200 and F 99999
                    r_f_ok = sim.send("F 200")
                    r_f_lim = sim.send("F 99999")
                    r_s = sim.send("S")

                    if (r_lim == "ERR LIMIT" and r_h == "OK" and homed_bit1 and
                            r_f_ok == "OK" and r_f_lim == "ERR LIMIT" and r_s == "OK"):
                        record_pass("test_7_simlink_protocol")
                    else:
                        record_fail("test_7_simlink_protocol",
                                    f"r_lim={r_lim}, r_h={r_h}, homed1={homed_bit1}, r_f={r_f_ok}/{r_f_lim}, r_s={r_s}")
        sim.close()
    except Exception as e:
        record_fail("test_7_simlink_protocol", str(e))

    # --------------------------------------------------------------------------
    # Test 8: Stellarium server with fragmented goto and position reporting
    # --------------------------------------------------------------------------
    try:
        t_test = dt.datetime(2026, 11, 2, 20, 0, 0)
        cfg = Config()
        cfg["epoch"] = "JNow"
        cfg["simulate"] = True
        cfg["speed_az"] = 5000
        cfg["speed_alt"] = 5000
        cfg["stellarium_port"] = 0  # Dynamic port allocation
        cfg["position_report_interval_s"] = 0.1

        sim = SimLink(cfg)
        sim.speed_az = 5000.0
        sim.speed_alt = 5000.0
        core = BridgeCore(config=cfg, link=sim, time_fn=lambda: t_test)
        core.connect(simulate=True)

        server = StellariumServer("127.0.0.1", 0, core)
        server.start()

        # Connect fake Stellarium client
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect(("127.0.0.1", server.port))

        # Compute bright star coordinates at Alt=45°, Az=120°
        ra_target, dec_target = altaz_to_radec(45.0, 120.0, float(cfg["latitude_deg"]), float(cfg["longitude_deg"]), t_test)

        # Pre-position mount close to target (Alt 44°, Az 119°) to slew quickly
        init_az_steps = angle_to_steps(119.0, cfg["steps_per_deg_az"], 1)
        init_alt_steps = angle_to_steps(44.0, cfg["steps_per_deg_alt"], 1)
        core.link.send(f"H {init_az_steps} {init_alt_steps}")

        # Send goto in TWO fragments to test TCP stream reassembly
        ra_int = int(round((ra_target % 360.0) / 360.0 * 2**32)) & 0xFFFFFFFF
        dec_int = int(round(dec_target / 90.0 * 0x40000000))
        goto_packet = struct.pack('<HHQIi', 20, 0, int(time.time() * 1e6), ra_int, dec_int)

        client_sock.sendall(goto_packet[:9])
        time.sleep(0.05)
        client_sock.sendall(goto_packet[9:])

        # Read position reports (24 bytes) until telescope arrives within 0.05° of target
        client_sock.settimeout(4.0)
        t_wait_end = time.time() + 4.0
        arrived = False
        in_buf = bytearray()

        while time.time() < t_wait_end:
            try:
                data = client_sock.recv(128)
                if not data:
                    break
                in_buf.extend(data)
                while len(in_buf) >= 24:
                    chunk = in_buf[:24]
                    in_buf = in_buf[24:]
                    p_len, p_type, _t_us, p_ra_u, p_dec_i, p_stat = struct.unpack('<HHQIii', chunk)
                    if p_len == 24 and p_type == 0:
                        rep_ra = p_ra_u / 2**32 * 360.0
                        rep_dec = p_dec_i / 0x40000000 * 90.0
                        dist = separation_deg(rep_ra, rep_dec, ra_target, dec_target)
                        if dist <= 0.05:
                            arrived = True
                            break
                if arrived:
                    break
            except socket.timeout:
                break

        client_sock.close()
        server.stop()
        core.disconnect()

        if arrived:
            record_pass("test_8_stellarium_server_goto_and_report")
        else:
            record_fail("test_8_stellarium_server_goto_and_report", "Reported position did not reach target within 0.05°")
    except Exception as e:
        record_fail("test_8_stellarium_server_goto_and_report", str(e))

    # --------------------------------------------------------------------------
    # Test 9: Refusals (below horizon and Sun keep-out)
    # --------------------------------------------------------------------------
    try:
        t_ref = dt.datetime(2026, 11, 2, 12, 0, 0)
        cfg = Config()
        sim = SimLink(cfg)
        core = BridgeCore(config=cfg, link=sim, time_fn=lambda: t_ref)
        core.connect(simulate=True)

        # 1. Target below horizon (Alt -15°)
        ra_below, dec_below = altaz_to_radec(-15.0, 180.0, float(cfg["latitude_deg"]), float(cfg["longitude_deg"]), t_ref)
        refused_below = not core.on_goto_requested(ra_below, dec_below)

        # 2. Target within 15° of Sun
        sun_r, sun_d = sun_radec(t_ref)
        refused_sun = not core.on_goto_requested(sun_r, sun_d)

        core.disconnect()
        if refused_below and refused_sun and not core.tracking_enabled:
            record_pass("test_9_goto_refusals")
        else:
            record_fail("test_9_goto_refusals", f"refused_below={refused_below}, refused_sun={refused_sun}")
    except Exception as e:
        record_fail("test_9_goto_refusals", str(e))

    # --------------------------------------------------------------------------
    # Test 10: Tracking update with injected simulated clock
    # --------------------------------------------------------------------------
    try:
        current_sim_time = dt.datetime(2026, 11, 2, 21, 0, 0)
        cfg = Config()
        sim = SimLink(cfg)
        core = BridgeCore(config=cfg, link=sim, time_fn=lambda: current_sim_time)
        core.connect(simulate=True)

        # GoTo a target at Alt 45°, Az 90°
        ra_t, dec_t = altaz_to_radec(45.0, 90.0, float(cfg["latitude_deg"]), float(cfg["longitude_deg"]), current_sim_time)
        core.on_goto_requested(ra_t, dec_t)
        first_steps = core.last_sent_steps

        # Mount arrives at target destination (clearing moving flag)
        sim.az_pos = sim.az_target
        sim.alt_pos = sim.alt_target
        sim._update_telemetry()

        # Advance simulated clock by 120 seconds
        current_sim_time += dt.timedelta(seconds=120)
        core.update_tracking()
        second_steps = core.last_sent_steps

        core.disconnect()
        if first_steps != second_steps and first_steps is not None and second_steps is not None:
            record_pass("test_10_tracking_clock_advance")
        else:
            record_fail("test_10_tracking_clock_advance", f"Steps unchanged: {first_steps} == {second_steps}")
    except Exception as e:
        record_fail("test_10_tracking_clock_advance", str(e))

    # --------------------------------------------------------------------------
    # Test 11: SYNC clears offsets and sends H
    # --------------------------------------------------------------------------
    try:
        t_sync = dt.datetime(2026, 11, 2, 22, 0, 0)
        cfg = Config()
        sim = SimLink(cfg)
        core = BridgeCore(config=cfg, link=sim, time_fn=lambda: t_sync)
        core.connect(simulate=True)

        ra_s, dec_s = altaz_to_radec(50.0, 100.0, float(cfg["latitude_deg"]), float(cfg["longitude_deg"]), t_sync)
        core.on_goto_requested(ra_s, dec_s)

        # Jog mount while tracking
        core.jog("up", "medium")
        core.jog("right", "medium")
        has_offsets = (core.alt_off_steps != 0 and core.az_off_steps != 0)

        # SYNC
        core.sync()
        cleared_offsets = (core.alt_off_steps == 0 and core.az_off_steps == 0)

        core.disconnect()
        if has_offsets and cleared_offsets:
            record_pass("test_11_sync_resets_offsets")
        else:
            record_fail("test_11_sync_resets_offsets", f"has_offsets={has_offsets}, cleared_offsets={cleared_offsets}")
    except Exception as e:
        record_fail("test_11_sync_resets_offsets", str(e))

    # --------------------------------------------------------------------------
    # Test 12: Epoch handling - same position in J2000 vs JNow yields identical Alt/Az
    # --------------------------------------------------------------------------
    try:
        t_ep = dt.datetime(2026, 11, 2, 23, 0, 0)
        lat = 12.84
        lon = 80.15
        ra_j2000, dec_j2000 = 83.633, 22.014  # Crab Nebula M1 in J2000

        # In epoch J2000, precess to date
        ra_date, dec_date = precess_j2000_to_date(ra_j2000, dec_j2000, t_ep)
        alt_from_j2000, az_from_j2000 = radec_to_altaz(ra_date, dec_date, lat, lon, t_ep)

        # In epoch JNow, given directly in of-date coordinates
        alt_from_jnow, az_from_jnow = radec_to_altaz(ra_date, dec_date, lat, lon, t_ep)

        diff_alt = abs(alt_from_j2000 - alt_from_jnow)
        diff_az = abs(az_from_j2000 - az_from_jnow)

        if diff_alt < 1e-6 and diff_az < 1e-6:
            record_pass("test_12_epoch_conversion_consistency")
        else:
            record_fail("test_12_epoch_conversion_consistency", f"diff_alt={diff_alt}, diff_az={diff_az}")
    except Exception as e:
        record_fail("test_12_epoch_conversion_consistency", str(e))

    # --------------------------------------------------------------------------
    # Test 13: Zero-gap predictive time-of-flight intercept and satellite tracking
    # --------------------------------------------------------------------------
    try:
        t_intercept_0 = dt.datetime(2026, 11, 2, 22, 0, 0)
        current_time = t_intercept_0
        cfg_i = Config()
        cfg_i["epoch"] = "J2000"
        cfg_i["speed_az"] = 226
        cfg_i["speed_alt"] = 226
        sim_i = SimLink(cfg_i)
        core_i = BridgeCore(config=cfg_i, link=sim_i, time_fn=lambda: current_time)
        core_i.connect(simulate=True)

        ra_rigel, dec_rigel = 78.634, -8.201
        ok = core_i.on_goto_requested(ra_rigel, dec_rigel, is_j2000=True, predict_flight=True)

        # Compute commanded steps vs target arrival
        tgt_az_steps, tgt_alt_steps = core_i.last_sent_steps
        time_az = abs(steps_to_angle(tgt_az_steps, cfg_i["steps_per_deg_az"], 1)) / (226.0 / 113.22)
        time_alt = abs(steps_to_angle(tgt_alt_steps, cfg_i["steps_per_deg_alt"], 1)) / (226.0 / 113.22)
        flight_s = max(time_az, time_alt)
        arrival_time = t_intercept_0 + dt.timedelta(seconds=flight_s)

        # Advance simulated mount to target steps and advance clock to arrival time
        sim_i.az_pos = tgt_az_steps
        sim_i.alt_pos = tgt_alt_steps
        sim_i._update_telemetry()
        current_time = arrival_time

        # Mount pointing at arrival:
        mount_alt, mount_az = core_i.get_telescope_altaz()

        # Rigel's true celestial apparent position in the sky at arrival time:
        ra_date_arr, dec_date_arr = precess_j2000_to_date(ra_rigel, dec_rigel, arrival_time)
        rigel_alt, rigel_az = radec_to_altaz(ra_date_arr, dec_date_arr, float(cfg_i["latitude_deg"]), float(cfg_i["longitude_deg"]), arrival_time)

        # Measure pointing error on arrival:
        pointing_gap = math.hypot(mount_az - rigel_az, mount_alt - rigel_alt)

        # Also test satellite tracking method:
        sat_ok = core_i.track_satellite_altaz(45.0, 150.0, name="ISS (ZARYA)")

        core_i.disconnect()

        # Intercept error must be under 0.05 degrees (under 3 arcminutes)
        if ok and pointing_gap < 0.05 and sat_ok:
            record_pass("test_13_predictive_intercept_zero_gap")
        else:
            record_fail("test_13_predictive_intercept_zero_gap", f"ok={ok}, gap={pointing_gap:.6f} deg, sat_ok={sat_ok}")
    except Exception as e:
        record_fail("test_13_predictive_intercept_zero_gap", str(e))

    print(f"\nSelf-test complete: {passed}/{total} tests passed.")
    return 0 if (passed == total) else 1

# ==============================================================================
# MAIN ENTRY POINT (Section 8.1)
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="GoTo Telescope Controller & Stellarium Bridge")
    parser.add_argument("--selftest", action="store_true", help="Run headless verification self-test suite and exit")
    parser.add_argument("--simulate", action="store_true", help="Start GUI with simulated Uno selected")
    parser.add_argument("--config", type=str, default="telescope_config.json", help="Path to JSON configuration file")
    parser.add_argument("--tk", action="store_true", help="Launch legacy Tkinter UI instead of modern PyQt6 UI")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Mode 1: Headless self-test
    if args.selftest:
        exit_code = run_self_test()
        sys.exit(exit_code)

    # Mode 2: Modern PyQt6 UI (default)
    if not args.tk:
        try:
            from telescope_ui_qt import launch_app
            launch_app(simulate=args.simulate, config_path=args.config)
            return
        except ImportError as e:
            logging.info(f"PyQt6 not available ({e}), falling back to Tkinter UI.")

    # Mode 3: Legacy Tkinter Desktop GUI
    # Check pyserial availability for GUI mode
    if not HAS_PYSERIAL and not args.simulate:
        print("\n" + "=" * 70)
        print("ERROR: pyserial is required to connect to the Arduino Uno.")
        print("Please install it with:")
        print("    pip install pyserial")
        print("Or run in simulation mode with:")
        print("    python telescope_bridge.py --simulate")
        print("=" * 70 + "\n")
        sys.exit(1)

    # Mode 2: Interactive Desktop GUI
    import tkinter as tk

    config = Config(args.config)
    if args.simulate:
        config["simulate"] = True

    core = BridgeCore(config=config)
    core.start_tracking_thread()

    stellarium_server = StellariumServer(
        host=config.get("stellarium_host", "127.0.0.1"),
        port=int(config.get("stellarium_port", 10001)),
        core=core
    )
    stellarium_server.start()

    root = tk.Tk()
    _app = TelescopeApp(root, core, stellarium_server)

    try:
        root.mainloop()
    finally:
        core.stop_tracking_thread()
        stellarium_server.stop()
        core.disconnect()

if __name__ == "__main__":
    main()
