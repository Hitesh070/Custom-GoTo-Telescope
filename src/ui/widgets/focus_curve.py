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
        self.setMinimumSize(420, 160)
        self.points: List[Tuple[int, float]] = []
        self.best_step: Optional[int] = None
        self.night_mode: bool = False

    def set_night_mode(self, enabled: bool) -> None:
        if self.night_mode != enabled:
            self.night_mode = enabled
            self.update()

    def set_data(self, points: List[Tuple[int, float]], best_step: Optional[int] = None) -> None:
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
        bg_col = QColor("#000000") if self.night_mode else QColor("#090d14")
        border_col = QColor("#4a000a") if self.night_mode else QColor("#222c3d")
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, 1))
        painter.drawRect(0, 0, w, h)

        if len(self.points) < 2:
            painter.setPen(QColor("#990014") if self.night_mode else QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "Click 'Start Auto-Focus Routine' to sweep V-curve calibration"
            )
            return

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x == min_x:
            max_x += 1
        if max_y == min_y:
            max_y += 1
        span_y = max(1.0, max_y - min_y)

        # Draw grid lines
        grid_col = QColor("#240404") if self.night_mode else QColor("#161f2e")
        painter.setPen(QPen(grid_col, 1, Qt.PenStyle.DashLine))
        for gy in [0.25, 0.5, 0.75]:
            py = h - margin - gy * (h - 2 * margin)
            painter.drawLine(QPointF(margin, py), QPointF(w - margin, py))

        # Plot curve
        poly_points = []
        for x, y in self.points:
            px = margin + (x - min_x) / (max_x - min_x) * (w - 2 * margin)
            py = h - margin - (y - min_y) / span_y * (h - 2 * margin)
            poly_points.append(QPointF(px, py))

        line_col = QColor("#ff0033") if self.night_mode else QColor("#38bdf8")
        pen_line = QPen(line_col, 2)
        painter.setPen(pen_line)
        for i in range(len(poly_points) - 1):
            painter.drawLine(poly_points[i], poly_points[i + 1])

        # Plot sample nodes
        node_col = QColor("#ff4d5a") if self.night_mode else QColor("#10b981")
        for pt in poly_points:
            painter.setBrush(QBrush(node_col))
            painter.setPen(QPen(bg_col, 1.5))
            painter.drawEllipse(pt, 4.0, 4.0)

        # Plot optimal vertex line
        if self.best_step is not None:
            bx = margin + (self.best_step - min_x) / (max_x - min_x) * (w - 2 * margin)
            best_col = QColor("#ff0022") if self.night_mode else QColor("#f59e0b")
            painter.setPen(QPen(best_col, 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(bx, margin), QPointF(bx, h - margin))
            painter.setPen(best_col)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(bx + 4, margin, 80, 16),
                Qt.AlignmentFlag.AlignLeft,
                f"Best: {self.best_step}"
            )
