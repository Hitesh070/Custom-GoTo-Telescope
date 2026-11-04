"""
weather_service.py
Asynchronous Open-Meteo astronomical weather & seeing conditions telemetry service.
"""

from __future__ import annotations
import datetime as dt
import json
import threading
import urllib.request
from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class LiveWeatherService(QObject):
    """Asynchronous, non-blocking astronomical weather & cloud transparency telemetry
    queried from Open-Meteo API for real-time sky observation conditions.
    """
    weather_updated = pyqtSignal(dict)
    weather_error = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config
        self.latest_data: Optional[Dict[str, Any]] = None
        self._is_fetching: bool = False

        # Periodic auto-refresh every 15 minutes (900,000 ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.fetch_async)
        self._timer.start(900000)

    def fetch_async(self) -> None:
        if self._is_fetching:
            return
        self._is_fetching = True
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))
        threading.Thread(target=self._worker, args=(lat, lon), daemon=True).start()

    def _worker(self, lat: float, lon: float) -> None:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
                f"&current=cloud_cover,relative_humidity_2m,temperature_2m,wind_speed_10m,visibility,weather_code"
                f"&hourly=cloud_cover&forecast_days=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "CustomGoTo/3.1 (Telescope Controller)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            cur = data.get("current", {})
            cloud = int(cur.get("cloud_cover", 0))
            temp = float(cur.get("temperature_2m", 0.0))
            hum = int(cur.get("relative_humidity_2m", 0))
            wind = float(cur.get("wind_speed_10m", 0.0))
            vis_m = float(cur.get("visibility", 10000.0))
            vis_km = vis_m / 1000.0
            code = int(cur.get("weather_code", 0))

            wmo_desc = {
                0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing Rime Fog",
                51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
                61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
                71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
                80: "Rain Showers", 81: "Moderate Showers", 82: "Violent Showers",
                95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Heavy Hail Storm"
            }.get(code, "Cloudy" if cloud > 60 else "Partly Cloudy")

            if cloud >= 80:
                transparency = "Obscured (Overcast)"
                obs_status = "HEAVILY OBSCURED"
                badge = "[OVERCAST]"
            elif cloud >= 50:
                transparency = "Poor (Broken Clouds)"
                obs_status = "PARTIALLY OBSCURED"
                badge = "[BROKEN CLOUDS]"
            elif cloud >= 25:
                transparency = "Fair (Scattered Clouds)"
                obs_status = "FAIR SEEING"
                badge = "[SCATTERED CLOUDS]"
            elif cloud >= 10:
                transparency = "Good (Few Clouds)"
                obs_status = "GOOD SEEING"
                badge = "[MAINLY CLEAR]"
            else:
                transparency = "Pristine (Clear Dark Sky)"
                obs_status = "PRISTINE CONDITIONS"
                badge = "[CLEAR SKY]"

            result = {
                "cloud_cover": cloud,
                "temperature_c": temp,
                "humidity_pct": hum,
                "wind_kmh": wind,
                "visibility_km": vis_km,
                "weather_code": code,
                "condition": wmo_desc,
                "transparency": transparency,
                "obs_status": obs_status,
                "badge": badge,
                "is_overcast": (cloud >= 80),
                "updated_at": dt.datetime.now().strftime("%H:%M:%S")
            }
            self.latest_data = result
            try:
                self.weather_updated.emit(result)
            except RuntimeError:
                pass
        except Exception as e:
            try:
                self.weather_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            self._is_fetching = False


def play_audio_cue(cue_name: str, enabled: bool = False) -> None:
    """Audio cue hook (disabled or silent)."""
    pass
