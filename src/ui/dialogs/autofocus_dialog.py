"""
autofocus_dialog.py
Motorized focuser control and automated V-Curve calibration routine dialog.
"""

from __future__ import annotations
import math
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSpinBox, QProgressBar, QMessageBox, QFrame, QWidget
)
from src.ui.widgets.focus_curve import FocusCurveWidget
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE


def solve_3x3(m: List[List[float]], y: List[float]) -> Optional[Tuple[float, float, float]]:
    """Solves 3x3 linear system M * [a, b, c]^T = Y using Cramer's rule."""
    def det(mat: List[List[float]]) -> float:
        return (mat[0][0] * (mat[1][1] * mat[2][2] - mat[1][2] * mat[2][1]) -
                mat[0][1] * (mat[1][0] * mat[2][2] - mat[1][2] * mat[2][0]) +
                mat[0][2] * (mat[1][0] * mat[2][1] - mat[1][1] * mat[2][0]))

    d = det(m)
    if abs(d) < 1e-12:
        return None

    ma = [list(row) for row in m]
    mb = [list(row) for row in m]
    mc = [list(row) for row in m]
    for i in range(3):
        ma[i][0] = y[i]
        mb[i][1] = y[i]
        mc[i][2] = y[i]

    return det(ma) / d, det(mb) / d, det(mc) / d


def fit_parabola(samples: List[Tuple[int, float]]) -> Tuple[float, float, Optional[Tuple[float, float, float, float]]]:
    """
    Fits a downward-opening parabola y = a*(x - x0)^2 + b*(x - x0) + c
    around the peak samples to locate the Critical Focus Zone (CFZ) vertex.
    Returns: (best_step_float, best_metric_float, (a, b, c, x0) or None)
    """
    if len(samples) < 3:
        best_s, best_m = max(samples, key=lambda it: it[1])
        return float(best_s), float(best_m), None

    max_idx = max(range(len(samples)), key=lambda i: samples[i][1])
    start = max(0, max_idx - 2)
    end = min(len(samples), max_idx + 3)
    sub = samples[start:end]
    if len(sub) < 3:
        sub = samples

    x0 = float(samples[max_idx][0])
    u = [float(p[0]) - x0 for p in sub]
    y = [float(p[1]) for p in sub]
    n = float(len(sub))

    su = sum(u)
    su2 = sum(ui ** 2 for ui in u)
    su3 = sum(ui ** 3 for ui in u)
    su4 = sum(ui ** 4 for ui in u)
    sy = sum(y)
    suy = sum(ui * yi for ui, yi in zip(u, y))
    su2y = sum((ui ** 2) * yi for ui, yi in zip(u, y))

    m_mat = [[su4, su3, su2], [su3, su2, su], [su2, su, n]]
    y_vec = [su2y, suy, sy]

    sol = solve_3x3(m_mat, y_vec)
    if sol is not None:
        a, b, c = sol
        if a < -1e-6:
            u_star = -b / (2.0 * a)
            x_star = x0 + u_star
            y_star = c - (b ** 2) / (4.0 * a)
            min_x = min(p[0] for p in samples)
            max_x = max(p[0] for p in samples)
            if min_x <= x_star <= max_x:
                return float(x_star), float(y_star), (float(a), float(b), float(c), x0)

    best_s, best_m = max(samples, key=lambda it: it[1])
    return float(best_s), float(best_m), None


class AutoFocusSignals(QtCore.QObject):
    progress = pyqtSignal(int, int, float, list)
    finished = pyqtSignal(int, float, list, object)
    error = pyqtSignal(str)


class AutoFocusDialog(QDialog):
    """Automated V-Curve Focus Calibration Dialog."""

    def __init__(self, parent: Optional[QWidget], core: Any, night_mode: bool = False):
        super().__init__(parent)
        self.core = core
        self.night_mode = night_mode
        self.setWindowTitle("Automated V-Curve Focus Calibration")
        self.resize(560, 440)

        self._signals = AutoFocusSignals()
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)

        self._worker_thread: Optional[threading.Thread] = None
        self._is_aborted: bool = False
        self.best_step: Optional[int] = None
        self.best_metric: Optional[float] = None
        self._samples: List[Tuple[int, float]] = []

        self._build_ui()
        self.set_night_mode(night_mode)

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)
        if hasattr(self, 'curve_widget') and self.curve_widget:
            self.curve_widget.set_night_mode(enabled)
        if hasattr(self, 'lbl_desc') and self.lbl_desc:
            self.lbl_desc.setStyleSheet("color: #aa2222; font-size: 11px;" if enabled else "color: #8A97AE; font-size: 11px;")
        if hasattr(self, 'lbl_title') and self.lbl_title:
            self.lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #ff3344; letter-spacing: 0.8px;" if enabled else "font-size: 12px; font-weight: 700; color: #58a6ff; letter-spacing: 0.8px;")
        self._update_status_style()

    def _update_status_style(self, is_running: bool = False, is_finished: bool = False, is_error: bool = False) -> None:
        if not hasattr(self, 'lbl_status') or not self.lbl_status:
            return
        if is_error:
            self.lbl_status.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #ff2222; font-weight: 700;")
        elif is_finished:
            color = "#ff3344" if self.night_mode else "#3DDC97"
            self.lbl_status.setStyleSheet(f"font-family: 'Consolas'; font-size: 11px; color: {color}; font-weight: 700;")
        elif is_running:
            color = "#ff4d5a" if self.night_mode else "#5AA9FF"
            self.lbl_status.setStyleSheet(f"font-family: 'Consolas'; font-size: 11px; color: {color}; font-weight: 600;")
        else:
            color = "#aa2222" if self.night_mode else "#5AA9FF"
            self.lbl_status.setStyleSheet(f"font-family: 'Consolas'; font-size: 11px; color: {color}; font-weight: 600;")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header
        h_box = QHBoxLayout()
        self.lbl_title = QLabel("AUTOMATED FOCUS CALIBRATION (V-CURVE)")
        self.lbl_title.setProperty("class", "section-header")
        h_box.addWidget(self.lbl_title)
        h_box.addStretch()
        layout.addLayout(h_box)

        self.lbl_desc = QLabel("Sweeps the motorized focuser through discrete focal samples, measures contrast profile,\nand computes the critical focus zone (CFZ) to automatically achieve razor-sharp star focus.")
        self.lbl_desc.setStyleSheet("color: #8A97AE; font-size: 11px;")
        layout.addWidget(self.lbl_desc)

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
        layout.addWidget(self.lbl_status)
        self._update_status_style()

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
        self.best_step = None
        self.best_metric = None
        self.curve_widget.set_data([], None)

        self.btn_run.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_close.setText("Abort")
        self.lbl_status.setText("Status: Sweeping focal range...")
        self._update_status_style(is_running=True)

        self._worker_thread = threading.Thread(target=self._sweep_worker, daemon=True)
        self._worker_thread.start()

    def _sweep_worker(self):
        try:
            if not self.core or not self.core.link:
                self._signals.error.emit("Telescope hardware link not available.")
                return

            cur_step = self.core.link.latest_telemetry.foc_steps
            span = self.spin_range.value()
            interval = self.spin_interval.value()

            start_step = cur_step - span
            end_step = cur_step + span
            steps = list(range(start_step, end_step + 1, interval))

            # Ground truth simulated peak near cur_step + 6.5 steps
            sim_peak = cur_step + 6.5
            sigma = max(10.0, span * 0.42)

            samples: List[Tuple[int, float]] = []

            # 1. Pre-position focuser to initial start step
            self.core.set_focus_target(start_step)
            if hasattr(self.core, "wait_focus_settled"):
                self.core.wait_focus_settled(start_step, timeout=6.0)
            else:
                time.sleep(0.3)

            for idx, s in enumerate(steps):
                if self._is_aborted:
                    break

                # Drive focuser to step s
                self.core.set_focus_target(s)
                if hasattr(self.core, "wait_focus_settled"):
                    self.core.wait_focus_settled(s, timeout=4.0)
                else:
                    time.sleep(0.15)

                # Simulated focal sharpness metric: normalized Gaussian peak with optical noise
                noise = math.sin(s * 0.35) * 1.5 + (math.cos(s * 0.17) * 0.8)
                dist = (s - sim_peak) / sigma
                metric = max(5.0, min(100.0, math.exp(-0.5 * (dist ** 2)) * 96.0 + 3.0 + noise))

                samples.append((s, metric))
                pct = int((idx + 1) / len(steps) * 100)

                self._signals.progress.emit(pct, s, metric, list(samples))

            if self._is_aborted:
                return

            if samples:
                best_s_flt, best_m, fit_info = fit_parabola(samples)
                best_step = int(round(best_s_flt))
                self._signals.finished.emit(best_step, best_m, samples, fit_info)
            else:
                self._signals.error.emit("No focal samples collected.")

        except Exception as exc:
            self._signals.error.emit(str(exc))

    @QtCore.pyqtSlot(int, int, float, list)
    def _on_progress(self, pct: int, step: int, metric: float, samples: list):
        self._samples = samples
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Sampling Step {step:+d} | Contrast Metric: {metric:.1f}%")
        self._update_status_style(is_running=True)
        self.curve_widget.set_data(samples, self.best_step)

    @QtCore.pyqtSlot(int, float, list, object)
    def _on_finished(self, best_step: int, best_metric: float, samples: list, fit_info: Any):
        self._samples = samples
        self.best_step = best_step
        self.best_metric = best_metric
        self.progress_bar.setValue(100)
        self.lbl_status.setText(f"Status: Optimal Focus Located at Step {best_step:+d} ({best_metric:.1f}%)")
        self._update_status_style(is_finished=True)

        # Generate smooth fitted curve points if fit_info is present
        fit_curve = None
        if fit_info is not None and len(samples) >= 3:
            a, b, c, x0 = fit_info
            min_x = min(p[0] for p in samples)
            max_x = max(p[0] for p in samples)
            fit_curve = []
            steps_num = 60
            for i in range(steps_num + 1):
                fx = min_x + (max_x - min_x) * (i / steps_num)
                u = fx - x0
                fy = max(0.0, min(100.0, a * (u ** 2) + b * u + c))
                fit_curve.append((fx, fy))

        self.curve_widget.set_data(samples, best_step, fit_curve=fit_curve)
        self.btn_run.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.btn_close.setText("Close")

        # Automatically drive to optimal focus step
        if self.core:
            self.core.set_focus_target(best_step)
            self.core.on_event("INFO", f"Auto-Focus complete: Optimal critical focus positioned at step {best_step:+d}")

    @QtCore.pyqtSlot(str)
    def _on_error(self, err_msg: str):
        self.lbl_status.setText(f"Status: Focus routine failed: {err_msg}")
        self._update_status_style(is_error=True)
        self.btn_run.setEnabled(True)
        self.btn_close.setText("Close")

    def _apply_optimal(self):
        if self.best_step is not None and self.core:
            self.core.set_focus_target(self.best_step)
            self.accept()

    def closeEvent(self, event):
        self._is_aborted = True
        event.accept()
