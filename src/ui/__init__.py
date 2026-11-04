"""
User interface package for Custom GoTo Telescope Mount.
"""
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE, apply_theme_to_widget
from src.ui.widgets import EnlargedPolarRadarWidget, FocusCurveWidget
from src.ui.dialogs import (
    HelpGuideDialog, SettingsDialog, AutoFocusDialog, TonightSkyTourDialog,
    GoToDialog, SerialMonitorDialog
)
from src.ui.main_window import AstroTelescopeWindow, SolarSafetyBridge
from src.ui.app import launch_app
