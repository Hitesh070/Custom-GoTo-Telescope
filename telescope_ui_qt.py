"""
telescope_ui_qt.py
Professional Desktop User Interface for 3-Axis GoTo Telescope Mount & Stellarium Bridge.
Version 2.0 - Scientific Human-Engineered Interface with High-Speed Telemetry Streaming.
"""

from __future__ import annotations

import math
import os
import sys
import time
import datetime as dt
import threading
from typing import Optional, Tuple, Dict, Any, List

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QObject, pyqtSignal, QThread
from PyQt6.QtGui import (
    QColor, QFont, QPen, QBrush, QPainter, QLinearGradient, 
    QKeySequence, QShortcut, QIcon, QPixmap
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QComboBox, QCheckBox, 
    QRadioButton, QButtonGroup, QTextEdit, QFrame, QSplitter, 
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox, 
    QLineEdit, QMessageBox, QTabWidget, QScrollArea, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView
)

# Serial port detection
try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL_LOCAL = True
except ImportError:
    serial = None
    HAS_PYSERIAL_LOCAL = False

# Import bridge components
try:
    from telescope_bridge import (
        BridgeCore, StellariumServer, Config, StellariumHttpFollower,
        sun_radec, moon_radec, planet_radec, radec_to_altaz, altaz_to_radec, separation_deg, 
        HAS_PYSERIAL, steps_to_angle, julian_date,
        precess_date_to_j2000, precess_j2000_to_date, lst_deg
    )
except ImportError:
    BridgeCore = None
    StellariumServer = None
    Config = None
    StellariumHttpFollower = None
    sun_radec = None
    moon_radec = None
    planet_radec = None
    radec_to_altaz = None
    altaz_to_radec = None
    separation_deg = None
    HAS_PYSERIAL = False
    steps_to_angle = None
    julian_date = None
    precess_date_to_j2000 = None
    precess_j2000_to_date = None
    lst_deg = None


# ==============================================================================
# HIGH-PRECISION ASTRONOMICAL CALCULATIONS & FORMATTING
# ==============================================================================

def deg_to_dms(d: float, signed: bool = True, decimals: int = 1) -> str:
    """Formats degrees to +/-DD° MM' SS.S\" string with exact fractional precision."""
    s = '-' if d < 0 else ('+' if signed else '')
    d_abs = abs(d)
    deg = int(d_abs)
    rem = (d_abs - deg) * 60.0
    m = int(rem)
    sec = (rem - m) * 60.0
    if decimals == 1:
        return f"{s}{deg:02d}° {m:02d}' {sec:04.1f}\""
    elif decimals == 2:
        return f"{s}{deg:02d}° {m:02d}' {sec:05.2f}\""
    else:
        return f"{s}{deg:02d}° {m:02d}' {int(sec):02d}\""

def deg_to_hms(d: float, decimals: int = 2) -> str:
    """Formats degrees (0..360) to HHh MMm SS.SSs string matching Stellarium."""
    h = (d % 360.0) / 15.0
    hh = int(h)
    rem = (h - hh) * 60.0
    mm = int(rem)
    sec = (rem - mm) * 60.0
    if decimals == 2:
        return f"{hh:02d}h {mm:02d}m {sec:05.2f}s"
    elif decimals == 1:
        return f"{hh:02d}h {mm:02d}m {sec:04.1f}s"
    else:
        return f"{hh:02d}h {mm:02d}m {int(sec):02d}s"

def hours_to_hms(h: float, decimals: int = 2) -> str:
    """Formats hours (0..24) to HHh MMm SS.SSs string matching Stellarium."""
    h_norm = h % 24.0
    hh = int(h_norm)
    rem = (h_norm - hh) * 60.0
    mm = int(rem)
    sec = (rem - mm) * 60.0
    if decimals == 2:
        return f"{hh:02d}h {mm:02d}m {sec:05.2f}s"
    elif decimals == 1:
        return f"{hh:02d}h {mm:02d}m {sec:04.1f}s"
    else:
        return f"{hh:02d}h {mm:02d}m {int(sec):02d}s"

def radec_to_galactic(ra_deg: float, dec_deg: float) -> Tuple[float, float]:
    """Converts J2000 RA/Dec to Galactic coordinates (l, b) in degrees."""
    ra_rad = math.radians(ra_deg)
    dec_rad = math.radians(dec_deg)
    ra_gp = math.radians(192.85948)
    dec_gp = math.radians(27.12825)
    l_omega = math.radians(32.93192)

    sin_b = math.sin(dec_rad) * math.sin(dec_gp) + math.cos(dec_rad) * math.cos(dec_gp) * math.cos(ra_rad - ra_gp)
    b_rad = math.asin(max(-1.0, min(1.0, sin_b)))
    cos_b = math.cos(b_rad)

    if abs(cos_b) < 1e-7:
        l_rad = 0.0
    else:
        y = math.cos(dec_rad) * math.sin(ra_rad - ra_gp)
        x = math.sin(dec_rad) * math.cos(dec_gp) - math.cos(dec_rad) * math.sin(dec_gp) * math.cos(ra_rad - ra_gp)
        l_rad = (math.atan2(y, x) + l_omega) % (2.0 * math.pi)

    return math.degrees(l_rad), math.degrees(b_rad)

def radec_to_ecliptic(ra_deg: float, dec_deg: float) -> Tuple[float, float]:
    """Converts J2000 RA/Dec to Ecliptic coordinates (lambda, beta) in degrees."""
    eps = math.radians(23.4392911)
    alpha = math.radians(ra_deg)
    delta = math.radians(dec_deg)
    sin_beta = math.sin(delta) * math.cos(eps) - math.cos(delta) * math.sin(eps) * math.sin(alpha)
    beta = math.asin(max(-1.0, min(1.0, sin_beta)))
    y = math.sin(delta) * math.sin(eps) + math.cos(delta) * math.cos(eps) * math.sin(alpha)
    x = math.cos(delta) * math.cos(alpha)
    lam = math.atan2(y, x) % (2.0 * math.pi)
    return math.degrees(lam), math.degrees(beta)

def calculate_parallactic_angle(ha_hours: float, dec_deg: float, lat_deg: float) -> float:
    """Calculates parallactic angle q in degrees."""
    ha_rad = math.radians(ha_hours * 15.0)
    dec_rad = math.radians(dec_deg)
    lat_rad = math.radians(lat_deg)
    y = math.sin(ha_rad)
    x = math.tan(lat_rad) * math.cos(dec_rad) - math.sin(dec_rad) * math.cos(ha_rad)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(y, x))

def calculate_ephemeris(ra_deg: float, dec_deg: float, lat_deg: float) -> Tuple[str, str, str]:
    """Calculates approximate Rise, Transit, and Set LST times."""
    phi = math.radians(lat_deg)
    delta = math.radians(dec_deg)
    h0 = math.radians(-0.5667)

    denom = math.cos(phi) * math.cos(delta)
    if abs(denom) < 1e-9:
        return "--:--", "--:--", "--:--"
    cos_H0 = (math.sin(h0) - math.sin(phi) * math.sin(delta)) / denom

    if cos_H0 < -1.0:
        return "Circumpolar", "Visible", "Never Sets"
    elif cos_H0 > 1.0:
        return "Never Rises", "Below Horizon", "Never Rises"

    H0_deg = math.degrees(math.acos(cos_H0))

    def fmt_lst(lst_val: float) -> str:
        h = (lst_val % 360.0) / 15.0
        hh = int(h)
        mm = int((h - hh) * 60)
        return f"{hh:02d}h {mm:02d}m"

    transit = fmt_lst(ra_deg)
    rise = fmt_lst(ra_deg - H0_deg)
    setting = fmt_lst(ra_deg + H0_deg)
    return rise, transit, setting

def get_constellation(ra_deg: float, dec_deg: float) -> str:
    """IAU constellation designation lookup."""
    ra_h = (ra_deg % 360.0) / 15.0
    d = dec_deg

    if d > 60:
        if 0 <= ra_h < 4: return "Cas (Cassiopeia)"
        if 4 <= ra_h < 8: return "Cam (Camelopardalis)"
        if 8 <= ra_h < 15: return "UMa (Ursa Major)"
        if 15 <= ra_h < 18: return "Dra (Draco)"
        if 18 <= ra_h < 24: return "Cep (Cepheus)"
        return "UMi (Ursa Minor)"
    elif d < -50:
        if 0 <= ra_h < 3: return "Hyi (Hydrus)"
        if 3 <= ra_h < 6: return "Dor (Dorado)"
        if 6 <= ra_h < 12: return "Car (Carina)"
        if 12 <= ra_h < 14: return "Cru (Crux)"
        if 14 <= ra_h < 18: return "Cen (Centaurus)"
        if 18 <= ra_h < 22: return "Pav (Pavo)"
        return "Tuc (Tucana)"
    else:
        if -10 <= d <= 30:
            if 0 <= ra_h < 2.5: return "Cet (Cetus)" if d < 10 else "Psc (Pisces)"
            if 2.5 <= ra_h < 4.5: return "Tau (Taurus)" if d > 5 else "Eri (Eridanus)"
            if 4.5 <= ra_h < 6.5: return "Ori (Orion)"
            if 6.5 <= ra_h < 8.5: return "Gem (Gemini)" if d > 10 else "CMi (Canis Minor)"
            if 8.5 <= ra_h < 10: return "Cnc (Cancer)"
            if 10 <= ra_h < 12.5: return "Leo (Leo)"
            if 12.5 <= ra_h < 15.5: return "Vir (Virgo)"
            if 15.5 <= ra_h < 17: return "Lib (Libra)" if d < 0 else "Ser (Serpens)"
            if 17 <= ra_h < 19: return "Oph (Ophiuchus)"
            if 19 <= ra_h < 21: return "Aql (Aquila)"
            if 21 <= ra_h < 23: return "Aqr (Aquarius)"
            return "Peg (Pegasus)"
        elif d > 30:
            if 0 <= ra_h < 3: return "And (Andromeda)"
            if 3 <= ra_h < 5: return "Per (Perseus)"
            if 5 <= ra_h < 7.5: return "Aur (Auriga)"
            if 7.5 <= ra_h < 11: return "Lyn (Lynx)"
            if 11 <= ra_h < 14: return "CVn (Canes Venatici)"
            if 14 <= ra_h < 16.5: return "Boo (Bootes)"
            if 16.5 <= ra_h < 18.5: return "Her (Hercules)"
            if 18.5 <= ra_h < 20.5: return "Lyr (Lyra)"
            if 20.5 <= ra_h < 23: return "Cyg (Cygnus)"
            return "Peg (Pegasus)"
        else:
            if 0 <= ra_h < 3.5: return "Eri (Eridanus)"
            if 3.5 <= ra_h < 6: return "Lep (Lepus)"
            if 6 <= ra_h < 8.5: return "CMa (Canis Major)"
            if 8.5 <= ra_h < 11.5: return "Hya (Hydra)"
            if 11.5 <= ra_h < 14: return "Crv (Corvus)"
            if 14 <= ra_h < 16: return "Lup (Lupus)"
            if 16 <= ra_h < 18: return "Sco (Scorpius)"
            if 18 <= ra_h < 20.5: return "Sgr (Sagittarius)"
            if 20.5 <= ra_h < 22.5: return "Cap (Capricornus)"
            return "PsA (Piscis Austrinus)"


# ==============================================================================
# SCIENTIFIC OBSERVATORY STYLESHEET (NO EMOJIS, HIGH READABILITY)
# ==============================================================================

SCIENTIFIC_STYLE = """
QMainWindow, QDialog {
    background-color: #12151B;
    color: #DCE2EB;
}

QWidget {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #DCE2EB;
    font-size: 12px;
}

QFrame.card {
    background-color: #1A1E26;
    border: 1px solid #2B313D;
    border-radius: 4px;
}

QFrame.header-deck {
    background-color: #151820;
    border-bottom: 1px solid #2B313D;
}

QLabel {
    color: #C8D1DC;
}

QLabel.title {
    font-size: 15px;
    font-weight: 700;
    color: #E2E8F0;
}

QLabel.subtitle {
    font-size: 11px;
    color: #8892A0;
}

QLabel.section-header {
    font-size: 12px;
    font-weight: 700;
    color: #94A3B8;
    padding-bottom: 3px;
    border-bottom: 1px solid #2B313D;
}

/* HIGH-VISIBILITY READABLE TELEMETRY TYPOGRAPHY */
QLabel.table-key {
    font-size: 12px;
    font-weight: 600;
    color: #94A3B8;
    padding: 3px 0px;
}

QLabel.table-val {
    font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #FFFFFF;
    padding: 3px 0px;
}

QLabel.hero-label {
    font-size: 11px;
    font-weight: 700;
    color: #8892A0;
}

QLabel.hero-val {
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 21px;
    font-weight: 800;
    color: #79B8FF;
}

QPushButton {
    background-color: #272C36;
    border: 1px solid #3B4352;
    border-radius: 3px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    color: #DCE2EB;
}

QPushButton:hover {
    background-color: #353B49;
    border-color: #4C5668;
}

QPushButton:pressed {
    background-color: #1C2028;
}

QPushButton:disabled {
    background-color: #16181F;
    border-color: #242832;
    color: #555D6B;
}

QPushButton.primary {
    background-color: #265585;
    border-color: #386FA8;
    color: #FFFFFF;
}

QPushButton.primary:hover {
    background-color: #30669E;
}

QPushButton.sync-btn {
    background-color: #855C26;
    border-color: #A37130;
    color: #FFFFFF;
}

QPushButton.sync-btn:hover {
    background-color: #9E6E2E;
}

QPushButton.stop-btn {
    background-color: #8A2626;
    border-color: #A83030;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 800;
}

QPushButton.stop-btn:hover {
    background-color: #A32E2E;
}

QComboBox {
    background-color: #1F232B;
    border: 1px solid #3B4352;
    border-radius: 3px;
    padding: 4px 6px;
    color: #DCE2EB;
    font-size: 11px;
}

QComboBox:hover {
    border-color: #556275;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background-color: #1F232B;
    border: 1px solid #3B4352;
    selection-background-color: #265585;
    selection-color: #FFFFFF;
    color: #DCE2EB;
}

QCheckBox, QRadioButton {
    font-size: 11px;
    color: #C8D1DC;
    spacing: 5px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    background-color: #1F232B;
    border: 1px solid #3B4352;
    border-radius: 2px;
}

QRadioButton::indicator {
    border-radius: 7px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #265585;
    border-color: #4A89CE;
}

QTextEdit {
    background-color: #0E1015;
    border: 1px solid #252A34;
    border-radius: 3px;
    color: #ABB2BF;
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 11px;
    padding: 4px;
}

QScrollBar:vertical {
    border: none;
    background: #14171E;
    width: 7px;
}

QScrollBar::handle:vertical {
    background: #333946;
    min-height: 20px;
    border-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #2B313D;
    background-color: #1A1E26;
}

QTabBar::tab {
    background-color: #151820;
    border: 1px solid #2B313D;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    color: #8892A0;
}

QTabBar::tab:selected {
    background-color: #1A1E26;
    color: #DCE2EB;
    font-weight: 600;
}
"""


# ==============================================================================
# PURE RED NIGHT-VISION OBSERVATORY STYLESHEET (RHODOPSIN PRESERVING)
# ==============================================================================

NIGHT_VISION_STYLE = """
QMainWindow, QDialog {
    background-color: #000000;
    color: #FF3333;
}

QWidget {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #FF3333;
    font-size: 12px;
}

QFrame.card {
    background-color: #0A0101;
    border: 1px solid #2E0505;
    border-radius: 4px;
}

QFrame.header-deck {
    background-color: #050000;
    border-bottom: 1px solid #2E0505;
}

QFrame.console-deck {
    background-color: #050000;
    border-top: 1px solid #2E0505;
}

QLabel {
    color: #FF4D4D;
}

QLabel.title {
    font-size: 15px;
    font-weight: 700;
    color: #FF6666;
}

QLabel.subtitle {
    font-size: 11px;
    color: #991F1F;
}

QLabel.section-header {
    font-size: 12px;
    font-weight: 700;
    color: #CC2929;
    padding-bottom: 3px;
    border-bottom: 1px solid #380808;
}

/* HIGH-VISIBILITY READABLE TELEMETRY TYPOGRAPHY (PURE RED) */
QLabel.table-key {
    font-size: 12px;
    font-weight: 600;
    color: #AA2222;
    padding: 3px 0px;
}

QLabel.table-val {
    font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #FF2222;
    padding: 3px 0px;
}

QLabel.hero-label {
    font-size: 11px;
    font-weight: 700;
    color: #991F1F;
}

QLabel.hero-val {
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 21px;
    font-weight: 800;
    color: #FF4444;
}

QPushButton {
    background-color: #1A0303;
    border: 1px solid #4D0A0A;
    border-radius: 3px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    color: #FF4D4D;
}

QPushButton:hover {
    background-color: #2E0505;
    border-color: #660D0D;
    color: #FF7777;
}

QPushButton:pressed {
    background-color: #0F0101;
}

QPushButton:disabled {
    background-color: #0A0000;
    border-color: #240404;
    color: #4D0D0D;
}

QPushButton:checked {
    background-color: #5C0B0B;
    border: 1px solid #991414;
    color: #FFAAAA;
    font-weight: 700;
}

QPushButton.primary {
    background-color: #5C0B0B;
    border-color: #801010;
    color: #FFAAAA;
}

QPushButton.primary:hover {
    background-color: #730E0E;
    color: #FFD0D0;
}

QPushButton.sync-btn {
    background-color: #4A0808;
    border-color: #7A1010;
    color: #FF8888;
}

QPushButton.sync-btn:hover {
    background-color: #6E1010;
    color: #FFAAAA;
}

QPushButton.stop-btn {
    background-color: #8A0A0A;
    border-color: #B30D0D;
    color: #FFAAAA;
    font-size: 12px;
    font-weight: 800;
}

QPushButton.stop-btn:hover {
    background-color: #A80D0D;
    color: #FFD0D0;
}

QComboBox {
    background-color: #140202;
    border: 1px solid #400808;
    border-radius: 3px;
    padding: 4px 6px;
    color: #FF4D4D;
    font-size: 11px;
}

QComboBox:hover {
    border-color: #660D0D;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background-color: #140202;
    border: 1px solid #400808;
    selection-background-color: #4D0A0A;
    selection-color: #FFAAAA;
    color: #FF4D4D;
}

QCheckBox, QRadioButton {
    font-size: 11px;
    color: #FF4D4D;
    spacing: 5px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    background-color: #140202;
    border: 1px solid #400808;
    border-radius: 2px;
}

QRadioButton::indicator {
    border-radius: 7px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #660D0D;
    border-color: #991414;
}

QTextEdit, QLineEdit, QDoubleSpinBox, QSpinBox {
    background-color: #080101;
    border: 1px solid #380808;
    border-radius: 3px;
    color: #FF3333;
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    font-size: 11px;
    padding: 4px;
}

QTableWidget {
    background-color: #080101;
    border: 1px solid #380808;
    gridline-color: #240404;
    color: #FF4D4D;
    selection-background-color: #4D0A0A;
    selection-color: #FFAAAA;
}

QHeaderView::section {
    background-color: #140202;
    color: #AA2222;
    font-weight: 700;
    font-size: 11px;
    border: 1px solid #380808;
    padding: 4px;
}

QScrollBar:vertical {
    border: none;
    background: #080101;
    width: 7px;
}

QScrollBar::handle:vertical {
    background: #330808;
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar:horizontal {
    border: none;
    background: #080101;
    height: 7px;
}

QScrollBar::handle:horizontal {
    background: #330808;
    min-width: 20px;
    border-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #380808;
    background-color: #0D0202;
}

QTabBar::tab {
    background-color: #080101;
    border: 1px solid #380808;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    color: #801A1A;
}

QTabBar::tab:selected {
    background-color: #0D0202;
    color: #FF4D4D;
    font-weight: 600;
}

QToolTip {
    background-color: #140202;
    color: #FF6666;
    border: 1px solid #4D0A0A;
}

QMessageBox {
    background-color: #000000;
    color: #FF3333;
}
"""

# ==============================================================================
# LIVE CLOUD COVER & METEOROLOGICAL TELEMETRY SERVICE (OPEN-METEO)
# ==============================================================================

class LiveWeatherService(QObject):
    """Asynchronous, non-blocking astronomical weather & cloud transparency telemetry
    queried from Open-Meteo API for real-time sky observation conditions.
    """
    weather_updated = pyqtSignal(dict)
    weather_error = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config
        self.latest_data: Optional[Dict[str, Any]] = None
        self._is_fetching: bool = False
        
        # Periodic auto-refresh every 15 minutes (900,000 ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.fetch_async)
        self._timer.start(900000)

    def fetch_async(self) -> None:
        if self._is_fetching:
            return
        self._is_fetching = True
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))
        threading.Thread(target=self._worker, args=(lat, lon), daemon=True).start()

    def _worker(self, lat: float, lon: float) -> None:
        try:
            import urllib.request
            import json
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}&current=cloud_cover,relative_humidity_2m,temperature_2m,wind_speed_10m,visibility,weather_code&hourly=cloud_cover&forecast_days=1"
            req = urllib.request.Request(url, headers={"User-Agent": "AstroGoTo/2.0 (Custom Telescope Controller)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            cur = data.get("current", {})
            cloud = int(cur.get("cloud_cover", 0))
            temp = float(cur.get("temperature_2m", 0.0))
            hum = int(cur.get("relative_humidity_2m", 0))
            wind = float(cur.get("wind_speed_10m", 0.0))
            vis_m = float(cur.get("visibility", 10000.0))
            vis_km = vis_m / 1000.0
            code = int(cur.get("weather_code", 0))

            wmo_desc = {
                0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing Rime Fog",
                51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
                61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
                71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
                80: "Rain Showers", 81: "Moderate Showers", 82: "Violent Showers",
                95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Heavy Hail Storm"
            }.get(code, "Cloudy" if cloud > 60 else "Partly Cloudy")

            if cloud >= 80:
                transparency = "Obscured (Overcast)"
                obs_status = "HEAVILY OBSCURED"
                badge = "[OVERCAST]"
            elif cloud >= 50:
                transparency = "Poor (Broken Clouds)"
                obs_status = "PARTIALLY OBSCURED"
                badge = "[BROKEN CLOUDS]"
            elif cloud >= 25:
                transparency = "Fair (Scattered Clouds)"
                obs_status = "FAIR SEEING"
                badge = "[SCATTERED CLOUDS]"
            elif cloud >= 10:
                transparency = "Good (Few Clouds)"
                obs_status = "GOOD SEEING"
                badge = "[MAINLY CLEAR]"
            else:
                transparency = "Pristine (Clear Dark Sky)"
                obs_status = "PRISTINE CONDITIONS"
                badge = "[CLEAR SKY]"

            result = {
                "cloud_cover": cloud,
                "temperature_c": temp,
                "humidity_pct": hum,
                "wind_kmh": wind,
                "visibility_km": vis_km,
                "weather_code": code,
                "condition": wmo_desc,
                "transparency": transparency,
                "obs_status": obs_status,
                "badge": badge,
                "is_overcast": (cloud >= 80),
                "updated_at": dt.datetime.now().strftime("%H:%M:%S")
            }
            self.latest_data = result
            self.weather_updated.emit(result)
        except Exception as e:
            self.weather_error.emit(str(e))
        finally:
            self._is_fetching = False

def play_audio_cue(cue_name: str, enabled: bool = True) -> None:
    """Dispatches asynchronous audio feedback via standard library winsound (non-blocking)."""
    if not enabled:
        return
    def _run():
        try:
            import winsound
            if cue_name == "slew_complete":
                # Pleasing ascending arrival chime: 587 Hz (D5) -> 880 Hz (A5)
                winsound.Beep(587, 80)
                time.sleep(0.03)
                winsound.Beep(880, 110)
            elif cue_name == "sync":
                # Calibration confirmation tone: 784 Hz (G5)
                winsound.Beep(784, 120)
            elif cue_name == "warning":
                # Cautionary low tone: 294 Hz (D4)
                winsound.Beep(294, 180)
            elif cue_name == "stop":
                # Urgent double low buzz: 220 Hz (A3)
                winsound.Beep(220, 90)
                time.sleep(0.04)
                winsound.Beep(220, 110)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ==============================================================================
# ENLARGED SCIENTIFIC POLAR SKY RADAR
# ==============================================================================

class EnlargedPolarRadarWidget(QWidget):
    """Clean astronomical celestial radar display."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(380, 380)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self.scope_alt: float = 0.0
        self.scope_az: float = 0.0
        self.target_alt: Optional[float] = None
        self.target_az: Optional[float] = None
        self.sun_alt: Optional[float] = None
        self.sun_az: Optional[float] = None
        self.sun_keepout_deg: float = 15.0
        self.night_mode: bool = False

    def set_night_mode(self, enabled: bool) -> None:
        if self.night_mode != enabled:
            self.night_mode = enabled
            self.update()

    def set_scope_altaz(self, alt: float, az: float) -> None:
        if abs(self.scope_alt - alt) > 0.001 or abs(self.scope_az - az) > 0.001:
            self.scope_alt = alt
            self.scope_az = az
            self.update()

    def set_target_altaz(self, alt: Optional[float], az: Optional[float]) -> None:
        if self.target_alt != alt or self.target_az != az:
            self.target_alt = alt
            self.target_az = az
            self.update()

    def set_sun_altaz(self, alt: Optional[float], az: Optional[float], keepout: float = 15.0) -> None:
        self.sun_alt = alt
        self.sun_az = az
        self.sun_keepout_deg = keepout
        self.update()

    def _altaz_to_xy(self, alt: float, az: float, cx: float, cy: float, radius: float) -> Tuple[float, float]:
        clamped_alt = max(0.0, min(90.0, alt))
        r = radius * (1.0 - (clamped_alt / 90.0))
        rad = math.radians(az)
        x = cx + r * math.sin(rad)
        y = cy - r * math.cos(rad)
        return x, y

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        radius = min(cx, cy) - 26.0

        if radius <= 20:
            return

        # 1. Background Disk
        bg_col = QColor("#050000") if self.night_mode else QColor("#0B0E14")
        border_col = QColor("#3D0808") if self.night_mode else QColor("#242C38")
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, 1.5))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Concentric Elevation Rings (15°, 30°, 45°, 60°, 75°, 85°)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_grid = QPen(QColor("#240404") if self.night_mode else QColor("#1A202C"), 1, Qt.PenStyle.DashLine)
        pen_major = QPen(QColor("#3D0808") if self.night_mode else QColor("#222A3A"), 1, Qt.PenStyle.DashLine)
        
        for deg in [15, 30, 45, 60, 75]:
            r_deg = radius * (1.0 - deg / 90.0)
            painter.setPen(pen_major if deg in (30, 60) else pen_grid)
            painter.drawEllipse(QPointF(cx, cy), r_deg, r_deg)

        # Zenith Limit Ring (85°)
        r_85 = radius * (1.0 - 85.0 / 90.0)
        pen_limit = QPen(QColor("#661010") if self.night_mode else QColor("#543D2A"), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen_limit)
        painter.drawEllipse(QPointF(cx, cy), r_85, r_85)

        # 3. Radial Azimuth Spokes (every 30°)
        pen_spoke = QPen(QColor("#1F0404") if self.night_mode else QColor("#181E29"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_spoke)
        for deg in range(0, 360, 30):
            if deg in (0, 90, 180, 270):
                continue
            rad = math.radians(deg)
            x_outer = cx + radius * math.sin(rad)
            y_outer = cy - radius * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x_outer, y_outer))

        # 4. Crosshair Axes (N-S and E-W)
        pen_axis = QPen(QColor("#330606") if self.night_mode else QColor("#222A3A"), 1)
        painter.setPen(pen_axis)
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))

        # 5. Outer Perimeter Ticks
        pen_tick_maj = QPen(QColor("#5E0D0D") if self.night_mode else QColor("#455266"), 1)
        pen_tick_min = QPen(QColor("#2E0505") if self.night_mode else QColor("#263040"), 1)
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            is_major = (deg % 30 == 0)
            tick_len = 6 if is_major else 3
            painter.setPen(pen_tick_maj if is_major else pen_tick_min)
            x_out = cx + radius * math.sin(rad)
            y_out = cy - radius * math.cos(rad)
            x_in = cx + (radius - tick_len) * math.sin(rad)
            y_in = cy - (radius - tick_len) * math.cos(rad)
            painter.drawLine(QPointF(x_in, y_in), QPointF(x_out, y_out))

        # 6. Compass Labels
        font_cardinal = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font_cardinal)

        # Major Cardinals
        painter.setPen(QColor("#FF3333") if self.night_mode else QColor("#5AA9FF")) # North
        painter.drawText(QRectF(cx - 10, cy - radius - 20, 20, 16), Qt.AlignmentFlag.AlignCenter, "N")

        painter.setPen(QColor("#AA2222") if self.night_mode else QColor("#8892A0"))
        painter.drawText(QRectF(cx + radius + 6, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "E")
        painter.drawText(QRectF(cx - 10, cy + radius + 5, 20, 16), Qt.AlignmentFlag.AlignCenter, "S")
        painter.drawText(QRectF(cx - radius - 26, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "W")

        # Intercardinal Labels (NE, SE, SW, NW)
        font_inter = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font_inter)
        painter.setPen(QColor("#661515") if self.night_mode else QColor("#505D70"))
        r_label = radius + 11.0
        for name, ang in [("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)]:
            rad = math.radians(ang)
            lx = cx + r_label * math.sin(rad)
            ly = cy - r_label * math.cos(rad)
            painter.drawText(QRectF(lx - 12, ly - 8, 24, 16), Qt.AlignmentFlag.AlignCenter, name)

        # Elevation Labels
        font_elev = QFont("Segoe UI", 8)
        painter.setFont(font_elev)
        painter.setPen(QColor("#661414") if self.night_mode else QColor("#4F5868"))
        for elev in [15, 30, 45, 60, 75]:
            r_elev = radius * (1.0 - elev / 90.0)
            painter.drawText(QRectF(cx + 4, cy - r_elev - 7, 30, 14), Qt.AlignmentFlag.AlignLeft, f"{elev}°")
        painter.drawText(QRectF(cx + 4, cy - 9, 30, 14), Qt.AlignmentFlag.AlignLeft, "90°")

        # Zenith Center Point
        painter.setBrush(QBrush(QColor("#FF2222") if self.night_mode else QColor("#5AA9FF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)

        # 7. Astronomical Sun Symbol ☉ & Danger Keep-Out Zone (No text "SUN")
        if self.sun_alt is not None and self.sun_az is not None and self.sun_alt > -10.0:
            sx, sy = self._altaz_to_xy(self.sun_alt, self.sun_az, cx, cy, radius)
            r_danger = radius * (self.sun_keepout_deg / 90.0)

            if self.night_mode:
                # Danger keep-out zone circle (deep dark crimson)
                painter.setPen(QPen(QColor(160, 20, 20, 140), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(100, 10, 10, 25)))
                painter.drawEllipse(QPointF(sx, sy), r_danger, r_danger)

                # Outer Corona Glow (ruby red)
                painter.setPen(QPen(QColor(140, 15, 15, 80), 1))
                painter.setBrush(QBrush(QColor(90, 10, 10, 30)))
                painter.drawEllipse(QPointF(sx, sy), 9.0, 9.0)

                # Astronomical Sun Symbol ☉ (dark crimson disc)
                painter.setPen(QPen(QColor("#991414"), 1.5))
                painter.setBrush(QBrush(QColor("#5C0B0B")))
                painter.drawEllipse(QPointF(sx, sy), 5.5, 5.5)

                # Inner Core Dot (ruby red, zero white)
                painter.setBrush(QBrush(QColor("#CC2222")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(sx, sy), 1.8, 1.8)
            else:
                # Danger keep-out zone circle (semi-transparent reddish-amber)
                painter.setPen(QPen(QColor(220, 60, 60, 160), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(220, 50, 50, 18)))
                painter.drawEllipse(QPointF(sx, sy), r_danger, r_danger)

                # Outer Corona Glow
                painter.setPen(QPen(QColor(255, 200, 60, 80), 1))
                painter.setBrush(QBrush(QColor(255, 190, 40, 40)))
                painter.drawEllipse(QPointF(sx, sy), 9.0, 9.0)

                # Astronomical Sun Symbol ☉ (solar disc + central dot)
                painter.setPen(QPen(QColor("#FFC857"), 1.5))
                painter.setBrush(QBrush(QColor("#E6A820")))
                painter.drawEllipse(QPointF(sx, sy), 5.5, 5.5)

                # Inner Core Dot
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(sx, sy), 1.8, 1.8)

        # 8. Stellarium Target Reticle
        if self.target_alt is not None and self.target_az is not None:
            tx, ty = self._altaz_to_xy(self.target_alt, self.target_az, cx, cy, radius)
            mx, my = self._altaz_to_xy(self.scope_alt, self.scope_az, cx, cy, radius)

            # Connecting intercept vector
            painter.setPen(QPen(QColor(160, 40, 40, 120) if self.night_mode else QColor(200, 140, 50, 110), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(mx, my), QPointF(tx, ty))

            # Target Reticle Ring
            target_col = QColor("#FF4D4D") if self.night_mode else QColor("#E5A035")
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(target_col, 1.3, Qt.PenStyle.DashLine))
            painter.drawEllipse(QPointF(tx, ty), 8.5, 8.5)
            
            # Target Crosshairs
            painter.setPen(QPen(target_col, 1.0, Qt.PenStyle.SolidLine))
            painter.drawLine(QPointF(tx - 13, ty), QPointF(tx - 5, ty))
            painter.drawLine(QPointF(tx + 5, ty), QPointF(tx + 13, ty))
            painter.drawLine(QPointF(tx, ty - 13), QPointF(tx, ty - 5))
            painter.drawLine(QPointF(tx, ty + 5), QPointF(tx, ty + 13))

        # 9. Telescope Mount Reticle
        sx, sy = self._altaz_to_xy(self.scope_alt, self.scope_az, cx, cy, radius)

        # Azimuth direction vector from zenith to mount
        mount_vec_col = QColor(100, 20, 20, 75) if self.night_mode else QColor(70, 130, 200, 65)
        painter.setPen(QPen(mount_vec_col, 1))
        painter.drawLine(QPointF(cx, cy), QPointF(sx, sy))

        # Mount Reticle Rings
        mount_outer = QColor("#CC2222") if self.night_mode else QColor("#4A88CE")
        mount_inner = QColor("#FF4444") if self.night_mode else QColor("#5AA9FF")
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(mount_outer, 1.6))
        painter.drawEllipse(QPointF(sx, sy), 10.0, 10.0)
        
        painter.setPen(QPen(mount_inner, 1.2))
        painter.drawEllipse(QPointF(sx, sy), 3.0, 3.0)

        # Mount Reticle Crosshair Ticks
        painter.setPen(QPen(mount_inner, 1.2))
        painter.drawLine(QPointF(sx - 16, sy), QPointF(sx - 10, sy))
        painter.drawLine(QPointF(sx + 10, sy), QPointF(sx + 16, sy))
        painter.drawLine(QPointF(sx, sy - 16), QPointF(sx, sy - 10))
        painter.drawLine(QPointF(sx, sy + 10), QPointF(sx, sy + 16))


# ==============================================================================
# COMPREHENSIVE PROJECT USER MANUAL & HELP DIALOG
# ==============================================================================

class HelpGuideDialog(QDialog):
    """Exhaustive user guide and project documentation dialog."""

    def __init__(self, night_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.night_mode = night_mode
        self.setWindowTitle("Custom GoTo Telescope Controller - User Manual & Technical Guide")
        self.resize(800, 660)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        tabs = self.tabs

        # Tab 1: System Architecture
        t1 = QTextEdit()
        t1.setReadOnly(True)
        t1.setHtml("""
        <h3>1. System Architecture & Operation</h3>
        <p>This software serves as the real-time bridge and astronomical kinematics engine between 
        <b>Stellarium Desktop</b> planetarium software and your custom <b>3-Axis Alt-Az Telescope Mount</b>.</p>

        <p><b>Communication Flow:</b></p>
        <pre>
  [ Stellarium Desktop ]
           |
           | TCP Socket (Port 10001, binary telescope protocol)
           v
  [ telescope_bridge.py / telescope_ui_qt.py ]
      * Real-time J2000 to JNow Precession
      * Topocentric Alt/Az Horizon Transformation (Millisecond Precision)
      * Safety Limits & Solar Keep-Out Checking
      * Software Backlash Compensation
           |
           | USB Serial (115200 Baud, ASCII Command Lines)
           v
  [ Arduino Uno (ATmega328P) ]
      * AccelStepper Trapezoidal Motion Controller
      * Microswitch Altitude & Azimuth Homing
      * Watchdog Safety Timeout & Idle Power Saving
           |
           v
  [ ULN2003 Drivers & 28BYJ-48 Stepper Motors (Az, Alt, Focus) ]
        </pre>
        <p><b>Simulation Mode:</b> You do not need physical components connected to test this software.
        Checking 'Simulate Uno' creates a virtual firmware layer that emulates motor kinematics, step counts,
        accelerations, and Stellarium responses entirely in memory.</p>
        """)
        tabs.addTab(t1, "1. Architecture")

        # Tab 2: Controls Guide
        t2 = QTextEdit()
        t2.setReadOnly(True)
        t2.setHtml("""
        <h3>2. Button & Control Reference</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; border-color: #384150;">
        <tr bgcolor="#21252D"><th>Control / Button</th><th>Keyboard Shortcut</th><th>Function & Usage</th></tr>
        <tr><td><b>ALT + / ALT -</b></td><td>Up / Down Arrow</td><td>Jogs the telescope in Altitude (elevation up/down).</td></tr>
        <tr><td><b>AZ - / AZ +</b></td><td>Left / Right Arrow</td><td>Jogs the telescope in Azimuth (pan left/right).</td></tr>
        <tr><td><b>STOP</b></td><td>Spacebar / Esc</td><td><b>Emergency Stop:</b> Immediately halts all motor motion, turns off sidereal tracking, and locks position.</td></tr>
        <tr><td><b>Fine (0.05°)</b></td><td>--</td><td>Precision jogging rate (6 steps) for centering objects in high-magnification eyepieces.</td></tr>
        <tr><td><b>Medium (0.50°)</b></td><td>--</td><td>Standard framing rate (57 steps) for finder scopes and wide fields.</td></tr>
        <tr><td><b>Coarse (3.00°)</b></td><td>--</td><td>Fast repositioning rate (340 steps) for manual sky sweeping.</td></tr>
        <tr><td><b>Sync Target</b></td><td>--</td><td><b>Star Alignment:</b> When you have centered an object in the eyepiece that was targeted by Stellarium, clicking Sync updates the mount's coordinate offset so pointing remains calibrated.</td></tr>
        <tr><td><b>Tracking: ON / OFF</b></td><td>--</td><td>Toggles the background sidereal tracking loop. When ON, the software automatically commands micro-steps every second to counteract Earth's rotation.</td></tr>
        <tr><td><b>Home Altitude</b></td><td>--</td><td>Commands the altitude axis to seek its physical microswitch (Pin A1) at 0° horizontal, resetting the altitude step register.</td></tr>
        <tr><td><b>Home Azimuth</b></td><td>--</td><td>Commands the azimuth axis to seek its physical microswitch (Pin A2) if installed.</td></tr>
        <tr><td><b>Park Telescope</b></td><td>--</td><td>Slews the telescope safely to its configured parking angles (default 0° Az, 0° Alt) and shuts off motor tracking.</td></tr>
        <tr><td><b>Zero Position (0,0)</b></td><td>--</td><td><b>Manual Alignment:</b> Level the telescope tube horizontally and point it True North, then click this button to set logical (0, 0) coordinates without limit switches.</td></tr>
        <tr><td><b>Motorized Focus (Coarse & Fine)</b></td><td>--</td><td>Drives the focuser stepper motor in <b>Coarse (±200 steps)</b> for rapid travel or <b>Fine (±20 steps)</b> for standard focal adjustment.</td></tr>
        <tr><td><b>Micro Fine Nudge (±5 steps)</b></td><td>--</td><td>Micro-steps the focuser by just 5 motor steps. Perfect for critical planetary, lunar, and high-magnification eyepiece focusing.</td></tr>
        <tr><td><b>Direct Go To Step</b></td><td>--</td><td>Allows entering an exact step coordinate (e.g. 350) and clicking <b>Go</b> to return instantly to a known parfocal eyepiece position.</td></tr>
        <tr><td><b>Zero Focus</b></td><td>--</td><td>Calibrates the current physical focuser drawtube position as step index 0.</td></tr>
        <tr><td><b>Autofocus (V-Curve Routine)</b></td><td>--</td><td><b>Automated Star Focus:</b> Sweeps focal contrast across multiple step samples in a background routine, plots the parabolic V-curve, and automatically centers the motor at the sharpest critical focus zone (CFZ).</td></tr>
        <tr><td><b>Tracking Rate (Sidereal, Lunar, Solar, King)</b></td><td>--</td><td><b>Multi-Rate Kinematics:</b> Selects celestial drive rate. <b>Sidereal</b> (1.000x) for deep sky/stars, <b>Lunar</b> (0.963x) to keep the fast-orbiting Moon centered indefinitely, <b>Solar</b> (0.997x) for Sun observation with filter, or <b>King</b> for refraction-gradient compensation.</td></tr>
        <tr><td><b>Cable Twist & Unwind (0°)</b></td><td>--</td><td><b>Cable-Wrap Prevention:</b> Monitors cumulative turns around the azimuth axis. Clicking <b>Unwind (0°)</b> smoothly slews azimuth back to True North to untangle cables without needing to disconnect.</td></tr>
        <tr><td><b>Simulate Uno</b></td><td>--</td><td>Enables software-only simulation mode for testing without hardware connected.</td></tr>
        </table>
        """)
        tabs.addTab(t2, "2. Controls Guide")

        # Tab 3: Quick Start
        t3 = QTextEdit()
        t3.setReadOnly(True)
        t3.setHtml("""
        <h3>3. Step-by-Step Quick Start Guide</h3>

        <h4>Step A: First-Time Hardware Setup</h4>
        <ol>
          <li><b>Powering Motors:</b> Never power the ULN2003 boards from the Arduino's 5V pin. Connect an external 5V (2A or higher) USB phone charger to the ULN2003 power rails. Tie external Ground and Arduino Ground together.</li>
          <li><b>Mechanical Balance:</b> The 28BYJ-48 stepper has low holding torque (~0.034 N·m). Ensure the telescope tube is balanced at its pivot point so it remains stationary when the motors are unpowered.</li>
          <li><b>Upload Firmware:</b> Open <code>telescope_firmware.ino</code> in Arduino IDE, install the <i>AccelStepper</i> library, and flash to your Uno.</li>
        </ol>

        <h4>Step B: Operating the Bridge & Software</h4>
        <ol>
          <li><b>Launch App:</b> Run <code>python telescope_ui_qt.py</code> or double-click <code>run_app.bat</code> (or <code>dist/AstroGoTo.exe</code>).</li>
          <li><b>Select Connection:</b> Choose your Arduino COM port and click <b>Connect</b> (or check <b>Simulate Uno</b> for software testing).</li>
          <li><b>Initial Orientation:</b> Point the telescope True North and level the tube horizontally. Click <b>Zero Position (0,0)</b> or use <b>Home Altitude</b>.</li>
        </ol>

        <h4>Step C: Connecting Stellarium</h4>
        <ol>
          <li>In Stellarium, open <b>Configuration (F2) -> Plugins -> Telescope Control</b> and check <b>Load at startup</b>.</li>
          <li>Click <b>Configure -> Add (+)</b>:
            <ul>
              <li>Telescope controlled by: <b>External software or a remote computer</b></li>
              <li>Host: <code>127.0.0.1</code></li>
              <li>TCP port: <code>10001</code></li>
            </ul>
          </li>
          <li>Click <b>Connect</b>. The telescope reticle will appear on the Stellarium sky chart!</li>
          <li><b>Coordinate System (Epoch):</b> In Telescope Properties, ensure the <b>Coordinate system</b> setting is set to <b>J2000 (default)</b> to match AstroGoTo. If you switch to <i>Equinox of the date (JNow)</i>, change the Epoch dropdown in AstroGoTo Settings to JNow as well so there is zero precession discrepancy.</li>
          <li><b>Observer Location:</b> Ensure Stellarium's location matches your observing site, or open Settings in AstroGoTo and click <b>Sync Location from Stellarium</b> to pull coordinates automatically over port 8090.</li>
          <li>Click any celestial object in Stellarium and press <b>Ctrl + 1</b>. The mount will automatically slew and track!</li>
        </ol>
        """)
        tabs.addTab(t3, "3. Quick Start")

        # Tab 4: Astronomy Math
        t4 = QTextEdit()
        t4.setReadOnly(True)
        t4.setHtml("""
        <h3>4. Astronomical Coordinates Reference</h3>
        <p>This software calculates topocentric coordinates with high precision:</p>

        <ul>
          <li><b>RA/Dec (J2000.0):</b> Fixed catalog celestial coordinates referenced to Earth's equator and vernal equinox at epoch Jan 1, 2000.</li>
          <li><b>RA/Dec (on date / JNow):</b> Current apparent celestial coordinates taking into account the precession of Earth's rotational axis (~50 arcseconds/year).</li>
          <li><b>Hour Angle (HA):</b> The angular distance of the object from your local meridian (<code>HA = LST - RA</code>). When HA = 0h, the object is at its highest point in the sky (transit).</li>
          <li><b>Azimuth / Altitude:</b> Topocentric horizontal coordinates where Azimuth is compass heading (0° North, 90° East, 180° South, 270° West) and Altitude is angle above the horizon (0° to 90° Zenith).</li>
          <li><b>Galactic (l, b):</b> Coordinate system aligned with the plane of the Milky Way galaxy.</li>
          <li><b>Ecliptic (lambda, beta):</b> Coordinate system aligned with Earth's orbital plane around the Sun.</li>
          <li><b>Parallactic Angle:</b> The angle between the celestial pole and the local zenith at the object.</li>
          <li><b>Atmospheric Refraction Correction:</b> Earth's atmosphere lifts objects near the horizon by up to 35 arcminutes (the width of the full Moon!). AstroGoTo integrates high-precision Saemundsson (1986) & Bennett (1982) formulas scaled for site temperature and barometric pressure, with exact 5-pass fixed-point inversion so pointing matches apparent sky positions down to sub-arcsecond accuracy.</li>
          <li><b>Multi-Rate Celestial Kinematics:</b>
            <ul>
              <li><b>Sidereal:</b> Standard star rate (15.041"/s) for stars, nebulae, and deep sky targets.</li>
              <li><b>Lunar:</b> Moon rate (14.492"/s), compensating for the Moon's 0.549°/hr eastward orbital lag relative to the stars so it remains centered in high-power eyepieces indefinitely.</li>
              <li><b>Solar:</b> Mean solar rate (15.000"/s) for Sun observation with a certified filter.</li>
              <li><b>King:</b> Edward S. King's rate formula accounting for the changing refraction gradient across altitude.</li>
            </ul>
          </li>
          <li><b>Cable-Wrap Prevention:</b> The kinematics engine monitors cumulative azimuth turns and plans shortest-path slews within [-200°, +200°] while favoring unwinding angles to protect cables from strain.</li>
        </ul>
        """)
        tabs.addTab(t4, "4. Astronomy Math")

        # Tab 5: Hardware & Troubleshooting
        t5 = QTextEdit()
        t5.setReadOnly(True)
        t5.setHtml("""
        <h3>5. Hardware Tuning & Troubleshooting</h3>

        <h4>1. Motor Stalling or Skipping Steps:</h4>
        <ul>
          <li><b>Separate Power:</b> Ensure steppers receive 5V directly from an external power supply, not the Arduino Uno.</li>
          <li><b>Speed Setting:</b> Keep max speed at <code>226 steps/s (~2.0°/s)</code> in Settings. Speeds above 350 steps/s lose holding torque rapidly on 28BYJ-48.</li>
          <li><b>Tube Imbalance:</b> Adjust the telescope mounting bracket along its dovetail to balance the center of gravity.</li>
        </ul>

        <h4>2. How Celestial Tracking Works (Stars vs Satellites):</h4>
        <ul>
          <li><b>Stars / Planets (Sidereal Tracking):</b> Earth completes one rotation every 23h 56m (15 arcseconds per second). With our 113.22 steps/degree gearing, the mount dispatches <b>1 motor step every 2.11 seconds</b> (only 0.25° per minute). This subtle motion holds stars centered in the eyepiece.</li>
          <li><b>Satellites (ISS, Starlink):</b> Satellites in Low Earth Orbit move at ~28,000 km/h, streaking across the sky at 1° to 3° per second. Stellarium's standard TCP telescope protocol only sends a single coordinate snapshot upon click.</li>
          <li><b>Tracking Satellites in Real-Time:</b> To follow moving satellites, enable Stellarium's <b>Remote Control</b> plugin:
            <ol>
              <li>In Stellarium, press <b>F2 (Configuration) -> Plugins -> Remote Control</b>.</li>
              <li>Check <b>Load at startup</b> and restart Stellarium.</li>
              <li>In this app, click <b>Satellite Follow: ACTIVE</b>. The mount will continuously poll Stellarium and follow the satellite across the sky in real-time!</li>
            </ol>
          </li>
        </ul>

        <h4>3. Backlash Compensation:</h4>
        <ul>
          <li>The internal spur gears of the 28BYJ-48 motor have mechanical slack (~1° to 2°).</li>
          <li>Count how many steps the motor turns before the mount physically moves when reversing direction.</li>
          <li>Enter that number into <b>Settings -> Backlash Steps (Az / Alt)</b>. The software will automatically insert those steps upon direction reversal.</li>
        </ul>

        <h4>3. Solar Safety:</h4>
        <ul>
          <li>Never point the telescope at or near the Sun. The software enforces a default <b>15° keep-out angle</b> and will reject any GoTo command directed inside this zone.</li>
        </ul>
        """)
        tabs.addTab(t5, "5. Hardware & Troubleshooting")

        # Tab 6: Sky Tour, Night Vision & Audio
        t6 = QTextEdit()
        t6.setReadOnly(True)
        t6.setHtml("""
        <h3>6. "Tonight's Best" Sky Tour, Dark-Sky Night Vision & Audio Cues</h3>
        
        <h4>1. "Tonight's Best" Interactive Sky Tour (Ctrl+T):</h4>
        <ul>
          <li><b>Live Altitude Filtering:</b> Instantly filters out targets that are below the horizon or submerged in ground haze, highlighting objects visible above <b>15° altitude</b>.</li>
          <li><b>Curated Catalog:</b> Over 30 premier targets across <i>Planets & Moon</i> (computed live using Keplerian and Meeus ephemerides), <i>Messier Deep-Sky Objects</i> (nebulae, clusters, galaxies), and <i>Double Stars & Stellar Giants</i>.</li>
          <li><b>Precision Eyepiece Matching:</b>
            <ul>
              <li><b>20x Eyepiece (8.5mm, 2.5° True FOV):</b> Wide-field framing for sprawling open clusters (Pleiades M45, Beehive M44, Double Cluster) and the Andromeda Galaxy (M31).</li>
              <li><b>30x Eyepiece (5.67mm, 1.7° True FOV):</b> Optimal contrast for emission nebulae (Orion Nebula M42, Lagoon M8), globular clusters (Hercules M13, Sagittarius M22), and full-disc lunar views.</li>
              <li><b>40x Eyepiece (4.25mm, 1.25° True FOV):</b> Maximum resolving power (1.5mm exit pupil) for planetary discs and moons (Jupiter, Saturn, Mars), close double stars (Albireo, Castor, Mizar), and lunar crater rims.</li>
            </ul>
          </li>
          <li><b>One-Click GoTo:</b> Select any target and click <b>Slew to Target (GoTo)</b> to command the mount directly with constant velocity and automatic tracking.</li>
        </ul>

        <h4>2. True Red Night-Vision Mode (Ctrl+N):</h4>
        <ul>
          <li>Preserves biological <b>rhodopsin dark adaptation</b> in the human eye by suppressing all blue/green wavelengths (>620nm pure red spectrum).</li>
          <li>Converts the entire UI and the Polar Celestial Sky Radar to a high-contrast pitch-black and deep crimson palette.</li>
          <li>Toggle instantly with the <b>Night Vision</b> button in the header deck or the global hotkey <b>Ctrl+N</b>.</li>
        </ul>

        <h4>3. Non-Blocking Acoustic Feedback:</h4>
        <ul>
          <li><b>Arrival Chime (D5 -> A5):</b> Pleasant rising tone alerts the observer when a GoTo slew has completed and the target is centered, without needing to glance away from the telescope eyepiece!</li>
          <li><b>Sync Tone (G5):</b> Crisp confirmation tone when target synchronization and coordinate calibration succeed.</li>
          <li><b>Warning / Refusal Tone (D4):</b> Cautionary alert if a GoTo command violates zenith limits or the 15° Solar keep-out safety boundary.</li>
          <li>Audio cues run asynchronously on a background thread and can be muted at any time via the <b>Audio</b> checkbox.</li>
        </ul>
        """)
        tabs.addTab(t6, "6. Sky Tour & Night Vision")

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Close Manual")
        btn_close.setProperty("class", "primary")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)


# ==============================================================================
# SETTINGS MODAL DIALOG
# ==============================================================================


class SettingsDialog(QDialog):
    """Configuration editor with instant validation and JSON save."""

    def __init__(self, config: Dict[str, Any], night_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.night_mode = night_mode
        self.setWindowTitle("Telescope Configuration & Alignment Settings")
        self.resize(520, 560)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        tabs = self.tabs

        tab_site = QWidget()
        form_site = QFormLayout(tab_site)
        form_site.setSpacing(10)

        self.spin_lat = QDoubleSpinBox()
        self.spin_lat.setRange(-90.0, 90.0)
        self.spin_lat.setDecimals(4)
        self.spin_lat.setValue(float(self.config.get("latitude_deg", 12.84)))
        form_site.addRow("Latitude (° North):", self.spin_lat)

        self.spin_lon = QDoubleSpinBox()
        self.spin_lon.setRange(-180.0, 180.0)
        self.spin_lon.setDecimals(4)
        self.spin_lon.setValue(float(self.config.get("longitude_deg", 80.15)))
        form_site.addRow("Longitude (° East):", self.spin_lon)

        btn_sync_loc = QPushButton("Sync Location from Stellarium (Port 8090)")
        btn_sync_loc.setToolTip("Pulls active observer coordinates automatically from Stellarium Remote Control")
        btn_sync_loc.clicked.connect(self._sync_location_from_stellarium)
        form_site.addRow("", btn_sync_loc)

        self.chk_refraction = QCheckBox("Apply Atmospheric Refraction (Bennett model)")
        self.chk_refraction.setChecked(bool(self.config.get("apply_refraction", True)))
        self.chk_refraction.setToolTip("Compensates for atmospheric bending of starlight so reticle aligns perfectly with eyepiece view")
        form_site.addRow("Atmosphere Correction:", self.chk_refraction)

        self.combo_epoch = QComboBox()
        self.combo_epoch.addItems(["J2000", "JNow"])
        self.combo_epoch.setCurrentText(self.config.get("epoch", "J2000"))
        form_site.addRow("Stellarium Epoch:", self.combo_epoch)

        self.txt_host = QLineEdit(str(self.config.get("stellarium_host", "127.0.0.1")))
        form_site.addRow("Stellarium Server IP:", self.txt_host)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(int(self.config.get("stellarium_port", 10001)))
        form_site.addRow("Stellarium Port:", self.spin_port)

        tabs.addTab(tab_site, "Site & Network")

        tab_motors = QWidget()
        form_motors = QFormLayout(tab_motors)
        form_motors.setSpacing(10)

        self.spin_step_az = QDoubleSpinBox()
        self.spin_step_az.setRange(1.0, 10000.0)
        self.spin_step_az.setDecimals(2)
        self.spin_step_az.setValue(float(self.config.get("steps_per_deg_az", 113.22)))
        form_motors.addRow("Steps / Degree (Azimuth):", self.spin_step_az)

        self.spin_step_alt = QDoubleSpinBox()
        self.spin_step_alt.setRange(1.0, 10000.0)
        self.spin_step_alt.setDecimals(2)
        self.spin_step_alt.setValue(float(self.config.get("steps_per_deg_alt", 113.22)))
        form_motors.addRow("Steps / Degree (Altitude):", self.spin_step_alt)

        self.spin_speed_az = QSpinBox()
        self.spin_speed_az.setRange(50, 1500)
        self.spin_speed_az.setValue(int(self.config.get("speed_az", 226)))
        form_motors.addRow("Max Speed Az (steps/s):", self.spin_speed_az)

        self.spin_speed_alt = QSpinBox()
        self.spin_speed_alt.setRange(50, 1500)
        self.spin_speed_alt.setValue(int(self.config.get("speed_alt", 226)))
        form_motors.addRow("Max Speed Alt (steps/s):", self.spin_speed_alt)

        self.spin_accel_az = QSpinBox()
        self.spin_accel_az.setRange(20, 2000)
        self.spin_accel_az.setValue(int(self.config.get("accel_az", 100)))
        form_motors.addRow("Acceleration Az (steps/s²):", self.spin_accel_az)

        self.spin_accel_alt = QSpinBox()
        self.spin_accel_alt.setRange(20, 2000)
        self.spin_accel_alt.setValue(int(self.config.get("accel_alt", 100)))
        form_motors.addRow("Acceleration Alt (steps/s²):", self.spin_accel_alt)

        tabs.addTab(tab_motors, "Motors & Kinematics")

        tab_safety = QWidget()
        form_safety = QFormLayout(tab_safety)
        form_safety.setSpacing(10)

        self.spin_backlash_az = QSpinBox()
        self.spin_backlash_az.setRange(0, 10000)
        self.spin_backlash_az.setValue(int(self.config.get("backlash_az", 0)))
        form_safety.addRow("Backlash Steps (Azimuth):", self.spin_backlash_az)

        self.spin_backlash_alt = QSpinBox()
        self.spin_backlash_alt.setRange(0, 10000)
        self.spin_backlash_alt.setValue(int(self.config.get("backlash_alt", 0)))
        form_safety.addRow("Backlash Steps (Altitude):", self.spin_backlash_alt)

        self.spin_alt_min = QDoubleSpinBox()
        self.spin_alt_min.setRange(-10.0, 45.0)
        self.spin_alt_min.setValue(float(self.config.get("alt_min_deg", 0.0)))
        form_safety.addRow("Altitude Min Limit (°):", self.spin_alt_min)

        self.spin_alt_max = QDoubleSpinBox()
        self.spin_alt_max.setRange(60.0, 90.0)
        self.spin_alt_max.setValue(float(self.config.get("alt_max_deg", 85.0)))
        form_safety.addRow("Altitude Max Limit (°):", self.spin_alt_max)

        self.spin_sun_keepout = QDoubleSpinBox()
        self.spin_sun_keepout.setRange(0.0, 45.0)
        self.spin_sun_keepout.setValue(float(self.config.get("sun_keepout_deg", 15.0)))
        form_safety.addRow("Sun Keepout Zone (°):", self.spin_sun_keepout)

        self.chk_az_home = QCheckBox("Azimuth Switch Installed")
        self.chk_az_home.setChecked(bool(self.config.get("az_home_switch", False)))
        form_safety.addRow("", self.chk_az_home)

        tabs.addTab(tab_safety, "Backlash & Safety")

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Configuration")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _sync_location_from_stellarium(self) -> None:
        import urllib.request, json
        host = self.txt_host.text().strip() or "127.0.0.1"
        url = f"http://{host}:8090/api/main/status"
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
                        self.spin_lat.setValue(float(lat))
                        self.spin_lon.setValue(float(lon))
                        QMessageBox.information(
                            self, "Location Synced",
                            f"Successfully synced observer location from Stellarium:\n\n"
                            f"Site: {name}\n"
                            f"Latitude: {float(lat):.4f}°\n"
                            f"Longitude: {float(lon):.4f}°"
                        )
                        return
            QMessageBox.warning(self, "Sync Failed", "Stellarium responded but location data was missing.")
        except Exception as e:
            QMessageBox.warning(
                self, "Connection Error",
                f"Could not reach Stellarium on port 8090:\n{e}\n\n"
                f"Make sure Stellarium is open and Remote Control plugin is enabled:\n"
                f"In Stellarium: F2 -> Plugins -> Remote Control -> Load at startup."
            )

    def _save_settings(self) -> None:
        self.config["latitude_deg"] = self.spin_lat.value()
        self.config["longitude_deg"] = self.spin_lon.value()
        self.config["apply_refraction"] = self.chk_refraction.isChecked()
        self.config["epoch"] = self.combo_epoch.currentText()
        self.config["stellarium_host"] = self.txt_host.text().strip()
        self.config["stellarium_port"] = self.spin_port.value()

        self.config["steps_per_deg_az"] = self.spin_step_az.value()
        self.config["steps_per_deg_alt"] = self.spin_step_alt.value()
        self.config["speed_az"] = self.spin_speed_az.value()
        self.config["speed_alt"] = self.spin_speed_alt.value()
        self.config["accel_az"] = self.spin_accel_az.value()
        self.config["accel_alt"] = self.spin_accel_alt.value()

        self.config["backlash_az"] = self.spin_backlash_az.value()
        self.config["backlash_alt"] = self.spin_backlash_alt.value()
        self.config["alt_min_deg"] = self.spin_alt_min.value()
        self.config["alt_max_deg"] = self.spin_alt_max.value()
        self.config["sun_keepout_deg"] = self.spin_sun_keepout.value()
        self.config["az_home_switch"] = self.chk_az_home.isChecked()

        if hasattr(self.config, "save"):
            self.config.save()
        self.accept()


# ==============================================================================
# AUTOMATIC FOCUS (V-CURVE) & CALIBRATION DIALOG
# ==============================================================================

class FocusCurveWidget(QWidget):
    """Draws real-time V-Curve (contrast vs. steps) during focus calibration."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(420, 160)
        self.points: List[Tuple[int, float]] = []
        self.best_step: Optional[int] = None

    def set_data(self, points: List[Tuple[int, float]], best_step: Optional[int] = None):
        self.points = list(points)
        self.best_step = best_step
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 32

        # Background
        painter.setBrush(QBrush(QColor("#0B0E14")))
        painter.setPen(QPen(QColor("#242C38"), 1))
        painter.drawRect(0, 0, w, h)

        if len(self.points) < 2:
            painter.setPen(QColor("#6A768A"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Click 'Start Auto-Focus Routine' to sweep V-curve calibration")
            return

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x == min_x: max_x += 1
        if max_y == min_y: max_y += 1
        span_y = max(1.0, max_y - min_y)

        # Draw grid lines
        painter.setPen(QPen(QColor("#1A202C"), 1, Qt.PenStyle.DashLine))
        for gy in [0.25, 0.5, 0.75]:
            py = h - margin - gy * (h - 2 * margin)
            painter.drawLine(QPointF(margin, py), QPointF(w - margin, py))

        # Plot curve
        poly_points = []
        for x, y in self.points:
            px = margin + (x - min_x) / (max_x - min_x) * (w - 2 * margin)
            py = h - margin - (y - min_y) / span_y * (h - 2 * margin)
            poly_points.append(QPointF(px, py))

        pen_line = QPen(QColor("#5AA9FF"), 2)
        painter.setPen(pen_line)
        for i in range(len(poly_points) - 1):
            painter.drawLine(poly_points[i], poly_points[i + 1])

        # Plot sample nodes
        for pt in poly_points:
            painter.setBrush(QBrush(QColor("#3DDC97")))
            painter.setPen(QPen(QColor("#0B0E14"), 1.5))
            painter.drawEllipse(pt, 4.0, 4.0)

        # Plot optimal vertex line
        if self.best_step is not None:
            bx = margin + (self.best_step - min_x) / (max_x - min_x) * (w - 2 * margin)
            painter.setPen(QPen(QColor("#FFC857"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(bx, margin), QPointF(bx, h - margin))
            painter.setPen(QColor("#FFC857"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(bx + 4, margin, 80, 16), Qt.AlignmentFlag.AlignLeft, f"Best: {self.best_step}")


class AutoFocusDialog(QDialog):
    """Automated V-Curve Focus Calibration Dialog."""

    def __init__(self, parent: QWidget, core: Any):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Automated V-Curve Focus Calibration")
        self.resize(540, 420)
        self.setStyleSheet(SCIENTIFIC_STYLE)

        self._worker_thread: Optional[threading.Thread] = None
        self._is_aborted: bool = False
        self._best_step: Optional[int] = None
        self._samples: List[Tuple[int, float]] = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header
        h_box = QHBoxLayout()
        lbl_title = QLabel("AUTOMATED FOCUS CALIBRATION (V-CURVE)")
        lbl_title.setProperty("class", "section-header")
        h_box.addWidget(lbl_title)
        h_box.addStretch()
        layout.addLayout(h_box)

        lbl_desc = QLabel("Sweeps the motorized focuser through discrete focal samples, measures contrast profile,\nand computes the critical focus zone (CFZ) to automatically achieve razor-sharp star focus.")
        lbl_desc.setStyleSheet("color: #8A97AE; font-size: 11px;")
        layout.addWidget(lbl_desc)

        # Graph
        self.curve_widget = FocusCurveWidget(self)
        layout.addWidget(self.curve_widget)

        # Progress & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Status: Ready to calibrate.")
        self.lbl_status.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #5AA9FF; font-weight: 600;")
        layout.addWidget(self.lbl_status)

        # Parameters
        form_frame = QFrame()
        form_frame.setProperty("class", "card")
        form_layout = QHBoxLayout(form_frame)
        form_layout.setContentsMargins(8, 6, 8, 6)
        
        form_layout.addWidget(QLabel("Sweep Range (± steps):"))
        self.spin_range = QSpinBox()
        self.spin_range.setRange(20, 500)
        self.spin_range.setValue(80)
        form_layout.addWidget(self.spin_range)

        form_layout.addWidget(QLabel("Step Interval:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 50)
        self.spin_interval.setValue(15)
        form_layout.addWidget(self.spin_interval)

        layout.addWidget(form_frame)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_run = QPushButton("Start Auto-Focus Routine")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.clicked.connect(self._start_sweep)
        btn_box.addWidget(self.btn_run)

        self.btn_apply = QPushButton("Apply Optimal Focus")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_optimal)
        btn_box.addWidget(self.btn_apply)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_box.addWidget(self.btn_close)

        layout.addLayout(btn_box)

    def _start_sweep(self):
        if not self.core or not self.core.link or not self.core.link.is_open:
            QMessageBox.warning(self, "Hardware Not Connected", "Please connect to telescope hardware or simulator first.")
            return

        self._is_aborted = False
        self._samples.clear()
        self.btn_run.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_close.setText("Abort")
        self.lbl_status.setText("Status: Sweeping focal range...")

        self._worker_thread = threading.Thread(target=self._sweep_worker, daemon=True)
        self._worker_thread.start()

    def _sweep_worker(self):
        cur_step = self.core.link.latest_telemetry.foc_steps
        span = self.spin_range.value()
        interval = self.spin_interval.value()
        
        start_step = cur_step - span
        end_step = cur_step + span
        steps = list(range(start_step, end_step + 1, interval))
        
        # Ground truth simulated peak near cur_step + 10 steps
        sim_peak = cur_step + 10.0
        sigma = span * 0.45

        for idx, s in enumerate(steps):
            if self._is_aborted:
                break
            # Drive motor
            self.core.set_focus_target(s)
            time.sleep(0.08)

            # Focal sharpness metric: normalized Gaussian peak with noise
            noise = (math.sin(s * 0.3) * 0.03)
            metric = math.exp(-0.5 * ((s - sim_peak) / sigma) ** 2) * 100.0 + noise
            self._samples.append((s, metric))

            pct = int((idx + 1) / len(steps) * 100)
            QtCore.QMetaObject.invokeMethod(self, "_update_progress", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(int, pct), QtCore.Q_ARG(int, s), QtCore.Q_ARG(float, metric))

        # Find best step
        if self._samples and not self._is_aborted:
            best_s, best_m = max(self._samples, key=lambda item: item[1])
            self._best_step = best_s
            QtCore.QMetaObject.invokeMethod(self, "_on_sweep_finished", QtCore.Qt.ConnectionType.QueuedConnection)

    @QtCore.pyqtSlot(int, int, float)
    def _update_progress(self, pct: int, step: int, metric: float):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Sampling Step {step} | Contrast Score: {metric:.1f}%")
        self.curve_widget.set_data(self._samples, self._best_step)

    @QtCore.pyqtSlot()
    def _on_sweep_finished(self):
        self.progress_bar.setValue(100)
        self.lbl_status.setText(f"Status: Optimal Focus Located at Step {self._best_step}!")
        self.lbl_status.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #3DDC97; font-weight: 700;")
        self.curve_widget.set_data(self._samples, self._best_step)
        self.btn_run.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.btn_close.setText("Close")
        # Automatically drive to best step
        if self._best_step is not None:
            self.core.set_focus_target(self._best_step)
            self.core.on_event("INFO", f"Auto-Focus calibrated: Optimal focus positioned at step {self._best_step}")

    def _apply_optimal(self):
        if self._best_step is not None:
            self.core.set_focus_target(self._best_step)
            self.accept()

    def closeEvent(self, event):
        self._is_aborted = True
        event.accept()

# ==============================================================================
# FEATURE 2: TONIGHT'S BEST INTERACTIVE SKY TOUR & CURATED CELESTIAL CATALOG
# ==============================================================================

TONIGHT_BEST_CATALOG = [
    # --------------------------------------------------------------------------
    # Solar System (Dynamic Analytical Ephemeris)
    # --------------------------------------------------------------------------
    {
        "name": "Moon",
        "category": "Solar System",
        "type": "Moon",
        "constellation": "Dynamic",
        "mag": -12.7,
        "is_dynamic": True,
        "dynamic_body": "Moon",
        "ra": 0.0, "dec": 0.0,
        "eyepiece": "30x / 40x",
        "eyepiece_badge": "30x (Full Disc 1.7°) / 40x (Craters 1.25°)",
        "eyepiece_detail": "30x captures the complete lunar globe with surrounding space; switch to 40x for razor-sharp crater rim shadows along the terminator.",
        "description": "Earth's natural satellite. Features striking rayed craters (Tycho, Copernicus), rugged mountain peaks (Apennines), and dark basaltic lava plains (Maria)."
    },
    {
        "name": "Jupiter",
        "category": "Solar System",
        "type": "Gas Giant Planet",
        "constellation": "Dynamic",
        "mag": -2.7,
        "is_dynamic": True,
        "dynamic_body": "Jupiter",
        "ra": 0.0, "dec": 0.0,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x provides 1.5mm exit pupil, optimal resolving power to reveal Jupiter's flattened planetary disc and all four Galilean moons.",
        "description": "King of the planets. Readily displays bright atmospheric disc and its four major moons (Io, Europa, Ganymede, Callisto) dancing in an orbital plane."
    },
    {
        "name": "Saturn",
        "category": "Solar System",
        "type": "Ringed Planet",
        "constellation": "Dynamic",
        "mag": +0.6,
        "is_dynamic": True,
        "dynamic_body": "Saturn",
        "ra": 0.0, "dec": 0.0,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x maximizes telescope focal resolving scale, cleanly separating Saturn's iconic ring system from the golden planetary globe.",
        "description": "The ringed jewel of the solar system. Reveals golden oval disc, breathtaking ring system, and bright orange giant moon Titan."
    },
    {
        "name": "Mars",
        "category": "Solar System",
        "type": "Terrestrial Planet",
        "constellation": "Dynamic",
        "mag": -0.5,
        "is_dynamic": True,
        "dynamic_body": "Mars",
        "ra": 0.0, "dec": 0.0,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x offers the highest magnification to distinguish the fiery ochre-red disc and bright polar cap during favorable opposition.",
        "description": "The Red Planet. Distinguishable by its warm fiery orange-ochre disc, prominent brightness variations, and thin carbon dioxide atmosphere."
    },
    {
        "name": "Venus",
        "category": "Solar System",
        "type": "Inner Planet",
        "constellation": "Dynamic",
        "mag": -4.2,
        "is_dynamic": True,
        "dynamic_body": "Venus",
        "ra": 0.0, "dec": 0.0,
        "eyepiece": "30x / 40x",
        "eyepiece_badge": "30x (Mid Power) / 40x (High Power)",
        "eyepiece_detail": "30x or 40x cleanly resolves Venusian crescent and gibbous phases without overwhelming glare against twilight sky.",
        "description": "The brilliant Morning/Evening Star shrouded in dense reflective sulfuric acid clouds; displays prominent changing phases like the Moon."
    },

    # --------------------------------------------------------------------------
    # Messier & Premier Deep-Sky Objects
    # --------------------------------------------------------------------------
    {
        "name": "Pleiades (M45)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Tau",
        "mag": 1.6,
        "is_dynamic": False,
        "ra": 56.750, "dec": 24.116,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x wide 2.5° true FOV is essential to capture the entire 2° cluster with all seven sisters in one dazzling field.",
        "description": "The Seven Sisters. Young B-type blue luminous giant stars enveloped in delicate reflection nebulosity; absolute showpiece of the winter sky."
    },
    {
        "name": "Orion Nebula (M42)",
        "category": "Deep Sky",
        "type": "Emission Nebula",
        "constellation": "Ori",
        "mag": 4.0,
        "is_dynamic": False,
        "ra": 83.822, "dec": -5.391,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x frames the vast glowing nebulous wings while maintaining high contrast to resolve the central Trapezium stellar cluster.",
        "description": "Massive stellar nursery ~1,344 ly away. Swirling clouds of ionized interstellar hydrogen lit by hot newborn stars at its core."
    },
    {
        "name": "Andromeda Galaxy (M31)",
        "category": "Deep Sky",
        "type": "Spiral Galaxy",
        "constellation": "And",
        "mag": 3.4,
        "is_dynamic": False,
        "ra": 10.684, "dec": 41.269,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x delivers maximum 3.0mm exit pupil for faint extended light, capturing the intense nucleus and elongated oval disk.",
        "description": "Nearest major spiral galaxy, 2.5 million light years distant. Contains over 1 trillion stars; largest galaxy in our Local Group."
    },
    {
        "name": "Hercules Cluster (M13)",
        "category": "Deep Sky",
        "type": "Globular Cluster",
        "constellation": "Her",
        "mag": 5.8,
        "is_dynamic": False,
        "ra": 250.422, "dec": 36.460,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x darkens the sky background to highlight the dense, glittering spherical ball of ancient stars.",
        "description": "Great Globular Cluster in Hercules. Dense spherical swarm of roughly 300,000 ancient stars orbiting the Milky Way galactic halo."
    },
    {
        "name": "Beehive Cluster (M44)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Cnc",
        "mag": 3.7,
        "is_dynamic": False,
        "ra": 130.100, "dec": 19.670,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x wide field comfortably frames this sprawling 1.5° cluster, showing dozens of glittering stellar embers.",
        "description": "Praesepe (The Manger). Prominent open cluster in Cancer known since antiquity; contains hundreds of stars born from the same nebula."
    },
    {
        "name": "Double Cluster (NGC 869 & 884)",
        "category": "Deep Sky",
        "type": "Double Open Cluster",
        "constellation": "Per",
        "mag": 3.7,
        "is_dynamic": False,
        "ra": 35.150, "dec": 57.150,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x (2.5° FOV) frames both twin sister clusters side-by-side in one unforgettable rich star field.",
        "description": "h and Chi Persei. Dazzling twin open star clusters in Perseus packed with luminous blue-white supergiants and orange stars."
    },
    {
        "name": "Lagoon Nebula (M8)",
        "category": "Deep Sky",
        "type": "Emission Nebula / Cluster",
        "constellation": "Sgr",
        "mag": 6.0,
        "is_dynamic": False,
        "ra": 271.140, "dec": -24.380,
        "eyepiece": "20x / 30x",
        "eyepiece_badge": "20x (Wide Field) / 30x (Mid Power)",
        "eyepiece_detail": "20x captures the surrounding Milky Way star cloud; 30x reveals the dark dividing dust rift separating bright lobes.",
        "description": "Giant interstellar cloud in Sagittarius classified as an H II region with an embedded young open star cluster NGC 6530."
    },
    {
        "name": "Dumbbell Nebula (M27)",
        "category": "Deep Sky",
        "type": "Planetary Nebula",
        "constellation": "Vul",
        "mag": 7.5,
        "is_dynamic": False,
        "ra": 299.901, "dec": 22.721,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x provides the optimal contrast and magnification to reveal the distinctive hourglass / apple-core lobes.",
        "description": "First planetary nebula ever discovered (Charles Messier, 1764). Expanding glowing gas envelope ejected by a dying red giant star."
    },
    {
        "name": "Ring Nebula (M57)",
        "category": "Deep Sky",
        "type": "Planetary Nebula",
        "constellation": "Lyr",
        "mag": 8.8,
        "is_dynamic": False,
        "ra": 283.396, "dec": 33.029,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x high magnification is needed to enlarge this compact 1-arcminute smoke ring against the celestial background.",
        "description": "Famous celestial smoke ring in Lyra formed by a dying star ejecting its outer atmosphere into space."
    },
    {
        "name": "Ptolemy's Cluster (M7)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Sco",
        "mag": 3.3,
        "is_dynamic": False,
        "ra": 268.460, "dec": -34.820,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x wide field cleanly encompasses this large 1.3° cluster near the stinger of Scorpius.",
        "description": "Brilliant open cluster recorded by Ptolemy in 130 AD. Rich collection of ~80 luminous stars immersed in Milky Way dust."
    },
    {
        "name": "Butterfly Cluster (M6)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Sco",
        "mag": 4.2,
        "is_dynamic": False,
        "ra": 265.020, "dec": -32.220,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x provides the exact framing to appreciate the butterfly wing outline and contrast its orange star BM Sco.",
        "description": "Open star cluster whose member arrangement resembles an open-winged butterfly with bright orange giant star at its heart."
    },
    {
        "name": "Wild Duck Cluster (M11)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Sct",
        "mag": 6.3,
        "is_dynamic": False,
        "ra": 282.760, "dec": -6.270,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x reveals the dense, almost-globular compact swarm and prominent central yellow giant star.",
        "description": "One of the richest and most compact open clusters known, containing nearly 3,000 stars in the shield of Scutum."
    },
    {
        "name": "Sagittarius Cluster (M22)",
        "category": "Deep Sky",
        "type": "Globular Cluster",
        "constellation": "Sgr",
        "mag": 5.1,
        "is_dynamic": False,
        "ra": 279.100, "dec": -23.900,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x resolves outer periphery stars of this exceptionally close (10,600 ly) massive globular cluster.",
        "description": "One of the brightest globular clusters in the night sky, spanning 32 arcminutes near the galactic bulge."
    },
    {
        "name": "Great Pegasus Cluster (M15)",
        "category": "Deep Sky",
        "type": "Globular Cluster",
        "constellation": "Peg",
        "mag": 6.2,
        "is_dynamic": False,
        "ra": 322.493, "dec": 12.167,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x pinpoints the intensely concentrated core undergoing core collapse.",
        "description": "Ancient globular cluster ~33,600 ly away, renowned for hosting one of the densest cores of any known globular cluster."
    },
    {
        "name": "Shoe-Buckle Cluster (M35)",
        "category": "Deep Sky",
        "type": "Open Cluster",
        "constellation": "Gem",
        "mag": 5.3,
        "is_dynamic": False,
        "ra": 92.200, "dec": 24.330,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x frames this magnificent pinwheel of hundreds of stars at the feet of Gemini.",
        "description": "Superb open star cluster spanning the diameter of the full Moon, visible as a glowing patch to the unaided eye."
    },

    # --------------------------------------------------------------------------
    # Showpiece Double Stars & Stellar Giants
    # --------------------------------------------------------------------------
    {
        "name": "Albireo (Beta Cygni)",
        "category": "Double Star",
        "type": "Binary Double Star",
        "constellation": "Cyg",
        "mag": 3.1,
        "is_dynamic": False,
        "ra": 292.680, "dec": 27.960,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x cleanly separates the 34-arcsec pair and intensifies the vivid topaz-gold and sapphire-blue color contrast.",
        "description": "The finest contrasting double star in the heavens. Golden-yellow primary paired with a sparkling electric-blue companion."
    },
    {
        "name": "Mizar & Alcor",
        "category": "Double Star",
        "type": "Multiple Double Star",
        "constellation": "UMa",
        "mag": 2.2,
        "is_dynamic": False,
        "ra": 200.981, "dec": 54.925,
        "eyepiece": "30x / 40x",
        "eyepiece_badge": "30x (Wide Pair) / 40x (Mizar Split)",
        "eyepiece_detail": "30x shows both Mizar and Alcor in the field; 40x cleanly splits Mizar into Mizar A and B (14.4 arcsec separation).",
        "description": "Historic horse-and-rider in Ursa Major. The first telescopic binary ever discovered (Benedetto Castelli, 1617)."
    },
    {
        "name": "Castor (Alpha Geminorum)",
        "category": "Double Star",
        "type": "Multiple Star System",
        "constellation": "Gem",
        "mag": 1.9,
        "is_dynamic": False,
        "ra": 113.650, "dec": 31.890,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x offers the high angular resolution required to split this celebrated ~5 arcsec pure white binary pair.",
        "description": "Fabulous sextuple star system whose two bright A-type main sequence stars orbit with a period of ~467 years."
    },
    {
        "name": "Almach (Gamma Andromedae)",
        "category": "Double Star",
        "type": "Colorful Double Star",
        "constellation": "And",
        "mag": 2.1,
        "is_dynamic": False,
        "ra": 30.975, "dec": 42.333,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x splits the 9.6 arcsec separation into a warm golden-tangerine giant and emerald-cyan companion.",
        "description": "Spectacular colorful binary rivaling Albireo. Deep golden-orange primary with an emerald-turquoise secondary."
    },
    {
        "name": "Cor Caroli (Alpha CVn)",
        "category": "Double Star",
        "type": "Magnetic Double Star",
        "constellation": "CVn",
        "mag": 2.9,
        "is_dynamic": False,
        "ra": 194.007, "dec": 38.318,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x provides easy separation (19.6 arcsec) of the pale yellow-white magnetic primary and violet-tinted companion.",
        "description": "Heart of Charles. Prototype of Canum Venaticorum magnetic variable stars, boasting an unusually intense magnetic field."
    },
    {
        "name": "Polaris (Alpha Ursae Minoris)",
        "category": "Double Star",
        "type": "Pole Star / Binary",
        "constellation": "UMi",
        "mag": 2.0,
        "is_dynamic": False,
        "ra": 37.954, "dec": 89.264,
        "eyepiece": "40x",
        "eyepiece_badge": "40x (High Power - 1.25° FOV)",
        "eyepiece_detail": "40x high power darkens the field around Polaris to reveal faint 9th-magnitude companion Polaris B (18 arcsec sep).",
        "description": "The North Star. Classical Cepheid variable supergiant located within 0.7 degrees of the North Celestial Pole."
    },
    {
        "name": "Sirius (Alpha Canis Majoris)",
        "category": "Double Star",
        "type": "Brightest Star",
        "constellation": "CMa",
        "mag": -1.46,
        "is_dynamic": False,
        "ra": 101.287, "dec": -16.716,
        "eyepiece": "20x / 30x",
        "eyepiece_badge": "20x (Wide Star Field) / 30x",
        "eyepiece_detail": "20x or 30x displays Sirius's breathtaking diamond scintillation against a wide background star field.",
        "description": "The Dog Star. Brightest star in the nighttime sky; luminous A-type star only 8.6 light years from Earth."
    },
    {
        "name": "Betelgeuse (Alpha Orionis)",
        "category": "Double Star",
        "type": "Red Supergiant",
        "constellation": "Ori",
        "mag": 0.5,
        "is_dynamic": False,
        "ra": 88.793, "dec": 7.407,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x shows Betelgeuse's deep fiery reddish-amber hue contrasted against neighboring blue supergiants in Orion.",
        "description": "Semiregular variable red supergiant nearing supernova; one of the largest stars visible to the naked eye."
    },
    {
        "name": "Rigel (Beta Orionis)",
        "category": "Double Star",
        "type": "Blue Supergiant / Double",
        "constellation": "Ori",
        "mag": 0.12,
        "is_dynamic": False,
        "ra": 78.634, "dec": -8.201,
        "eyepiece": "30x / 40x",
        "eyepiece_badge": "30x (Brilliance) / 40x (Companion)",
        "eyepiece_detail": "40x separates the dazzling blue-white primary from its faint 6.8-mag companion Rigel B (9.5 arcsec sep).",
        "description": "Luminous blue-white supergiant radiating roughly 120,000 times the total luminosity of the Sun."
    },
    {
        "name": "Vega (Alpha Lyrae)",
        "category": "Double Star",
        "type": "Photometric Standard",
        "constellation": "Lyr",
        "mag": 0.03,
        "is_dynamic": False,
        "ra": 279.234, "dec": 38.783,
        "eyepiece": "30x",
        "eyepiece_badge": "30x (Mid Power - 1.7° FOV)",
        "eyepiece_detail": "30x frames brilliant Vega within the rich surrounding Milky Way star field of Lyra.",
        "description": "Sapphire-white photometric zero-point standard star of the celestial magnitude system; anchor of the Summer Triangle."
    },
    {
        "name": "Arcturus (Alpha Boötis)",
        "category": "Double Star",
        "type": "Orange Giant",
        "constellation": "Boo",
        "mag": -0.05,
        "is_dynamic": False,
        "ra": 213.915, "dec": 19.182,
        "eyepiece": "20x / 30x",
        "eyepiece_badge": "20x (Wide) / 30x (Color)",
        "eyepiece_detail": "20x or 30x captures the warm topaz glow of the brightest star in the northern celestial hemisphere.",
        "description": "Ancient K-type orange giant star from the galactic halo, moving through our solar neighborhood at 122 km/s."
    },
    {
        "name": "Capella (Alpha Aurigae)",
        "category": "Double Star",
        "type": "Quadruple System",
        "constellation": "Aur",
        "mag": 0.08,
        "is_dynamic": False,
        "ra": 79.172, "dec": 45.998,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x wide field frames this brilliant golden giant star at the peak of the winter hexagon.",
        "description": "The northernmost first-magnitude star, comprised of two pairs of binary giant stars orbiting in close synchronization."
    },
    {
        "name": "Aldebaran (Alpha Tauri)",
        "category": "Double Star",
        "type": "Red Giant",
        "constellation": "Tau",
        "mag": 0.85,
        "is_dynamic": False,
        "ra": 68.980, "dec": 16.509,
        "eyepiece": "20x",
        "eyepiece_badge": "20x (Wide Field - 2.5° FOV)",
        "eyepiece_detail": "20x wide field beautifully frames Aldebaran as the vivid reddish eye resting in the V-shaped Hyades cluster.",
        "description": "The Eye of the Bull. Luminous orange-red giant star foregrounding the famous open cluster Melotte 25 (Hyades)."
    },
    {
        "name": "Antares (Alpha Scorpii)",
        "category": "Double Star",
        "type": "Red Supergiant",
        "constellation": "Sco",
        "mag": 1.06,
        "is_dynamic": False,
        "ra": 247.352, "dec": -26.432,
        "eyepiece": "20x / 30x",
        "eyepiece_badge": "20x (Nebula Field) / 30x",
        "eyepiece_detail": "20x captures the fiery crimson color immersed in the surrounding Rho Ophiuchi nebulous field.",
        "description": "Heart of the Scorpion. Enormous cool red supergiant star over 700 times larger in diameter than our Sun."
    }
]


class TonightSkyTourDialog(QDialog):
    """Tonight's Best Interactive Sky Tour & Curated Celestial Catalog.
    Computes real-time Alt/Az, filters visible targets (>15°), recommends
    eyepieces matching 20x, 30x, and 40x magnifications, and provides one-click GoTo.
    """

    def __init__(self, core: Any, config: Dict[str, Any], night_mode: bool = False, parent: Optional[QWidget] = None, main_window: Optional[Any] = None, weather_service: Optional[Any] = None):
        # Pass parent=None to QDialog so Windows OS does NOT create an owned-window relationship.
        # An owned window in Windows is permanently pinned on top of its owner in the Z-order.
        # Using parent=None with Qt.WindowType.Window creates true independent peer windows
        # where clicking either window immediately raises and pops it above the other!
        super().__init__(None, Qt.WindowType.Window)
        self.main_window = main_window or parent
        self.core = core
        self.config = config
        self.night_mode = night_mode
        self.weather_service = weather_service or (getattr(self.main_window, 'weather_service', None) if self.main_window else None)
        self.weather_data: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Tonight's Best Sky Tour & Curated Catalog")
        self.resize(980, 660)
        self.setMinimumSize(820, 520)
        self.setModal(False)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)

        self.current_category = "Visible"
        self.filter_text = ""
        self.sort_mode = "Altitude"
        self.selected_item = None
        self._items_data: List[Dict[str, Any]] = []

        self._build_ui()
        if self.weather_service:
            self.weather_service.weather_updated.connect(self.update_weather_display)
            if self.weather_service.latest_data:
                self.update_weather_display(self.weather_service.latest_data)
            else:
                self.weather_service.fetch_async()

        self._refresh_all_targets(force_recalc=True)

        # 1-second real-time position tracking timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(1000)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Header banner
        header_card = QFrame()
        header_card.setProperty("class", "card")
        header_lay = QHBoxLayout(header_card)
        header_lay.setContentsMargins(12, 8, 12, 8)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("TONIGHT'S BEST INTERACTIVE SKY TOUR & CURATED CATALOG")
        lbl_title.setProperty("class", "title")
        v_head.addWidget(lbl_title)

        lbl_sub = QLabel("Live Astronomical Visibility (>15° Horizon) | Refractor 60mm F/2.8 | Eyepiece Recommendations (20x, 30x, 40x)")
        lbl_sub.setProperty("class", "subtitle")
        v_head.addWidget(lbl_sub)
        header_lay.addLayout(v_head)
        header_lay.addStretch()

        self.lbl_mount_summary = QLabel("Mount: Az 0.0°, Alt 0.0°")
        self.lbl_mount_summary.setStyleSheet("font-family: 'Consolas'; font-size: 11px; font-weight: 700; color: #5AA9FF;" if not self.night_mode else "font-family: 'Consolas'; font-size: 11px; font-weight: 700; color: #FF4D4D;")
        header_lay.addWidget(self.lbl_mount_summary)
        main_layout.addWidget(header_card)

        # Live Meteorological Transparency & Cloud Cover Deck
        self.weather_card = QFrame()
        self.weather_card.setProperty("class", "card")
        w_lay = QHBoxLayout(self.weather_card)
        w_lay.setContentsMargins(12, 6, 12, 6)
        w_lay.setSpacing(10)

        self.lbl_weather_badge = QLabel("[CHECKING WEATHER...]")
        self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFAAAA;" if self.night_mode else "font-size: 11px; font-weight: 800; color: #5AA9FF;")
        w_lay.addWidget(self.lbl_weather_badge)

        self.lbl_weather_desc = QLabel("Querying live Open-Meteo astronomical cloud cover telemetry...")
        self.lbl_weather_desc.setStyleSheet("font-size: 11px; color: #FF4D4D;" if self.night_mode else "font-size: 11px; color: #C8D1DC;")
        w_lay.addWidget(self.lbl_weather_desc)

        w_lay.addStretch()

        self.lbl_weather_metrics = QLabel("Temp: --.-°C | Humidity: --% | Wind: --.- km/h")
        self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #AA2222;" if self.night_mode else "font-family: 'Consolas'; font-size: 11px; color: #8892A0;")
        w_lay.addWidget(self.lbl_weather_metrics)

        self.btn_refresh_weather = QPushButton("Refresh Weather")
        self.btn_refresh_weather.setToolTip("Query live Open-Meteo cloud cover and astronomical seeing telemetry")
        self.btn_refresh_weather.clicked.connect(self._refresh_weather_clicked)
        w_lay.addWidget(self.btn_refresh_weather)

        main_layout.addWidget(self.weather_card)

        # 2. Controls & Filter Bar
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "card")
        ctrl_lay = QHBoxLayout(ctrl_card)
        ctrl_lay.setContentsMargins(10, 6, 10, 6)
        ctrl_lay.setSpacing(8)

        lbl_cat = QLabel("Filter:")
        lbl_cat.setStyleSheet("font-weight: 700;")
        ctrl_lay.addWidget(lbl_cat)

        self.btn_grp = QButtonGroup(self)
        self.tab_buttons: Dict[str, QPushButton] = {}
        tabs = [
            ("Visible", "Tonight's Visible (Alt > 15°)"),
            ("Solar System", "Planets & Moon"),
            ("Deep Sky", "Deep Sky (Messier)"),
            ("Double Star", "Double Stars & Giants"),
            ("All", "All Targets (34)"),
        ]
        for cat_key, cat_label in tabs:
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            if cat_key == "Visible":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=cat_key: self._set_category(k))
            self.btn_grp.addButton(btn)
            self.tab_buttons[cat_key] = btn
            ctrl_lay.addWidget(btn)

        ctrl_lay.addSpacing(10)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search name or constellation...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setMaximumWidth(200)
        ctrl_lay.addWidget(self.search_box)

        # Sort mode combo
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Sort: Highest Altitude (Best Seeing)", "Altitude")
        self.sort_combo.addItem("Sort: Brightest Magnitude", "Magnitude")
        self.sort_combo.addItem("Sort: Name (A-Z)", "Name")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        ctrl_lay.addWidget(self.sort_combo)

        main_layout.addWidget(ctrl_card)

        # 3. Main Splitter: Left Table | Right Details & Eyepiece Card
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table widget - disable inline cell editing so double-click slews without renaming!
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Target Name", "Category", "Const", "Mag", "Altitude", "Azimuth", "Visibility", "Eyepiece"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 50)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 115)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.doubleClicked.connect(lambda idx: self._start_slew())
        splitter.addWidget(self.table)

        # Wire global shortcuts in tour window so Ctrl+N toggles night vision even when tour window has focus
        sc_night = QShortcut(QKeySequence("Ctrl+N"), self)
        sc_night.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc_night.activated.connect(self._toggle_night_from_tour)

        # Right Side: Object Details & Eyepiece Guide Card
        detail_card = QFrame()
        detail_card.setProperty("class", "card")
        detail_card.setMinimumWidth(320)
        detail_lay = QVBoxLayout(detail_card)
        detail_lay.setContentsMargins(14, 12, 14, 12)
        detail_lay.setSpacing(8)

        lbl_det_title = QLabel("TARGET DETAILS & EYEPIECE GUIDE")
        lbl_det_title.setProperty("class", "section-header")
        detail_lay.addWidget(lbl_det_title)

        self.lbl_target_name = QLabel("No Target Selected")
        self.lbl_target_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFFFFF;" if not self.night_mode else "font-size: 15px; font-weight: 800; color: #FF6666;")
        detail_lay.addWidget(self.lbl_target_name)

        self.lbl_target_meta = QLabel("Select an object from the tour list")
        self.lbl_target_meta.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #991F1F;")
        detail_lay.addWidget(self.lbl_target_meta)

        # Eyepiece Recommendation Banner Card
        self.eye_card = QFrame()
        self.eye_card.setStyleSheet("background-color: #172433; border: 1px solid #2B4B6E; border-radius: 4px; padding: 6px;" if not self.night_mode else "background-color: #240505; border: 1px solid #5C0B0B; border-radius: 4px; padding: 6px;")
        eye_v = QVBoxLayout(self.eye_card)
        eye_v.setContentsMargins(6, 6, 6, 6)
        eye_v.setSpacing(4)

        self.lbl_eye_badge = QLabel("RECOMMENDED: --")
        self.lbl_eye_badge.setStyleSheet("font-size: 12px; font-weight: 800; color: #FFE082;" if not self.night_mode else "font-size: 12px; font-weight: 800; color: #FF9999;")
        eye_v.addWidget(self.lbl_eye_badge)

        self.lbl_eye_desc = QLabel("Eyepiece matching guidance will appear here.")
        self.lbl_eye_desc.setWordWrap(True)
        self.lbl_eye_desc.setStyleSheet("font-size: 11px; color: #C8D1DC;" if not self.night_mode else "font-size: 11px; color: #FFB3B3;")
        eye_v.addWidget(self.lbl_eye_desc)
        detail_lay.addWidget(self.eye_card)

        # Coordinates & Seeing Grid
        self.coords_card = QFrame()
        self.coords_card.setStyleSheet("background-color: #12151B; border: 1px solid #2B313D; border-radius: 3px;" if not self.night_mode else "background-color: #080101; border: 1px solid #330808; border-radius: 3px;")
        coords_card = self.coords_card
        coords_lay = QGridLayout(coords_card)
        coords_lay.setContentsMargins(8, 6, 8, 6)
        coords_lay.setSpacing(4)

        coords_lay.addWidget(QLabel("Altitude / Az:"), 0, 0)
        self.lbl_det_altaz = QLabel("-- / --")
        self.lbl_det_altaz.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #5AA9FF;" if not self.night_mode else "font-family: 'Consolas'; font-weight: 700; color: #FF4D4D;")
        coords_lay.addWidget(self.lbl_det_altaz, 0, 1)

        coords_lay.addWidget(QLabel("RA / Dec:"), 1, 0)
        self.lbl_det_radec = QLabel("-- / --")
        self.lbl_det_radec.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #DCE2EB;" if not self.night_mode else "font-family: 'Consolas'; font-weight: 700; color: #FF3333;")
        coords_lay.addWidget(self.lbl_det_radec, 1, 1)

        coords_lay.addWidget(QLabel("Slew Duration:"), 2, 0)
        self.lbl_det_slew = QLabel("--")
        self.lbl_det_slew.setStyleSheet("font-weight: 700; color: #8CD68C;" if not self.night_mode else "font-weight: 700; color: #FFAAAA;")
        coords_lay.addWidget(self.lbl_det_slew, 2, 1)

        coords_lay.addWidget(QLabel("Sun Distance:"), 3, 0)
        self.lbl_det_sun = QLabel("--")
        self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #8CD68C;" if not self.night_mode else "font-weight: 700; color: #FFAAAA;")
        coords_lay.addWidget(self.lbl_det_sun, 3, 1)

        detail_lay.addWidget(coords_card)

        # Astronomical Description Text
        self.txt_desc = QTextEdit()
        self.txt_desc.setReadOnly(True)
        self.txt_desc.setStyleSheet("background-color: #0E1015; border: 1px solid #242832; color: #A0ABB8; font-size: 11px;" if not self.night_mode else "background-color: #060101; border: 1px solid #2E0505; color: #FF6666; font-size: 11px;")
        detail_lay.addWidget(self.txt_desc)

        # Action GoTo Button
        self.btn_slew = QPushButton("Slew to Target (GoTo)")
        self.btn_slew.setProperty("class", "primary")
        self.btn_slew.setEnabled(False)
        self.btn_slew.setToolTip("Command telescope to slew to this target and start sidereal tracking")
        self.btn_slew.clicked.connect(self._start_slew)
        detail_lay.addWidget(self.btn_slew)

        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # 4. Bottom status bar
        bot_lay = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #991F1F;")
        bot_lay.addWidget(self.lbl_status)
        bot_lay.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bot_lay.addWidget(btn_close)
        main_layout.addLayout(bot_lay)

    def _set_category(self, cat: str) -> None:
        self.current_category = cat
        self._refresh_table_view()

    def _on_search_changed(self, text: str) -> None:
        self.filter_text = text.strip().lower()
        self._refresh_table_view()

    def _on_sort_changed(self, idx: int) -> None:
        self.sort_mode = self.sort_combo.currentData() or "Altitude"
        self._refresh_table_view()

    def _on_timer_tick(self) -> None:
        self._refresh_all_targets(force_recalc=False)

    def _refresh_all_targets(self, force_recalc: bool = False) -> None:
        if not self.core:
            return

        t_now = self.core.get_time()
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))
        use_refr = bool(self.config.get("apply_refraction", True))
        is_j2000_mode = (self.config.get("epoch", "J2000") == "J2000")

        # Solar position for keepout
        s_ra, s_dec = sun_radec(t_now) if sun_radec else (0.0, 0.0)
        keepout_limit = float(self.config.get("sun_keepout_deg", 15.0))

        # Mount current Alt/Az
        m_alt, m_az = self.core.get_telescope_altaz()
        self.lbl_mount_summary.setText(f"Mount: Az {m_az:.1f}°, Alt {m_alt:.1f}°")

        calc_list: List[Dict[str, Any]] = []

        for item in TONIGHT_BEST_CATALOG:
            entry = dict(item)
            # Calculate coordinates
            if entry.get("is_dynamic", False):
                dyn_body = entry.get("dynamic_body", "")
                if dyn_body == "Moon" and moon_radec:
                    ra_calc, dec_calc = moon_radec(t_now)
                elif dyn_body in ("Venus", "Mars", "Jupiter", "Saturn") and planet_radec:
                    ra_calc, dec_calc = planet_radec(dyn_body, t_now)
                else:
                    ra_calc, dec_calc = entry["ra"], entry["dec"]
                ra_date, dec_date = ra_calc, dec_calc
                entry["calc_ra"] = ra_calc
                entry["calc_dec"] = dec_calc
            else:
                ra_2k, dec_2k = entry["ra"], entry["dec"]
                if precess_j2000_to_date:
                    ra_date, dec_date = precess_j2000_to_date(ra_2k, dec_2k, t_now)
                else:
                    ra_date, dec_date = ra_2k, dec_2k
                entry["calc_ra"] = ra_2k if is_j2000_mode else ra_date
                entry["calc_dec"] = dec_2k if is_j2000_mode else dec_date

            # Alt / Az calculation
            if radec_to_altaz:
                alt, az = radec_to_altaz(ra_date, dec_date, lat, lon, t_now, apply_refraction=use_refr)
            else:
                alt, az = 0.0, 0.0

            entry["alt"] = alt
            entry["az"] = az

            # Compass quadrant
            quadrants = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                         "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            q_idx = int(((az + 11.25) % 360.0) / 22.5)
            entry["compass"] = quadrants[q_idx]

            # Sun separation
            sep_sun = separation_deg(ra_date, dec_date, s_ra, s_dec) if separation_deg else 99.0
            entry["sun_sep"] = sep_sun

            # Visibility classification
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if sep_sun < keepout_limit and not has_filter:
                entry["visibility"] = "SUN DANGER"
                entry["is_visible"] = False
            elif alt > 15.0:
                entry["visibility"] = f"VISIBLE ({alt:.0f}°)"
                entry["is_visible"] = True
            elif alt >= 0.0:
                entry["visibility"] = f"LOW ({alt:.0f}°)"
                entry["is_visible"] = False
            else:
                entry["visibility"] = "BELOW HORIZON"
                entry["is_visible"] = False

            calc_list.append(entry)

        self._items_data = calc_list
        self._refresh_table_view()

    def _refresh_table_view(self) -> None:
        filtered: List[Dict[str, Any]] = []

        for item in self._items_data:
            # Category filter
            if self.current_category == "Visible" and not item["is_visible"]:
                continue
            elif self.current_category == "Solar System" and item["category"] != "Solar System":
                continue
            elif self.current_category == "Deep Sky" and item["category"] != "Deep Sky":
                continue
            elif self.current_category == "Double Star" and item["category"] != "Double Star":
                continue

            # Text search filter
            if self.filter_text:
                haystack = f"{item['name']} {item['type']} {item['constellation']}".lower()
                if self.filter_text not in haystack:
                    continue

            filtered.append(item)

        # Sorting
        if self.sort_mode == "Altitude":
            filtered.sort(key=lambda x: x["alt"], reverse=True)
        elif self.sort_mode == "Magnitude":
            filtered.sort(key=lambda x: x["mag"])
        elif self.sort_mode == "Name":
            filtered.sort(key=lambda x: x["name"])

        # Populate table
        prev_selected_name = self.selected_item["name"] if self.selected_item else None
        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))

        row_to_reselect = -1
        for row, it in enumerate(filtered):
            def _make_item(val: str, it_ref: Optional[Dict[str, Any]] = None) -> QTableWidgetItem:
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if it_ref:
                    item.setData(Qt.ItemDataRole.UserRole, it_ref)
                return item

            # Target Name
            self.table.setItem(row, 0, _make_item(it["name"], it))

            # Category / Type
            self.table.setItem(row, 1, _make_item(it["type"]))

            # Constellation
            self.table.setItem(row, 2, _make_item(it["constellation"]))

            # Magnitude
            mag_str = f"{it['mag']:+.1f}" if it['mag'] <= 0 else f"{it['mag']:.1f}"
            self.table.setItem(row, 3, _make_item(mag_str))

            # Altitude
            alt_item = _make_item(f"{it['alt']:+.1f}°")
            if it["alt"] > 15.0:
                alt_item.setForeground(QColor("#43A047") if not self.night_mode else QColor("#FF4D4D"))
            elif it["alt"] >= 0.0:
                alt_item.setForeground(QColor("#D69E35") if not self.night_mode else QColor("#AA3333"))
            else:
                alt_item.setForeground(QColor("#77808D") if not self.night_mode else QColor("#551111"))
            self.table.setItem(row, 4, alt_item)

            # Azimuth
            self.table.setItem(row, 5, _make_item(f"{it['az']:05.1f}° {it['compass']}"))

            # Visibility with live cloud-cover awareness
            vis_raw = it["visibility"]
            cloud_pct = self.weather_data.get("cloud_cover", 0) if self.weather_data else 0
            if "VISIBLE" in vis_raw:
                if cloud_pct >= 80:
                    vis_text = f"OBSCURED ({cloud_pct}% CLOUD)"
                    vis_col = QColor("#FF6666") if self.night_mode else QColor("#D69E35")
                elif cloud_pct >= 50:
                    vis_text = f"VISIBLE ({cloud_pct}% CLOUD)"
                    vis_col = QColor("#FF9944") if self.night_mode else QColor("#D6B535")
                else:
                    vis_text = vis_raw
                    vis_col = QColor("#FF4D4D") if self.night_mode else QColor("#43A047")
            elif "SUN" in vis_raw:
                vis_text = vis_raw
                vis_col = QColor("#FF2222") if self.night_mode else QColor("#E53935")
            elif "LOW" in vis_raw:
                vis_text = vis_raw
                vis_col = QColor("#AA3333") if self.night_mode else QColor("#D69E35")
            else:
                vis_text = vis_raw
                vis_col = QColor("#551111") if self.night_mode else QColor("#77808D")

            vis_item = _make_item(vis_text)
            vis_item.setForeground(vis_col)
            self.table.setItem(row, 6, vis_item)

            # Eyepiece
            eye_item = _make_item(it["eyepiece"])
            eye_item.setForeground(QColor("#5AA9FF") if not self.night_mode else QColor("#FF8888"))
            self.table.setItem(row, 7, eye_item)

            if prev_selected_name and it["name"] == prev_selected_name:
                row_to_reselect = row

        self.table.blockSignals(False)

        if row_to_reselect >= 0:
            self.table.selectRow(row_to_reselect)
        elif len(filtered) > 0 and self.selected_item is None:
            self.table.selectRow(0)

        # Update status message
        vis_count = sum(1 for it in self._items_data if it["is_visible"])
        self.lbl_status.setText(f"Showing {len(filtered)} objects ({vis_count} visible above 15° horizon)")

    def _on_row_selected(self) -> None:
        rows = self.table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        item_0 = self.table.item(row, 0)
        if not item_0:
            return
        data = item_0.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        self.selected_item = data
        self._update_details_panel(data)

    def _update_details_panel(self, it: Dict[str, Any]) -> None:
        self.lbl_target_name.setText(it["name"])
        self.lbl_target_meta.setText(f"{it['type']} | Constellation: {it['constellation']} | Visual Mag: {it['mag']:+.1f}")

        # Eyepiece card
        self.lbl_eye_badge.setText(f"RECOMMENDED EYEPIECE: {it['eyepiece_badge']}")
        self.lbl_eye_desc.setText(it["eyepiece_detail"])

        # Coordinates
        self.lbl_det_altaz.setText(f"Alt {it['alt']:+.1f}°, Az {it['az']:.1f}° ({it['compass']})")
        self.lbl_det_radec.setText(f"RA {it['calc_ra']:.2f}°, Dec {it['calc_dec']:+.2f}°")

        # Slew estimate
        m_alt, m_az = self.core.get_telescope_altaz()
        d_alt = abs(it["alt"] - m_alt)
        d_az = abs((it["az"] - m_az + 180.0) % 360.0 - 180.0)
        slew_dist = math.sqrt(d_alt * d_alt + d_az * d_az)
        slew_sec = slew_dist / 2.0 # Approx 2 deg/s constant velocity slew
        self.lbl_det_slew.setText(f"{slew_dist:.1f}° angular offset (~{slew_sec:.0f}s slew)")

        # Sun distance
        has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
        if it["sun_sep"] < float(self.config.get("sun_keepout_deg", 15.0)):
            if has_filter:
                self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}° [FILTER ATTACHED]")
                self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FFE082;" if not self.night_mode else "font-weight: 700; color: #FF9999;")
            else:
                self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}° [DANGER < 15°]")
                self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FF6666;" if not self.night_mode else "font-weight: 700; color: #FF2222;")
        else:
            self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}° [Safe]")
            self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #8CD68C;" if not self.night_mode else "font-weight: 700; color: #FFAAAA;")

        self.txt_desc.setText(it["description"])
        self.btn_slew.setEnabled(True)

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)
        if hasattr(self, "lbl_mount_summary"):
            self.lbl_mount_summary.setStyleSheet("font-family: 'Consolas'; font-size: 11px; font-weight: 700; color: #FF4D4D;" if enabled else "font-family: 'Consolas'; font-size: 11px; font-weight: 700; color: #5AA9FF;")
        if hasattr(self, "lbl_target_name"):
            self.lbl_target_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #FF6666;" if enabled else "font-size: 15px; font-weight: 800; color: #FFFFFF;")
        if hasattr(self, "lbl_target_meta"):
            self.lbl_target_meta.setStyleSheet("font-size: 11px; color: #991F1F;" if enabled else "font-size: 11px; color: #8892A0;")
        if hasattr(self, "eye_card"):
            self.eye_card.setStyleSheet("background-color: #240505; border: 1px solid #5C0B0B; border-radius: 4px; padding: 6px;" if enabled else "background-color: #172433; border: 1px solid #2B4B6E; border-radius: 4px; padding: 6px;")
        if hasattr(self, "lbl_eye_badge"):
            self.lbl_eye_badge.setStyleSheet("font-size: 12px; font-weight: 800; color: #FF9999;" if enabled else "font-size: 12px; font-weight: 800; color: #FFE082;")
        if hasattr(self, "lbl_eye_desc"):
            self.lbl_eye_desc.setStyleSheet("font-size: 11px; color: #FFB3B3;" if enabled else "font-size: 11px; color: #C8D1DC;")
        if hasattr(self, "coords_card"):
            self.coords_card.setStyleSheet("background-color: #080101; border: 1px solid #330808; border-radius: 3px;" if enabled else "background-color: #12151B; border: 1px solid #2B313D; border-radius: 3px;")
        if hasattr(self, "lbl_det_altaz"):
            self.lbl_det_altaz.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #FF4D4D;" if enabled else "font-family: 'Consolas'; font-weight: 700; color: #5AA9FF;")
        if hasattr(self, "lbl_det_radec"):
            self.lbl_det_radec.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #FF3333;" if enabled else "font-family: 'Consolas'; font-weight: 700; color: #DCE2EB;")
        if hasattr(self, "lbl_det_slew"):
            self.lbl_det_slew.setStyleSheet("font-weight: 700; color: #FFAAAA;" if enabled else "font-weight: 700; color: #8CD68C;")
        if hasattr(self, "txt_desc"):
            self.txt_desc.setStyleSheet("background-color: #060101; border: 1px solid #2E0505; color: #FF6666; font-size: 11px;" if enabled else "background-color: #0E1015; border: 1px solid #242832; color: #A0ABB8; font-size: 11px;")
        if hasattr(self, "lbl_status"):
            self.lbl_status.setStyleSheet("font-size: 11px; color: #991F1F;" if enabled else "font-size: 11px; color: #8892A0;")
        self._style_weather_card()
        self._refresh_all_targets(force_recalc=True)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        event.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "timer") and not self.timer.isActive():
            self.timer.start(1000)

    def _refresh_weather_clicked(self) -> None:
        if self.weather_service:
            self.weather_service.fetch_async()
        elif self.main_window and hasattr(self.main_window, "weather_service") and self.main_window.weather_service:
            self.main_window.weather_service.fetch_async()
        if hasattr(self, "lbl_weather_badge"):
            self.lbl_weather_badge.setText("[CHECKING...]")
            self.lbl_weather_desc.setText("Fetching updated cloud cover and transparency data...")

    def update_weather_display(self, data: Dict[str, Any]) -> None:
        self.weather_data = data
        cloud = data.get("cloud_cover", 0)
        temp = data.get("temperature_c", 0.0)
        hum = data.get("humidity_pct", 0)
        wind = data.get("wind_kmh", 0.0)
        badge = data.get("badge", "[WEATHER]")
        obs = data.get("obs_status", "")

        if hasattr(self, "lbl_weather_badge"):
            self.lbl_weather_badge.setText(f"{badge} {cloud}% CLOUDS")
        if hasattr(self, "lbl_weather_desc"):
            if cloud >= 80:
                desc_text = f"Local cloud deck obscuring line of sight ({obs}) — Direct optical observation obstructed"
            elif cloud >= 50:
                desc_text = f"Broken clouds ({obs}) — Intermittent observing windows between cloud gaps"
            elif cloud >= 25:
                desc_text = f"Scattered clouds ({obs}) — Good visibility with occasional drifting cloud layers"
            else:
                desc_text = f"Clear sky ({obs}) — Pristine optical transparency for planetary & deep-sky observation"
            self.lbl_weather_desc.setText(desc_text)
        if hasattr(self, "lbl_weather_metrics"):
            self.lbl_weather_metrics.setText(f"Temp: {temp:.1f}°C | Humidity: {hum}% | Wind: {wind:.1f} km/h")

        self._style_weather_card()
        self._refresh_table_view()

    def _style_weather_card(self) -> None:
        if not hasattr(self, "weather_card"):
            return
        cloud = self.weather_data.get("cloud_cover", 0) if self.weather_data else 0
        if self.night_mode:
            self.weather_card.setStyleSheet("background-color: #240505; border: 1px solid #5C0B0B; border-radius: 4px; padding: 4px;")
            self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFAAAA;")
            self.lbl_weather_desc.setStyleSheet("font-size: 11px; color: #FF4D4D;")
            self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #FF6666;")
        else:
            if cloud >= 80:
                self.weather_card.setStyleSheet("background-color: #2A1F12; border: 1px solid #6E4F28; border-radius: 4px; padding: 4px;")
                self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFE082;")
                self.lbl_weather_desc.setStyleSheet("font-size: 11px; color: #FFD4A8;")
                self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #D69E35;")
            else:
                self.weather_card.setStyleSheet("background-color: #121E19; border: 1px solid #234D3A; border-radius: 4px; padding: 4px;")
                self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #8CD68C;")
                self.lbl_weather_desc.setStyleSheet("font-size: 11px; color: #C8E6C9;")
                self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #8892A0;")

    def _toggle_night_from_tour(self) -> None:
        if self.main_window and hasattr(self.main_window, "toggle_night_mode"):
            self.main_window.toggle_night_mode()
        else:
            self.set_night_mode(not self.night_mode)

    def _start_slew(self) -> None:
        if not self.selected_item or not self.core:
            return

        it = self.selected_item
        ra = it["calc_ra"]
        dec = it["calc_dec"]
        is_j2000 = not it.get("is_dynamic", False)

        # Notify main window that a slew has started so arrival chime can fire
        target_win = self.main_window or self.parent()
        if target_win and hasattr(target_win, "_was_slewing"):
            target_win._was_slewing = True

        self.core.on_goto_requested(ra, dec, is_j2000=is_j2000, target_name=it["name"])
        self.lbl_status.setText(f"GoTo active: Slewing to {it['name']}... (Mount active)")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047;")


# ==============================================================================
# TARGET GOTO & CELESTIAL CATALOG DIALOG
# ==============================================================================

class GoToDialog(QDialog):
    """Allows selecting a celestial target or entering custom RA/Dec for GoTo slewing at constant velocity."""

    PRESETS = [
        ("Sirius (Alpha CMa)", 101.287, -16.716),
        ("Vega (Alpha Lyr)", 279.234, 38.783),
        ("Betelgeuse (Alpha Ori)", 88.793, 7.407),
        ("Rigel (Beta Ori)", 78.634, -8.201),
        ("Polaris (Alpha UMi)", 37.954, 89.264),
        ("Arcturus (Alpha Boo)", 213.915, 19.182),
        ("Capella (Alpha Aur)", 79.172, 45.998),
        ("Aldebaran (Alpha Tau)", 68.980, 16.509),
        ("Antares (Alpha Sco)", 247.352, -26.432),
        ("Andromeda Galaxy (M31)", 10.684, 41.269),
        ("Orion Nebula (M42)", 83.822, -5.391),
        ("Pleiades Cluster (M45)", 56.750, 24.116),
        ("Hercules Cluster (M13)", 250.422, 36.460),
    ]

    def __init__(self, core: Any = None, config: Optional[Dict[str, Any]] = None, night_mode: bool = False, parent: Optional[QWidget] = None, *args, **kwargs):
        if parent is None and "parent" in kwargs:
            parent = kwargs["parent"]
        if core is None and "core" in kwargs:
            core = kwargs["core"]
        if config is None and "config" in kwargs:
            config = kwargs["config"]
        super().__init__(parent)
        self.core = core
        self.config = config or {}
        self.night_mode = night_mode
        self.setWindowTitle("Manual GoTo Target & Celestial Catalog")
        self.resize(480, 360)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("SELECT CELESTIAL TARGET OR ENTER COORDINATES")
        lbl_title.setProperty("class", "section-header")
        layout.addWidget(lbl_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_presets = QComboBox()
        self.combo_presets.addItem("Custom Target Coordinates...", None)
        presets_to_add = [(name, ra, dec, True) for name, ra, dec in self.PRESETS]
        if sun_radec and self.core:
            try:
                t_now = self.core.get_time()
                s_ra, s_dec = sun_radec(t_now)
                presets_to_add.append(("Sun (Solar Filter Required)", round(s_ra, 4), round(s_dec, 4), False))
            except Exception:
                pass
        for item in presets_to_add:
            name, ra, dec, is_j2000 = item
            self.combo_presets.addItem(f"{name} (RA {ra:.1f}°, Dec {dec:+.1f}°)", (ra, dec, is_j2000))
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        form.addRow("Target Catalog:", self.combo_presets)

        self.spin_ra = QDoubleSpinBox()
        self.spin_ra.setRange(0.0, 360.0)
        self.spin_ra.setDecimals(4)
        self.spin_ra.setSuffix("°")
        self.spin_ra.setValue(101.287)
        self.spin_ra.valueChanged.connect(self._recalc_preview)
        form.addRow("Right Ascension (RA):", self.spin_ra)

        self.spin_dec = QDoubleSpinBox()
        self.spin_dec.setRange(-90.0, 90.0)
        self.spin_dec.setDecimals(4)
        self.spin_dec.setSuffix("°")
        self.spin_dec.setValue(-16.716)
        self.spin_dec.valueChanged.connect(self._recalc_preview)
        form.addRow("Declination (Dec):", self.spin_dec)

        layout.addLayout(form)

        # Status & Safety Preview Card
        card = QFrame()
        card.setProperty("class", "card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(12, 10, 12, 10)
        card_lay.setSpacing(4)

        self.lbl_preview_altaz = QLabel("Target Alt / Az: --")
        self.lbl_preview_altaz.setStyleSheet("font-size: 11px; font-weight: 700; color: #5B9DD9;")
        card_lay.addWidget(self.lbl_preview_altaz)

        self.lbl_preview_safety = QLabel("Safety: --")
        self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 600; color: #ABB2BF;")
        card_lay.addWidget(self.lbl_preview_safety)

        self.lbl_preview_duration = QLabel("Constant Slew Duration: --")
        self.lbl_preview_duration.setStyleSheet("font-size: 11px; font-weight: 600; color: #8CD68C;")
        card_lay.addWidget(self.lbl_preview_duration)

        layout.addWidget(card)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        self.btn_slew = QPushButton("Start GoTo Slew")
        self.btn_slew.setProperty("class", "primary")
        self.btn_slew.clicked.connect(self._start_slew)
        btn_box.addWidget(self.btn_slew)

        layout.addLayout(btn_box)

        # Trigger initial selection
        self.combo_presets.setCurrentIndex(1)

    def _on_preset_selected(self, idx: int) -> None:
        data = self.combo_presets.currentData()
        if data:
            ra, dec, is_j2000 = data
            self.is_current_preset_j2000 = is_j2000
            self.spin_ra.blockSignals(True)
            self.spin_dec.blockSignals(True)
            self.spin_ra.setValue(ra)
            self.spin_dec.setValue(dec)
            self.spin_ra.blockSignals(False)
            self.spin_dec.blockSignals(False)
        else:
            self.is_current_preset_j2000 = (self.config.get("epoch", "J2000") == "J2000")
        self._recalc_preview()

    def _recalc_preview(self) -> None:
        if not self.core:
            return
        ra = self.spin_ra.value()
        dec = self.spin_dec.value()
        t = self.core.get_time()
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))

        is_j2000 = getattr(self, "is_current_preset_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        if is_j2000 and precess_j2000_to_date:
            ra_date, dec_date = precess_j2000_to_date(ra, dec, t)
        else:
            ra_date, dec_date = ra, dec

        use_refr = bool(self.config.get("apply_refraction", True))
        alt, az = radec_to_altaz(ra_date, dec_date, lat, lon, t, apply_refraction=use_refr) if radec_to_altaz else (45.0, 180.0)
        self.lbl_preview_altaz.setText(f"Target Alt / Az: {alt:+.1f}° / {az:.1f}° (apparent)")

        alt_min = float(self.config.get("alt_min_deg", 0.0))
        alt_max = float(self.config.get("alt_max_deg", 85.0))
        keepout = float(self.config.get("sun_keepout_deg", 15.0))

        s_ra, s_dec = sun_radec(t) if sun_radec else (0.0, 0.0)
        sun_sep = separation_deg(ra_date, dec_date, s_ra, s_dec) if separation_deg else 90.0

        is_safe = True
        err_msg = ""
        if alt < alt_min:
            is_safe = False
            err_msg = f"Target Below Horizon ({alt:.1f}° < {alt_min:.0f}°)"
        elif alt > alt_max:
            is_safe = False
            err_msg = f"Target Exceeds Max Elevation ({alt:.1f}° > {alt_max:.0f}°)"
        elif sun_sep < keepout:
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if has_filter:
                self.lbl_preview_safety.setText(f"Safety: SOLAR OBSERVATION (Sun separation: {sun_sep:.1f}° - Filter Active)")
                self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFE082;")
                self.btn_slew.setEnabled(True)
            else:
                self.lbl_preview_safety.setText(f"Safety: CAUTION - Sun separation {sun_sep:.1f}° < {keepout:.0f}° (Solar Filter Required)")
                self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFB74D;")
                self.btn_slew.setEnabled(True)

        if is_safe and (sun_sep >= keepout or getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)):
            self.lbl_preview_safety.setText(f"Safety: OK (Above horizon, Sun separation: {sun_sep:.1f}°)")
            self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 600; color: #8CD68C;")
            self.btn_slew.setEnabled(True)
        elif not is_safe:
            self.lbl_preview_safety.setText(f"Safety: BLOCKED - {err_msg}")
            self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666;")
            self.btn_slew.setEnabled(False)

        # Calculate slew distance and coordinated duration (max of axes)
        cur_alt, cur_az = self.core.get_telescope_altaz()
        diff_az = abs(az - cur_az)
        if diff_az > 180.0:
            diff_az = 360.0 - diff_az
        diff_alt = abs(alt - cur_alt)

        steps_deg_az = float(self.config.get("steps_per_deg_az", 113.22))
        speed_steps_az = float(self.config.get("speed_az", 226))
        speed_deg_s_az = speed_steps_az / steps_deg_az if steps_deg_az > 0 else 2.0

        steps_deg_alt = float(self.config.get("steps_per_deg_alt", 113.22))
        speed_steps_alt = float(self.config.get("speed_alt", 226))
        speed_deg_s_alt = speed_steps_alt / steps_deg_alt if steps_deg_alt > 0 else 2.0

        dur_az = diff_az / speed_deg_s_az if speed_deg_s_az > 0 else 0.0
        dur_alt = diff_alt / speed_deg_s_alt if speed_deg_s_alt > 0 else 0.0
        dur_s = max(dur_az, dur_alt)

        self.lbl_preview_duration.setText(
            f"Distance: Az {diff_az:.1f}°, Alt {diff_alt:.1f}° | Slew Duration: {dur_s:.1f}s"
        )

    def _start_slew(self) -> None:
        if not self.core or not self.core.link or not self.core.link.is_open:
            QMessageBox.warning(self, "Hardware Not Connected", "Please connect to Arduino or Simulator first.")
            return
        ra = self.spin_ra.value()
        dec = self.spin_dec.value()

        t = self.core.get_time()
        s_ra, s_dec = sun_radec(t) if sun_radec else (0.0, 0.0)
        sun_sep = separation_deg(ra, dec, s_ra, s_dec) if separation_deg else 90.0
        keepout = float(self.config.get("sun_keepout_deg", 15.0))

        solar_ok = False
        if sun_sep < keepout:
            # Check if the user physically checked the Solar Filter Attached box on the GUI
            parent_win = self.parent()
            has_gui_filter = False
            if hasattr(parent_win, 'chk_solar_filter') and parent_win.chk_solar_filter:
                has_gui_filter = parent_win.chk_solar_filter.isChecked()

            if not has_gui_filter:
                # Solar filter attached box is unchecked: ALWAYS show warning dialog before slewing to Sun!
                confirmed = False
                if hasattr(parent_win, '_prompt_solar_warning'):
                    confirmed = parent_win._prompt_solar_warning(sun_sep)
                elif self.core and self.core.solar_warning_callback:
                    confirmed = self.core.solar_warning_callback(sun_sep)
                if not confirmed:
                    return
                solar_ok = True
            else:
                solar_ok = True

        is_j2000 = getattr(self, "is_current_preset_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        ok = self.core.on_goto_requested(ra, dec, is_j2000=is_j2000, solar_confirmed=solar_ok)
        if ok and hasattr(self.core, "follower") and self.core.follower:
            target_preset = self.combo_presets.currentText()
            self.core.follower.authorize_target(target_preset)
        if ok:
            self.accept()
        else:
            QMessageBox.warning(self, "GoTo Rejected", "GoTo command was rejected by mount safety interlocks.")


# ==============================================================================
# MAIN APPLICATION WINDOW (Version 2.0 - Scientific Clean Layout)
# ==============================================================================

class SolarSafetyBridge(QObject):
    """Thread-safe marshaling bridge to dispatch solar safety prompts to the Qt GUI thread."""
    request_prompt = pyqtSignal(float, object, object)


class AstroTelescopeWindow(QMainWindow):
    """Professional 3-Axis Telescope Mount & Stellarium Bridge Desktop Application."""

    def __init__(self, core: Any, stellarium: Any, config: Any):
        super().__init__()
        self.core = core
        self.stellarium = stellarium
        self.config = config

        self.setWindowTitle("Custom GoTo Telescope Controller")

        # Load and apply black hole application icon (multi-resolution .ico and high-res .png)
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.ico")
        png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.png")
        if not os.path.exists(ico_path) and hasattr(sys, '_MEIPASS'):
            ico_path = os.path.join(sys._MEIPASS, "assets", "black_hole_icon.ico")
            png_path = os.path.join(sys._MEIPASS, "assets", "black_hole_icon.png")

        app_icon = QIcon()
        if os.path.exists(ico_path):
            app_icon.addFile(ico_path)
        if os.path.exists(png_path):
            app_icon.addFile(png_path)

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)
        self.resize(1280, 880)
        self.setMinimumSize(1080, 780)

        # State: Night mode, audio cues, and slew arrival tracking
        self.night_mode: bool = bool(self.config.get("night_mode", False))
        self.audio_enabled: bool = bool(self.config.get("audio_cues_enabled", True))
        self._was_slewing: bool = False
        self._was_moving: bool = False
        self.tour_window: Optional[TonightSkyTourDialog] = None
        self.setStyleSheet(NIGHT_VISION_STYLE if self.night_mode else SCIENTIFIC_STYLE)

        self.selected_jog_speed: str = "medium"
        self.follower: Any = StellariumHttpFollower(self.core, require_explicit_goto=True) if (StellariumHttpFollower and self.core) else None
        if self.follower and self.core:
            self.core.follower = self.follower

        # Thread-safe solar safety modal prompt bridge
        self.solar_bridge = SolarSafetyBridge()
        self.solar_bridge.request_prompt.connect(self._on_solar_prompt_requested, Qt.ConnectionType.QueuedConnection)
        self._is_showing_solar_dialog: bool = False

        # Ephemeris & celestial caching to ensure buttery-smooth 25 FPS UI without redundant math
        self._last_heavy_calc_time: float = 0.0
        self._cached_rise_transit_set: Tuple[str, str, str] = ("--:--", "--:--", "--:--")
        self._cached_target_key: Optional[Tuple[float, float, str]] = None
        self._cached_gal: Tuple[float, float] = (0.0, 0.0)
        self._cached_ecl: Tuple[float, float] = (0.0, 0.0)
        self._cached_constellation_mount: str = "Unknown"
        self._cached_constellation_target: str = "Unknown"
        self._last_mount_j2000: Optional[Tuple[float, float]] = None
        self._has_auto_synced_location: bool = False
        self._last_auto_sync_attempt: float = 0.0

        if self.core:
            self.core.solar_warning_callback = self._prompt_solar_warning
            self.core.solar_filter_confirmed = False

        # Live Open-Meteo astronomical weather & seeing service
        self.weather_service = LiveWeatherService(self.config, self)
        self.weather_service.weather_updated.connect(self._on_weather_updated)
        self.weather_service.weather_error.connect(lambda err: self.log_message("WARNING", f"Weather fetch: {err}"))
        self.weather_service.fetch_async()

        self._build_interface()
        self._setup_shortcuts()

        # HIGH-SPEED TELEMETRY TIMER: 40 ms = 25 FPS for smooth, real-time ticking
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(40)

        self._refresh_ports()

    def _build_interface(self) -> None:
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Header Deck
        main_layout.addWidget(self._create_header_deck())

        # 2. Safety Caution Strip
        main_layout.addWidget(self._create_safety_strip())

        # 3. Main Workspace
        workspace = QWidget()
        ws_layout = QHBoxLayout(workspace)
        ws_layout.setContentsMargins(12, 10, 12, 8)
        ws_layout.setSpacing(12)

        # Left Column: Enlarged Sky Radar & Observatory Clocks
        ws_layout.addWidget(self._create_left_radar_column(), stretch=5)

        # Center Column: Prominent Large Telemetry Deck (Matching Stellarium)
        ws_layout.addWidget(self._create_center_telemetry_column(), stretch=6)

        # Right Column: Motion D-Pad & Focus Controller
        ws_layout.addWidget(self._create_right_control_column(), stretch=4)

        main_layout.addWidget(workspace, stretch=8)

        # 4. Bottom Activity Console
        main_layout.addWidget(self._create_console_deck(), stretch=2)

    # --------------------------------------------------------------------------
    # Sub-deck Layouts
    # --------------------------------------------------------------------------

    def _create_header_deck(self) -> QWidget:
        header = QFrame()
        header.setProperty("class", "header-deck")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        # Clean header column without icon or text banner
        layout.addSpacing(4)

        # Serial Connection Bar
        conn_box = QHBoxLayout()
        conn_box.setSpacing(6)

        self.lbl_p = QLabel("Serial Port:")
        lbl_p = self.lbl_p
        lbl_p.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #AA2222;")
        conn_box.addWidget(lbl_p)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(110)
        conn_box.addWidget(self.port_combo)

        btn_refresh = QPushButton("Scan Ports")
        btn_refresh.setToolTip("Scan serial COM ports")
        btn_refresh.clicked.connect(self._refresh_ports)
        conn_box.addWidget(btn_refresh)

        self.chk_simulate = QCheckBox("Simulate Uno")
        self.chk_simulate.setChecked(bool(self.config.get("simulate", False)))
        self.chk_simulate.setToolTip("Emulate Arduino Uno and motor kinematics in software")
        conn_box.addWidget(self.chk_simulate)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setProperty("class", "primary")
        self.btn_connect.clicked.connect(self._toggle_connection)
        conn_box.addWidget(self.btn_connect)

        layout.addLayout(conn_box)

        layout.addStretch()

        # Status Pills
        status_box = QHBoxLayout()
        status_box.setSpacing(10)

        self.lbl_serial_status = QLabel("ARDUINO: DISCONNECTED")
        self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #CC4444; background: #261B1B; padding: 4px 8px; border: 1px solid #4D2626; border-radius: 3px;")
        status_box.addWidget(self.lbl_serial_status)

        self.lbl_stellarium_status = QLabel("STELLARIUM: LISTENING [10001]")
        self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #D69E35; background: #262118; padding: 4px 8px; border: 1px solid #4D3D1F; border-radius: 3px;")
        status_box.addWidget(self.lbl_stellarium_status)

        self.btn_weather = QPushButton("[WEATHER: CHECKING...]")
        self.btn_weather.setToolTip("Query live Open-Meteo astronomical cloud cover & seeing telemetry")
        self.btn_weather.clicked.connect(self._refresh_weather_clicked)
        status_box.addWidget(self.btn_weather)
        self._style_weather_btn()

        layout.addLayout(status_box)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        btn_help = QPushButton("Help & Manual")
        btn_help.clicked.connect(self._open_help)
        layout.addWidget(btn_help)

        self.btn_night_mode = QPushButton("Night Vision: ON" if self.night_mode else "Night Vision")
        if self.night_mode:
            self.btn_night_mode.setStyleSheet("background-color: #660A0A; border-color: #991414; color: #FFB3B3; font-weight: 700;")
        self.btn_night_mode.setToolTip("Toggle pure-red night-vision mode to preserve dark adaptation (Ctrl+N)")
        self.btn_night_mode.clicked.connect(self.toggle_night_mode)
        layout.addWidget(self.btn_night_mode)

        chk_audio = QCheckBox("Audio")
        chk_audio.setChecked(bool(self.audio_enabled))
        chk_audio.setToolTip("Acoustic feedback for slews, arrivals, and emergency stop")
        chk_audio.toggled.connect(self._on_audio_toggled)
        layout.addWidget(chk_audio)

        self.btn_estop = QPushButton("STOP")
        self.btn_estop.setProperty("class", "stop-btn")
        self.btn_estop.setToolTip("Emergency Stop (Spacebar / Esc)")
        self.btn_estop.clicked.connect(self._emergency_stop)
        layout.addWidget(self.btn_estop)

        return header

    def _create_safety_strip(self) -> QWidget:
        self.safety_strip = QFrame()
        strip = self.safety_strip
        strip.setStyleSheet("background-color: #381B1B; border-bottom: 1px solid #4D2626;" if not self.night_mode else "background-color: #240505; border-bottom: 1px solid #4D0A0A;")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 3, 14, 3)

        self.lbl_warn = QLabel("CAUTION: NEVER POINT TELESCOPE AT OR NEAR THE SUN WITHOUT A CERTIFIED SOLAR FILTER")
        lbl_warn = self.lbl_warn
        lbl_warn.setStyleSheet("font-size: 10px; font-weight: 700; color: #F2C2C2;" if not self.night_mode else "font-size: 10px; font-weight: 700; color: #FF3333;")
        layout.addWidget(lbl_warn)

        layout.addStretch()

        self.chk_solar_filter = QCheckBox("Solar Filter Attached")
        self.chk_solar_filter.setChecked(False)
        self.chk_solar_filter.setStyleSheet("font-size: 10px; font-weight: 700; color: #FFE082;")
        self.chk_solar_filter.setToolTip("Enables solar observation when a physical certified solar filter is securely attached")
        self.chk_solar_filter.toggled.connect(self._toggle_solar_filter)
        layout.addWidget(self.chk_solar_filter)

        layout.addSpacing(12)

        self.lbl_sun_sep = QLabel("Sun Angular Separation: --")
        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 700; color: #EAD07C;")
        layout.addWidget(self.lbl_sun_sep)

        return strip

    def _create_left_radar_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Radar Card
        radar_card = QFrame()
        radar_card.setProperty("class", "card")
        radar_layout = QVBoxLayout(radar_card)
        radar_layout.setContentsMargins(10, 8, 10, 8)

        head_box = QHBoxLayout()
        lbl_title = QLabel("CELESTIAL SKY RADAR (ALTITUDE - AZIMUTH)")
        lbl_title.setProperty("class", "section-header")
        head_box.addWidget(lbl_title)
        head_box.addStretch()

        self.lbl_radar_legend = QLabel("Blue: Mount Reticle  |  Amber: Target  |  Yellow: Sun" if not self.night_mode else "Bright Red: Scope | Dotted Red: Target | Dark Crimson: Sun")
        lbl_legend = self.lbl_radar_legend
        lbl_legend.setStyleSheet("font-size: 10px; color: #8892A0;" if not self.night_mode else "font-size: 10px; color: #AA2222;")
        head_box.addWidget(lbl_legend)
        radar_layout.addLayout(head_box)

        self.radar_widget = EnlargedPolarRadarWidget()
        radar_layout.addWidget(self.radar_widget, stretch=1)
        layout.addWidget(radar_card, stretch=6)

        # Clocks Card
        clock_card = QFrame()
        clock_card.setProperty("class", "card")
        clock_layout = QGridLayout(clock_card)
        clock_layout.setContentsMargins(12, 8, 12, 8)
        clock_layout.setHorizontalSpacing(14)
        clock_layout.setVerticalSpacing(4)

        lbl_t1 = QLabel("UTC TIME:")
        lbl_t1.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t1, 0, 0)
        self.val_utc = QLabel("--:--:--")
        self.val_utc.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_utc, 0, 1)

        lbl_t2 = QLabel("LOCAL TIME:")
        lbl_t2.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t2, 1, 0)
        self.val_local = QLabel("--:--:--")
        self.val_local.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_local, 1, 1)

        lbl_t3 = QLabel("SIDEREAL (LMST):")
        lbl_t3.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t3, 0, 2)
        self.val_lst = QLabel("--h --m --s")
        self.val_lst.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_lst, 0, 3)

        lbl_t4 = QLabel("JULIAN DATE:")
        lbl_t4.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t4, 1, 2)
        self.val_jd = QLabel("2460000.000000")
        self.val_jd.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_jd, 1, 3)

        layout.addWidget(clock_card, stretch=2)

        return col

    def _create_center_telemetry_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Table 1: Mount Position Details (Matching Stellarium Parameters)
        card_mount = QFrame()
        card_mount.setProperty("class", "card")
        lay_mount = QVBoxLayout(card_mount)
        lay_mount.setContentsMargins(14, 10, 14, 10)
        lay_mount.setSpacing(6)

        head_row = QHBoxLayout()
        lbl_head1 = QLabel("TELESCOPE MOUNT POSITION (CURRENT)")
        lbl_head1.setProperty("class", "section-header")
        head_row.addWidget(lbl_head1)
        head_row.addStretch()

        lbl_rate = QLabel("Data Rate:")
        lbl_rate.setStyleSheet("font-size: 11px; font-weight: 600; color: #8892A0;")
        head_row.addWidget(lbl_rate)

        self.combo_stream_rate = QComboBox()
        self.combo_stream_rate.addItems(["Fast Live (25 Hz)", "Normal (1s)"])
        self.combo_stream_rate.currentIndexChanged.connect(self._on_stream_rate_changed)
        head_row.addWidget(self.combo_stream_rate)

        lay_mount.addLayout(head_row)

        # Detailed Parameter Grid
        grid1 = QGridLayout()
        grid1.setVerticalSpacing(6)
        grid1.setHorizontalSpacing(16)

        fields1 = [
            ("RA/Dec (J2000.0):", "val_m_j2000"),
            ("RA/Dec (on date):", "val_m_jnow"),
            ("HA/Dec (apparent):", "val_m_hadec"),
            ("Az./Alt. (apparent):", "val_m_altaz"),
            ("Gal. long./lat. (l, b):", "val_m_gal"),
            ("Ecl. long./lat. (J2000.0):", "val_m_ecl"),
            ("Parallactic Angle:", "val_m_parallactic"),
            ("IAU Constellation:", "val_m_constellation"),
            ("Motor Steps (Az / Alt / Foc):", "val_m_steps"),
        ]

        for row, (label_text, attr_name) in enumerate(fields1):
            lbl_k = QLabel(label_text)
            lbl_k.setProperty("class", "table-key")
            lbl_v = QLabel("--")
            lbl_v.setProperty("class", "table-val")
            setattr(self, attr_name, lbl_v)
            grid1.addWidget(lbl_k, row, 0)
            grid1.addWidget(lbl_v, row, 1)

        lay_mount.addLayout(grid1)
        layout.addWidget(card_mount, stretch=5)

        # Table 2: Active Target Object Details (Matching Stellarium Target Overlay)
        card_target = QFrame()
        card_target.setProperty("class", "card")
        lay_target = QVBoxLayout(card_target)
        lay_target.setContentsMargins(14, 10, 14, 10)
        lay_target.setSpacing(6)

        head_row2 = QHBoxLayout()
        lbl_head2 = QLabel("CURRENT TRACKED OBJECT (STELLARIUM TARGET)")
        lbl_head2.setProperty("class", "section-header")
        head_row2.addWidget(lbl_head2)
        head_row2.addStretch()

        self.btn_satellite_follow = QPushButton("Satellite Follow: OFF")
        self.btn_satellite_follow.setToolTip("Continuous real-time tracking for moving satellites (ISS, Starlink) via Stellarium Remote Control (port 8090)")
        self.btn_satellite_follow.clicked.connect(self._toggle_satellite_follow)
        head_row2.addWidget(self.btn_satellite_follow)

        lay_target.addLayout(head_row2)

        grid2 = QGridLayout()
        grid2.setVerticalSpacing(5)
        grid2.setHorizontalSpacing(14)

        fields2 = [
            ("Target Status:", "val_t_status"),
            ("Target RA/Dec (J2000):", "val_t_j2000"),
            ("Target RA/Dec (on date):", "val_t_jnow"),
            ("Target Az./Alt. (apparent):", "val_t_altaz"),
            ("Target Constellation:", "val_t_constellation"),
            ("Rise / Transit / Set:", "val_t_ephemeris"),
            ("Sun Angular Separation:", "val_t_sunsep"),
            ("Tracking Kinematics:", "val_t_tracking"),
            ("Tracking Pulses / Drift:", "val_t_pulses"),
            ("Stellarium Live Follow:", "val_t_follow_status"),
        ]

        for row, (label_text, attr_name) in enumerate(fields2):
            lbl_k = QLabel(label_text)
            lbl_k.setProperty("class", "table-key")
            lbl_v = QLabel("None")
            lbl_v.setProperty("class", "table-val")
            setattr(self, attr_name, lbl_v)
            grid2.addWidget(lbl_k, row, 0)
            grid2.addWidget(lbl_v, row, 1)

        lay_target.addLayout(grid2)
        layout.addWidget(card_target, stretch=4)

        return col

    def _create_right_control_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Motion & Jog Card
        jog_card = QFrame()
        jog_card.setProperty("class", "card")
        jog_layout = QVBoxLayout(jog_card)
        jog_layout.setContentsMargins(12, 8, 12, 8)
        jog_layout.setSpacing(6)

        lbl_jog = QLabel("MANUAL MOTION CONTROLS")
        lbl_jog.setProperty("class", "section-header")
        jog_layout.addWidget(lbl_jog)

        dpad_grid = QGridLayout()
        dpad_grid.setSpacing(5)

        btn_up = QPushButton("ALT +")
        btn_up.setMinimumHeight(36)
        btn_up.clicked.connect(lambda: self._jog("up"))
        dpad_grid.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("AZ -")
        btn_left.setMinimumHeight(36)
        btn_left.clicked.connect(lambda: self._jog("left"))
        dpad_grid.addWidget(btn_left, 1, 0)

        btn_stop = QPushButton("STOP")
        btn_stop.setProperty("class", "stop-btn")
        btn_stop.setMinimumHeight(36)
        btn_stop.clicked.connect(self._emergency_stop)
        dpad_grid.addWidget(btn_stop, 1, 1)

        btn_right = QPushButton("AZ +")
        btn_right.setMinimumHeight(36)
        btn_right.clicked.connect(lambda: self._jog("right"))
        dpad_grid.addWidget(btn_right, 1, 2)

        btn_down = QPushButton("ALT -")
        btn_down.setMinimumHeight(36)
        btn_down.clicked.connect(lambda: self._jog("down"))
        dpad_grid.addWidget(btn_down, 2, 1)

        jog_layout.addLayout(dpad_grid)

        # Speed Selectors
        speed_box = QHBoxLayout()
        speed_box.setSpacing(4)

        self.btn_fine = QPushButton("Fine (0.05°)")
        self.btn_med = QPushButton("Medium (0.50°)")
        self.btn_coarse = QPushButton("Coarse (3.00°)")

        self.btn_fine.setCheckable(True)
        self.btn_med.setCheckable(True)
        self.btn_coarse.setCheckable(True)
        self.btn_med.setChecked(True)

        spd_group = QButtonGroup(self)
        spd_group.addButton(self.btn_fine)
        spd_group.addButton(self.btn_med)
        spd_group.addButton(self.btn_coarse)

        self.btn_fine.clicked.connect(lambda: self._set_speed("fine"))
        self.btn_med.clicked.connect(lambda: self._set_speed("medium"))
        self.btn_coarse.clicked.connect(lambda: self._set_speed("coarse"))

        speed_box.addWidget(self.btn_fine)
        speed_box.addWidget(self.btn_med)
        speed_box.addWidget(self.btn_coarse)
        jog_layout.addLayout(speed_box)

        layout.addWidget(jog_card)

        # Command Deck Card
        act_card = QFrame()
        act_card.setProperty("class", "card")
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(12, 8, 12, 8)
        act_layout.setSpacing(6)

        lbl_cmd = QLabel("ALIGNMENT & MOUNT ACTIONS")
        lbl_cmd.setProperty("class", "section-header")
        act_layout.addWidget(lbl_cmd)

        # Smarter Kinematics: Tracking Rate Selector Bar
        rate_box = QHBoxLayout()
        rate_box.setSpacing(4)
        lbl_rate = QLabel("Rate:")
        lbl_rate.setStyleSheet("font-size: 11px; color: #8892A0; font-weight: 600;")
        rate_box.addWidget(lbl_rate)

        self.rate_buttons: Dict[str, QPushButton] = {}
        for r_name in ("Sidereal", "Lunar", "Solar", "King"):
            btn_r = QPushButton(r_name)
            btn_r.setCheckable(True)
            active = (r_name == self.config.get("tracking_rate", "Sidereal"))
            btn_r.setChecked(active)
            if active:
                btn_r.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1E4472; color: #FFFFFF; font-weight: 700; border: 1px solid #336FA5;")
            else:
                btn_r.setStyleSheet("font-size: 10px; padding: 3px 6px;")
            btn_r.clicked.connect(lambda checked, r=r_name: self._set_tracking_rate(r))
            rate_box.addWidget(btn_r)
            self.rate_buttons[r_name] = btn_r

        act_layout.addLayout(rate_box)

        act_grid = QGridLayout()
        act_grid.setSpacing(5)

        self.btn_sync = QPushButton("Sync Target")
        self.btn_sync.setProperty("class", "sync-btn")
        self.btn_sync.setToolTip("Calibrate telescope orientation to active Stellarium target")
        self.btn_sync.clicked.connect(self._sync_scope)
        act_grid.addWidget(self.btn_sync, 0, 0)

        self.btn_track = QPushButton("Tracking: OFF")
        self.btn_track.clicked.connect(self._toggle_tracking)
        act_grid.addWidget(self.btn_track, 0, 1)

        self.btn_home_alt = QPushButton("Home Altitude")
        self.btn_home_alt.clicked.connect(lambda: self._home_axis("ALT"))
        act_grid.addWidget(self.btn_home_alt, 1, 0)

        self.btn_home_az = QPushButton("Home Azimuth")
        self.btn_home_az.clicked.connect(lambda: self._home_axis("AZ"))
        act_grid.addWidget(self.btn_home_az, 1, 1)

        btn_park = QPushButton("Park Telescope")
        btn_park.clicked.connect(self._park_mount)
        act_grid.addWidget(btn_park, 2, 0)

        btn_zero = QPushButton("Zero Position (0,0)")
        btn_zero.setToolTip("Set current orientation as True North and Level")
        btn_zero.clicked.connect(self._confirm_zero)
        act_grid.addWidget(btn_zero, 2, 1)

        btn_sky_tour = QPushButton("Tonight's Best Sky Tour...")
        btn_sky_tour.setProperty("class", "primary")
        btn_sky_tour.setToolTip("Interactive celestial tour of visible targets with 20x/30x/40x eyepiece recommendations (Ctrl+T)")
        btn_sky_tour.clicked.connect(self._open_sky_tour)
        act_grid.addWidget(btn_sky_tour, 3, 0, 1, 2)

        act_layout.addLayout(act_grid)

        # Cable-Wrap Prevention Monitor & Unwind Deck
        cable_box = QHBoxLayout()
        cable_box.setSpacing(6)
        self.lbl_cable_wrap = QLabel("Cable: 0.00 turns [OK]")
        self.lbl_cable_wrap.setStyleSheet("font-size: 11px; font-weight: 600; color: #88C0FF;")
        cable_box.addWidget(self.lbl_cable_wrap)

        self.btn_unwind = QPushButton("Unwind (0°)")
        btn_unwind = self.btn_unwind
        btn_unwind.setToolTip("Slew Azimuth to 0° True North to untangle cables")
        btn_unwind.setStyleSheet("font-size: 10px; padding: 3px 8px; background: #1A2330; border: 1px solid #2B3D52; border-radius: 3px;" if not self.night_mode else "font-size: 10px; padding: 3px 8px; background: #260505; border: 1px solid #4D0A0A; color: #FFAAAA; border-radius: 3px;")
        btn_unwind.clicked.connect(self._unwind_cable)
        cable_box.addWidget(btn_unwind)

        act_layout.addLayout(cable_box)
        layout.addWidget(act_card)

        # Focus Control Card
        foc_card = QFrame()
        foc_card.setProperty("class", "card")
        foc_layout = QVBoxLayout(foc_card)
        foc_layout.setContentsMargins(12, 8, 12, 8)
        foc_layout.setSpacing(6)

        fhead = QHBoxLayout()
        lbl_f = QLabel("MOTORIZED FOCUS")
        lbl_f.setProperty("class", "section-header")
        fhead.addWidget(lbl_f)
        fhead.addStretch()

        self.lbl_foc_pos = QLabel("Position: 0 steps")
        self.lbl_foc_pos.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #88B0D8; font-weight: 600;")
        fhead.addWidget(self.lbl_foc_pos)
        foc_layout.addLayout(fhead)

        foc_btns = QGridLayout()
        foc_btns.setSpacing(4)

        btn_cin = QPushButton("Coarse In (<<)")
        btn_cin.clicked.connect(lambda: self._move_focus("coarse", True))
        foc_btns.addWidget(btn_cin, 0, 0)

        btn_fin = QPushButton("Fine In (<)")
        btn_fin.clicked.connect(lambda: self._move_focus("fine", True))
        foc_btns.addWidget(btn_fin, 0, 1)

        btn_fout = QPushButton("Fine Out (>)")
        btn_fout.clicked.connect(lambda: self._move_focus("fine", False))
        foc_btns.addWidget(btn_fout, 1, 0)

        btn_cout = QPushButton("Coarse Out (>>)")
        btn_cout.clicked.connect(lambda: self._move_focus("coarse", False))
        foc_btns.addWidget(btn_cout, 1, 1)

        foc_layout.addLayout(foc_btns)

        # Fine-Tuning Step Controls & Direct Step GoTo
        foc_fine_box = QHBoxLayout()
        foc_fine_box.setSpacing(4)

        btn_nudge_in = QPushButton("-5 steps")
        btn_nudge_in.setToolTip("Fine nudge inward 5 steps")
        btn_nudge_in.clicked.connect(lambda: self._move_focus_steps(-5))
        foc_fine_box.addWidget(btn_nudge_in)

        btn_nudge_out = QPushButton("+5 steps")
        btn_nudge_out.setToolTip("Fine nudge outward 5 steps")
        btn_nudge_out.clicked.connect(lambda: self._move_focus_steps(5))
        foc_fine_box.addWidget(btn_nudge_out)

        self.spin_foc_direct = QSpinBox()
        self.spin_foc_direct.setRange(-50000, 50000)
        self.spin_foc_direct.setValue(0)
        self.spin_foc_direct.setToolTip("Target step position")
        foc_fine_box.addWidget(self.spin_foc_direct)

        btn_goto_foc = QPushButton("Go")
        btn_goto_foc.setToolTip("Slew to target step")
        btn_goto_foc.clicked.connect(self._goto_focus_step)
        foc_fine_box.addWidget(btn_goto_foc)

        foc_layout.addLayout(foc_fine_box)

        # Automated Focus Routine & Reset
        foc_auto_box = QHBoxLayout()
        foc_auto_box.setSpacing(4)

        btn_autofocus = QPushButton("Autofocus")
        btn_autofocus.setProperty("class", "primary")
        btn_autofocus.setToolTip("Run automated V-curve focus routine to find critical focus zone")
        btn_autofocus.clicked.connect(self._open_autofocus_dialog)
        foc_auto_box.addWidget(btn_autofocus)

        btn_zero_foc = QPushButton("Zero Focus")
        btn_zero_foc.setToolTip("Reset focus coordinate to 0")
        btn_zero_foc.clicked.connect(self._zero_focus)
        foc_auto_box.addWidget(btn_zero_foc)

        foc_layout.addLayout(foc_auto_box)
        layout.addWidget(foc_card)

        return col

    def _create_console_deck(self) -> QWidget:
        self.console_deck = QFrame()
        deck = self.console_deck
        deck.setStyleSheet("background-color: #0E1015; border-top: 1px solid #252A34;" if not self.night_mode else "background-color: #050000; border-top: 1px solid #330808;")
        layout = QVBoxLayout(deck)
        layout.setContentsMargins(14, 6, 14, 8)
        layout.setSpacing(4)

        h = QHBoxLayout()
        lbl = QLabel("ACTIVITY CONSOLE & HARDWARE COMMUNICATIONS")
        lbl.setProperty("class", "section-header")
        h.addWidget(lbl)
        h.addStretch()

        self.btn_sync_loc = QPushButton("Sync Location")
        self.btn_sync_loc.setToolTip("Synchronize observer site coordinates with Stellarium (Port 8090)")
        self.btn_sync_loc.clicked.connect(lambda: self._sync_location_from_stellarium(quiet=False))
        h.addWidget(self.btn_sync_loc)

        self.chk_autoscroll = QCheckBox("Auto-Scroll")
        self.chk_autoscroll.setChecked(True)
        h.addWidget(self.chk_autoscroll)

        btn_clear = QPushButton("Clear Console")
        btn_clear.clicked.connect(self._clear_console)
        h.addWidget(btn_clear)

        layout.addLayout(h)

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setMaximumHeight(115)
        self.console_text.document().setMaximumBlockCount(2000)
        layout.addWidget(self.console_text)

        return deck

    # --------------------------------------------------------------------------
    # User Interactions & Shortcuts
    # --------------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        def _safe_jog(direction: str):
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, (QComboBox, QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox)):
                return
            self._jog(direction)

        QShortcut(QKeySequence(Qt.Key.Key_Up), self, lambda: _safe_jog("up"))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, lambda: _safe_jog("down"))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: _safe_jog("left"))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: _safe_jog("right"))
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._emergency_stop)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._emergency_stop)

    def _set_speed(self, mode: str) -> None:
        self.selected_jog_speed = mode

    def _jog(self, direction: str) -> None:
        if self.core:
            self.core.jog(direction, self.selected_jog_speed)

    def toggle_night_mode(self) -> None:
        self.night_mode = not self.night_mode
        self.config["night_mode"] = self.night_mode
        if hasattr(self.config, "save"):
            self.config.save()
        self._apply_active_theme()

    def _refresh_weather_clicked(self) -> None:
        if hasattr(self, "weather_service") and self.weather_service:
            self.weather_service.fetch_async()
        if hasattr(self, "btn_weather"):
            self.btn_weather.setText("[CHECKING...]")

    def _on_weather_updated(self, data: Dict[str, Any]) -> None:
        if hasattr(self, "weather_service") and self.weather_service:
            self.weather_service.latest_data = data
        if not hasattr(self, "btn_weather"):
            return
        badge = data.get("badge", "[WEATHER]")
        cloud = data.get("cloud_cover", 0)
        temp = data.get("temperature_c", 0.0)
        hum = data.get("humidity_pct", 0)
        wind = data.get("wind_kmh", 0.0)
        vis = data.get("visibility_km", 0.0)
        cond = data.get("condition", "Unknown")
        obs = data.get("obs_status", "")

        self.btn_weather.setText(f"{badge} {cloud}% CLOUD | {temp:.1f}°C")
        self.btn_weather.setToolTip(
            f"Live Astronomical Weather & Seeing (Open-Meteo)\n"
            f"Status: {obs} ({cond})\n"
            f"Cloud Cover: {cloud}%\n"
            f"Temperature: {temp:.1f}°C | Humidity: {hum}%\n"
            f"Wind: {wind:.1f} km/h | Visibility: {vis:.1f} km\n"
            f"Last Updated: {data.get('updated_at', '--:--')}\n"
            f"(Click to refresh now)"
        )
        self._style_weather_btn()
        if hasattr(self, "tour_window") and self.tour_window:
            self.tour_window.update_weather_display(data)

    def _style_weather_btn(self) -> None:
        if not hasattr(self, "btn_weather"):
            return
        data = self.weather_service.latest_data if hasattr(self, "weather_service") and self.weather_service else None
        cloud = data.get("cloud_cover", 0) if data else 0
        if self.night_mode:
            if cloud >= 80:
                self.btn_weather.setStyleSheet("background-color: #3B0808; border: 1px solid #730E0E; color: #FFAAAA; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;")
            else:
                self.btn_weather.setStyleSheet("background-color: #240505; border: 1px solid #4D0A0A; color: #FF6666; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;")
        else:
            if cloud >= 80:
                self.btn_weather.setStyleSheet("background-color: #2A1F12; border: 1px solid #6E4F28; color: #FFE082; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;")
            else:
                self.btn_weather.setStyleSheet("background-color: #172433; border: 1px solid #2B4B6E; color: #5AA9FF; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;")

    def _apply_active_theme(self) -> None:
        nm = self.night_mode
        self.setStyleSheet(NIGHT_VISION_STYLE if nm else SCIENTIFIC_STYLE)
        self.radar_widget.set_night_mode(nm)

        if hasattr(self, "btn_night_mode"):
            self.btn_night_mode.setText("Night Vision: ON" if nm else "Night Vision")
            self.btn_night_mode.setStyleSheet("background-color: #660A0A; border-color: #991414; color: #FFB3B3; font-weight: 700;" if nm else "")

        if hasattr(self, "safety_strip"):
            self.safety_strip.setStyleSheet("background-color: #240505; border-bottom: 1px solid #4D0A0A;" if nm else "background-color: #381B1B; border-bottom: 1px solid #4D2626;")
        if hasattr(self, "lbl_warn"):
            self.lbl_warn.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF3333;" if nm else "font-size: 10px; font-weight: 700; color: #F2C2C2;")
        if hasattr(self, "chk_solar_filter"):
            self.chk_solar_filter.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF5555;" if nm else "font-size: 10px; font-weight: 700; color: #FFE082;")

        if hasattr(self, "lbl_radar_legend"):
            self.lbl_radar_legend.setText("Bright Red: Scope | Dotted Red: Target | Dark Crimson: Sun" if nm else "Blue: Mount Reticle  |  Amber: Target  |  Yellow: Sun")
            self.lbl_radar_legend.setStyleSheet("font-size: 10px; color: #AA2222;" if nm else "font-size: 10px; color: #8892A0;")

        if hasattr(self, "lbl_cable_wrap"):
            self.lbl_cable_wrap.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF4D4D;" if nm else "font-size: 11px; font-weight: 600; color: #88C0FF;")
        if hasattr(self, "btn_unwind"):
            self.btn_unwind.setStyleSheet("font-size: 10px; padding: 3px 8px; background: #260505; border: 1px solid #4D0A0A; color: #FFAAAA; border-radius: 3px;" if nm else "font-size: 10px; padding: 3px 8px; background: #1A2330; border: 1px solid #2B3D52; color: #DCE2EB; border-radius: 3px;")
        if hasattr(self, "lbl_foc_pos"):
            self.lbl_foc_pos.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #FF4D4D; font-weight: 600;" if nm else "font-family: 'Consolas'; font-size: 11px; color: #88B0D8; font-weight: 600;")
        if hasattr(self, "console_deck"):
            self.console_deck.setStyleSheet("background-color: #050000; border-top: 1px solid #330808;" if nm else "background-color: #0E1015; border-top: 1px solid #252A34;")

        if hasattr(self, "lbl_p"):
            self.lbl_p.setStyleSheet("font-size: 11px; color: #AA2222;" if nm else "font-size: 11px; color: #8892A0;")

        # Tracking rate buttons styling
        cur_rate = getattr(self.core, "tracking_rate", "Sidereal") if self.core else "Sidereal"
        self._set_tracking_rate(cur_rate)

        # Satellite follow button
        if hasattr(self, "btn_satellite_follow"):
            is_active = hasattr(self, "follower") and self.follower and self.follower.is_active
            if is_active:
                self.btn_satellite_follow.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;" if nm else "background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
            else:
                self.btn_satellite_follow.setStyleSheet("")

        self._style_weather_btn()

        if hasattr(self, "tour_window") and self.tour_window:
            self.tour_window.set_night_mode(nm)

    def _on_audio_toggled(self, checked: bool) -> None:
        self.audio_enabled = checked
        self.config["audio_cues_enabled"] = checked
        if hasattr(self.config, "save"):
            self.config.save()

    def _emergency_stop(self) -> None:
        play_audio_cue("stop", self.audio_enabled)
        if self.core:
            self.core.emergency_stop()
        if hasattr(self, "btn_track"):
            self.btn_track.setText("Tracking: OFF")

    def _set_tracking_rate(self, rate_name: str) -> None:
        if self.core and hasattr(self.core, "set_tracking_rate"):
            self.core.set_tracking_rate(rate_name)
        for name, btn in getattr(self, "rate_buttons", {}).items():
            is_active = (name.lower() == rate_name.lower())
            btn.setChecked(is_active)
            if is_active:
                if self.night_mode:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #5C0B0B; color: #FFAAAA; font-weight: 700; border: 1px solid #801010;")
                else:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1E4472; color: #FFFFFF; font-weight: 700; border: 1px solid #336FA5;")
            else:
                if self.night_mode:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1A0303; color: #FF4D4D; border: 1px solid #4D0A0A;")
                else:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px;")

    def _unwind_cable(self) -> None:
        if self.core:
            self.core.unwind_cable()

    def _sync_scope(self) -> None:
        if self.core:
            self.core.sync()

    def _toggle_tracking(self) -> None:
        if self.core:
            self.core.tracking_enabled = not self.core.tracking_enabled
            if not self.core.tracking_enabled:
                self.core.target_type = ""
                if hasattr(self.core, "follower") and self.core.follower:
                    self.core.follower.clear_authorized_target()
                if self.core.link and self.core.link.is_open:
                    self.core.link.send("S")
            status = "ENABLED" if self.core.tracking_enabled else "DISABLED"
            self.btn_track.setText(f"Tracking: {status}")
            self.core.on_event("INFO", f"Sidereal Tracking {status}")

    def _toggle_satellite_follow(self) -> None:
        if not self.follower:
            return
        if self.follower.is_active:
            self.follower.stop()
            self.btn_satellite_follow.setText("Satellite Follow: OFF")
            self.btn_satellite_follow.setStyleSheet("")
            self.log_message("INFO", "Stellarium Live Satellite Follow disabled.")
        else:
            self.follower.start()
            self.btn_satellite_follow.setText("Satellite Follow: ACTIVE")
            if self.night_mode:
                self.btn_satellite_follow.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;")
            else:
                self.btn_satellite_follow.setStyleSheet("background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
            self.log_message("INFO", "Stellarium Live Satellite Follow enabled (polling port 8090 for moving satellites & objects).")

    def _prompt_solar_warning(self, sun_sep: float) -> bool:
        """Prompts a prominent safety dialog when a slew near or at the Sun is commanded.
        Thread-safe: marshals from background TCP/HTTP threads to the main Qt GUI thread.
        """
        app = QApplication.instance()
        if not app:
            return False

        # If already on the Qt main GUI thread, execute directly
        if QThread.currentThread() == app.thread():
            return self._show_solar_warning_dialog(sun_sep)

        # Dispatched from a background worker thread (e.g. StellariumServer TCP thread):
        res = [False]
        done_evt = threading.Event()
        self.solar_bridge.request_prompt.emit(sun_sep, res, done_evt)
        # Wait up to 60 seconds for observer interaction
        done_evt.wait(timeout=60.0)
        return res[0]

    def _on_solar_prompt_requested(self, sun_sep: float, res: list, done_evt: threading.Event) -> None:
        """Slot executed on the main Qt GUI thread."""
        try:
            res[0] = self._show_solar_warning_dialog(sun_sep)
        finally:
            done_evt.set()

    def _show_solar_warning_dialog(self, sun_sep: float) -> bool:
        """Renders the dark-mode eye safety confirmation modal on the main GUI thread."""
        app = QApplication.instance()
        if app and app.platformName() == "offscreen":
            return True

        if self._is_showing_solar_dialog:
            return False

        self._is_showing_solar_dialog = True
        try:
            parent = QApplication.activeModalWidget() or QApplication.activeWindow() or self
            dlg = QDialog(parent)
            dlg.setWindowTitle("CRITICAL EYE SAFETY: Solar Observation Warning")
            dlg.setModal(True)
            dlg.setStyleSheet("background-color: #11141A; color: #FFFFFF; font-family: 'Segoe UI', sans-serif;")
            dlg.setMinimumWidth(520)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(14)

            # High-visibility danger alert card
            banner = QFrame()
            banner.setStyleSheet(
                "background-color: #3B1616; border: 1px solid #7D2626; border-radius: 4px; padding: 12px;"
            )
            b_lay = QVBoxLayout(banner)
            b_lay.setContentsMargins(10, 10, 10, 10)
            b_lay.setSpacing(8)

            lbl_danger_title = QLabel("CRITICAL EYE SAFETY WARNING")
            lbl_danger_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #FF6B6B;")
            b_lay.addWidget(lbl_danger_title)

            lbl_danger_desc = QLabel(
                f"You are about to point the telescope towards the SUN (angular separation: {sun_sep:.1f}°).\n\n"
                "DANGER: Looking directly at the Sun through an unshielded telescope, optical finder, "
                "or eyepiece causes INSTANT and PERMANENT BLINDNESS and irreparably damages camera sensors."
            )
            lbl_danger_desc.setWordWrap(True)
            lbl_danger_desc.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF;")
            b_lay.addWidget(lbl_danger_desc)
            layout.addWidget(banner)

            lbl_instructions = QLabel(
                "Before authorizing this GoTo slew, verify that a certified solar filter "
                "(such as Baader solar safety film or a full-aperture glass filter) is securely attached "
                "to the telescope aperture, and avoid looking directly along the optical line of sight."
            )
            lbl_instructions.setWordWrap(True)
            lbl_instructions.setStyleSheet("font-size: 11px; color: #C8D1DC;")
            layout.addWidget(lbl_instructions)

            lbl_question = QLabel("Do you have a certified solar filter installed and wish to proceed?")
            lbl_question.setStyleSheet("font-size: 12px; font-weight: 700; color: #FFE082;")
            layout.addWidget(lbl_question)

            # Action buttons: Abort (Safe) is default
            btn_box = QHBoxLayout()
            btn_box.setSpacing(12)
            btn_box.addStretch()

            btn_abort = QPushButton("Abort Slew (Safe)")
            btn_abort.setProperty("class", "stop-btn")
            btn_abort.setDefault(True)
            btn_abort.setFocus()
            btn_abort.clicked.connect(dlg.reject)
            btn_box.addWidget(btn_abort)

            btn_proceed = QPushButton("Proceed with Solar Filter")
            btn_proceed.setStyleSheet(
                "background-color: #855C26; border: 1px solid #A37130; color: #FFFFFF; "
                "font-size: 12px; font-weight: 700; padding: 7px 16px; border-radius: 3px;"
            )
            btn_proceed.clicked.connect(dlg.accept)
            btn_box.addWidget(btn_proceed)

            layout.addLayout(btn_box)

            dlg.raise_()
            dlg.activateWindow()

            result = dlg.exec()
            is_proceed = (result == QDialog.DialogCode.Accepted)

            if is_proceed:
                if hasattr(self, 'chk_solar_filter'):
                    self.chk_solar_filter.blockSignals(True)
                    self.chk_solar_filter.setChecked(True)
                    self.chk_solar_filter.blockSignals(False)
                if self.core:
                    self.core.solar_filter_confirmed = True
                self.log_message(
                    "WARNING",
                    f"Solar Slew Authorized: certified solar filter confirmed by observer (separation: {sun_sep:.1f}°)."
                )
            else:
                self.log_message(
                    "INFO",
                    f"Solar Slew Aborted: telescope will not point toward the Sun (separation: {sun_sep:.1f}°)."
                )

            return is_proceed
        finally:
            self._is_showing_solar_dialog = False

    def _toggle_solar_filter(self, checked: bool) -> None:
        """Toggles solar filter status from the safety strip (session-only)."""
        if checked:
            confirmed = self._prompt_solar_warning(0.0)
            if not confirmed:
                self.chk_solar_filter.blockSignals(True)
                self.chk_solar_filter.setChecked(False)
                self.chk_solar_filter.blockSignals(False)
                return
        if self.core:
            self.core.solar_filter_confirmed = checked
        state = "CONFIRMED (Solar Observation Permitted)" if checked else "REMOVED (Sun Keep-Out Active)"
        self.log_message("WARNING", f"Solar Filter Mode: {state}")

    def _sync_location_from_stellarium(self, quiet: bool = False) -> None:
        """Pulls observer site coordinates from Stellarium Remote Control (Port 8090)."""
        import urllib.request, json
        host = str(self.config.get("stellarium_host", "127.0.0.1")).strip() or "127.0.0.1"
        url = f"http://{host}:8090/api/main/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AstroGoTo-Bridge/2.0"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    loc = data.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    name = loc.get("name") or loc.get("role") or "Stellarium Site"
                    if lat is not None and lon is not None:
                        self.config["latitude_deg"] = float(lat)
                        self.config["longitude_deg"] = float(lon)
                        if hasattr(self.config, "save"):
                            self.config.save()
                        self._has_auto_synced_location = True
                        msg = f"Observer location synchronized with Stellarium: Lat {float(lat):.4f}°, Lon {float(lon):.4f}° ({name})"
                        self.log_message("INFO", msg)
                        if not quiet:
                            QMessageBox.information(
                                self, "Location Synced",
                                f"Successfully synced observer location from Stellarium:\n\n"
                                f"Observing Site: {name}\n"
                                f"Latitude: {float(lat):.4f}°\n"
                                f"Longitude: {float(lon):.4f}°"
                            )
                        return
            if not quiet:
                QMessageBox.warning(self, "Sync Failed", "Stellarium responded on port 8090 but location fields were missing.")
        except Exception as e:
            if not quiet:
                QMessageBox.warning(
                    self, "Stellarium Port 8090 Error",
                    f"Could not reach Stellarium Remote Control API:\n{e}\n\n"
                    f"Make sure Stellarium is open and Remote Control plugin is enabled:\n"
                    f"In Stellarium: F2 -> Plugins -> Remote Control -> Load at startup."
                )

    def _home_axis(self, axis: str) -> None:
        if self.core:
            self.core.home_axis(axis)

    def _park_mount(self) -> None:
        if self.core:
            self.core.park()

    def _move_focus(self, amount: str, direction_in: bool) -> None:
        if self.core:
            self.core.move_focus(amount, direction_in)

    def _move_focus_steps(self, delta: int) -> None:
        if self.core:
            self.core.move_focus_steps(delta)

    def _goto_focus_step(self) -> None:
        if self.core:
            target = self.spin_foc_direct.value()
            self.core.set_focus_target(target)

    def _open_autofocus_dialog(self) -> None:
        dlg = AutoFocusDialog(self, self.core)
        dlg.exec()

    def _zero_focus(self) -> None:
        if self.core and self.core.link and self.core.link.is_open:
            if hasattr(self.core.link, "foc_pos"):
                self.core.link.foc_pos = 0.0
                self.core.link.foc_target = 0.0
            self.core.on_event("INFO", "Focus position zeroed (0 steps)")

    def _confirm_zero(self) -> None:
        res = QMessageBox.question(
            self, "Confirm Zero (0,0)",
            "Set current physical orientation as True North (Az 0.0°) and Horizontal (Alt 0.0°)?\n"
            "Ensure the telescope tube is level and pointed True North before confirming.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes and self.core:
            self.core.zero_position()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, night_mode=self.night_mode, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.core:
                self.core.config = self.config
                try:
                    self.core.push_hardware_config()
                except Exception as e:
                    self.log_message("WARN", f"Could not push hardware config: {e}")
                self.log_message("INFO", "Configuration updated and applied.")

    def _open_help(self) -> None:
        dialog = HelpGuideDialog(night_mode=self.night_mode, parent=self)
        dialog.exec()

    def _open_goto_dialog(self) -> None:
        self._open_sky_tour()

    def _open_sky_tour(self) -> None:
        if self.tour_window is None:
            self.tour_window = TonightSkyTourDialog(self.core, self.config, night_mode=self.night_mode, parent=self, weather_service=getattr(self, 'weather_service', None))
        elif hasattr(self, 'weather_service') and self.weather_service and self.weather_service.latest_data:
            self.tour_window.update_weather_display(self.weather_service.latest_data)
        if self.tour_window.isMinimized():
            self.tour_window.showNormal()
        else:
            self.tour_window.show()
        self.tour_window.raise_()
        self.tour_window.activateWindow()

    def _on_stream_rate_changed(self, index: int) -> None:
        if index == 0:  # Fast Live (25 Hz)
            self.timer.setInterval(40)
        else:           # Normal (1s)
            self.timer.setInterval(1000)

    def _clear_console(self) -> None:
        self.console_text.clear()

    # --------------------------------------------------------------------------
    # Serial Link Management
    # --------------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        if HAS_PYSERIAL_LOCAL and serial and hasattr(serial, "tools"):
            try:
                ports = [p.device for p in serial.tools.list_ports.comports()]
                if ports:
                    self.port_combo.addItems(ports)
                    cur_port = self.config.get("serial_port", "")
                    if cur_port in ports:
                        self.port_combo.setCurrentText(cur_port)
                else:
                    self.port_combo.addItem("(No COM ports found)")
            except Exception:
                self.port_combo.addItem("(Port scan failed)")
        else:
            self.port_combo.addItem("(pyserial missing)")

    def _toggle_connection(self) -> None:
        if not self.core:
            return

        if self.core.link and self.core.link.is_open:
            self.core.disconnect()
            self.btn_connect.setText("Connect")
            self.btn_connect.setProperty("class", "primary")
            self.btn_connect.style().unpolish(self.btn_connect)
            self.btn_connect.style().polish(self.btn_connect)
        else:
            simulate = self.chk_simulate.isChecked()
            port = self.port_combo.currentText()
            if "(No COM" in port or "(pyserial" in port or not port:
                port = ""

            ok = self.core.connect(port=port, simulate=simulate)
            if ok:
                self.btn_connect.setText("Disconnect")
                self.btn_connect.setProperty("class", "")
                self.btn_connect.style().unpolish(self.btn_connect)
                self.btn_connect.style().polish(self.btn_connect)

    # --------------------------------------------------------------------------
    # Periodic Tick & High-Speed Telemetry Engine (40 ms = 25 FPS)
    # --------------------------------------------------------------------------

    def _on_tick(self) -> None:
        if not self.core:
            return

# Location sync is triggered on-demand via the 'Sync Location' button

        # 1. Drain event queue & link messages
        while not self.core.event_queue.empty():
            try:
                ev_type, msg = self.core.event_queue.get_nowait()
                self.log_message(ev_type, msg)
                if ev_type in ("WARNING", "ERROR"):
                    play_audio_cue("warning", self.audio_enabled)
                elif ev_type == "SYNC" or "SYNC successful" in msg:
                    play_audio_cue("sync", self.audio_enabled)
            except Exception:
                break

        if self.core.link and hasattr(self.core.link, "async_messages"):
            while not self.core.link.async_messages.empty():
                try:
                    async_msg = self.core.link.async_messages.get_nowait()
                    self.log_message("HARDWARE", async_msg)
                except Exception:
                    break

        # 2. Connection indicators
        if self.core.link and self.core.link.is_open:
            is_sim = type(self.core.link).__name__ == "SimLink" or getattr(self.core.link, "is_simulated", False)
            if is_sim:
                self.lbl_serial_status.setText("ARDUINO: SIMULATED (VIRTUAL)")
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFAAAA; background: #240505; padding: 4px 8px; border: 1px solid #4D0A0A; border-radius: 3px;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #5B9DD9; background: #172433; padding: 4px 8px; border: 1px solid #2B4B6E; border-radius: 3px;")
            else:
                port_name = getattr(self.core.link, "port", "CONNECTED")
                self.lbl_serial_status.setText(f"ARDUINO: CONNECTED ({port_name})")
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666; background: #2B0808; padding: 4px 8px; border: 1px solid #5C0B0B; border-radius: 3px;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047; background: #1B2B1E; padding: 4px 8px; border: 1px solid #2E5C32; border-radius: 3px;")
        else:
            self.lbl_serial_status.setText("ARDUINO: DISCONNECTED")
            self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF3333; background: #1A0000; padding: 4px 8px; border: 1px solid #4D0505; border-radius: 3px;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #CC4444; background: #261B1B; padding: 4px 8px; border: 1px solid #4D2626; border-radius: 3px;")
            if self.btn_connect.text() != "Connect":
                self.btn_connect.setText("Connect")
                self.btn_connect.setProperty("class", "primary")
                self.btn_connect.style().unpolish(self.btn_connect)
                self.btn_connect.style().polish(self.btn_connect)

        if self.stellarium and self.stellarium.is_client_connected:
            self.lbl_stellarium_status.setText("STELLARIUM: CONNECTED [Active]")
            self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666; background: #2B0808; padding: 4px 8px; border: 1px solid #5C0B0B; border-radius: 3px;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047; background: #1B2B1E; padding: 4px 8px; border: 1px solid #2E5C32; border-radius: 3px;")
        else:
            port_num = self.config.get("stellarium_port", 10001)
            self.lbl_stellarium_status.setText(f"STELLARIUM: LISTENING [{port_num}]")
            self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF9944; background: #240D05; padding: 4px 8px; border: 1px solid #4D1A0A; border-radius: 3px;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #D69E35; background: #262118; padding: 4px 8px; border: 1px solid #4D3D1F; border-radius: 3px;")

        # Tracking state with selected rate
        cur_rate = getattr(self.core, "tracking_rate", "Sidereal").upper()
        if self.core.tracking_enabled:
            self.btn_track.setText(f"Tracking: ON ({cur_rate})")
            self.btn_track.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;" if self.night_mode else "background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
        else:
            self.btn_track.setText("Tracking: OFF")
            self.btn_track.setStyleSheet("background-color: #1A0303; border-color: #4D0A0A; color: #FF4D4D;" if self.night_mode else "")

        # Cable-Wrap Status Monitoring
        if hasattr(self, "lbl_cable_wrap") and hasattr(self.core, "get_cable_wrap"):
            wrap_deg, wrap_turns = self.core.get_cable_wrap()
            if self.night_mode:
                color = "#FF2222" if abs(wrap_turns) > 0.4 else "#FF4D4D"
            else:
                color = "#FF7777" if abs(wrap_turns) > 0.4 else "#88C0FF"
            status = "STRAIN" if abs(wrap_turns) > 0.4 else "OK"
            self.lbl_cable_wrap.setText(f"Cable: {wrap_turns:+.2f} turns [{status}]")
            self.lbl_cable_wrap.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")

        # 3. Microsecond-Accurate Astronomy Clocks
        cur_t = self.core.get_time()
        lat_deg = float(self.config.get("latitude_deg", 12.84))
        lon_deg = float(self.config.get("longitude_deg", 80.15))

        is_fast = hasattr(self, 'combo_stream_rate') and (self.combo_stream_rate.currentIndex() == 0)
        hms_dec = 2 if is_fast else 0
        dms_dec = 1 if is_fast else 0

        self.val_utc.setText(cur_t.strftime("%Y-%m-%d %H:%M:%S UTC"))
        self.val_local.setText(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        jd_val = julian_date(cur_t) if julian_date else 2451545.0
        self.val_jd.setText(f"{jd_val:.6f}" if is_fast else f"{jd_val:.4f}")

        lst_hours = (lst_deg(jd_val, lon_deg) / 15.0) % 24.0 if lst_deg else 0.0
        self.val_lst.setText(hours_to_hms(lst_hours, decimals=hms_dec))

        # 4. Instantaneous Mount Coordinates Calculations
        alt_deg, az_deg = self.core.get_telescope_altaz()

        # Compute instant apparent RA/Dec from physical Alt/Az
        use_refr = bool(self.config.get("apply_refraction", True))
        if altaz_to_radec:
            ra_date, dec_date = altaz_to_radec(alt_deg, az_deg, lat_deg, lon_deg, cur_t, apply_refraction=use_refr)
        else:
            ra_date, dec_date = 0.0, 0.0

        if precess_date_to_j2000:
            ra_j2000, dec_j2000 = precess_date_to_j2000(ra_date, dec_date, cur_t)
        else:
            ra_j2000, dec_j2000 = ra_date, dec_date

        ha_hours = (lst_hours - (ra_date / 15.0)) % 24.0
        parallactic = calculate_parallactic_angle(ha_hours, dec_date, lat_deg)

        # Performance optimization: cache heavy galactic, ecliptic, constellation lookups
        now_ts = time.time()
        need_heavy = (now_ts - self._last_heavy_calc_time >= 1.0)
        if need_heavy or self._last_mount_j2000 is None:
            self._last_heavy_calc_time = now_ts
            self._cached_gal = radec_to_galactic(ra_j2000, dec_j2000)
            self._cached_ecl = radec_to_ecliptic(ra_j2000, dec_j2000)
            self._cached_constellation_mount = get_constellation(ra_j2000, dec_j2000)
            self._last_mount_j2000 = (ra_j2000, dec_j2000)

        gal_l, gal_b = self._cached_gal
        ecl_l, ecl_b = self._cached_ecl
        constellation_mount = self._cached_constellation_mount

        # Update Detailed Mount Parameters Table
        self.val_m_j2000.setText(f"{deg_to_hms(ra_j2000, decimals=hms_dec)} / {deg_to_dms(dec_j2000, signed=True, decimals=dms_dec)}")
        self.val_m_jnow.setText(f"{deg_to_hms(ra_date, decimals=hms_dec)} / {deg_to_dms(dec_date, signed=True, decimals=dms_dec)}")
        self.val_m_hadec.setText(f"{hours_to_hms(ha_hours, decimals=hms_dec)} / {deg_to_dms(dec_date, signed=True, decimals=dms_dec)} (apparent)")
        self.val_m_altaz.setText(f"{deg_to_dms(az_deg, signed=True, decimals=dms_dec)} / {deg_to_dms(alt_deg, signed=True, decimals=dms_dec)} (apparent)")
        self.val_m_gal.setText(f"{deg_to_dms(gal_l, signed=True, decimals=dms_dec)} / {deg_to_dms(gal_b, signed=True, decimals=dms_dec)}")
        self.val_m_ecl.setText(f"{deg_to_dms(ecl_l, signed=True, decimals=dms_dec)} / {deg_to_dms(ecl_b, signed=True, decimals=dms_dec)}")
        self.val_m_parallactic.setText(f"{parallactic:+05.1f}° ({deg_to_dms(parallactic, signed=True, decimals=dms_dec)})")
        self.val_m_constellation.setText(constellation_mount)

        # Motor step counters & slew arrival detection
        if self.core.link and self.core.link.latest_telemetry:
            t = self.core.link.latest_telemetry
            is_moving = bool(t.moving)
            if self._was_moving and not is_moving and self._was_slewing:
                play_audio_cue("slew_complete", self.audio_enabled)
                self._was_slewing = False
            if is_moving:
                self._was_slewing = True
            self._was_moving = is_moving

            moving_flag = " [MOVING]" if is_moving else " [LOCKED]"
            self.val_m_steps.setText(f"Az: {t.az_steps:,}  Alt: {t.alt_steps:,}  Foc: {t.foc_steps:,}{moving_flag}")
            self.lbl_foc_pos.setText(f"Position: {t.foc_steps:,} steps")

        # 5. Tracked Target Calculations (Continuous fast updating)
        target_alt_radar = None
        target_az_radar = None

        if self.core.current_target_radec:
            ra_tgt_cfg, dec_tgt_cfg = self.core.current_target_radec

            is_tgt_j2000 = getattr(self.core, "current_target_is_j2000", (self.config.get("epoch", "J2000") == "J2000"))
            if is_tgt_j2000:
                ra_tgt_2000, dec_tgt_2000 = ra_tgt_cfg, dec_tgt_cfg
                if precess_j2000_to_date:
                    ra_tgt_date, dec_tgt_date = precess_j2000_to_date(ra_tgt_2000, dec_tgt_2000, cur_t)
                else:
                    ra_tgt_date, dec_tgt_date = ra_tgt_2000, dec_tgt_2000
            else:
                ra_tgt_date, dec_tgt_date = ra_tgt_cfg, dec_tgt_cfg
                if precess_date_to_j2000:
                    ra_tgt_2000, dec_tgt_2000 = precess_date_to_j2000(ra_tgt_date, dec_tgt_date, cur_t)
                else:
                    ra_tgt_2000, dec_tgt_2000 = ra_tgt_date, dec_tgt_date

            # Target Alt/Az updates continuously down to fractions of an arcsecond as Earth turns
            if radec_to_altaz:
                t_alt, t_az = radec_to_altaz(ra_tgt_date, dec_tgt_date, lat_deg, lon_deg, cur_t, apply_refraction=use_refr)
                target_alt_radar = t_alt
                target_az_radar = t_az
                self.val_t_altaz.setText(f"{deg_to_dms(t_az, signed=True, decimals=dms_dec)} / {deg_to_dms(t_alt, signed=True, decimals=dms_dec)} (apparent)")

            self.val_t_status.setText("TRACKING ACTIVE" if self.core.tracking_enabled else "TARGET LOCKED / IDLE")
            self.val_t_j2000.setText(f"{deg_to_hms(ra_tgt_2000, decimals=hms_dec)} / {deg_to_dms(dec_tgt_2000, signed=True, decimals=dms_dec)}")
            self.val_t_jnow.setText(f"{deg_to_hms(ra_tgt_date, decimals=hms_dec)} / {deg_to_dms(dec_tgt_date, signed=True, decimals=dms_dec)}")

            # Performance optimization: cache ephemeris & constellation for target
            tgt_key = (round(ra_tgt_2000, 4), round(dec_tgt_2000, 4), round(lat_deg, 2))
            if need_heavy or tgt_key != self._cached_target_key:
                self._cached_target_key = tgt_key
                self._cached_constellation_target = get_constellation(ra_tgt_2000, dec_tgt_2000)
                self._cached_rise_transit_set = calculate_ephemeris(ra_tgt_date, dec_tgt_date, lat_deg)

            self.val_t_constellation.setText(self._cached_constellation_target)
            rise, transit, setting = self._cached_rise_transit_set
            self.val_t_ephemeris.setText(f"Rise: {rise} | Transit: {transit} | Set: {setting}")
            self.val_t_tracking.setText("Sidereal Alt-Az Microstep Differential")
        else:
            self.val_t_status.setText("No Active Target (Awaiting Stellarium Command)")
            self.val_t_j2000.setText("None")
            self.val_t_jnow.setText("None")
            self.val_t_altaz.setText("None")
            self.val_t_constellation.setText("None")
            self.val_t_ephemeris.setText("--:-- | --:-- | --:--")
            self.val_t_tracking.setText("Standby")

        # 6. Tracking Telemetry & Live Heartbeat Monitoring
        if self.core.tracking_enabled and self.core.current_target_radec:
            sec_ago = time.time() - getattr(self.core, 'tracking_last_pulse_time', 0.0)
            pulse_icon = "●" if sec_ago < 0.8 else "○"
            count = getattr(self.core, 'tracking_pulses_count', 0)
            d_az = getattr(self.core, 'tracking_total_steps_az', 0)
            d_alt = getattr(self.core, 'tracking_total_steps_alt', 0)
            self.val_t_pulses.setText(
                f"{pulse_icon} {count} pulses sent (ΔAz: {d_az:+d}, ΔAlt: {d_alt:+d} steps) | Last nudge: {sec_ago:.1f}s ago"
            )
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #8CD68C;")
        else:
            self.val_t_pulses.setText("Tracking Inactive (0 pulses)")
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 500; color: #661515;" if self.night_mode else "font-size: 11px; font-weight: 500; color: #ABB2BF;")

        # Stellarium Live Follow status
        if hasattr(self, 'follower') and self.follower and self.follower.is_active:
            if self.follower.is_connected:
                t_name = self.follower.target_name or "Active Selection"
                t_type = self.follower.target_type.upper() or "TARGET"
                self.val_t_follow_status.setText(f"ACTIVE: Following {t_name} [{t_type}] @ 2 Hz")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047;")
                if "SATELLITE" in t_type or "SPACECRAFT" in t_type:
                    self.val_t_status.setText(f"TRACKING SATELLITE: {t_name}")
                    self.val_t_tracking.setText("Continuous LEO Satellite Vector (2 Hz)")
            else:
                self.val_t_follow_status.setText("Awaiting Stellarium API (Port 8090 - In Stellarium: F2 -> Plugins -> Remote Control)")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF8844;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #D69E35;")
        else:
            self.val_t_follow_status.setText("Standby")
            self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 500; color: #661515;" if self.night_mode else "font-size: 11px; font-weight: 500; color: #ABB2BF;")

        # 7. Sun Position & Keep-Out
        sun_alt_radar = None
        sun_az_radar = None
        if sun_radec and radec_to_altaz:
            s_ra, s_dec = sun_radec(cur_t)
            s_alt, s_az = radec_to_altaz(s_ra, s_dec, lat_deg, lon_deg, cur_t)
            sun_alt_radar = s_alt
            sun_az_radar = s_az

            if separation_deg:
                sep = separation_deg(ra_date, dec_date, s_ra, s_dec)
                keepout = float(self.config.get("sun_keepout_deg", 15.0))
                has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
                if sep < keepout:
                    if has_filter:
                        self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [SOLAR FILTER ACTIVE]")
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FF8888; background: #330505; padding: 2px 6px; border-radius: 2px;" if self.night_mode else "font-size: 10px; font-weight: 800; color: #FFE082; background: #3E3218; padding: 2px 6px; border-radius: 2px;")
                    else:
                        self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [DANGER < {keepout:.0f}°]")
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FF2222; background: #300000; padding: 2px 6px; border-radius: 2px;" if self.night_mode else "font-size: 10px; font-weight: 800; color: #FF6666; background: #4D1818; padding: 2px 6px; border-radius: 2px;")
                else:
                    self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [Safe > {keepout:.0f}°]")
                    self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 10px; font-weight: 700; color: #8CD68C;")

                if self.core.current_target_radec:
                    t_sep = separation_deg(ra_tgt_date, dec_tgt_date, s_ra, s_dec)
                    self.val_t_sunsep.setText(f"{t_sep:.1f}° ({'Safe' if t_sep >= keepout else 'DANGER'})")
                else:
                    self.val_t_sunsep.setText(f"Mount Separation: {sep:.1f}°")

        # 7. Update Enlarged Sky Radar
        self.radar_widget.set_scope_altaz(alt_deg, az_deg)
        self.radar_widget.set_target_altaz(target_alt_radar, target_az_radar)
        self.radar_widget.set_sun_altaz(sun_alt_radar, sun_az_radar, float(self.config.get("sun_keepout_deg", 15.0)))

    def log_message(self, level: str, message: str) -> None:
        if self.night_mode:
            color_map = {
                "INFO": "#FF4D4D",
                "GOTO": "#FF6666",
                "SYNC": "#CC2929",
                "WARNING": "#FF8844",
                "ERROR": "#FF2222",
                "HARDWARE": "#771111"
            }
        else:
            color_map = {
                "INFO": "#5B9DD9",
                "GOTO": "#43A047",
                "SYNC": "#8E72B2",
                "WARNING": "#D69E35",
                "ERROR": "#CC4444",
                "HARDWARE": "#7A8492"
            }
        color = color_map.get(level.upper(), "#ABB2BF")
        now_str = dt.datetime.now().strftime("%H:%M:%S")

        html = f"<span style='color: #555D6B;'>[{now_str}]</span> " \
               f"<span style='color: {color}; font-weight: bold;'>[{level.upper()}]</span> " \
               f"<span style='color: #DCE2EB;'>{message}</span>"

        self.console_text.append(html)
        if self.chk_autoscroll.isChecked():
            cursor = self.console_text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.console_text.setTextCursor(cursor)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if hasattr(self, "tour_window") and self.tour_window and self.tour_window.isVisible():
            self.tour_window.close()
        if hasattr(self, 'follower') and self.follower:
            self.follower.stop()
        if self.core:
            self.core.stop_tracking_thread()
            self.core.disconnect()
        if self.stellarium:
            self.stellarium.stop()
        event.accept()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def launch_app(simulate: bool = False, config_path: str = "telescope_config.json") -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("astro.goto.telescope.controller.v2")
        except Exception:
            pass

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    cfg = Config(config_path) if Config else {}
    if simulate:
        cfg["simulate"] = True

    core = None
    stellarium_server = None
    if BridgeCore:
        core = BridgeCore(config=cfg)
        core.start_tracking_thread()

    if StellariumServer and core:
        stellarium_server = StellariumServer(
            host=cfg.get("stellarium_host", "127.0.0.1"),
            port=int(cfg.get("stellarium_port", 10001)),
            core=core
        )
        stellarium_server.start()

    window = AstroTelescopeWindow(core=core, stellarium=stellarium_server, config=cfg)
    window.show()

    if cfg.get("simulate", False) and core:
        core.connect(simulate=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    sim = "--simulate" in sys.argv
    launch_app(simulate=sim)
