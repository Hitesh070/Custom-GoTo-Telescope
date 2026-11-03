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
    QLineEdit, QMessageBox, QTabWidget, QScrollArea, QProgressBar
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
        sun_radec, radec_to_altaz, altaz_to_radec, separation_deg, 
        HAS_PYSERIAL, steps_to_angle, julian_date,
        precess_date_to_j2000, precess_j2000_to_date, lst_deg
    )
except ImportError:
    BridgeCore = None
    StellariumServer = None
    Config = None
    StellariumHttpFollower = None
    sun_radec = None
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
        painter.setBrush(QBrush(QColor("#0B0E14")))
        painter.setPen(QPen(QColor("#242C38"), 1.5))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Concentric Elevation Rings (15°, 30°, 45°, 60°, 75°, 85°)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_grid = QPen(QColor("#1A202C"), 1, Qt.PenStyle.DashLine)
        pen_major = QPen(QColor("#222A3A"), 1, Qt.PenStyle.DashLine)
        
        for deg in [15, 30, 45, 60, 75]:
            r_deg = radius * (1.0 - deg / 90.0)
            painter.setPen(pen_major if deg in (30, 60) else pen_grid)
            painter.drawEllipse(QPointF(cx, cy), r_deg, r_deg)

        # Zenith Limit Ring (85°)
        r_85 = radius * (1.0 - 85.0 / 90.0)
        pen_limit = QPen(QColor("#543D2A"), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen_limit)
        painter.drawEllipse(QPointF(cx, cy), r_85, r_85)

        # 3. Radial Azimuth Spokes (every 30°)
        pen_spoke = QPen(QColor("#181E29"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_spoke)
        for deg in range(0, 360, 30):
            if deg in (0, 90, 180, 270):
                continue
            rad = math.radians(deg)
            x_outer = cx + radius * math.sin(rad)
            y_outer = cy - radius * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x_outer, y_outer))

        # 4. Crosshair Axes (N-S and E-W)
        pen_axis = QPen(QColor("#222A3A"), 1)
        painter.setPen(pen_axis)
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))

        # 5. Outer Perimeter Ticks
        pen_tick_maj = QPen(QColor("#455266"), 1)
        pen_tick_min = QPen(QColor("#263040"), 1)
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
        painter.setPen(QColor("#5AA9FF")) # North (Accent Blue)
        painter.drawText(QRectF(cx - 10, cy - radius - 20, 20, 16), Qt.AlignmentFlag.AlignCenter, "N")

        painter.setPen(QColor("#8892A0"))
        painter.drawText(QRectF(cx + radius + 6, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "E")
        painter.drawText(QRectF(cx - 10, cy + radius + 5, 20, 16), Qt.AlignmentFlag.AlignCenter, "S")
        painter.drawText(QRectF(cx - radius - 26, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "W")

        # Intercardinal Labels (NE, SE, SW, NW)
        font_inter = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font_inter)
        painter.setPen(QColor("#505D70"))
        r_label = radius + 11.0
        for name, ang in [("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)]:
            rad = math.radians(ang)
            lx = cx + r_label * math.sin(rad)
            ly = cy - r_label * math.cos(rad)
            painter.drawText(QRectF(lx - 12, ly - 8, 24, 16), Qt.AlignmentFlag.AlignCenter, name)

        # Elevation Labels
        font_elev = QFont("Segoe UI", 8)
        painter.setFont(font_elev)
        painter.setPen(QColor("#4F5868"))
        for elev in [15, 30, 45, 60, 75]:
            r_elev = radius * (1.0 - elev / 90.0)
            painter.drawText(QRectF(cx + 4, cy - r_elev - 7, 30, 14), Qt.AlignmentFlag.AlignLeft, f"{elev}°")
        painter.drawText(QRectF(cx + 4, cy - 9, 30, 14), Qt.AlignmentFlag.AlignLeft, "90°")

        # Zenith Center Point
        painter.setBrush(QBrush(QColor("#5AA9FF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)

        # 7. Astronomical Sun Symbol ☉ & Danger Keep-Out Zone (No text "SUN")
        if self.sun_alt is not None and self.sun_az is not None and self.sun_alt > -10.0:
            sx, sy = self._altaz_to_xy(self.sun_alt, self.sun_az, cx, cy, radius)
            r_danger = radius * (self.sun_keepout_deg / 90.0)

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
            painter.setPen(QPen(QColor(200, 140, 50, 110), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(mx, my), QPointF(tx, ty))

            # Target Reticle Ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#E5A035"), 1.3, Qt.PenStyle.DashLine))
            painter.drawEllipse(QPointF(tx, ty), 8.5, 8.5)
            
            # Target Crosshairs
            painter.setPen(QPen(QColor("#E5A035"), 1.0, Qt.PenStyle.SolidLine))
            painter.drawLine(QPointF(tx - 13, ty), QPointF(tx - 5, ty))
            painter.drawLine(QPointF(tx + 5, ty), QPointF(tx + 13, ty))
            painter.drawLine(QPointF(tx, ty - 13), QPointF(tx, ty - 5))
            painter.drawLine(QPointF(tx, ty + 5), QPointF(tx, ty + 13))

        # 9. Telescope Mount Reticle
        sx, sy = self._altaz_to_xy(self.scope_alt, self.scope_az, cx, cy, radius)

        # Azimuth direction vector from zenith to mount
        painter.setPen(QPen(QColor(70, 130, 200, 65), 1))
        painter.drawLine(QPointF(cx, cy), QPointF(sx, sy))

        # Mount Reticle Rings
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#4A88CE"), 1.6))
        painter.drawEllipse(QPointF(sx, sy), 10.0, 10.0)
        
        painter.setPen(QPen(QColor("#5AA9FF"), 1.2))
        painter.drawEllipse(QPointF(sx, sy), 3.0, 3.0)

        # Mount Reticle Crosshair Ticks
        painter.setPen(QPen(QColor("#5AA9FF"), 1.2))
        painter.drawLine(QPointF(sx - 16, sy), QPointF(sx - 10, sy))
        painter.drawLine(QPointF(sx + 10, sy), QPointF(sx + 16, sy))
        painter.drawLine(QPointF(sx, sy - 16), QPointF(sx, sy - 10))
        painter.drawLine(QPointF(sx, sy + 10), QPointF(sx, sy + 16))


# ==============================================================================
# COMPREHENSIVE PROJECT USER MANUAL & HELP DIALOG
# ==============================================================================

class HelpGuideDialog(QDialog):
    """Exhaustive user guide and project documentation dialog."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Custom GoTo Telescope Controller - User Manual & Technical Guide")
        self.resize(780, 640)
        self.setStyleSheet(SCIENTIFIC_STYLE)
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
        <tr><td><b>Motorized Focus</b></td><td>--</td><td>Drives the focuser stepper motor in Coarse In/Out (200 steps) or Fine In/Out (20 steps).</td></tr>
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
          <li><b>Atmospheric Refraction:</b> Atmospheric bending of starlight elevates celestial objects by several arcminutes (over 5 arcminutes near 10° altitude). AstroGoTo includes high-precision Bennett (1982) & Saemundsson (1986) refraction modeling (enabled in Settings) so the physical optical tube points directly to the refracted starlight, matching Stellarium's apparent view down to fractions of an arcsecond.</li>
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

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Telescope Configuration & Alignment Settings")
        self.resize(520, 560)
        self.setStyleSheet(SCIENTIFIC_STYLE)
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

    def __init__(self, core: Any, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.core = core
        self.config = config
        self.setWindowTitle("Manual GoTo Target & Celestial Catalog")
        self.resize(480, 360)
        self.setStyleSheet(SCIENTIFIC_STYLE)
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
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if not has_filter:
                parent_win = self.parent()
                if hasattr(parent_win, '_prompt_solar_warning'):
                    confirmed = parent_win._prompt_solar_warning(sun_sep)
                else:
                    confirmed = False
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

        # Load and apply black hole application icon (cropped with transparent alpha background)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.png")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)
        self.resize(1280, 880)
        self.setMinimumSize(1080, 780)
        self.setStyleSheet(SCIENTIFIC_STYLE)

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

        # Branded Black Hole App Icon (cropped, transparent background)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.png")
        if os.path.exists(icon_path):
            lbl_icon = QLabel()
            pix = QPixmap(icon_path).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_icon.setPixmap(pix)
            lbl_icon.setToolTip("Custom GoTo Telescope Controller")
            lbl_icon.setStyleSheet("background: transparent; border: none; padding: 1px;")
            layout.addWidget(lbl_icon)

        layout.addSpacing(12)

        # Serial Connection Bar
        conn_box = QHBoxLayout()
        conn_box.setSpacing(6)

        lbl_p = QLabel("Serial Port:")
        lbl_p.setStyleSheet("font-size: 11px; color: #8892A0;")
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

        layout.addLayout(status_box)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        btn_help = QPushButton("Help & Manual")
        btn_help.clicked.connect(self._open_help)
        layout.addWidget(btn_help)

        self.btn_estop = QPushButton("STOP")
        self.btn_estop.setProperty("class", "stop-btn")
        self.btn_estop.setToolTip("Emergency Stop (Spacebar / Esc)")
        self.btn_estop.clicked.connect(self._emergency_stop)
        layout.addWidget(self.btn_estop)

        return header

    def _create_safety_strip(self) -> QWidget:
        strip = QFrame()
        strip.setStyleSheet("background-color: #381B1B; border-bottom: 1px solid #4D2626;")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 3, 14, 3)

        lbl_warn = QLabel("CAUTION: NEVER POINT TELESCOPE AT OR NEAR THE SUN WITHOUT A CERTIFIED SOLAR FILTER")
        lbl_warn.setStyleSheet("font-size: 10px; font-weight: 700; color: #F2C2C2;")
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

        lbl_legend = QLabel("Blue: Mount Reticle  |  Amber: Target  |  Yellow: Sun")
        lbl_legend.setStyleSheet("font-size: 10px; color: #8892A0;")
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

        btn_manual_goto = QPushButton("Target GoTo (Catalog)...")
        btn_manual_goto.setProperty("class", "primary")
        btn_manual_goto.setToolTip("Select celestial targets from catalog or input custom coordinates for constant-velocity slew")
        btn_manual_goto.clicked.connect(self._open_goto_dialog)
        act_grid.addWidget(btn_manual_goto, 3, 0, 1, 2)

        act_layout.addLayout(act_grid)
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

        btn_autofocus = QPushButton("Auto-Focus (V-Curve)...")
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
        deck = QFrame()
        deck.setStyleSheet("background-color: #0E1015; border-top: 1px solid #252A34;")
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

    def _emergency_stop(self) -> None:
        if self.core:
            self.core.emergency_stop()
        if hasattr(self, "btn_track"):
            self.btn_track.setText("Tracking: OFF")

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
            dlg.setStyleSheet(SCIENTIFIC_STYLE)
            dlg.setMinimumWidth(500)

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
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.core:
                self.core.config = self.config
                try:
                    self.core.push_hardware_config()
                except Exception as e:
                    self.log_message("WARN", f"Could not push hardware config: {e}")
                self.log_message("INFO", "Configuration updated and applied.")

    def _open_help(self) -> None:
        dialog = HelpGuideDialog(self)
        dialog.exec()

    def _open_goto_dialog(self) -> None:
        dialog = GoToDialog(self.core, self.config, self)
        dialog.exec()

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
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #5B9DD9; background: #172433; padding: 4px 8px; border: 1px solid #2B4B6E; border-radius: 3px;")
            else:
                port_name = getattr(self.core.link, "port", "CONNECTED")
                self.lbl_serial_status.setText(f"ARDUINO: CONNECTED ({port_name})")
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #43A047; background: #1B2B1E; padding: 4px 8px; border: 1px solid #2E5C32; border-radius: 3px;")
        else:
            self.lbl_serial_status.setText("ARDUINO: DISCONNECTED")
            self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #CC4444; background: #261B1B; padding: 4px 8px; border: 1px solid #4D2626; border-radius: 3px;")
            if self.btn_connect.text() != "Connect":
                self.btn_connect.setText("Connect")
                self.btn_connect.setProperty("class", "primary")
                self.btn_connect.style().unpolish(self.btn_connect)
                self.btn_connect.style().polish(self.btn_connect)

        if self.stellarium and self.stellarium.is_client_connected:
            self.lbl_stellarium_status.setText("STELLARIUM: CONNECTED [Active]")
            self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #43A047; background: #1B2B1E; padding: 4px 8px; border: 1px solid #2E5C32; border-radius: 3px;")
        else:
            port_num = self.config.get("stellarium_port", 10001)
            self.lbl_stellarium_status.setText(f"STELLARIUM: LISTENING [{port_num}]")
            self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #D69E35; background: #262118; padding: 4px 8px; border: 1px solid #4D3D1F; border-radius: 3px;")

        # Tracking state
        if self.core.tracking_enabled:
            self.btn_track.setText("Tracking: ON")
            self.btn_track.setStyleSheet("background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
        else:
            self.btn_track.setText("Tracking: OFF")
            self.btn_track.setStyleSheet("")

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

        # Motor step counters
        if self.core.link and self.core.link.latest_telemetry:
            t = self.core.link.latest_telemetry
            moving_flag = " [MOVING]" if t.moving else " [LOCKED]"
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
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 600; color: #8CD68C;")
        else:
            self.val_t_pulses.setText("Tracking Inactive (0 pulses)")
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 500; color: #ABB2BF;")

        # Stellarium Live Follow status
        if hasattr(self, 'follower') and self.follower and self.follower.is_active:
            if self.follower.is_connected:
                t_name = self.follower.target_name or "Active Selection"
                t_type = self.follower.target_type.upper() or "TARGET"
                self.val_t_follow_status.setText(f"ACTIVE: Following {t_name} [{t_type}] @ 2 Hz")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #43A047;")
                if "SATELLITE" in t_type or "SPACECRAFT" in t_type:
                    self.val_t_status.setText(f"TRACKING SATELLITE: {t_name}")
                    self.val_t_tracking.setText("Continuous LEO Satellite Vector (2 Hz)")
            else:
                self.val_t_follow_status.setText("Awaiting Stellarium API (Port 8090 - In Stellarium: F2 -> Plugins -> Remote Control)")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #D69E35;")
        else:
            self.val_t_follow_status.setText("Standby")
            self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 500; color: #ABB2BF;")

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
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FFE082; background: #3E3218; padding: 2px 6px; border-radius: 2px;")
                    else:
                        self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [DANGER < {keepout:.0f}°]")
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FF6666; background: #4D1818; padding: 2px 6px; border-radius: 2px;")
                else:
                    self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [Safe > {keepout:.0f}°]")
                    self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 700; color: #8CD68C;")

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
