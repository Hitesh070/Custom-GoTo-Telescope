"""
Unit tests for Serial Monitor and Stellarium Optics Loader.
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telescope_bridge as tb
import telescope_ui_qt as ui

class TestSerialMonitorAndOptics(unittest.TestCase):
    def setUp(self):
        self.config = dict(tb.DEFAULT_CONFIG)
        self.config["simulate"] = True
        self.core = tb.BridgeCore(self.config)
        self.core.link = tb.SimLink()
        self.core.link.open()

    def tearDown(self):
        if self.core.link:
            self.core.link.close()

    def test_load_stellarium_optics(self):
        """Verifies that load_stellarium_optics successfully reads user equipment from ocular.ini."""
        res = tb.load_stellarium_optics()
        self.assertIsInstance(res, dict)
        if res.get("found"):
            self.assertIn("telescope", res)
            self.assertIn("fl", res)
            self.assertIn("dia", res)
            self.assertIn("ocular", res)
            self.assertIn("all_oculars", res)
            self.assertGreater(len(res["all_oculars"]), 0)

    def test_serial_monitor_hooks(self):
        """Verifies that BridgeCore and LinkBase dispatch raw TX and RX events to listeners."""
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

    def test_tracking_button_text_only_on_off(self):
        """Verifies tracking button text contains only 'Tracking: ON' without rate name."""
        from PyQt6.QtWidgets import QApplication
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
