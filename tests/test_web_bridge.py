import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import urllib.request
import json
import time
from src.web_bridge import WebBridgeServer
from telescope_bridge import BridgeCore, SimLink


class MockCore:
    def __init__(self):
        self.link = SimLink()
        self.link.open()
        self.mount_az = 180.0
        self.mount_alt = 45.0
        self.mount_ra = 120.0
        self.mount_dec = 25.0
        self.target_name = "Jupiter"
        self.target_type = "Planet"
        self.target_az = 180.0
        self.target_alt = 45.0
        self.last_sun_distance_deg = 85.0
        self.solar_filter_confirmed = False
        self.cable_wrap_turns = 0.25
        self.focus_pos = 100
        self.is_slewing = False
        self.is_tracking = True
        self.tracking_rate_name = "Sidereal"
        self.stopped = False

    def emergency_stop(self):
        self.stopped = True
        self.is_slewing = False
        self.is_tracking = False

    def slew_to_altaz(self, az, alt, target_name="Target"):
        self.mount_az = az
        self.mount_alt = alt
        self.target_name = target_name
        return True, f"Slew to {target_name} ok"

    def jog_axis(self, axis, dir_sign, deg):
        if axis == "az":
            self.mount_az += dir_sign * deg
        elif axis == "alt":
            self.mount_alt += dir_sign * deg
        return True

    def set_tracking_rate(self, rate):
        self.tracking_rate_name = rate

    def set_tracking(self, enable):
        self.is_tracking = enable

    def unwind_cable(self):
        self.mount_az = 0.0
        self.cable_wrap_turns = 0.0

    def move_focus(self, steps):
        self.focus_pos += steps

    def park_mount(self):
        self.mount_az = 0.0
        self.mount_alt = 0.0

    def sync_to_target(self):
        pass


class TestWebBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = MockCore()
        cls.port = 18088
        cls.server = WebBridgeServer(cls.core, host="127.0.0.1", port=cls.port, auth_token="secret123")
        cls.server.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_get_telemetry_and_cors(self):
        url = f"http://127.0.0.1:{self.port}/api/telemetry"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["connected"])
            self.assertEqual(data["az_deg"], 180.0)
            self.assertEqual(data["alt_deg"], 45.0)
            self.assertEqual(data["target_name"], "Jupiter")

    def test_auth_rejection(self):
        url = f"http://127.0.0.1:{self.port}/api/mount/stop"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                self.fail("Should have failed with 401 Unauthorized")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_post_stop_command(self):
        url = f"http://127.0.0.1:{self.port}/api/mount/stop"
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret123"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertTrue(self.core.stopped)

    def test_post_goto_command(self):
        url = f"http://127.0.0.1:{self.port}/api/mount/goto"
        payload = json.dumps({"name": "Vega", "az": 270.5, "alt": 60.0}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret123"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertEqual(self.core.mount_az, 270.5)
            self.assertEqual(self.core.mount_alt, 60.0)
            self.assertEqual(self.core.target_name, "Vega")


if __name__ == "__main__":
    unittest.main()
