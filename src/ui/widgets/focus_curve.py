"""
focus_curve.py
Real-time V-Curve (contrast vs. steps) parabolic focus visualizer widget.
"""

from __future__ import annotations
from typing import Optional, List, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPainter
from PyQt6.QtWidgets import QWidget


class FocusCurveWidget(QWidget):
    """Draws real-time V-Curve (contrast vs. steps) during focus calibration."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(440, 180)
        self.points: List[Tuple[int, float]] = []
        self.best_step: Optional[int] = None
        self.fit_curve: Optional[List[Tuple[float, float]]] = None
        self.night_mode: bool = False

    def set_night_mode(self, enabled: bool) -> None:
        if self.night_mode != enabled:
            self.night_mode = enabled
            self.update()

    def set_data(self, points: List[Tuple[int, float]], best_step: Optional[int] = None,
                 fit_curve: Optional[List[Tuple[float, float]]] = None) -> None:
        self.points = list(points)
        self.best_step = best_step
        self.fit_curve = list(fit_curve) if fit_curve is not None else None
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 46
        margin_right = 24
        margin_top = 26
        margin_bottom = 32

        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        # Background & Frame
        bg_col = QColor("#000000") if self.night_mode else QColor("#090d14")
        border_col = QColor("#4a000a") if self.night_mode else QColor("#222c3d")
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, 1))
        painter.drawRect(0, 0, w, h)

        if len(self.points) < 2:
            painter.setPen(QColor("#aa1122") if self.night_mode else QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "Click 'Start Auto-Focus Routine' to sweep V-curve calibration"
            )
            return

        xs = [float(p[0]) for p in self.points]
        ys = [float(p[1]) for p in self.points]
        if self.best_step is not None:
            xs.append(float(self.best_step))
        if self.fit_curve:
            for fx, fy in self.fit_curve:
                xs.append(fx)
                ys.append(fy)

        min_x, max_x = min(xs), max(xs)
        if max_x == min_x:
            max_x += 1.0

        min_y = 0.0
        max_y = max(100.0, max(ys))
        span_y = max(1.0, max_y - min_y)

        # Draw Grid & Y Ticks (0%, 25%, 50%, 75%, 100%)
        grid_col = QColor("#220407") if self.night_mode else QColor("#161f2e")
        tick_col = QColor("#881122") if self.night_mode else QColor("#4b5563")
        painter.setFont(QFont("Consolas", 8))

        for frac in [0.25, 0.5, 0.75, 1.0]:
            py = margin_top + plot_h - (frac * (100.0 - min_y) / span_y) * plot_h
            painter.setPen(QPen(grid_col, 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(margin_left, py), QPointF(w - margin_right, py))

            # Y-axis percentage tick label
            painter.setPen(tick_col)
            label = f"{int(frac * 100)}%"
            painter.drawText(QRectF(2, py - 7, margin_left - 6, 14), Qt.AlignmentFlag.AlignRight, label)

        # Baseline
        base_py = margin_top + plot_h
        painter.setPen(QPen(border_col, 1))
        painter.drawLine(QPointF(margin_left, base_py), QPointF(w - margin_right, base_py))

        # X Ticks & Labels
        painter.setPen(tick_col)
        painter.drawText(QRectF(margin_left - 10, base_py + 4, 60, 14), Qt.AlignmentFlag.AlignLeft, f"{int(min_x):+d}")
        painter.drawText(QRectF(w - margin_right - 50, base_py + 4, 60, 14), Qt.AlignmentFlag.AlignRight, f"{int(max_x):+d}")

        # Axis label
        lbl_col = QColor("#aa2233") if self.night_mode else QColor("#64748b")
        painter.setPen(lbl_col)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(QRectF(margin_left, base_py + 16, plot_w, 14), Qt.AlignmentFlag.AlignCenter, "Motorized Focus Steps")

        # Function to map (x, y) -> (px, py)
        def map_coords(x_val: float, y_val: float) -> QPointF:
            px = margin_left + ((x_val - min_x) / (max_x - min_x)) * plot_w
            py = margin_top + plot_h - ((y_val - min_y) / span_y) * plot_h
            return QPointF(px, py)

        # 1. Plot Fitted Parabolic Curve (if available)
        if self.fit_curve and len(self.fit_curve) >= 2:
            fit_line_col = QColor("#ff3344") if self.night_mode else QColor("#38bdf8")
            pen_fit = QPen(fit_line_col, 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen_fit)
            for i in range(len(self.fit_curve) - 1):
                p1 = map_coords(self.fit_curve[i][0], self.fit_curve[i][1])
                p2 = map_coords(self.fit_curve[i + 1][0], self.fit_curve[i + 1][1])
                painter.drawLine(p1, p2)

        # 2. Plot Discrete Measurement Line
        line_col = QColor("#ff1122") if self.night_mode else QColor("#0ea5e9")
        pen_line = QPen(line_col, 2)
        painter.setPen(pen_line)
        sample_pts = [map_coords(float(x), float(y)) for x, y in self.points]
        for i in range(len(sample_pts) - 1):
            painter.drawLine(sample_pts[i], sample_pts[i + 1])

        # 3. Plot Sample Nodes (Dots)
        node_col = QColor("#ff4d5a") if self.night_mode else QColor("#10b981")
        for pt in sample_pts:
            painter.setBrush(QBrush(node_col))
            painter.setPen(QPen(bg_col, 1.5))
            painter.drawEllipse(pt, 3.5, 3.5)

        # 4. Plot Optimal Focus (CFZ) Vertex Guideline & Badge
        if self.best_step is not None:
            bx = margin_left + ((float(self.best_step) - min_x) / (max_x - min_x)) * plot_w
            bx = max(float(margin_left), min(float(w - margin_right), bx))

            best_line_col = QColor("#ff0022") if self.night_mode else QColor("#f59e0b")
            painter.setPen(QPen(best_line_col, 1.5, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(bx, margin_top), QPointF(bx, base_py))

            # Badge box
            badge_text = f"Optimal CFZ: {self.best_step:+d}"
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            badge_w = 120
            badge_x = bx - badge_w / 2.0
            badge_x = max(float(margin_left), min(float(w - margin_right - badge_w), badge_x))

            painter.setPen(QPen(best_line_col, 1))
            badge_bg = QColor("#330005") if self.night_mode else QColor("#1f2937")
            painter.setBrush(QBrush(badge_bg))
            painter.drawRoundedRect(QRectF(badge_x, margin_top + 2, badge_w, 18), 3, 3)

            painter.setPen(best_line_col)
            painter.drawText(QRectF(badge_x, margin_top + 2, badge_w, 18), Qt.AlignmentFlag.AlignCenter, badge_text)
