"""
test_autofocus.py
Comprehensive unit tests for motorized focus control, parabolic V-curve fitting,
and AutoFocusDialog calibration routine in Custom GoTo.
"""

import sys
import os
import math
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

from telescope_bridge import BridgeCore, Config, SimLink
from src.ui.dialogs.autofocus_dialog import (
    solve_3x3, fit_parabola, AutoFocusDialog, AutoFocusSignals
)
from src.ui.widgets.focus_curve import FocusCurveWidget


class TestAutoFocusMath(unittest.TestCase):
    """Verifies Cramer 3x3 solver and parabolic vertex regression."""

    def test_solve_3x3_basic(self):
        # Identity matrix: I * [1, 2, 3] = [1, 2, 3]
        m = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        y = [1.0, 2.0, 3.0]
        sol = solve_3x3(m, y)
        self.assertIsNotNone(sol)
        self.assertAlmostEqual(sol[0], 1.0)
        self.assertAlmostEqual(sol[1], 2.0)
        self.assertAlmostEqual(sol[2], 3.0)

    def test_solve_3x3_singular(self):
        # Degenerate all-zero matrix
        m = [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0]
        ]
        y = [1.0, 2.0, 3.0]
        sol = solve_3x3(m, y)
        self.assertIsNone(sol)

    def test_fit_parabola_substep_vertex(self):
        # 1. Exact quadratic recovery: y = 100 - 0.05 * (x - 6.0)^2
        samples_quad = [(s, 100.0 - 0.05 * ((s - 6.0) ** 2)) for s in range(-60, 61, 15)]
        s_quad, m_quad, fit_quad = fit_parabola(samples_quad)
        self.assertAlmostEqual(s_quad, 6.0, places=4)
        self.assertAlmostEqual(m_quad, 100.0, places=4)
        self.assertIsNotNone(fit_quad)

        # 2. Gaussian peak recovery
        samples_gauss = []
        for s in range(-60, 61, 15):
            m = math.exp(-0.5 * ((s - 6.0) / 30.0) ** 2) * 98.0
            samples_gauss.append((s, m))

        best_s, best_m, fit_info = fit_parabola(samples_gauss)
        # Discrete best in samples is step 0 or 15 (neither is 6.0)
        discrete_best_s = max(samples_gauss, key=lambda it: it[1])[0]
        self.assertNotEqual(discrete_best_s, 6.0)

        # Parabolic fit recovers vertex within 1.0 step of true 6.0
        self.assertAlmostEqual(best_s, 6.0, delta=1.0)
        self.assertAlmostEqual(best_m, 98.0, delta=2.0)
        self.assertIsNotNone(fit_info)

    def test_fit_parabola_short_or_flat(self):
        # Less than 3 points
        samples = [(10, 50.0), (20, 80.0)]
        s, m, fit = fit_parabola(samples)
        self.assertEqual(s, 20.0)
        self.assertEqual(m, 80.0)
        self.assertIsNone(fit)

        # Truly flat data: all y values equal, no downward curvature possible
        samples_flat = [(-20, 50.0), (-10, 50.0), (0, 50.0), (10, 50.0)]
        s_flat, m_flat, fit_flat = fit_parabola(samples_flat)
        self.assertEqual(s_flat, -20.0)
        self.assertEqual(m_flat, 50.0)
        self.assertIsNone(fit_flat)


class TestFocusCurveWidget(unittest.TestCase):
    """Verifies FocusCurveWidget rendering and theme compliance."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_curve_widget_rendering(self):
        widget = FocusCurveWidget()
        widget.resize(440, 180)

        # 1. Empty state in scientific mode
        pix_sci = QPixmap(440, 180)
        widget.render(pix_sci)
        self.assertFalse(pix_sci.isNull())

        # 2. Populated state with V-curve data and best_step in Night Vision mode
        widget.set_night_mode(True)
        samples = [(-45, 20.0), (-30, 45.0), (-15, 78.0), (0, 96.0), (15, 82.0), (30, 48.0), (45, 18.0)]
        fit_curve = [(float(x), max(0.0, 96.0 - 0.04 * (x ** 2))) for x in range(-45, 46)]
        widget.set_data(samples, best_step=0, fit_curve=fit_curve)

        pix_night = QPixmap(440, 180)
        widget.render(pix_night)
        self.assertFalse(pix_night.isNull())


class TestCoreFocusCommands(unittest.TestCase):
    """Verifies BridgeCore focus targeting, settling, and zeroing."""

    def setUp(self):
        self.cfg = Config()
        self.link = SimLink(self.cfg)
        self.link.open()
        self.core = BridgeCore(self.cfg, self.link)

    def tearDown(self):
        if self.link and self.link.is_open:
            self.link.close()

    def test_focus_targeting_and_settling(self):
        # 1. Zero focus
        res = self.core.zero_focus()
        self.assertTrue(res)
        self.assertEqual(self.link.latest_telemetry.foc_steps, 0)

        # 2. Command target +80 steps
        self.core.set_focus_target(80)
        settled = self.core.wait_focus_settled(80, timeout=3.0)
        self.assertTrue(settled)
        self.assertAlmostEqual(self.link.latest_telemetry.foc_steps, 80, delta=2)

        # 3. Command relative nudge -15 steps
        self.core.move_focus_steps(-15)
        settled = self.core.wait_focus_settled(65, timeout=3.0)
        self.assertTrue(settled)
        self.assertAlmostEqual(self.link.latest_telemetry.foc_steps, 65, delta=2)

        # 4. Zero focus again
        self.core.zero_focus()
        self.assertEqual(self.link.latest_telemetry.foc_steps, 0)


class TestAutoFocusDialog(unittest.TestCase):
    """Verifies AutoFocusDialog workflow, night mode, and thread safety."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.cfg = Config()
        self.link = SimLink(self.cfg)
        self.link.open()
        self.core = BridgeCore(self.cfg, self.link)

    def tearDown(self):
        if self.link and self.link.is_open:
            self.link.close()

    def test_autofocus_dialog_lifecycle_and_night_mode(self):
        # 1. Test instantiation with night mode
        dlg_night = AutoFocusDialog(None, self.core, night_mode=True)
        self.assertTrue(dlg_night.night_mode)
        self.assertTrue(dlg_night.curve_widget.night_mode)

        # 2. Test toggle night mode to false
        dlg_night.set_night_mode(False)
        self.assertFalse(dlg_night.night_mode)
        self.assertFalse(dlg_night.curve_widget.night_mode)

        # 3. Test sweep worker execution
        dlg_night.spin_range.setValue(30)
        dlg_night.spin_interval.setValue(15)

        # Run sweep
        dlg_night._start_sweep()
        self.assertIsNotNone(dlg_night._worker_thread)

        # Wait for worker thread to finish
        dlg_night._worker_thread.join(timeout=8.0)
        self.assertFalse(dlg_night._worker_thread.is_alive())

        # Process Qt events so queued signals arrive
        self.app.processEvents()

        # Verify best step was located and applied
        self.assertIsNotNone(dlg_night.best_step)
        self.assertIsNotNone(dlg_night.best_metric)
        self.assertTrue(dlg_night.btn_apply.isEnabled())
        self.assertEqual(dlg_night.progress_bar.value(), 100)

        # Wait for the focuser to settle at the optimal focus step
        self.core.wait_focus_settled(dlg_night.best_step, timeout=3.0)
        self.assertAlmostEqual(self.link.latest_telemetry.foc_steps, dlg_night.best_step, delta=2)


if __name__ == "__main__":
    unittest.main()
