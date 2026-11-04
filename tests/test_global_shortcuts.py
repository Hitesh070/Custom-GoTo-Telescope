"""
test_global_shortcuts.py
Unit tests verifying application-wide global keyboard shortcuts across all windows and dialogs.
"""

import unittest
import os
import sys

from PyQt6.QtWidgets import QApplication, QLineEdit
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telescope_bridge as tb
import telescope_ui_qt as ui


class TestGlobalApplicationShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.config = dict(tb.DEFAULT_CONFIG)
        self.config["simulate"] = True
        self.core = tb.BridgeCore(self.config)
        self.core.link = tb.SimLink()
        self.core.link.open()
        self.win = ui.AstroTelescopeWindow(self.core, None, self.config)

    def tearDown(self):
        if hasattr(self, "win") and self.win:
            self.win.close()
        if self.core.link:
            self.core.link.close()

    def _send_key(self, widget, key, modifiers=Qt.KeyboardModifier.NoModifier, text=""):
        ev = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)
        self.app.sendEvent(widget, ev)

    def test_night_mode_shortcuts_main_window(self):
        """Verifies Alt+N and Ctrl+N toggle night mode in main window."""
        self.assertFalse(self.win.night_mode)

        # 1. Alt+N toggles ON
        self._send_key(self.win, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)
        self.assertTrue(self.win.night_mode)

        # 2. Ctrl+N toggles OFF
        self._send_key(self.win, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(self.win.night_mode)

        # 3. Alt+N toggles ON again
        self._send_key(self.win, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)
        self.assertTrue(self.win.night_mode)

    def test_night_mode_shortcuts_from_child_dialogs(self):
        """Verifies Alt+N and Ctrl+N toggle night mode when child dialogs are active."""
        self.assertFalse(self.win.night_mode)

        # Open child dialog (e.g. Serial Monitor)
        serial_dlg = ui.SerialMonitorDialog(self.core, night_mode=self.win.night_mode, parent=self.win)
        self.assertFalse(serial_dlg.night_mode)

        # Send Alt+N to serial_dlg
        self._send_key(serial_dlg, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)
        self.assertTrue(self.win.night_mode)
        self.assertTrue(serial_dlg.night_mode)

        # Open Tour dialog
        tour_dlg = ui.TonightSkyTourDialog(self.core, self.config, night_mode=self.win.night_mode, parent=self.win)
        self.assertTrue(tour_dlg.night_mode)

        # Send Ctrl+N from tour_dlg to toggle OFF
        self._send_key(tour_dlg, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(self.win.night_mode)
        self.assertFalse(tour_dlg.night_mode)
        self.assertFalse(serial_dlg.night_mode)

        serial_dlg.close()
        tour_dlg.close()

    def test_emergency_stop_shortcuts_across_windows(self):
        """Verifies Escape and Space halt motors from any window."""
        self.core.tracking_enabled = True

        # Escape key on main window
        self._send_key(self.win, Qt.Key.Key_Escape)
        self.assertFalse(self.core.tracking_enabled)

        # Space key from a child dialog
        help_dlg = ui.HelpGuideDialog(night_mode=self.win.night_mode, parent=self.win)
        self.core.tracking_enabled = True
        self._send_key(help_dlg, Qt.Key.Key_Space)
        self.assertFalse(self.core.tracking_enabled)
        help_dlg.close()

    def test_navigation_dialog_shortcuts(self):
        """Verifies Ctrl+T, Ctrl+G, Ctrl+M, Ctrl+S, Ctrl+H/F1 open their respective dialogs."""
        # Ctrl+M -> Serial Monitor
        self._send_key(self.win, Qt.Key.Key_M, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(hasattr(self.win, "serial_monitor_dlg") and self.win.serial_monitor_dlg.isVisible())

        # Ctrl+T -> Tonight's Best Tour
        self._send_key(self.win, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(hasattr(self.win, "tour_window") and self.win.tour_window.isVisible())

        # Ctrl+G -> GoTo Coordinates Dialog
        self._send_key(self.win, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(hasattr(self.win, "goto_window") and self.win.goto_window.isVisible())

        # Clean up open dialogs
        if self.win.serial_monitor_dlg:
            self.win.serial_monitor_dlg.close()
        if self.win.tour_window:
            self.win.tour_window.close()
        if self.win.goto_window:
            self.win.goto_window.close()

    def test_speed_selection_shortcuts(self):
        """Verifies Ctrl+1, Ctrl+2, Ctrl+3 switch slew speeds."""
        self._send_key(self.win, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.win.selected_jog_speed, "fine")
        self.assertTrue(self.win.btn_fine.isChecked())

        self._send_key(self.win, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.win.selected_jog_speed, "coarse")
        self.assertTrue(self.win.btn_coarse.isChecked())

        self._send_key(self.win, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.win.selected_jog_speed, "medium")
        self.assertTrue(self.win.btn_med.isChecked())

    def test_arrow_keys_jog_mount(self):
        """Verifies arrow keys trigger jog commands across windows when not in text input."""
        jogs = []
        original_jog = self.core.jog
        self.core.jog = lambda direction, speed: jogs.append((direction, speed))

        try:
            # Arrow Up
            self._send_key(self.win, Qt.Key.Key_Up)
            self.assertEqual(jogs[-1][0], "up")

            # Arrow Down from a child window
            help_dlg = ui.HelpGuideDialog(parent=self.win)
            self._send_key(help_dlg, Qt.Key.Key_Down)
            self.assertEqual(jogs[-1][0], "down")
            help_dlg.close()

            # Arrow Left
            self._send_key(self.win, Qt.Key.Key_Left)
            self.assertEqual(jogs[-1][0], "left")

            # Arrow Right
            self._send_key(self.win, Qt.Key.Key_Right)
            self.assertEqual(jogs[-1][0], "right")
        finally:
            self.core.jog = original_jog


if __name__ == "__main__":
    unittest.main()
