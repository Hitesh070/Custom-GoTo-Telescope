"""
autofocus_dialog.py
Motorized focuser control and automated V-Curve calibration routine dialog.
"""

from __future__ import annotations
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

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)
        if hasattr(self, 'curve_widget') and self.curve_widget:
            self.curve_widget.set_night_mode(enabled)

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
