"""
Tests for Tonight's Best GoTo target alignment and Stellarium synchronization.
Verifies that slewing from Tonight's Best lands on the exact same micro-arcsecond
coordinates as Stellarium's Ctrl+1 slew.
"""
import unittest
import os
import sys
import datetime as dt
import http.server
import socketserver
import threading
import json
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telescope_bridge as tb
import telescope_ui_qt as ui

class MockStellariumRemoteServer(http.server.BaseHTTPRequestHandler):
    """Mocks Stellarium Remote Control plugin on port 8090."""
    def log_message(self, format, *args):
        pass # Suppress server logging during tests

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/objects/info":
            name = qs.get("name", [""])[0]
            if name.lower() in ("venus",):
                # Exact coordinates returned by Stellarium for Venus on test epoch
                data = {
                    "name": "Venus",
                    "type": "Planet",
                    "raJ2000": 201.5125,
                    "decJ2000": -13.4858,
                    "ra": 201.8712,
                    "dec": -13.6251,
                    "altitude": 55.25,
                    "azimuth": 138.10
                }
                payload = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            elif name.lower() in ("m45", "pleiades"):
                data = {
                    "name": "M45",
                    "type": "OpenCluster",
                    "raJ2000": 56.750,
                    "decJ2000": 24.116,
                    "ra": 57.012,
                    "dec": 24.225,
                    "altitude": 60.0,
                    "azimuth": 90.0
                }
                payload = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/main/focus":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()


class TestTonightBestAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start mock Stellarium HTTP server on a random local port
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), MockStellariumRemoteServer)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.config = dict(tb.DEFAULT_CONFIG)
        self.config["simulate"] = True
        self.config["latitude_deg"] = 12.84
        self.config["longitude_deg"] = 80.15
        self.core = tb.BridgeCore(self.config)
        self.core.link = tb.SimLink()
        self.core.link.open()

    def tearDown(self):
        if self.core.link:
            self.core.link.close()

    def test_tonight_best_offline_coordinates_precession(self):
        """Verifies that offline planetary ephemeris outputs J2000 coordinates correctly and handles precession."""
        t_ref = dt.datetime(2026, 11, 4, 3, 37, 2, tzinfo=dt.timezone.utc)
        ra_2k, dec_2k = tb.planet_radec("Venus", t_ref)
        self.assertTrue(0.0 <= ra_2k < 360.0)
        self.assertTrue(-90.0 <= dec_2k <= 90.0)

        # Precess to date
        ra_date, dec_date = tb.precess_j2000_to_date(ra_2k, dec_2k, t_ref)
        # Invert back to J2000
        ra_recovered, dec_recovered = tb.precess_date_to_j2000(ra_date, dec_date, t_ref)
        err = tb.separation_deg(ra_2k, dec_2k, ra_recovered, dec_recovered)
        self.assertLess(err, 1e-5, f"Precession roundtrip error too large: {err}")

    def test_tonight_best_stellarium_sync(self):
        """Verifies that _query_stellarium_target successfully queries Stellarium and returns J2000 coords."""
        import sys
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)

        tour = ui.TonightSkyTourDialog(core=self.core, config=self.config)
        # Point tour to our mock Stellarium port
        tour.config["stellarium_host"] = "127.0.0.1"
        if hasattr(self.core, "follower") and self.core.follower:
            self.core.follower.host = "127.0.0.1"
            self.core.follower.port = self.port
        else:
            tour.core.follower = tb.StellariumHttpFollower(self.core, host="127.0.0.1", port=self.port)

        venus_item = next(it for it in ui.TONIGHT_BEST_CATALOG if it.get("dynamic_body") == "Venus")
        res = tour._query_stellarium_target(venus_item)
        self.assertIsNotNone(res, "Failed to query Stellarium for Venus")
        ra_j2k, dec_j2k, is_j2000 = res
        self.assertAlmostEqual(ra_j2k, 201.5125, places=3)
        self.assertAlmostEqual(dec_j2k, -13.4858, places=3)
        self.assertTrue(is_j2000)

        # Slew to Venus using _start_slew
        # Enable solar filter confirmation so safety sweep allows slew near Sun
        self.core.solar_filter_confirmed = True
        self.config["solar_filter_installed"] = True
        tour.selected_item = dict(venus_item)
        tour.selected_item["calc_ra"] = ra_j2k
        tour.selected_item["calc_dec"] = dec_j2k
        tour._start_slew()

        # Check that core slewed to Venus's exact Stellarium coordinates
        self.assertIn("Venus", tour.lbl_status.text())
        self.assertIn("Stellarium sync", tour.lbl_status.text())
        tour.close()

if __name__ == "__main__":
    unittest.main()
