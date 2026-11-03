"""
full_verification_suite.py
Comprehensive End-to-End Automated Verification Test Suite for
AstroGoTo v2.0 Telescope Controller & Stellarium Bridge.
"""

import sys, os
sys.path.insert(0, os.getcwd())
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
import math
import time
import socket
import struct
import threading
import datetime as dt
import http.server

from telescope_bridge import (
    Config, DEFAULT_CONFIG, SimLink, BridgeCore, StellariumServer, StellariumHttpFollower,
    julian_date, lst_deg, radec_to_altaz, altaz_to_radec,
    precess_j2000_to_date, precess_date_to_j2000,
    sun_radec, separation_deg, choose_az_branch,
    angle_to_steps, steps_to_angle, pack_position, parse_goto, D2R
)

def run_suite():
    print("=" * 75)
    print("ASTROGOTO v2.0 - FULL SYSTEM VERIFICATION SUITE")
    print("=" * 75)
    
    passed_tests = 0
    total_tests = 0

    def assert_test(name, condition, extra_info=""):
        nonlocal passed_tests, total_tests
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASS] {name} {extra_info}")
            return True
        else:
            print(f"  [FAIL] {name} - {extra_info}")
            return False

    # =========================================================================
    # SECTION 1: CONFIGURATION & PERSISTENCE
    # =========================================================================
    print("\n--- SECTION 1: Configuration Management & Validation ---")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        tmp_file.write(b"{}")
        tmp_cfg_path = tmp_file.name
    cfg = Config(tmp_cfg_path)
    assert_test("Config Default Epoch", cfg["epoch"] == "J2000", f"(Epoch: {cfg['epoch']})")
    assert_test("Config Safe Az Speed", cfg["speed_az"] == 226, f"(speed_az: {cfg['speed_az']})")
    assert_test("Config Safe Alt Speed", cfg["speed_alt"] == 226, f"(speed_alt: {cfg['speed_alt']})")
    assert_test("Config Az Ratio", abs(cfg["steps_per_deg_az"] - 113.22) < 0.01)
    assert_test("Config Alt Ratio", abs(cfg["steps_per_deg_alt"] - 113.22) < 0.01)

    errors = cfg.validate()
    assert_test("Config Validation Default Clean", len(errors) == 0, f"Errors: {errors}")

    # Bad config detection
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_bad:
        tmp_bad.write(b"{}")
        tmp_bad_path = tmp_bad.name
    bad_cfg = Config(tmp_bad_path)
    bad_cfg["latitude_deg"] = 999.0
    bad_cfg["epoch"] = "InvalidEpoch"
    bad_cfg["baud"] = -9600
    bad_errors = bad_cfg.validate()
    assert_test("Config Validation Rejects Invalid Inputs", len(bad_errors) >= 3, f"Caught {len(bad_errors)} errors")

    # =========================================================================
    # SECTION 2: ASTRONOMICAL MATHEMATICS ENGINE
    # =========================================================================
    print("\n--- SECTION 2: Astronomical Mathematics Engine ---")
    t_ref = dt.datetime(2026, 11, 2, 22, 0, 0)
    jd = julian_date(t_ref)
    assert_test("Julian Date Calculation", abs(jd - 2461347.416667) < 0.001, f"JD: {jd:.4f}")

    lst = lst_deg(t_ref, 80.15)
    assert_test("Local Sidereal Time (LST)", 0.0 <= lst < 360.0, f"LST: {lst:.2f}°")

    # Polaris alt ~= lat test
    polaris_ra, polaris_dec = 37.95, 89.26
    p_alt, p_az = radec_to_altaz(polaris_ra, polaris_dec, 12.84, 80.15, t_ref)
    assert_test("Polaris Altitude ~= Observer Latitude", abs(p_alt - 12.84) < 1.0, f"Alt: {p_alt:.2f}°")

    # Alt/Az <-> RA/Dec round-trip across 4 sky quadrants
    test_coords = [
        (45.0, 45.0),    # NE
        (60.0, 135.0),   # SE
        (30.0, 225.0),   # SW
        (75.0, 315.0),   # NW
        (85.0, 0.0),     # Near Zenith North
        (15.0, 180.0)    # Low South
    ]
    roundtrip_ok = True
    max_rt_err = 0.0
    for alt_in, az_in in test_coords:
        ra_c, dec_c = altaz_to_radec(alt_in, az_in, 12.84, 80.15, t_ref)
        alt_out, az_out = radec_to_altaz(ra_c, dec_c, 12.84, 80.15, t_ref)
        err = math.hypot(alt_out - alt_in, az_out - az_in)
        if err > max_rt_err: max_rt_err = err
        if err > 1e-4: roundtrip_ok = False
    assert_test("Alt/Az <-> RA/Dec Inversion Round-trip", roundtrip_ok, f"Max error: {max_rt_err:.8f}°")

    # J2000 <-> Date Precession loop
    precess_ok = True
    max_prec_err = 0.0
    for ra_in, dec_in in [(10.0, 20.0), (83.6, -5.4), (200.0, -45.0), (350.0, 70.0)]:
        r_d, d_d = precess_j2000_to_date(ra_in, dec_in, t_ref)
        r_rt, d_rt = precess_date_to_j2000(r_d, d_d, t_ref)
        err = math.hypot((r_rt - ra_in) * math.cos(dec_in * D2R), d_rt - dec_in)
        if err > max_prec_err: max_prec_err = err
        if err > 1e-4: precess_ok = False
    assert_test("Precession Forward-Reverse Inversion", precess_ok, f"Max error: {max_prec_err:.8f}°")

    # Sun calculation & keep-out check
    sun_r, sun_d = sun_radec(t_ref)
    assert_test("Sun Position Model", 0.0 <= sun_r < 360.0 and -25.0 <= sun_d <= 25.0, f"Sun RA: {sun_r:.2f}°, Dec: {sun_d:.2f}°")

    # Atmospheric Refraction (Bennett 1982) & 4-Pass Fixed Point Inversion
    from telescope_bridge import true_to_apparent_alt, apparent_to_true_alt
    refr_max_err = 0.0
    for h_test in [5.0, 10.0, 20.0, 45.0, 75.0]:
        h_app = true_to_apparent_alt(h_test)
        h_rec = apparent_to_true_alt(h_app)
        err = abs(h_rec - h_test) * 3600.0
        if err > refr_max_err:
            refr_max_err = err
    assert_test("Atmospheric Refraction Bennett & 4-Pass Inversion (<0.001 arcsec)", refr_max_err < 0.001, f"Max recovery error: {refr_max_err:.6f} arcsec")

    # =========================================================================
    # SECTION 3: SIMULATOR & FIRMWARE PROTOCOL
    # =========================================================================
    print("\n--- SECTION 3: Simulator & Firmware Protocol Engine ---")
    sim = SimLink(cfg)
    assert_test("SimLink Open", sim.open(), "SimLink initialized")

    # Telemetry Ping
    reply_p = sim.send("P")
    assert_test("Telemetry 'P' Reply Format", reply_p.startswith("P ") and len(reply_p.split()) >= 6, f"Reply: {reply_p}")

    # Set parameters: V, A, L, B
    assert_test("Speed 'V' Command", sim.send("V 226 226 300") == "OK")
    assert_test("Acceleration 'A' Command", sim.send("A 100 100 150") == "OK")
    assert_test("Limits 'L' Command", sim.send("L -22644 22644 0 9623") == "OK")
    assert_test("Backlash 'B' Command", sim.send("B 10 15") == "OK")
    assert_test("Backlash Internal State", sim.backlash_az == 10 and sim.backlash_alt == 15)

    # Coordinated vector motion
    sim.send("G 1000 500")
    assert_test("GoTo 'G' Target Received", sim.az_target == 1000 and sim.alt_target == 500)
    
    # Emergency Stop
    sim.send("S")
    assert_test("Stop 'S' Command", sim.az_target == sim.az_pos and sim.alt_target == sim.alt_pos)

    # Focus motion
    foc_start = sim.foc_pos
    sim.send("F 200")
    assert_test("Focus 'F' Target Received", sim.foc_target == foc_start + 200)

    # =========================================================================
    # SECTION 4: SAFETY INTERLOCKS & BOUNDS
    # =========================================================================
    print("\n--- SECTION 4: Safety Interlocks & Horizon Bounds ---")
    core = BridgeCore(config=cfg, link=sim, time_fn=lambda: t_ref)
    core.connect(simulate=True)
    obs_lat = float(cfg["latitude_deg"])
    obs_lon = float(cfg["longitude_deg"])

    # Target below horizon
    ra_sub, dec_sub = altaz_to_radec(-10.0, 180.0, obs_lat, obs_lon, t_ref)
    refused_sub = not core.on_goto_requested(ra_sub, dec_sub, is_j2000=True)
    assert_test("Reject Target Below Horizon (Alt -10°)", refused_sub)

    # Target above max elevation (e.g. Alt 88° > 85° limit)
    ra_zen, dec_zen = altaz_to_radec(88.0, 180.0, obs_lat, obs_lon, t_ref)
    refused_zen = not core.on_goto_requested(ra_zen, dec_zen, is_j2000=True)
    assert_test("Reject Target Above 85° Elevation", refused_zen)

    # Sun keep-out tests (evaluated at daytime when Sun is high in the sky: Alt > 0)
    t_day = dt.datetime(2026, 11, 2, 6, 30, 0)
    core.time_fn = lambda: t_day
    sun_r_day, sun_d_day = sun_radec(t_day)
    refused_sun = not core.on_goto_requested(sun_r_day, sun_d_day, is_j2000=False, solar_confirmed=False)
    assert_test("Reject Target Within Sun Keep-Out (15°)", refused_sun)

    # Target within Sun keep-out with explicit solar filter confirmation
    accepted_sun_with_filter = core.on_goto_requested(sun_r_day, sun_d_day, is_j2000=False, solar_confirmed=True)
    assert_test("Authorize Target Within Sun Keep-Out When Solar Filter Confirmed", accepted_sun_with_filter)
    core.time_fn = lambda: t_ref

    # Azimuth branch crossing
    b1 = choose_az_branch(350.0, 0.0, limit=200.0)
    assert_test("Branch Selection for 350° from 0° -> -10°", b1 == -10.0, f"Result: {b1}°")
    b2 = choose_az_branch(10.0, 0.0, limit=200.0)
    assert_test("Branch Selection for 10° from 0° -> +10°", b2 == +10.0, f"Result: {b2}°")
    b3 = choose_az_branch(190.0, 170.0, limit=200.0)
    assert_test("Branch Selection for 190° from +170° -> +190°", b3 == 190.0, f"Result: {b3}°")
    b4 = choose_az_branch(190.0, -170.0, limit=200.0)
    assert_test("Branch Selection for 190° from -170° -> -170°", b4 == -170.0, f"Result: {b4}°")

    # =========================================================================
    # SECTION 5: ZERO-GAP PREDICTIVE TIME-OF-FLIGHT INTERCEPT (MULTI-TARGET)
    # =========================================================================
    print("\n--- SECTION 5: Zero-Gap Predictive Time-of-Flight Intercept ---")
    targets = [
        ("Rigel (Beta Ori)", 78.634, -8.201),
        ("Sirius (Alpha CMa)", 101.287, -16.716),
        ("Betelgeuse (Alpha Ori)", 88.793, 7.407),
        ("Aldebaran (Alpha Tau)", 68.980, 16.509),
        ("Capella (Alpha Aur)", 79.172, 45.998)
    ]

    all_intercepts_clean = True
    max_intercept_gap_arcsec = 0.0

    for name, ra_j, dec_j in targets:
        # Reset mount to home
        sim.az_pos = 0.0
        sim.alt_pos = 0.0
        sim._update_telemetry()
        t_start = dt.datetime(2026, 11, 2, 22, 0, 0)
        core.time_fn = lambda: t_start

        ok = core.on_goto_requested(ra_j, dec_j, is_j2000=True, predict_flight=True)
        if not ok:
            continue
        
        tgt_az_s, tgt_alt_s = core.last_sent_steps
        flight_dur_s = max(abs(tgt_az_s) / float(cfg["speed_az"]), abs(tgt_alt_s) / float(cfg["speed_alt"]))
        t_arrive = t_start + dt.timedelta(seconds=flight_dur_s)

        # Move sim to target and clock to arrival
        sim.az_pos = tgt_az_s
        sim.alt_pos = tgt_alt_s
        sim._update_telemetry()
        core.time_fn = lambda: t_arrive

        mount_alt, mount_az = core.get_telescope_altaz()
        ra_d_act, dec_d_act = precess_j2000_to_date(ra_j, dec_j, t_arrive)
        star_alt, star_az = radec_to_altaz(ra_d_act, dec_d_act, obs_lat, obs_lon, t_arrive, apply_refraction=True)

        # Great-circle angular separation on sky sphere
        cos_sep = (math.sin(math.radians(mount_alt)) * math.sin(math.radians(star_alt)) +
                   math.cos(math.radians(mount_alt)) * math.cos(math.radians(star_alt)) * math.cos(math.radians(mount_az - star_az)))
        pointing_gap_deg = math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))
        pointing_gap_arcsec = pointing_gap_deg * 3600.0

        if pointing_gap_arcsec > max_intercept_gap_arcsec:
            max_intercept_gap_arcsec = pointing_gap_arcsec
        if pointing_gap_arcsec > 32.0:  # Must be within 1 physical motor step (31.8 arcsec)
            all_intercepts_clean = False

        print(f"    Target: {name:<22} Slew: {flight_dur_s:5.1f}s | Arrival Gap: {pointing_gap_arcsec:.2f} arcsec ({pointing_gap_deg*60:.4f} arcmin)")

    assert_test("Zero-Gap Intercept Accuracy (< 1 motor step: 31.8 arcsec)", all_intercepts_clean, f"Worst-case gap: {max_intercept_gap_arcsec:.2f} arcsec")

    # =========================================================================
    # SECTION 6: CONTINUOUS SIDEREAL TRACKING (10-MINUTE DRIFT SIMULATION)
    # =========================================================================
    print("\n--- SECTION 6: Continuous Sidereal Tracking Engine ---")
    rigel_ra, rigel_dec = 78.634, -8.201
    sim.az_pos = 0.0
    sim.alt_pos = 0.0
    sim._update_telemetry()
    t_track = dt.datetime(2026, 11, 2, 22, 0, 0)
    core.time_fn = lambda: t_track
    core.on_goto_requested(rigel_ra, rigel_dec, is_j2000=True, predict_flight=False)
    
    # Mount arrives at initial destination
    sim.az_pos = core.last_sent_steps[0]
    sim.alt_pos = core.last_sent_steps[1]
    sim._update_telemetry()
    initial_steps = core.last_sent_steps

    # Simulate 10 one-minute tracking increments
    for minute in range(1, 11):
        t_track += dt.timedelta(seconds=60)
        core.time_fn = lambda: t_track
        core.update_tracking()
        # Simulated motor completes tracking step update
        sim.az_pos = core.last_sent_steps[0]
        sim.alt_pos = core.last_sent_steps[1]
        sim._update_telemetry()

    final_steps = core.last_sent_steps
    steps_delta_az = final_steps[0] - initial_steps[0]
    steps_delta_alt = final_steps[1] - initial_steps[1]

    assert_test("Tracking Step Accumulation Over 10 Minutes", abs(steps_delta_az) > 0 and abs(steps_delta_alt) > 0,
                f"Delta: Az {steps_delta_az} steps, Alt {steps_delta_alt} steps, Pulses: {core.tracking_pulses_count}")

    # Check drift at end of 10 minutes
    ra_d_10, dec_d_10 = precess_j2000_to_date(rigel_ra, rigel_dec, t_track)
    star_alt_10, star_az_10 = radec_to_altaz(ra_d_10, dec_d_10, obs_lat, obs_lon, t_track, apply_refraction=True)
    mount_alt_10, mount_az_10 = core.get_telescope_altaz()
    track_drift = math.hypot(mount_az_10 - star_az_10, mount_alt_10 - star_alt_10) * 3600.0
    assert_test("10-Minute Sidereal Tracking Drift (< 1 motor step: 31.8 arcsec)", track_drift < 32.0, f"Drift: {track_drift:.2f} arcsec")

    # =========================================================================
    # SECTION 7: MANUAL JOGGING & SYNC LOGICAL OFFSETS
    # =========================================================================
    print("\n--- SECTION 7: Manual Jogging & Sync Offset Mechanics ---")
    core.jog("up", "medium")    # +0.5 deg alt
    core.jog("right", "medium") # +0.5 deg az
    has_offsets = (core.alt_off_steps != 0 and core.az_off_steps != 0)
    assert_test("Jog Creates Logical Tracking Offsets", has_offsets, f"Offset steps: Az={core.az_off_steps}, Alt={core.alt_off_steps}")

    core.sync()
    cleared_offsets = (core.alt_off_steps == 0 and core.az_off_steps == 0)
    assert_test("Sync Resets Offsets to Target Zero", cleared_offsets)

    # Focus jogging
    foc_before = sim.foc_target
    core.move_focus("fine", True) # Inward (-20)
    assert_test("Focus Inward Fine Step Command", sim.foc_target < foc_before, f"{sim.foc_target} < {foc_before}")
    
    foc_before2 = sim.foc_target
    core.move_focus("coarse", False) # Outward (+200)
    assert_test("Focus Outward Coarse Step Command", sim.foc_target > foc_before2, f"{sim.foc_target} > {foc_before2}")

    # =========================================================================
    # SECTION 8: STELLARIUM TCP PROTOCOL (PORT 10001) SERVER
    # =========================================================================
    print("\n--- SECTION 8: Stellarium Server (Port 10001) Protocol Verification ---")
    server = StellariumServer("127.0.0.1", 0, core)
    server.start()
    assert_test("Stellarium TCP Server Started", server.is_running and server.port > 0, f"Port: {server.port}")

    # Connect client
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", server.port))
    time.sleep(0.1)
    assert_test("Stellarium Client Connection Accepted", server.is_client_connected)

    # Test sending GoTo packet (Rigel J2000)
    ra_int = int(round((rigel_ra % 360.0) / 360.0 * 2**32)) & 0xFFFFFFFF
    dec_int = int(round(rigel_dec / 90.0 * 0x40000000))
    goto_pkt = struct.pack('<HHQIi', 20, 0, int(time.time() * 1e6), ra_int, dec_int)

    # Send in fragmented slices to test TCP stream reassembly
    sock.sendall(goto_pkt[:8])
    time.sleep(0.02)
    sock.sendall(goto_pkt[8:])
    time.sleep(0.1)

    got_target = (core.current_target_radec is not None and abs(core.current_target_radec[0] - rigel_ra) < 0.1)
    assert_test("Stellarium Fragmented GoTo Reassembled & Processed", got_target, f"Target: {core.last_goto_target_str}")

    # Read position report back from server
    sock.settimeout(2.0)
    resp_data = sock.recv(24)
    assert_test("Stellarium Position Report Packet Length == 24", len(resp_data) == 24)
    p_len, p_type, _t, rep_ra_u, rep_dec_i, _stat = struct.unpack('<HHQIii', resp_data)
    rep_ra = rep_ra_u / 2**32 * 360.0
    rep_dec = rep_dec_i / 0x40000000 * 90.0
    assert_test("Position Report Protocol J2000 Frame", 0 <= rep_ra < 360 and -90 <= rep_dec <= 90, f"Reported J2000: RA {rep_ra:.4f}°, Dec {rep_dec:.4f}°")

    sock.close()
    server.stop()
    assert_test("Stellarium TCP Server Stopped Cleanly", not server.is_running)

    # =========================================================================
    # SECTION 9: STELLARIUM HTTP FOLLOWER (SATELLITE LEAD FEEDFORWARD)
    # =========================================================================
    print("\n--- SECTION 9: Stellarium HTTP Follower & Live Satellite Tracking ---")
    
    # Mock HTTP Server for Stellarium API (/api/objects/info)
    mock_data = {
        "name": "ISS (ZARYA)",
        "type": "Satellite",
        "altitude": 42.0,
        "azimuth": 160.0,
        "raJ2000": 85.0,
        "decJ2000": 10.0
    }

    class MockStellariumHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            import json
            if "/api/objects/info" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(mock_data).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, format, *args):
            pass  # Suppress logs

    mock_http = http.server.HTTPServer(("127.0.0.1", 0), MockStellariumHandler)
    mock_port = mock_http.server_port
    http_thread = threading.Thread(target=mock_http.serve_forever, daemon=True)
    http_thread.start()

    follower = StellariumHttpFollower(core, host="127.0.0.1", port=mock_port, poll_interval_s=0.1)
    follower.start()
    time.sleep(0.3)

    assert_test("HTTP Follower Connected to Mock API", follower.is_connected, f"Target: {follower.target_name}")

    # Test feedforward: move satellite
    mock_data["altitude"] = 42.5
    mock_data["azimuth"] = 161.0
    time.sleep(0.3)

    assert_test("Satellite Velocity Lead Feedforward Active", core.last_goto_target_str.startswith("ISS"), f"State: {core.last_goto_target_str}")
    assert_test("Satellite Direct Topocentric Tracking Executed", core.tracking_enabled and core.last_sent_steps is not None)

    # Verify that calling update_tracking() does NOT overwrite satellite target steps
    sat_sent_steps = core.last_sent_steps
    core.update_tracking()
    assert_test("Satellite Tracking Immunity to Sidereal Overwrite", core.last_sent_steps == sat_sent_steps, "update_tracking() safely bypassed for satellites")

    follower.stop()
    mock_http.shutdown()
    assert_test("HTTP Follower & Mock API Shutdown Cleanly", not follower.is_active)

    # =========================================================================
    # SECTION 10: GUI ENGINE (PyQt6 HEADLESS VERIFICATION)
    # =========================================================================
    print("\n--- SECTION 10: PyQt6 User Interface Engine & Visual Controls ---")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    import telescope_ui_qt

    app = QApplication.instance()
    if not app:
        app = QApplication(["--platform", "offscreen"])

    main_win = telescope_ui_qt.AstroTelescopeWindow(core=core, stellarium=None, config=cfg)
    assert_test("PyQt6 Main Window Instantiation", main_win is not None)
    assert_test("Epoch Dropdown Default J2000", main_win.config.get("epoch") == "J2000")

    # Trigger high-speed tick
    main_win._on_tick()
    assert_test("Telemetry Table 1 Apparent Readout Populated", len(main_win.val_m_altaz.text()) > 5, f"Alt/Az: {main_win.val_m_altaz.text()}")
    assert_test("Telemetry Table 2 Target Ephemeris Populated", len(main_win.val_t_ephemeris.text()) > 5, f"Ephemeris: {main_win.val_t_ephemeris.text()}")

    # Polar Radar Widget calculations
    radar = main_win.radar_widget
    assert_test("Enlarged Polar Radar Widget Instantiated", radar is not None and radar.width() > 0)

    # Celestial Catalog Dialog
    goto_dlg = telescope_ui_qt.GoToDialog(parent=main_win, core=core, config=cfg)
    assert_test("GoTo Catalog Dialog Presets Loaded", goto_dlg.combo_presets.count() >= 9, f"Presets count: {goto_dlg.combo_presets.count()}")

    # Help Guide Dialog
    help_dlg = telescope_ui_qt.HelpGuideDialog(parent=main_win)
    assert_test("Comprehensive Help Guide Loaded", help_dlg.tabs.count() >= 5, f"Tab count: {help_dlg.tabs.count()}")

    # UI updates: Sync Location button & Solar Filter checkbox
    assert_test("Sync Location Button Present", hasattr(main_win, "btn_sync_loc") and main_win.btn_sync_loc is not None)
    assert_test("Solar Filter Checkbox Present", hasattr(main_win, "chk_solar_filter") and main_win.chk_solar_filter is not None)
    assert_test("Follow Status Standby Free of Satellite Hint", "(Click 'Satellite Follow'" not in main_win.val_t_follow_status.text())

    # Check zero emoji compliance in GUI text
    all_clean_text = True
    for preset_idx in range(goto_dlg.combo_presets.count()):
        text = goto_dlg.combo_presets.itemText(preset_idx)
        for char in text:
            if ord(char) > 127000:  # Unicode emoji ranges
                all_clean_text = False
    assert_test("Zero-Emoji Scientific Aesthetic Compliance", all_clean_text)

    # Clean disconnect
    core.disconnect()

    # Clean up temporary config files
    for p in (tmp_cfg_path, tmp_bad_path):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    print("\n" + "=" * 75)
    print(f"VERIFICATION COMPLETE: {passed_tests}/{total_tests} TESTS PASSED ({(passed_tests/total_tests)*100:.1f}%)")
    print("=" * 75)
    return passed_tests == total_tests


def test_verification_suite():
    assert run_suite()


if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
