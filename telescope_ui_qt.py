"""
telescope_ui_qt.py
Professional Desktop User Interface for 3-Axis GoTo Telescope Mount & Stellarium Bridge.
Version 3.1 - Scientific Human-Engineered Interface with High-Speed Telemetry Streaming.

Modularized facade integrating src.core and src.ui architecture for enterprise Windows deployment.
"""

from __future__ import annotations
import sys

# Core astronomical calculation & catalog re-exports
from src.core.astrometry import (
    deg_to_dms, deg_to_hms, hours_to_hms, radec_to_galactic, radec_to_ecliptic,
    calculate_parallactic_angle, calculate_ephemeris, get_constellation
)
from src.core.catalog import TONIGHT_BEST_CATALOG
from src.core.weather_service import LiveWeatherService, play_audio_cue

# UI theme, widgets, and dialog re-exports
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE, apply_theme_to_widget
from src.ui.widgets.sky_radar import EnlargedPolarRadarWidget
from src.ui.widgets.focus_curve import FocusCurveWidget
from src.ui.dialogs.help_dialog import HelpGuideDialog
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.dialogs.autofocus_dialog import AutoFocusDialog
from src.ui.dialogs.tour_dialog import TonightSkyTourDialog
from src.ui.dialogs.goto_dialog import GoToDialog
from src.ui.dialogs.serial_monitor_dialog import SerialMonitorDialog
from src.ui.main_window import AstroTelescopeWindow, SolarSafetyBridge
from src.ui.app import launch_app


if __name__ == "__main__":
    sim = "--simulate" in sys.argv
    launch_app(simulate=sim)
