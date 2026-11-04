"""
Unit tests for Serial Monitor, Global Night Mode Theme Propagation, and Cable Unwind Mechanics.
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telescope_bridge as tb
import telescope_ui_qt as ui
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette

class TestSerialMonitorAndThemeMechanics(unittest.TestCase):
    def setUp(self):
        self.config = dict(tb.DEFAULT_CONFIG)
        self.config["simulate"] = True
        self.core = tb.BridgeCore(self.config)
        self.core.link = tb.SimLink()
        self.core.link.open()

    def tearDown(self):
        if self.core.link:
            self.core.link.close()

    def test_unwind_cable_and_wrap_status(self):
        """Verifies cable wrap calculation, strain thresholds, and physical unwind slew."""
        sim = self.core.link
        # Set mount to Azimuth 180° (South)
        sim.az_pos = tb.angle_to_steps(180.0, self.config["steps_per_deg_az"], self.config["sign_az"])
        sim._update_telemetry()

        wrap_deg, wrap_turns = self.core.get_cable_wrap()
        self.assertAlmostEqual(wrap_deg, 180.0, places=1)
        self.assertAlmostEqual(wrap_turns, 0.5, places=2)

        # In UI: 0.5 turns must be OK (not STRAIN)
        abs_turns = abs(wrap_turns)
        status = "STRAIN" if abs_turns >= 1.0 else ("CAUTION" if abs_turns >= 0.75 else "OK")
        self.assertEqual(status, "OK")

        # Unwind cable to 0.0°
        self.core.tracking_enabled = True
        unwound = self.core.unwind_cable()
        self.assertTrue(unwound)
        self.assertFalse(self.core.tracking_enabled)

        # Simulate completion of slew
        sim.az_pos = sim.az_target
        sim._update_telemetry()
        unwound_deg, unwound_turns = self.core.get_cable_wrap()
        self.assertAlmostEqual(unwound_deg, 0.0, places=1)
        self.assertAlmostEqual(unwound_turns, 0.0, places=2)

    def test_serial_monitor_hooks_and_dialog(self):
        """Verifies that BridgeCore and LinkBase dispatch raw TX and RX events to listeners and dialog."""
        events = []
        def listener(direction, line):
            events.append((direction, line))

        self.core.register_serial_monitor(listener)
        reply = self.core.link.send("P")
        self.assertEqual(reply, "P 0 0 0 0 0")

        # Check that TX and RX were captured
        tx_events = [e for e in events if e[0] == "TX"]
        rx_events = [e for e in events if e[0] == "RX"]
        self.assertTrue(any("P" in e[1] for e in tx_events))
        self.assertTrue(any("P 0 0 0 0 0" in e[1] for e in rx_events))

        self.core.unregister_serial_monitor(listener)

    def test_night_mode_propagation_and_combobox_colors(self):
        """Verifies night mode applies globally to all dialogs, windows, and dropdown box items."""
        app = QApplication.instance() or QApplication(sys.argv)
        win = ui.AstroTelescopeWindow(self.core, None, self.config)

        # 1. Initially in normal mode
        self.assertFalse(win.night_mode)
        item_color_day = win.combo_stream_rate.view().palette().color(QPalette.ColorRole.Text).name().lower()
        self.assertEqual(item_color_day, "#dce2eb") # crisp light color, NOT red

        # 2. Open child dialogs (Serial Monitor, Tour, Settings, Help)
        serial_dlg = ui.SerialMonitorDialog(self.core, night_mode=win.night_mode, parent=win)
        settings_dlg = ui.SettingsDialog(self.config, night_mode=win.night_mode, parent=win)
        help_dlg = ui.HelpGuideDialog(night_mode=win.night_mode, parent=win)
        tour_dlg = ui.TonightSkyTourDialog(self.core, self.config, night_mode=win.night_mode, parent=win)

        self.assertFalse(serial_dlg.night_mode)
        self.assertFalse(settings_dlg.night_mode)
        self.assertFalse(help_dlg.night_mode)
        self.assertFalse(tour_dlg.night_mode)

        # 3. Toggle Night Mode ON: All windows and open dialogs must transition to night mode
        win.toggle_night_mode()
        self.assertTrue(win.night_mode)
        self.assertTrue(serial_dlg.night_mode)
        self.assertTrue(settings_dlg.night_mode)
        self.assertTrue(help_dlg.night_mode)
        self.assertTrue(tour_dlg.night_mode)

        item_color_night = win.combo_stream_rate.view().palette().color(QPalette.ColorRole.Text).name().lower()
        self.assertEqual(item_color_night, "#ff4d4d") # pure red

        # 4. Toggle Night Mode OFF: All windows and dialogs must cleanly revert, combobox view must revert
        win.toggle_night_mode()
        self.assertFalse(win.night_mode)
        self.assertFalse(serial_dlg.night_mode)
        self.assertFalse(settings_dlg.night_mode)
        self.assertFalse(help_dlg.night_mode)
        self.assertFalse(tour_dlg.night_mode)

        item_color_reverted = win.combo_stream_rate.view().palette().color(QPalette.ColorRole.Text).name().lower()
        self.assertEqual(item_color_reverted, "#dce2eb") # reverts cleanly, NEVER stuck on red

        # Clean up
        serial_dlg.close()
        settings_dlg.close()
        help_dlg.close()
        tour_dlg.close()
        win.close()

    def test_tracking_button_text_only_on_off(self):
        """Verifies tracking button text contains only 'Tracking: ON' without rate name."""
        app = QApplication.instance() or QApplication(sys.argv)
        win = ui.AstroTelescopeWindow(self.core, None, self.config)

        # Tracking enabled
        self.core.tracking_enabled = True
        win._on_tick()
        self.assertEqual(win.btn_track.text(), "Tracking: ON")

        # Tracking disabled
        self.core.tracking_enabled = False
        win._on_tick()
        self.assertEqual(win.btn_track.text(), "Tracking: OFF")
        win.close()

if __name__ == "__main__":
    unittest.main()
