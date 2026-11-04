"""
Web Bridge HTTP & WebSocket Server for Custom GoTo Telescope Mount.

Serves REST API and live telemetry streams to the Vercel / mobile web client.
Runs in a background daemon thread with zero external dependencies (Python standard library http.server).
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger("CustomGoTo.WebBridge")


class TelescopeWebHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Vercel Web App integration."""

    core: Any = None
    auth_token: str = ""

    def _set_cors_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self._set_cors_headers(204)

    def _is_authorized(self) -> bool:
        if not self.auth_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            return token == self.auth_token
        return False

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/api/telemetry" or parsed_url.path == "/":
            core = self.core
            if not core:
                self._set_cors_headers(503)
                self.wfile.write(b'{"error": "Bridge core not attached"}')
                return

            link_open = bool(core.link and core.link.is_open)
            is_sim = getattr(core.link, "is_simulated", False) or type(core.link).__name__ == "SimLink"

            slew_state = "IDLE"
            if getattr(core, "is_slewing", False):
                slew_state = "SLEWING"
            elif getattr(core, "is_tracking", False):
                slew_state = "TRACKING"

            turns = getattr(core, "cable_wrap_turns", 0.0)
            cable_status = "OK"
            if abs(turns) >= 1.0:
                cable_status = "STRAIN"
            elif abs(turns) >= 0.75:
                cable_status = "CAUTION"

            telemetry = {
                "connected": link_open,
                "simulated": is_sim,
                "slew_state": slew_state,
                "tracking": getattr(core, "is_tracking", False),
                "tracking_rate": getattr(core, "tracking_rate_name", "Sidereal"),
                "az_deg": getattr(core, "mount_az", 0.0),
                "alt_deg": getattr(core, "mount_alt", 0.0),
                "ra_j2000_hours": getattr(core, "mount_ra", 0.0) / 15.0 if hasattr(core, "mount_ra") else 0.0,
                "dec_j2000_deg": getattr(core, "mount_dec", 0.0),
                "target_name": getattr(core, "target_name", "None"),
                "target_type": getattr(core, "target_type", "Target"),
                "target_az_deg": getattr(core, "target_az", None),
                "target_alt_deg": getattr(core, "target_alt", None),
                "sun_sep_deg": getattr(core, "last_sun_distance_deg", 99.0),
                "solar_filter_confirmed": getattr(core, "solar_filter_confirmed", False),
                "cable_turns": turns,
                "cable_status": cable_status,
                "focus_pos": getattr(core, "focus_pos", 0),
                "data_rate_hz": 25,
            }

            self._set_cors_headers(200)
            self.wfile.write(json.dumps(telemetry).encode("utf-8"))
        else:
            self._set_cors_headers(404)
            self.wfile.write(b'{"error": "Not found"}')

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        if not self._is_authorized():
            self._set_cors_headers(401)
            self.wfile.write(b'{"success": false, "message": "Unauthorized"}')
            return

        try:
            params = json.loads(body)
        except Exception:
            params = {}

        core = self.core
        if not core:
            self._set_cors_headers(503)
            self.wfile.write(b'{"success": false, "message": "Bridge core not attached"}')
            return

        action = parsed_url.path.replace("/api/mount/", "").strip("/")

        try:
            if action == "stop":
                core.emergency_stop()
                resp = {"success": True, "message": "Emergency Stop executed"}
            elif action == "goto":
                az = float(params.get("az", core.mount_az))
                alt = float(params.get("alt", core.mount_alt))
                name = str(params.get("name", "Web Target"))
                success, msg = core.slew_to_altaz(az, alt, target_name=name)
                resp = {"success": success, "message": msg}
            elif action == "jog":
                axis = str(params.get("axis", "az"))
                dir_sign = int(params.get("dir", 1))
                deg = float(params.get("deg", 0.5))
                success = core.jog_axis(axis, dir_sign, deg)
                resp = {"success": success, "message": f"Jogged {axis.upper()} {dir_sign * deg}°"}
            elif action == "tracking":
                enable = bool(params.get("enabled", not getattr(core, "is_tracking", False)))
                rate = params.get("rate")
                if rate:
                    core.set_tracking_rate(rate)
                core.set_tracking(enable)
                resp = {"success": True, "message": f"Tracking set to {enable}"}
            elif action == "unwind":
                core.unwind_cable()
                resp = {"success": True, "message": "Unwinding cable initiated"}
            elif action == "focus":
                steps = int(params.get("steps", 0))
                core.move_focus(steps)
                resp = {"success": True, "message": f"Focus moved by {steps} steps"}
            elif action == "park":
                core.park_mount()
                resp = {"success": True, "message": "Mount parked"}
            elif action == "sync":
                core.sync_to_target()
                resp = {"success": True, "message": "Target synced"}
            else:
                resp = {"success": False, "message": f"Unknown action: {action}"}

            self._set_cors_headers(200)
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        except Exception as e:
            logger.exception("Error processing web command %s", action)
            self._set_cors_headers(500)
            self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Silence standard console spam."""
        pass


class WebBridgeServer:
    """Manages background HTTP server for Web and Vercel clients."""

    def __init__(self, core: Any, host: str = "0.0.0.0", port: int = 8080, auth_token: str = ""):
        self.core = core
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        TelescopeWebHandler.core = self.core
        TelescopeWebHandler.auth_token = self.auth_token

        ports_to_try = [self.port, 8088, 8000, 8888]
        started = False
        for p in ports_to_try:
            try:
                self.server = HTTPServer((self.host, p), TelescopeWebHandler)
                self.port = p
                self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="WebBridgeHTTP")
                self.thread.start()
                logger.info("Custom GoTo Web Bridge HTTP server started on http://%s:%d", self.host, self.port)
                started = True
                break
            except Exception as e:
                logger.debug("Port %d unavailable (%s), trying fallback...", p, e)

        if not started:
            logger.error("Failed to bind Web Bridge server on any port in %s", ports_to_try)

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            logger.info("Web Bridge HTTP server stopped")
