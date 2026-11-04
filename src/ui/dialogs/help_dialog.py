"""
help_dialog.py
Exhaustive user manual and documentation dialog.
"""

from __future__ import annotations
from typing import Optional
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit, QPushButton, QWidget
)
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE

class HelpGuideDialog(QDialog):
    """Exhaustive user guide and project documentation dialog."""

    def __init__(self, night_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.night_mode = night_mode
        self.setWindowTitle("Custom GoTo Telescope Controller - User Manual & Technical Guide")
        self.resize(800, 660)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)

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
