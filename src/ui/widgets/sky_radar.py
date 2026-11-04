"""
sky_radar.py
Vector polar sky radar widget rendering celestial coordinates, scope vectors,
targets, and astronomical keep-out zones with hardware-accelerated QPainter.
"""

from __future__ import annotations
import math
from typing import Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPainter
from PyQt6.QtWidgets import QWidget


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
        bg_col = QColor("#000000") if self.night_mode else QColor("#090d14")
        border_col = QColor("#3d0808") if self.night_mode else QColor("#222c3d")
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, 1.5))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 2. Concentric Elevation Rings (15°, 30°, 45°, 60°, 75°, 85°)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_grid = QPen(QColor("#240404") if self.night_mode else QColor("#161f2e"), 1, Qt.PenStyle.DashLine)
        pen_major = QPen(QColor("#3d0808") if self.night_mode else QColor("#1e293b"), 1, Qt.PenStyle.DashLine)

        for deg in [15, 30, 45, 60, 75]:
            r_deg = radius * (1.0 - deg / 90.0)
            painter.setPen(pen_major if deg in (30, 60) else pen_grid)
            painter.drawEllipse(QPointF(cx, cy), r_deg, r_deg)

        # Zenith Limit Ring (85°)
        r_85 = radius * (1.0 - 85.0 / 90.0)
        pen_limit = QPen(QColor("#661010") if self.night_mode else QColor("#543d2a"), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen_limit)
        painter.drawEllipse(QPointF(cx, cy), r_85, r_85)

        # 3. Radial Azimuth Spokes (every 30°)
        pen_spoke = QPen(QColor("#1f0404") if self.night_mode else QColor("#141a24"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_spoke)
        for deg in range(0, 360, 30):
            if deg in (0, 90, 180, 270):
                continue
            rad = math.radians(deg)
            x_outer = cx + radius * math.sin(rad)
            y_outer = cy - radius * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x_outer, y_outer))

        # 4. Crosshair Axes (N-S and E-W)
        pen_axis = QPen(QColor("#330606") if self.night_mode else QColor("#1e293b"), 1)
        painter.setPen(pen_axis)
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))

        # 5. Outer Perimeter Ticks
        pen_tick_maj = QPen(QColor("#5e0d0d") if self.night_mode else QColor("#475569"), 1)
        pen_tick_min = QPen(QColor("#2e0505") if self.night_mode else QColor("#273244"), 1)
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
        painter.setPen(QColor("#ff3333") if self.night_mode else QColor("#38bdf8")) # North
        painter.drawText(QRectF(cx - 10, cy - radius - 20, 20, 16), Qt.AlignmentFlag.AlignCenter, "N")

        painter.setPen(QColor("#aa2222") if self.night_mode else QColor("#8b949e"))
        painter.drawText(QRectF(cx + radius + 6, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "E")
        painter.drawText(QRectF(cx - 10, cy + radius + 5, 20, 16), Qt.AlignmentFlag.AlignCenter, "S")
        painter.drawText(QRectF(cx - radius - 26, cy - 8, 20, 16), Qt.AlignmentFlag.AlignCenter, "W")

        # Intercardinal Labels (NE, SE, SW, NW)
        font_inter = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font_inter)
        painter.setPen(QColor("#661515") if self.night_mode else QColor("#475569"))
        r_label = radius + 11.0
        for name, ang in [("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)]:
            rad = math.radians(ang)
            lx = cx + r_label * math.sin(rad)
            ly = cy - r_label * math.cos(rad)
            painter.drawText(QRectF(lx - 12, ly - 8, 24, 16), Qt.AlignmentFlag.AlignCenter, name)

        # Elevation Labels
        font_elev = QFont("Segoe UI", 8)
        painter.setFont(font_elev)
        painter.setPen(QColor("#661414") if self.night_mode else QColor("#475569"))
        for elev in [15, 30, 45, 60, 75]:
            r_elev = radius * (1.0 - elev / 90.0)
            painter.drawText(QRectF(cx + 4, cy - r_elev - 7, 30, 14), Qt.AlignmentFlag.AlignLeft, f"{elev}°")
        painter.drawText(QRectF(cx + 4, cy - 9, 30, 14), Qt.AlignmentFlag.AlignLeft, "90°")

        # Zenith Center Point
        painter.setBrush(QBrush(QColor("#ff2222") if self.night_mode else QColor("#38bdf8")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 2, 2)

        # 7. Astronomical Sun Symbol ☉ & Danger Keep-Out Zone
        if self.sun_alt is not None and self.sun_az is not None and self.sun_alt > -10.0:
            sx, sy = self._altaz_to_xy(self.sun_alt, self.sun_az, cx, cy, radius)
            r_danger = radius * (self.sun_keepout_deg / 90.0)

            if self.night_mode:
                painter.setPen(QPen(QColor(160, 20, 20, 140), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(100, 10, 10, 25)))
                painter.drawEllipse(QPointF(sx, sy), r_danger, r_danger)

                painter.setPen(QPen(QColor(140, 15, 15, 80), 1))
                painter.setBrush(QBrush(QColor(90, 10, 10, 30)))
                painter.drawEllipse(QPointF(sx, sy), 9.0, 9.0)

                painter.setPen(QPen(QColor("#991414"), 1.5))
                painter.setBrush(QBrush(QColor("#5c0b0b")))
                painter.drawEllipse(QPointF(sx, sy), 5.5, 5.5)

                painter.setBrush(QBrush(QColor("#cc2222")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(sx, sy), 1.8, 1.8)
            else:
                painter.setPen(QPen(QColor(220, 60, 60, 160), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(220, 50, 50, 18)))
                painter.drawEllipse(QPointF(sx, sy), r_danger, r_danger)

                painter.setPen(QPen(QColor(255, 200, 60, 80), 1))
                painter.setBrush(QBrush(QColor(255, 190, 40, 40)))
                painter.drawEllipse(QPointF(sx, sy), 9.0, 9.0)

                painter.setPen(QPen(QColor("#ffc857"), 1.5))
                painter.setBrush(QBrush(QColor("#e6a820")))
                painter.drawEllipse(QPointF(sx, sy), 5.5, 5.5)

                painter.setBrush(QBrush(QColor("#ffffff")))
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
            target_col = QColor("#ff4d4d") if self.night_mode else QColor("#e5a035")
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
        mount_vec_col = QColor(100, 20, 20, 75) if self.night_mode else QColor(56, 189, 248, 65)
        painter.setPen(QPen(mount_vec_col, 1))
        painter.drawLine(QPointF(cx, cy), QPointF(sx, sy))

        # Mount Reticle Rings
        mount_outer = QColor("#cc2222") if self.night_mode else QColor("#0284c7")
        mount_inner = QColor("#ff4444") if self.night_mode else QColor("#38bdf8")
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
