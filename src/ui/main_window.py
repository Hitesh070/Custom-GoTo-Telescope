"""
main_window.py
Primary application window for the Custom GoTo Telescope Mount Controller.
Built with modern Windows 11 Fluent design principles and PyQt6.
"""

from __future__ import annotations
import logging
import math
import os
import sys
import time
import datetime as dt
import threading
from typing import Optional, Tuple, Dict, Any, List

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QObject, pyqtSignal, QThread
from PyQt6.QtGui import (
    QColor, QFont, QPen, QBrush, QPainter, QLinearGradient, 
    QKeySequence, QShortcut, QIcon, QPixmap, QPalette
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QComboBox, QCheckBox, 
    QRadioButton, QButtonGroup, QTextEdit, QFrame, QSplitter, 
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox, 
    QLineEdit, QMessageBox, QTabWidget, QScrollArea, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView
)

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL_LOCAL = True
except ImportError:
    serial = None
    HAS_PYSERIAL_LOCAL = False

from src.core.astrometry import (
    deg_to_dms, deg_to_hms, hours_to_hms, radec_to_galactic, radec_to_ecliptic,
    calculate_parallactic_angle, calculate_ephemeris, get_constellation
)
from src.core.catalog import TONIGHT_BEST_CATALOG
from src.core.weather_service import LiveWeatherService, play_audio_cue
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE, apply_theme_to_widget
from src.ui.widgets.sky_radar import EnlargedPolarRadarWidget
from src.ui.widgets.focus_curve import FocusCurveWidget
from src.ui.dialogs.help_dialog import HelpGuideDialog
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.dialogs.autofocus_dialog import AutoFocusDialog
from src.ui.dialogs.tour_dialog import TonightSkyTourDialog
from src.ui.dialogs.goto_dialog import GoToDialog
from src.ui.dialogs.serial_monitor_dialog import SerialMonitorDialog

try:
    from telescope_bridge import (
        BridgeCore, StellariumServer, Config, StellariumHttpFollower,
        sun_radec, moon_radec, planet_radec, radec_to_altaz, altaz_to_radec, separation_deg, 
        HAS_PYSERIAL, steps_to_angle, julian_date,
        precess_date_to_j2000, precess_j2000_to_date, lst_deg
    )
except ImportError:
    BridgeCore = None
    StellariumServer = None
    Config = None
    StellariumHttpFollower = None
    sun_radec = None
    moon_radec = None
    planet_radec = None
    radec_to_altaz = None
    altaz_to_radec = None
    separation_deg = None
    HAS_PYSERIAL = False
    steps_to_angle = None
    julian_date = None
    precess_date_to_j2000 = None
    precess_j2000_to_date = None
    lst_deg = None

class SolarSafetyBridge(QObject):
    """Thread-safe marshaling bridge to dispatch solar safety prompts to the Qt GUI thread."""
    request_prompt = pyqtSignal(float, object, object)



class GlobalShortcutEventFilter(QObject):
    """Application-wide hotkey filter capturing shortcuts across every window and dialog."""

    def __init__(self, main_win: 'AstroTelescopeWindow'):
        super().__init__()
        self.main_win = main_win

    def eventFilter(self, watched: QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)

            focus_w = QApplication.focusWidget()
            is_text_entry = isinstance(focus_w, (QLineEdit, QTextEdit, QtWidgets.QPlainTextEdit))
            is_input_widget = is_text_entry or isinstance(focus_w, (QComboBox, QSpinBox, QDoubleSpinBox))

            # 1. Toggle Night Vision (Alt+N or Ctrl+N) - active in ANY window or dialog
            if (alt or ctrl) and key == Qt.Key.Key_N:
                self.main_win.toggle_night_mode()
                return True

            # 2. Emergency Stop (Escape always; Space when not typing text) - active in ANY window
            if key == Qt.Key.Key_Escape:
                self.main_win._emergency_stop()
                return True
            if key == Qt.Key.Key_Space and not is_text_entry:
                self.main_win._emergency_stop()
                return True

            # 3. Ctrl+T: Tonight's Best Tour - active in ANY window
            if ctrl and key == Qt.Key.Key_T:
                self.main_win._open_sky_tour()
                return True

            # 4. Ctrl+G: GoTo Coordinates Dialog - active in ANY window
            if ctrl and key == Qt.Key.Key_G:
                self.main_win._open_goto_dialog()
                return True

            # 5. Ctrl+M: Serial Monitor - active in ANY window
            if ctrl and key == Qt.Key.Key_M:
                self.main_win._open_serial_monitor()
                return True

            # 6. Ctrl+S: Settings Dialog - active in ANY window
            if ctrl and key == Qt.Key.Key_S:
                self.main_win._open_settings()
                return True

            # 7. F1 or Ctrl+H: Help Manual - active in ANY window
            if key == Qt.Key.Key_F1 or (ctrl and key == Qt.Key.Key_H):
                self.main_win._open_help()
                return True

            # 8. Ctrl+U: Unwind Cable - active in ANY window
            if ctrl and key == Qt.Key.Key_U:
                self.main_win._unwind_cable()
                return True

            # 9. Ctrl+1, Ctrl+2, Ctrl+3: Slew Speed (Fine, Medium, Coarse)
            if ctrl and key == Qt.Key.Key_1:
                self.main_win._set_speed_and_button("fine")
                return True
            if ctrl and key == Qt.Key.Key_2:
                self.main_win._set_speed_and_button("medium")
                return True
            if ctrl and key == Qt.Key.Key_3:
                self.main_win._set_speed_and_button("coarse")
                return True

            # 10. Arrow Keys: Altitude & Azimuth Jogging
            # Active in any window when focus is not inside an input box or dropdown
            if not is_input_widget and not ctrl and not alt:
                if key == Qt.Key.Key_Up:
                    self.main_win._jog("up")
                    return True
                elif key == Qt.Key.Key_Down:
                    self.main_win._jog("down")
                    return True
                elif key == Qt.Key.Key_Left:
                    self.main_win._jog("left")
                    return True
                elif key == Qt.Key.Key_Right:
                    self.main_win._jog("right")
                    return True

        return super().eventFilter(watched, event)

class AstroTelescopeWindow(QMainWindow):
    """Professional 3-Axis Telescope Mount & Stellarium Bridge Desktop Application."""

    def __init__(self, core: Any, stellarium: Any, config: Any):
        super().__init__()
        self.core = core
        self.stellarium = stellarium
        self.config = config

        self.setWindowTitle("Custom GoTo")

        # Load and apply black hole application icon (multi-resolution .ico and high-res .png)
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.ico")
        png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "black_hole_icon.png")
        if not os.path.exists(ico_path) and hasattr(sys, '_MEIPASS'):
            ico_path = os.path.join(sys._MEIPASS, "assets", "black_hole_icon.ico")
            png_path = os.path.join(sys._MEIPASS, "assets", "black_hole_icon.png")

        app_icon = QIcon()
        if os.path.exists(ico_path):
            app_icon.addFile(ico_path)
        if os.path.exists(png_path):
            app_icon.addFile(png_path)

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)
        self.resize(1360, 900)
        self.setMinimumSize(1080, 780)

        # State: Night mode, console history, and slew arrival tracking
        self.night_mode: bool = bool(self.config.get("night_mode", False))
        self.audio_enabled: bool = False
        self._console_history: List[Tuple[str, str, str]] = []
        self._prev_stellarium_connected: bool = False
        self._was_slewing: bool = False
        self._was_moving: bool = False
        self.tour_window: Optional[TonightSkyTourDialog] = None
        app = QApplication.instance()
        if app:
            app.setStyleSheet(NIGHT_VISION_STYLE if self.night_mode else SCIENTIFIC_STYLE)
        self.setStyleSheet(NIGHT_VISION_STYLE if self.night_mode else SCIENTIFIC_STYLE)

        self.selected_jog_speed: str = "medium"
        self.follower: Any = StellariumHttpFollower(self.core, require_explicit_goto=True) if (StellariumHttpFollower and self.core) else None
        if self.follower and self.core:
            self.core.follower = self.follower

        # Thread-safe solar safety modal prompt bridge
        self.solar_bridge = SolarSafetyBridge()
        self.solar_bridge.request_prompt.connect(self._on_solar_prompt_requested, Qt.ConnectionType.QueuedConnection)
        self._is_showing_solar_dialog: bool = False

        # Ephemeris & celestial caching to ensure buttery-smooth 25 FPS UI without redundant math
        self._last_heavy_calc_time: float = 0.0
        self._cached_rise_transit_set: Tuple[str, str, str] = ("--:--", "--:--", "--:--")
        self._cached_target_key: Optional[Tuple[float, float, str]] = None
        self._cached_gal: Tuple[float, float] = (0.0, 0.0)
        self._cached_ecl: Tuple[float, float] = (0.0, 0.0)
        self._cached_constellation_mount: str = "Unknown"
        self._cached_constellation_target: str = "Unknown"
        self._last_mount_j2000: Optional[Tuple[float, float]] = None
        self._has_auto_synced_location: bool = False
        self._last_auto_sync_attempt: float = 0.0

        if self.core:
            self.core.solar_warning_callback = self._prompt_solar_warning
            self.core.solar_filter_confirmed = False

        # Live Open-Meteo astronomical weather & seeing service
        self.weather_service = LiveWeatherService(self.config, self)
        self.weather_service.weather_updated.connect(self._on_weather_updated)
        self.weather_service.weather_error.connect(lambda err: self.log_message("WARNING", f"Weather fetch: {err}"))
        self.weather_service.fetch_async()

        self._build_interface()
        self._setup_shortcuts()
        self._apply_active_theme()

        # HIGH-SPEED TELEMETRY TIMER: 40 ms = 25 FPS for smooth, real-time ticking
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(40)

        self._refresh_ports()

        # Web Bridge Server for Vercel & Mobile Remote Control
        self.web_server: Optional[Any] = None
        if self.config.get("web_server_enabled", True):
            try:
                from src.web_bridge import WebBridgeServer
                web_port = int(self.config.get("web_server_port", 8080))
                web_token = str(self.config.get("web_server_token", ""))
                self.web_server = WebBridgeServer(self.core, host="0.0.0.0", port=web_port, auth_token=web_token)
                self.web_server.start()
                self.log_message("INFO", f"Web Bridge API active on port {web_port}")
            except Exception as e:
                self.log_message("WARNING", f"Web Bridge startup error: {e}")

    def _build_interface(self) -> None:
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        main_layout = QVBoxLayout(root_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Header Deck
        main_layout.addWidget(self._create_header_deck())

        # 2. Safety Caution Strip
        main_layout.addWidget(self._create_safety_strip())

        # 3. Main Workspace
        workspace = QWidget()
        ws_layout = QHBoxLayout(workspace)
        ws_layout.setContentsMargins(12, 10, 12, 8)
        ws_layout.setSpacing(12)

        # Left Column: Enlarged Sky Radar & Observatory Clocks
        ws_layout.addWidget(self._create_left_radar_column(), stretch=5)

        # Center Column: Prominent Large Telemetry Deck (Matching Stellarium)
        ws_layout.addWidget(self._create_center_telemetry_column(), stretch=6)

        # Right Column: Motion D-Pad & Focus Controller
        ws_layout.addWidget(self._create_right_control_column(), stretch=4)

        main_layout.addWidget(workspace, stretch=8)

        # 4. Bottom Activity Console
        main_layout.addWidget(self._create_console_deck(), stretch=2)

    # --------------------------------------------------------------------------
    # Sub-deck Layouts
    # --------------------------------------------------------------------------

    def _create_header_deck(self) -> QWidget:
        header = QFrame()
        header.setProperty("class", "header-deck")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        # Compact identity block anchors the connection and status controls.
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand_title = QLabel("CUSTOM GOTO")
        brand_title.setProperty("class", "title")
        brand_subtitle = QLabel("TELESCOPE CONTROL")
        brand_subtitle.setProperty("class", "subtitle")
        brand.addWidget(brand_title)
        brand.addWidget(brand_subtitle)
        layout.addLayout(brand)
        layout.addSpacing(10)

        # Serial Connection Bar
        conn_box = QHBoxLayout()
        conn_box.setSpacing(6)

        self.lbl_p = QLabel("Serial Port:")
        lbl_p = self.lbl_p
        lbl_p.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #AA2222;")
        conn_box.addWidget(lbl_p)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(110)
        conn_box.addWidget(self.port_combo)

        btn_refresh = QPushButton("Scan Ports")
        btn_refresh.setToolTip("Scan serial COM ports")
        btn_refresh.clicked.connect(self._refresh_ports)
        conn_box.addWidget(btn_refresh)

        self.chk_simulate = QCheckBox("Simulate Uno")
        self.chk_simulate.setChecked(bool(self.config.get("simulate", False)))
        self.chk_simulate.setToolTip("Emulate Arduino Uno and motor kinematics in software")
        conn_box.addWidget(self.chk_simulate)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setProperty("class", "primary")
        self.btn_connect.clicked.connect(self._toggle_connection)
        conn_box.addWidget(self.btn_connect)

        layout.addLayout(conn_box)

        layout.addStretch()

        # Status Pills
        status_box = QHBoxLayout()
        status_box.setSpacing(10)

        self.lbl_serial_status = QLabel("ARDUINO: DISCONNECTED")
        self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #8A1B1B; padding: 4px 8px; border: 1px solid #B31D1D; border-radius: 3px;")
        status_box.addWidget(self.lbl_serial_status)

        self.lbl_stellarium_status = QLabel("STELLARIUM: LISTENING [10001]")
        self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #8A1B1B; padding: 4px 8px; border: 1px solid #B31D1D; border-radius: 3px;")
        status_box.addWidget(self.lbl_stellarium_status)

        self.btn_weather = QPushButton("[WEATHER: CHECKING...]")
        self.btn_weather.setToolTip("Query live Open-Meteo meteorological cloud cover & seeing telemetry")
        self.btn_weather.clicked.connect(self._refresh_weather_clicked)
        self.btn_weather.setStyleSheet("background-color: #272C36; border: 1px solid #3B4352; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;")
        status_box.addWidget(self.btn_weather)



        layout.addLayout(status_box)

        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        self.btn_help = QPushButton("Help")
        self.btn_help.clicked.connect(self._open_help)
        layout.addWidget(self.btn_help)

        self.btn_night_mode = QPushButton("Night Vision: ON" if self.night_mode else "Night Vision")
        if self.night_mode:
            self.btn_night_mode.setStyleSheet("background-color: #660A0A; border-color: #991414; color: #FFB3B3; font-weight: 700;")
        self.btn_night_mode.setToolTip("Toggle pure-red night-vision mode to preserve dark adaptation (Ctrl+N)")
        self.btn_night_mode.clicked.connect(self.toggle_night_mode)
        layout.addWidget(self.btn_night_mode)

        self.btn_estop = QPushButton("STOP")
        self.btn_estop.setProperty("class", "stop-btn")
        self.btn_estop.setToolTip("Emergency Stop (Spacebar / Esc)")
        self.btn_estop.clicked.connect(self._emergency_stop)
        layout.addWidget(self.btn_estop)

        return header

    def _create_safety_strip(self) -> QWidget:
        self.safety_strip = QFrame()
        strip = self.safety_strip
        strip.setStyleSheet("background-color: #381B1B; border-bottom: 1px solid #4D2626;" if not self.night_mode else "background-color: #240505; border-bottom: 1px solid #4D0A0A;")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 3, 14, 3)

        self.lbl_warn = QLabel("CAUTION: NEVER POINT TELESCOPE AT OR NEAR THE SUN WITHOUT A CERTIFIED SOLAR FILTER")
        lbl_warn = self.lbl_warn
        lbl_warn.setStyleSheet("font-size: 10px; font-weight: 700; color: #FFFFFF;" if not self.night_mode else "font-size: 10px; font-weight: 700; color: #FF3333;")
        layout.addWidget(lbl_warn)

        layout.addStretch()

        self.chk_solar_filter = QCheckBox("Solar Filter Attached")
        self.chk_solar_filter.setChecked(False)
        self.chk_solar_filter.setStyleSheet("font-size: 10px; font-weight: 700; color: #FFFFFF;" if not self.night_mode else "font-size: 10px; font-weight: 700; color: #FF4D4D;")
        self.chk_solar_filter.setToolTip("Enables solar observation when a physical certified solar filter is securely attached")
        self.chk_solar_filter.toggled.connect(self._toggle_solar_filter)
        layout.addWidget(self.chk_solar_filter)

        layout.addSpacing(12)

        self.lbl_sun_sep = QLabel("Sun Angular Separation: --")
        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 700; color: #EAD07C;")
        layout.addWidget(self.lbl_sun_sep)

        return strip

    def _create_left_radar_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Radar Card
        radar_card = QFrame()
        radar_card.setProperty("class", "card")
        radar_layout = QVBoxLayout(radar_card)
        radar_layout.setContentsMargins(10, 8, 10, 8)

        head_box = QHBoxLayout()
        lbl_title = QLabel("CELESTIAL SKY RADAR (ALTITUDE - AZIMUTH)")
        lbl_title.setProperty("class", "section-header")
        head_box.addWidget(lbl_title)
        head_box.addStretch()

        self.lbl_radar_legend = QLabel("Blue: Mount Reticle  |  Amber: Target  |  Yellow: Sun" if not self.night_mode else "Bright Red: Scope | Dotted Red: Target | Dark Crimson: Sun")
        lbl_legend = self.lbl_radar_legend
        lbl_legend.setStyleSheet("font-size: 10px; color: #8892A0;" if not self.night_mode else "font-size: 10px; color: #AA2222;")
        head_box.addWidget(lbl_legend)
        radar_layout.addLayout(head_box)

        self.radar_widget = EnlargedPolarRadarWidget()
        radar_layout.addWidget(self.radar_widget, stretch=1)
        layout.addWidget(radar_card, stretch=6)

        # Clocks Card
        clock_card = QFrame()
        clock_card.setProperty("class", "card")
        clock_layout = QGridLayout(clock_card)
        clock_layout.setContentsMargins(12, 8, 12, 8)
        clock_layout.setHorizontalSpacing(14)
        clock_layout.setVerticalSpacing(4)

        lbl_t1 = QLabel("UTC TIME:")
        lbl_t1.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t1, 0, 0)
        self.val_utc = QLabel("--:--:--")
        self.val_utc.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_utc, 0, 1)

        lbl_t2 = QLabel("LOCAL TIME:")
        lbl_t2.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t2, 1, 0)
        self.val_local = QLabel("--:--:--")
        self.val_local.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_local, 1, 1)

        lbl_t3 = QLabel("SIDEREAL (LMST):")
        lbl_t3.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t3, 0, 2)
        self.val_lst = QLabel("--h --m --s")
        self.val_lst.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_lst, 0, 3)

        lbl_t4 = QLabel("JULIAN DATE:")
        lbl_t4.setProperty("class", "table-key")
        clock_layout.addWidget(lbl_t4, 1, 2)
        self.val_jd = QLabel("2460000.000000")
        self.val_jd.setProperty("class", "table-val")
        clock_layout.addWidget(self.val_jd, 1, 3)

        layout.addWidget(clock_card, stretch=2)

        return col

    def _create_center_telemetry_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Table 1: Mount Position Details (Matching Stellarium Parameters)
        card_mount = QFrame()
        card_mount.setProperty("class", "card")
        lay_mount = QVBoxLayout(card_mount)
        lay_mount.setContentsMargins(14, 10, 14, 10)
        lay_mount.setSpacing(6)

        head_row = QHBoxLayout()
        lbl_head1 = QLabel("TELESCOPE MOUNT POSITION (CURRENT)")
        lbl_head1.setProperty("class", "section-header")
        head_row.addWidget(lbl_head1)
        head_row.addStretch()

        self.lbl_data_rate_label = QLabel("Data Rate:")
        self.lbl_data_rate_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #AA2222;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #8892A0;")
        head_row.addWidget(self.lbl_data_rate_label)

        self.combo_stream_rate = QComboBox()
        self.combo_stream_rate.addItems(["Fast Live (25 Hz)", "Normal (1s)"])
        self.combo_stream_rate.currentIndexChanged.connect(self._on_stream_rate_changed)
        head_row.addWidget(self.combo_stream_rate)

        lay_mount.addLayout(head_row)

        # Detailed Parameter Grid
        grid1 = QGridLayout()
        grid1.setVerticalSpacing(6)
        grid1.setHorizontalSpacing(16)

        fields1 = [
            ("RA/Dec (J2000.0):", "val_m_j2000"),
            ("RA/Dec (on date):", "val_m_jnow"),
            ("HA/Dec (apparent):", "val_m_hadec"),
            ("Az./Alt. (apparent):", "val_m_altaz"),
            ("Gal. long./lat. (l, b):", "val_m_gal"),
            ("Ecl. long./lat. (J2000.0):", "val_m_ecl"),
            ("Parallactic Angle:", "val_m_parallactic"),
            ("IAU Constellation:", "val_m_constellation"),
            ("Motor Steps (Az / Alt / Foc):", "val_m_steps"),
        ]

        for row, (label_text, attr_name) in enumerate(fields1):
            lbl_k = QLabel(label_text)
            lbl_k.setProperty("class", "table-key")
            lbl_v = QLabel("--")
            lbl_v.setProperty("class", "table-val")
            setattr(self, attr_name, lbl_v)
            grid1.addWidget(lbl_k, row, 0)
            grid1.addWidget(lbl_v, row, 1)

        lay_mount.addLayout(grid1)
        layout.addWidget(card_mount, stretch=5)

        # Table 2: Active Target Object Details (Matching Stellarium Target Overlay)
        card_target = QFrame()
        card_target.setProperty("class", "card")
        lay_target = QVBoxLayout(card_target)
        lay_target.setContentsMargins(14, 10, 14, 10)
        lay_target.setSpacing(6)

        head_row2 = QHBoxLayout()
        lbl_head2 = QLabel("CURRENT TRACKED OBJECT (STELLARIUM TARGET)")
        lbl_head2.setProperty("class", "section-header")
        head_row2.addWidget(lbl_head2)
        head_row2.addStretch()

        self.btn_satellite_follow = QPushButton("Satellite Follow: OFF")
        self.btn_satellite_follow.setToolTip("Continuous real-time tracking for moving satellites (ISS, Starlink) via Stellarium Remote Control (port 8090)")
        self.btn_satellite_follow.clicked.connect(self._toggle_satellite_follow)
        head_row2.addWidget(self.btn_satellite_follow)

        lay_target.addLayout(head_row2)

        grid2 = QGridLayout()
        grid2.setVerticalSpacing(5)
        grid2.setHorizontalSpacing(14)

        fields2 = [
            ("Target Status:", "val_t_status"),
            ("Target RA/Dec (J2000):", "val_t_j2000"),
            ("Target RA/Dec (on date):", "val_t_jnow"),
            ("Target Az./Alt. (apparent):", "val_t_altaz"),
            ("Target Constellation:", "val_t_constellation"),
            ("Rise / Transit / Set:", "val_t_ephemeris"),
            ("Sun Angular Separation:", "val_t_sunsep"),
            ("Tracking Kinematics:", "val_t_tracking"),
            ("Tracking Pulses / Drift:", "val_t_pulses"),
            ("Stellarium Live Follow:", "val_t_follow_status"),
        ]

        for row, (label_text, attr_name) in enumerate(fields2):
            lbl_k = QLabel(label_text)
            lbl_k.setProperty("class", "table-key")
            lbl_v = QLabel("None")
            lbl_v.setProperty("class", "table-val")
            setattr(self, attr_name, lbl_v)
            grid2.addWidget(lbl_k, row, 0)
            grid2.addWidget(lbl_v, row, 1)

        lay_target.addLayout(grid2)
        layout.addWidget(card_target, stretch=4)

        return col

    def _create_right_control_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Motion & Jog Card
        jog_card = QFrame()
        jog_card.setProperty("class", "card")
        jog_layout = QVBoxLayout(jog_card)
        jog_layout.setContentsMargins(12, 8, 12, 8)
        jog_layout.setSpacing(6)

        lbl_jog = QLabel("MANUAL MOTION CONTROLS")
        lbl_jog.setProperty("class", "section-header")
        jog_layout.addWidget(lbl_jog)

        dpad_grid = QGridLayout()
        dpad_grid.setSpacing(5)

        btn_up = QPushButton("ALT +")
        btn_up.setMinimumHeight(36)
        btn_up.clicked.connect(lambda: self._jog("up"))
        dpad_grid.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("AZ -")
        btn_left.setMinimumHeight(36)
        btn_left.clicked.connect(lambda: self._jog("left"))
        dpad_grid.addWidget(btn_left, 1, 0)

        btn_stop = QPushButton("STOP")
        btn_stop.setProperty("class", "stop-btn")
        btn_stop.setMinimumHeight(36)
        btn_stop.clicked.connect(self._emergency_stop)
        dpad_grid.addWidget(btn_stop, 1, 1)

        btn_right = QPushButton("AZ +")
        btn_right.setMinimumHeight(36)
        btn_right.clicked.connect(lambda: self._jog("right"))
        dpad_grid.addWidget(btn_right, 1, 2)

        btn_down = QPushButton("ALT -")
        btn_down.setMinimumHeight(36)
        btn_down.clicked.connect(lambda: self._jog("down"))
        dpad_grid.addWidget(btn_down, 2, 1)

        jog_layout.addLayout(dpad_grid)

        # Speed Selectors
        speed_box = QHBoxLayout()
        speed_box.setSpacing(4)

        self.btn_fine = QPushButton("Fine (0.05°)")
        self.btn_med = QPushButton("Medium (0.50°)")
        self.btn_coarse = QPushButton("Coarse (3.00°)")

        self.btn_fine.setCheckable(True)
        self.btn_med.setCheckable(True)
        self.btn_coarse.setCheckable(True)
        self.btn_med.setChecked(True)

        spd_group = QButtonGroup(self)
        spd_group.addButton(self.btn_fine)
        spd_group.addButton(self.btn_med)
        spd_group.addButton(self.btn_coarse)

        self.btn_fine.clicked.connect(lambda: self._set_speed("fine"))
        self.btn_med.clicked.connect(lambda: self._set_speed("medium"))
        self.btn_coarse.clicked.connect(lambda: self._set_speed("coarse"))

        speed_box.addWidget(self.btn_fine)
        speed_box.addWidget(self.btn_med)
        speed_box.addWidget(self.btn_coarse)
        jog_layout.addLayout(speed_box)

        layout.addWidget(jog_card)

        # Command Deck Card
        act_card = QFrame()
        act_card.setProperty("class", "card")
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(12, 8, 12, 8)
        act_layout.setSpacing(6)

        lbl_cmd = QLabel("ALIGNMENT & MOUNT ACTIONS")
        lbl_cmd.setProperty("class", "section-header")
        act_layout.addWidget(lbl_cmd)

        # Smarter Kinematics: Tracking Rate Selector Bar
        rate_box = QHBoxLayout()
        rate_box.setSpacing(4)
        self.lbl_tracking_rate_label = QLabel("Rate:")
        self.lbl_tracking_rate_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #AA2222;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #8892A0;")
        rate_box.addWidget(self.lbl_tracking_rate_label)

        self.rate_buttons: Dict[str, QPushButton] = {}
        for r_name in ("Sidereal", "Lunar", "Solar", "King"):
            btn_r = QPushButton(r_name)
            btn_r.setCheckable(True)
            active = (r_name == self.config.get("tracking_rate", "Sidereal"))
            btn_r.setChecked(active)
            if active:
                btn_r.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1E4472; color: #FFFFFF; font-weight: 700; border: 1px solid #336FA5;")
            else:
                btn_r.setStyleSheet("font-size: 10px; padding: 3px 6px;")
            btn_r.clicked.connect(lambda checked, r=r_name: self._set_tracking_rate(r))
            rate_box.addWidget(btn_r)
            self.rate_buttons[r_name] = btn_r

        act_layout.addLayout(rate_box)

        act_grid = QGridLayout()
        act_grid.setSpacing(5)

        self.btn_sync = QPushButton("Sync Target")
        self.btn_sync.setProperty("class", "sync-btn")
        self.btn_sync.setToolTip("Calibrate telescope orientation to active Stellarium target")
        self.btn_sync.clicked.connect(self._sync_scope)
        act_grid.addWidget(self.btn_sync, 0, 0)

        self.btn_track = QPushButton("Tracking: OFF")
        self.btn_track.clicked.connect(self._toggle_tracking)
        act_grid.addWidget(self.btn_track, 0, 1)

        self.btn_home_alt = QPushButton("Home Altitude")
        self.btn_home_alt.clicked.connect(lambda: self._home_axis("ALT"))
        act_grid.addWidget(self.btn_home_alt, 1, 0)

        self.btn_home_az = QPushButton("Home Azimuth")
        self.btn_home_az.clicked.connect(lambda: self._home_axis("AZ"))
        act_grid.addWidget(self.btn_home_az, 1, 1)

        btn_park = QPushButton("Park Telescope")
        btn_park.clicked.connect(self._park_mount)
        act_grid.addWidget(btn_park, 2, 0)

        btn_zero = QPushButton("Zero Position (0,0)")
        btn_zero.setToolTip("Set current orientation as True North and Level")
        btn_zero.clicked.connect(self._confirm_zero)
        act_grid.addWidget(btn_zero, 2, 1)

        self.btn_sky_tour = QPushButton("Tonight's Best")
        self.btn_sky_tour.setProperty("class", "primary")
        self.btn_sky_tour.setToolTip("Interactive celestial tour of visible targets with 20x/30x/40x eyepiece recommendations (Ctrl+T)")
        self.btn_sky_tour.clicked.connect(self._open_sky_tour)
        act_grid.addWidget(self.btn_sky_tour, 3, 0, 1, 2)

        act_layout.addLayout(act_grid)

        # Cable-Wrap Prevention Monitor & Unwind Deck
        cable_box = QHBoxLayout()
        cable_box.setSpacing(6)
        self.lbl_cable_wrap = QLabel("Cable: 0.00 turns [OK]")
        self.lbl_cable_wrap.setStyleSheet("font-size: 11px; font-weight: 600; color: #88C0FF;")
        cable_box.addWidget(self.lbl_cable_wrap)

        self.btn_unwind = QPushButton("Unwind (0°)")
        btn_unwind = self.btn_unwind
        btn_unwind.setToolTip("Slew Azimuth to 0° True North to untangle cables")
        btn_unwind.setStyleSheet("font-size: 10px; padding: 3px 8px; background: #1A2330; border: 1px solid #2B3D52; border-radius: 3px;" if not self.night_mode else "font-size: 10px; padding: 3px 8px; background: #260505; border: 1px solid #4D0A0A; color: #FFAAAA; border-radius: 3px;")
        btn_unwind.clicked.connect(self._unwind_cable)
        cable_box.addWidget(btn_unwind)

        act_layout.addLayout(cable_box)
        layout.addWidget(act_card)

        # Focus Control Card
        foc_card = QFrame()
        foc_card.setProperty("class", "card")
        foc_layout = QVBoxLayout(foc_card)
        foc_layout.setContentsMargins(12, 8, 12, 8)
        foc_layout.setSpacing(6)

        fhead = QHBoxLayout()
        lbl_f = QLabel("MOTORIZED FOCUS")
        lbl_f.setProperty("class", "section-header")
        fhead.addWidget(lbl_f)
        fhead.addStretch()

        self.lbl_foc_pos = QLabel("Position: 0 steps")
        self.lbl_foc_pos.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #88B0D8; font-weight: 600;")
        fhead.addWidget(self.lbl_foc_pos)
        foc_layout.addLayout(fhead)

        foc_btns = QGridLayout()
        foc_btns.setSpacing(4)

        btn_cin = QPushButton("Coarse In (<<)")
        btn_cin.clicked.connect(lambda: self._move_focus("coarse", True))
        foc_btns.addWidget(btn_cin, 0, 0)

        btn_fin = QPushButton("Fine In (<)")
        btn_fin.clicked.connect(lambda: self._move_focus("fine", True))
        foc_btns.addWidget(btn_fin, 0, 1)

        btn_fout = QPushButton("Fine Out (>)")
        btn_fout.clicked.connect(lambda: self._move_focus("fine", False))
        foc_btns.addWidget(btn_fout, 1, 0)

        btn_cout = QPushButton("Coarse Out (>>)")
        btn_cout.clicked.connect(lambda: self._move_focus("coarse", False))
        foc_btns.addWidget(btn_cout, 1, 1)

        foc_layout.addLayout(foc_btns)

        # Fine-Tuning Step Controls & Direct Step GoTo
        foc_fine_box = QHBoxLayout()
        foc_fine_box.setSpacing(4)

        btn_nudge_in = QPushButton("-5 steps")
        btn_nudge_in.setToolTip("Fine nudge inward 5 steps")
        btn_nudge_in.clicked.connect(lambda: self._move_focus_steps(-5))
        foc_fine_box.addWidget(btn_nudge_in)

        btn_nudge_out = QPushButton("+5 steps")
        btn_nudge_out.setToolTip("Fine nudge outward 5 steps")
        btn_nudge_out.clicked.connect(lambda: self._move_focus_steps(5))
        foc_fine_box.addWidget(btn_nudge_out)

        self.spin_foc_direct = QSpinBox()
        self.spin_foc_direct.setRange(-50000, 50000)
        self.spin_foc_direct.setValue(0)
        self.spin_foc_direct.setToolTip("Target step position")
        foc_fine_box.addWidget(self.spin_foc_direct)

        btn_goto_foc = QPushButton("Go")
        btn_goto_foc.setToolTip("Slew to target step")
        btn_goto_foc.clicked.connect(self._goto_focus_step)
        foc_fine_box.addWidget(btn_goto_foc)

        foc_layout.addLayout(foc_fine_box)

        # Automated Focus Routine & Reset
        foc_auto_box = QHBoxLayout()
        foc_auto_box.setSpacing(4)

        btn_autofocus = QPushButton("Autofocus")
        btn_autofocus.setProperty("class", "primary")
        btn_autofocus.setToolTip("Run automated V-curve focus routine to find critical focus zone")
        btn_autofocus.clicked.connect(self._open_autofocus_dialog)
        foc_auto_box.addWidget(btn_autofocus)

        btn_zero_foc = QPushButton("Zero Focus")
        btn_zero_foc.setToolTip("Reset focus coordinate to 0")
        btn_zero_foc.clicked.connect(self._zero_focus)
        foc_auto_box.addWidget(btn_zero_foc)

        foc_layout.addLayout(foc_auto_box)
        layout.addWidget(foc_card)

        return col

    def _create_console_deck(self) -> QWidget:
        self.console_deck = QFrame()
        deck = self.console_deck
        deck.setStyleSheet("background-color: #0E1015; border-top: 1px solid #252A34;" if not self.night_mode else "background-color: #050000; border-top: 1px solid #330808;")
        layout = QVBoxLayout(deck)
        layout.setContentsMargins(14, 6, 14, 8)
        layout.setSpacing(4)

        h = QHBoxLayout()
        lbl = QLabel("ACTIVITY CONSOLE & HARDWARE COMMUNICATIONS")
        lbl.setProperty("class", "section-header")
        h.addWidget(lbl)
        h.addStretch()

        self.btn_sync_loc = QPushButton("Sync Location")
        self.btn_sync_loc.setToolTip("Synchronize observer site coordinates with Stellarium (Port 8090)")
        self.btn_sync_loc.clicked.connect(lambda: self._sync_location_from_stellarium(quiet=False))
        h.addWidget(self.btn_sync_loc)

        btn_clear = QPushButton("Clear Console")
        btn_clear.clicked.connect(self._clear_console)
        h.addWidget(btn_clear)

        self.btn_serial_mon = QPushButton("Serial Monitor")
        self.btn_serial_mon.setToolTip("Open real-time Arduino Serial Monitor (Testing)")
        self.btn_serial_mon.clicked.connect(self._open_serial_monitor)
        h.addWidget(self.btn_serial_mon)

        self.chk_autoscroll = QCheckBox("Auto-Scroll")
        self.chk_autoscroll.setChecked(True)
        h.addWidget(self.chk_autoscroll)

        layout.addLayout(h)

        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setMaximumHeight(115)
        self.console_text.document().setMaximumBlockCount(2000)
        layout.addWidget(self.console_text)

        return deck

    # --------------------------------------------------------------------------
    # User Interactions & Shortcuts
    # --------------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        """Installs application-wide event filters and multi-window shortcuts."""
        app = QApplication.instance()
        if app:
            if not hasattr(self, "_global_shortcut_filter") or self._global_shortcut_filter is None:
                self._global_shortcut_filter = GlobalShortcutEventFilter(self)
                app.installEventFilter(self._global_shortcut_filter)

        def _safe_jog(direction: str):
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, (QComboBox, QLineEdit, QTextEdit, QtWidgets.QPlainTextEdit, QSpinBox, QDoubleSpinBox)):
                return
            self._jog(direction)

        def _safe_space():
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, (QLineEdit, QTextEdit, QtWidgets.QPlainTextEdit)):
                return
            self._emergency_stop()

        def _reg(key_val, callback):
            sc = QShortcut(QKeySequence(key_val), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(callback)
            return sc

        self._registered_shortcuts = [
            _reg("Alt+N", self.toggle_night_mode),
            _reg("Ctrl+N", self.toggle_night_mode),
            _reg("Escape", self._emergency_stop),
            _reg("Space", _safe_space),
            _reg("Ctrl+T", self._open_sky_tour),
            _reg("Ctrl+G", self._open_goto_dialog),
            _reg("Ctrl+M", self._open_serial_monitor),
            _reg("Ctrl+S", self._open_settings),
            _reg("Ctrl+H", self._open_help),
            _reg(Qt.Key.Key_F1, self._open_help),
            _reg("Ctrl+U", self._unwind_cable),
            _reg("Ctrl+1", lambda: self._set_speed_and_button("fine")),
            _reg("Ctrl+2", lambda: self._set_speed_and_button("medium")),
            _reg("Ctrl+3", lambda: self._set_speed_and_button("coarse")),
            _reg(Qt.Key.Key_Up, lambda: _safe_jog("up")),
            _reg(Qt.Key.Key_Down, lambda: _safe_jog("down")),
            _reg(Qt.Key.Key_Left, lambda: _safe_jog("left")),
            _reg(Qt.Key.Key_Right, lambda: _safe_jog("right")),
        ]

    def _set_speed_and_button(self, mode: str) -> None:
        self._set_speed(mode)
        if mode == "fine" and hasattr(self, "btn_fine"):
            self.btn_fine.setChecked(True)
        elif mode == "medium" and hasattr(self, "btn_med"):
            self.btn_med.setChecked(True)
        elif mode == "coarse" and hasattr(self, "btn_coarse"):
            self.btn_coarse.setChecked(True)

    def _set_speed(self, mode: str) -> None:
        self.selected_jog_speed = mode

    def _jog(self, direction: str) -> None:
        if self.core:
            self.core.jog(direction, self.selected_jog_speed)

    def toggle_night_mode(self) -> None:
        self.night_mode = not self.night_mode
        self.config["night_mode"] = self.night_mode
        if hasattr(self.config, "save"):
            self.config.save()
        self._apply_active_theme()

    def _refresh_weather_clicked(self) -> None:
        if hasattr(self, "weather_service") and self.weather_service:
            self.weather_service.fetch_async()
        if hasattr(self, "btn_weather"):
            self.btn_weather.setText("[CHECKING...]")

    def _on_weather_updated(self, data: Dict[str, Any]) -> None:
        if hasattr(self, "weather_service") and self.weather_service:
            self.weather_service.latest_data = data
        if not hasattr(self, "btn_weather"):
            return
        badge = data.get("badge", "[WEATHER]")
        cloud = data.get("cloud_cover", 0)
        temp = data.get("temperature_c", 0.0)
        hum = data.get("humidity_pct", 0)
        wind = data.get("wind_kmh", 0.0)
        vis = data.get("visibility_km", 0.0)
        cond = data.get("condition", "Unknown")
        obs = data.get("obs_status", "")

        self.btn_weather.setText(f"{badge} {cloud}% CLOUD | {temp:.1f}°C")
        self.btn_weather.setToolTip(
            f"Live Astronomical Weather & Seeing (Open-Meteo)\n"
            f"Status: {obs} ({cond})\n"
            f"Cloud Cover: {cloud}%\n"
            f"Temperature: {temp:.1f}°C | Humidity: {hum}%\n"
            f"Wind: {wind:.1f} km/h | Visibility: {vis:.1f} km\n"
            f"Last Updated: {data.get('updated_at', '--:--')}\n"
            f"(Click to refresh now)"
        )
        self._style_weather_btn()
        if hasattr(self, "tour_window") and self.tour_window:
            self.tour_window.update_weather_display(data)

    def _style_weather_btn(self) -> None:
        if not hasattr(self, "btn_weather"):
            return
        if self.night_mode:
            self.btn_weather.setStyleSheet(
                "background-color: #1A0303; border: 1px solid #4D0A0A; color: #FFAAAA; "
                "font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;"
            )
        else:
            self.btn_weather.setStyleSheet(
                "background-color: #272C36; border: 1px solid #3B4352; color: #FFFFFF; "
                "font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 3px;"
            )

    def _update_connection_indicators(self) -> None:
        if not hasattr(self, "lbl_serial_status") or not hasattr(self, "lbl_stellarium_status"):
            return

        nm = self.night_mode

        # Arduino status badge
        if self.core.link and self.core.link.is_open:
            is_sim = type(self.core.link).__name__ == "SimLink" or getattr(self.core.link, "is_simulated", False)
            if is_sim:
                self.lbl_serial_status.setText("ARDUINO: SIMULATED")
                if nm:
                    self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFAAAA; background-color: #4A1020; padding: 4px 8px; border: 1px solid #801830; border-radius: 3px;")
                else:
                    self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #1E4472; padding: 4px 8px; border: 1px solid #2B6496; border-radius: 3px;")
            else:
                self.lbl_serial_status.setText("ARDUINO: CONNECTED")
                if nm:
                    self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFAAAA; background-color: #5C0B0B; padding: 4px 8px; border: 1px solid #991414; border-radius: 3px;")
                else:
                    self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #1E7E34; padding: 4px 8px; border: 1px solid #28A745; border-radius: 3px;")
        else:
            self.lbl_serial_status.setText("ARDUINO: DISCONNECTED")
            if nm:
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #AA2222; background-color: #1A0303; padding: 4px 8px; border: 1px solid #4D0A0A; border-radius: 3px;")
            else:
                self.lbl_serial_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #8A1B1B; padding: 4px 8px; border: 1px solid #B31D1D; border-radius: 3px;")

        # Stellarium status badge
        stel_conn = bool(self.stellarium and self.stellarium.is_client_connected)
        if stel_conn:
            self.lbl_stellarium_status.setText("STELLARIUM: CONNECTED")
            if nm:
                self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFAAAA; background-color: #5C0B0B; padding: 4px 8px; border: 1px solid #991414; border-radius: 3px;")
            else:
                self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #1E7E34; padding: 4px 8px; border: 1px solid #28A745; border-radius: 3px;")
        else:
            port_num = self.config.get("stellarium_port", 10001)
            self.lbl_stellarium_status.setText(f"STELLARIUM: LISTENING [{port_num}]")
            if nm:
                self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #AA2222; background-color: #1A0303; padding: 4px 8px; border: 1px solid #4D0A0A; border-radius: 3px;")
            else:
                self.lbl_stellarium_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; background-color: #8A1B1B; padding: 4px 8px; border: 1px solid #B31D1D; border-radius: 3px;")

    def _apply_active_theme(self) -> None:
        nm = self.night_mode
        app = QApplication.instance()
        if app:
            app.setStyleSheet(NIGHT_VISION_STYLE if nm else SCIENTIFIC_STYLE)
        self.setStyleSheet(NIGHT_VISION_STYLE if nm else SCIENTIFIC_STYLE)
        self.radar_widget.set_night_mode(nm)

        # Broadcast active night mode to all open top-level dialogs/windows
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, "set_night_mode") and callable(widget.set_night_mode) and widget is not self:
                try:
                    widget.set_night_mode(nm)
                except Exception:
                    pass

        if hasattr(self, "btn_night_mode"):
            self.btn_night_mode.setText("Night Vision: ON" if nm else "Night Vision")
            self.btn_night_mode.setStyleSheet("background-color: #660A0A; border-color: #991414; color: #FFB3B3; font-weight: 700;" if nm else "")

        if hasattr(self, "safety_strip"):
            self.safety_strip.setStyleSheet("background-color: #240505; border-bottom: 1px solid #4D0A0A;" if nm else "background-color: #381B1B; border-bottom: 1px solid #4D2626;")
        if hasattr(self, "lbl_warn"):
            self.lbl_warn.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF3333;" if nm else "font-size: 10px; font-weight: 700; color: #FFFFFF;")
        if hasattr(self, "chk_solar_filter"):
            self.chk_solar_filter.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF4D4D;" if nm else "font-size: 10px; font-weight: 700; color: #FFFFFF;")
        if hasattr(self, "lbl_data_rate_label"):
            self.lbl_data_rate_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #AA2222;" if nm else "font-size: 11px; font-weight: 600; color: #8892A0;")
        if hasattr(self, "lbl_tracking_rate_label"):
            self.lbl_tracking_rate_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #AA2222;" if nm else "font-size: 11px; font-weight: 600; color: #8892A0;")

        # Re-render console history with active theme colors
        if hasattr(self, "console_text") and hasattr(self, "_console_history"):
            self.console_text.clear()
            for ts, lvl, msg in self._console_history:
                self._append_console_entry(ts, lvl, msg)

        if hasattr(self, "lbl_radar_legend"):
            self.lbl_radar_legend.setText("Bright Red: Scope | Dotted Red: Target | Dark Crimson: Sun" if nm else "Blue: Mount Reticle  |  Amber: Target  |  Yellow: Sun")
            self.lbl_radar_legend.setStyleSheet("font-size: 10px; color: #AA2222;" if nm else "font-size: 10px; color: #8892A0;")

        if hasattr(self, "lbl_cable_wrap"):
            self.lbl_cable_wrap.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF4D4D;" if nm else "font-size: 11px; font-weight: 600; color: #88C0FF;")
        if hasattr(self, "btn_unwind"):
            self.btn_unwind.setStyleSheet("font-size: 10px; padding: 3px 8px; background: #260505; border: 1px solid #4D0A0A; color: #FFAAAA; border-radius: 3px;" if nm else "font-size: 10px; padding: 3px 8px; background: #1A2330; border: 1px solid #2B3D52; color: #DCE2EB; border-radius: 3px;")
        if hasattr(self, "lbl_foc_pos"):
            self.lbl_foc_pos.setStyleSheet("font-family: 'Consolas'; font-size: 11px; color: #FF4D4D; font-weight: 600;" if nm else "font-family: 'Consolas'; font-size: 11px; color: #88B0D8; font-weight: 600;")
        if hasattr(self, "console_deck"):
            self.console_deck.setStyleSheet("background-color: #050000; border-top: 1px solid #330808;" if nm else "background-color: #0E1015; border-top: 1px solid #252A34;")

        if hasattr(self, "lbl_p"):
            self.lbl_p.setStyleSheet("font-size: 11px; color: #AA2222;" if nm else "font-size: 11px; color: #8892A0;")

        # Tracking rate buttons styling
        cur_rate = getattr(self.core, "tracking_rate", "Sidereal") if self.core else "Sidereal"
        self._set_tracking_rate(cur_rate)

        # Satellite follow button
        if hasattr(self, "btn_satellite_follow"):
            is_active = hasattr(self, "follower") and self.follower and self.follower.is_active
            if is_active:
                self.btn_satellite_follow.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;" if nm else "background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
            else:
                self.btn_satellite_follow.setStyleSheet("")

        self._style_weather_btn()
        self._update_connection_indicators()

    def _on_audio_toggled(self, checked: bool) -> None:
        pass

    def _emergency_stop(self) -> None:
        play_audio_cue("stop", self.audio_enabled)
        if self.core:
            self.core.emergency_stop()
        if hasattr(self, "btn_track"):
            self.btn_track.setText("Tracking: OFF")

    def _set_tracking_rate(self, rate_name: str) -> None:
        if self.core and hasattr(self.core, "set_tracking_rate"):
            self.core.set_tracking_rate(rate_name)
        for name, btn in getattr(self, "rate_buttons", {}).items():
            is_active = (name.lower() == rate_name.lower())
            btn.setChecked(is_active)
            if is_active:
                if self.night_mode:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #5C0B0B; color: #FFAAAA; font-weight: 700; border: 1px solid #801010;")
                else:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1E4472; color: #FFFFFF; font-weight: 700; border: 1px solid #336FA5;")
            else:
                if self.night_mode:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px; background-color: #1A0303; color: #FF4D4D; border: 1px solid #4D0A0A;")
                else:
                    btn.setStyleSheet("font-size: 10px; padding: 3px 6px;")

    def _unwind_cable(self) -> None:
        if not self.core:
            return
        success = self.core.unwind_cable()
        if success and hasattr(self, "btn_track"):
            self.btn_track.setText("Tracking: OFF")
            self.btn_track.setStyleSheet("background-color: #1A0303; border-color: #4D0A0A; color: #FF4D4D;" if self.night_mode else "")

    def _sync_scope(self) -> None:
        if self.core:
            self.core.sync()

    def _toggle_tracking(self) -> None:
        if self.core:
            self.core.tracking_enabled = not self.core.tracking_enabled
            if not self.core.tracking_enabled:
                self.core.target_type = ""
                if hasattr(self.core, "follower") and self.core.follower:
                    self.core.follower.clear_authorized_target()
                if self.core.link and self.core.link.is_open:
                    self.core.link.send("S")
            status = "ON" if self.core.tracking_enabled else "OFF"
            self.btn_track.setText(f"Tracking: {status}")
            self.core.on_event("INFO", f"Tracking {status}")

    def _toggle_satellite_follow(self) -> None:
        if not self.follower:
            return
        if self.follower.is_active:
            self.follower.stop()
            self.btn_satellite_follow.setText("Satellite Follow: OFF")
            self.btn_satellite_follow.setStyleSheet("")
            self.log_message("INFO", "Stellarium Live Satellite Follow disabled.")
        else:
            self.follower.start()
            self.btn_satellite_follow.setText("Satellite Follow: ACTIVE")
            if self.night_mode:
                self.btn_satellite_follow.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;")
            else:
                self.btn_satellite_follow.setStyleSheet("background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
            self.log_message("INFO", "Stellarium Live Satellite Follow enabled (polling port 8090 for moving satellites & objects).")

    def _prompt_solar_warning(self, sun_sep: float) -> bool:
        """Prompts a prominent safety dialog when a slew near or at the Sun is commanded.
        Thread-safe: marshals from background TCP/HTTP threads to the main Qt GUI thread.
        """
        app = QApplication.instance()
        if not app:
            return False

        # If already on the Qt main GUI thread, execute directly
        if QThread.currentThread() == app.thread():
            return self._show_solar_warning_dialog(sun_sep)

        # Dispatched from a background worker thread (e.g. StellariumServer TCP thread):
        res = [False]
        done_evt = threading.Event()
        self.solar_bridge.request_prompt.emit(sun_sep, res, done_evt)
        # Wait up to 60 seconds for observer interaction
        done_evt.wait(timeout=60.0)
        return res[0]

    def _on_solar_prompt_requested(self, sun_sep: float, res: list, done_evt: threading.Event) -> None:
        """Slot executed on the main Qt GUI thread."""
        try:
            res[0] = self._show_solar_warning_dialog(sun_sep)
        finally:
            done_evt.set()

    def _show_solar_warning_dialog(self, sun_sep: float) -> bool:
        """Renders the dark-mode eye safety confirmation modal on the main GUI thread."""
        app = QApplication.instance()
        if app and app.platformName() == "offscreen":
            return True

        if self._is_showing_solar_dialog:
            return False

        self._is_showing_solar_dialog = True
        try:
            parent = QApplication.activeModalWidget() or QApplication.activeWindow() or self
            dlg = QDialog(parent)
            dlg.setWindowTitle("CRITICAL EYE SAFETY: Solar Observation Warning")
            dlg.setModal(True)
            dlg.setStyleSheet("background-color: #11141A; color: #FFFFFF; font-family: 'Segoe UI', sans-serif;")
            dlg.setMinimumWidth(520)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(14)

            # Warning Header Banner (no outer red box, no border on description)
            lbl_danger_title = QLabel("CRITICAL EYE SAFETY WARNING")
            lbl_danger_title.setStyleSheet(
                "background-color: #4A1212; border: 1px solid #C62828; border-radius: 4px; "
                "color: #FF6B6B; font-size: 14px; font-weight: 800; padding: 8px 14px;"
            )
            layout.addWidget(lbl_danger_title)

            lbl_danger_desc = QLabel(
                f"You are about to point the telescope towards the SUN (angular separation: {sun_sep:.1f}°).\n\n"
                "DANGER: Looking directly at the Sun through an unshielded telescope, optical finder, "
                "or eyepiece causes INSTANT and PERMANENT BLINDNESS and irreparably damages camera sensors."
            )
            lbl_danger_desc.setWordWrap(True)
            lbl_danger_desc.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF; border: none; background: transparent; padding: 4px 0px;")
            layout.addWidget(lbl_danger_desc)

            lbl_instructions = QLabel(
                "Before authorizing this GoTo slew, verify that a certified solar filter "
                "(such as Baader solar safety film or a full-aperture glass filter) is securely attached "
                "to the telescope aperture, and avoid looking directly along the optical line of sight."
            )
            lbl_instructions.setWordWrap(True)
            lbl_instructions.setStyleSheet("font-size: 11px; color: #C8D1DC; border: none; background: transparent;")
            layout.addWidget(lbl_instructions)

            lbl_question = QLabel("Do you have a certified solar filter installed and wish to proceed?")
            lbl_question.setStyleSheet("font-size: 12px; font-weight: 700; color: #FFE082; border: none; background: transparent;")
            layout.addWidget(lbl_question)

            # Standard colored buttons: Abort Slew (Red) & Proceed with Solar Filter (Green)
            btn_box = QHBoxLayout()
            btn_box.setSpacing(12)
            btn_box.addStretch()

            btn_abort = QPushButton("Abort Slew")
            btn_abort.setStyleSheet(
                "QPushButton { background-color: #D32F2F; border: 1px solid #B71C1C; color: #FFFFFF; "
                "font-size: 12px; font-weight: 700; padding: 8px 18px; border-radius: 4px; } "
                "QPushButton:hover { background-color: #E53935; } "
                "QPushButton:pressed { background-color: #B71C1C; }"
            )
            btn_abort.setDefault(True)
            btn_abort.setFocus()
            btn_abort.clicked.connect(dlg.reject)
            btn_box.addWidget(btn_abort)

            btn_proceed = QPushButton("Proceed with Solar Filter")
            btn_proceed.setStyleSheet(
                "QPushButton { background-color: #2E7D32; border: 1px solid #1B5E20; color: #FFFFFF; "
                "font-size: 12px; font-weight: 700; padding: 8px 18px; border-radius: 4px; } "
                "QPushButton:hover { background-color: #388E3C; } "
                "QPushButton:pressed { background-color: #1B5E20; }"
            )
            btn_proceed.clicked.connect(dlg.accept)
            btn_box.addWidget(btn_proceed)

            layout.addLayout(btn_box)

            dlg.raise_()
            dlg.activateWindow()

            result = dlg.exec()
            is_proceed = (result == QDialog.DialogCode.Accepted)

            if is_proceed:
                if hasattr(self, 'chk_solar_filter'):
                    self.chk_solar_filter.blockSignals(True)
                    self.chk_solar_filter.setChecked(True)
                    self.chk_solar_filter.blockSignals(False)
                if self.core:
                    self.core.solar_filter_confirmed = True
                self.log_message(
                    "WARNING",
                    f"Solar Slew Authorized: certified solar filter confirmed by observer (separation: {sun_sep:.1f}°)."
                )
            else:
                self.log_message(
                    "INFO",
                    f"Solar Slew Aborted: telescope will not point toward the Sun (separation: {sun_sep:.1f}°)."
                )

            return is_proceed
        finally:
            self._is_showing_solar_dialog = False

    def _toggle_solar_filter(self, checked: bool) -> None:
        """Toggles solar filter status from the safety strip (session-only)."""
        if checked:
            confirmed = self._prompt_solar_warning(0.0)
            if not confirmed:
                self.chk_solar_filter.blockSignals(True)
                self.chk_solar_filter.setChecked(False)
                self.chk_solar_filter.blockSignals(False)
                return
        if self.core:
            self.core.solar_filter_confirmed = checked
        state = "CONFIRMED (Solar Observation Permitted)" if checked else "REMOVED (Sun Keep-Out Active)"
        self.log_message("WARNING", f"Solar Filter Mode: {state}")

    def _sync_location_from_stellarium(self, quiet: bool = False) -> None:
        """Pulls observer site coordinates from Stellarium Remote Control (Port 8090)."""
        import urllib.request, json
        host = str(self.config.get("stellarium_host", "127.0.0.1")).strip() or "127.0.0.1"
        url = f"http://{host}:8090/api/main/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CustomGoTo-Bridge/4.0"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    loc = data.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    name = loc.get("name") or loc.get("role") or "Stellarium Site"
                    if lat is not None and lon is not None:
                        self.config["latitude_deg"] = float(lat)
                        self.config["longitude_deg"] = float(lon)
                        if hasattr(self.config, "save"):
                            self.config.save()
                        self._has_auto_synced_location = True
                        msg = f"Observer location synchronized with Stellarium: Lat {float(lat):.4f}°, Lon {float(lon):.4f}° ({name})"
                        self.log_message("INFO", msg)
                        if not quiet:
                            QMessageBox.information(
                                self, "Location Synced",
                                f"Successfully synced observer location from Stellarium:\n\n"
                                f"Observing Site: {name}\n"
                                f"Latitude: {float(lat):.4f}°\n"
                                f"Longitude: {float(lon):.4f}°"
                            )
                        return
            if not quiet:
                QMessageBox.warning(self, "Sync Failed", "Stellarium responded on port 8090 but location fields were missing.")
        except Exception as e:
            if not quiet:
                QMessageBox.warning(
                    self, "Stellarium Port 8090 Error",
                    f"Could not reach Stellarium Remote Control API:\n{e}\n\n"
                    f"Make sure Stellarium is open and Remote Control plugin is enabled:\n"
                    f"In Stellarium: F2 -> Plugins -> Remote Control -> Load at startup."
                )

    def _home_axis(self, axis: str) -> None:
        if self.core:
            self.core.home_axis(axis)

    def _park_mount(self) -> None:
        if self.core:
            self.core.park()

    def _move_focus(self, amount: str, direction_in: bool) -> None:
        if self.core:
            self.core.move_focus(amount, direction_in)

    def _move_focus_steps(self, delta: int) -> None:
        if self.core:
            self.core.move_focus_steps(delta)

    def _goto_focus_step(self) -> None:
        if self.core:
            target = self.spin_foc_direct.value()
            self.core.set_focus_target(target)

    def _open_autofocus_dialog(self) -> None:
        dlg = AutoFocusDialog(self, self.core)
        dlg.exec()

    def _zero_focus(self) -> None:
        if self.core and self.core.link and self.core.link.is_open:
            if hasattr(self.core.link, "foc_pos"):
                self.core.link.foc_pos = 0.0
                self.core.link.foc_target = 0.0
            self.core.on_event("INFO", "Focus position zeroed (0 steps)")

    def _confirm_zero(self) -> None:
        res = QMessageBox.question(
            self, "Confirm Zero (0,0)",
            "Set current physical orientation as True North (Az 0.0°) and Horizontal (Alt 0.0°)?\n"
            "Ensure the telescope tube is level and pointed True North before confirming.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes and self.core:
            self.core.zero_position()

    def _open_settings(self) -> None:
        if not hasattr(self, "settings_dlg") or self.settings_dlg is None:
            self.settings_dlg = SettingsDialog(self.config, night_mode=self.night_mode, parent=self)
            self.settings_dlg.accepted.connect(self._on_settings_applied)
        elif hasattr(self.settings_dlg, "set_night_mode"):
            self.settings_dlg.set_night_mode(self.night_mode)
        if self.settings_dlg.isMinimized():
            self.settings_dlg.showNormal()
        else:
            self.settings_dlg.show()
        self.settings_dlg.raise_()
        self.settings_dlg.activateWindow()

    def _on_settings_applied(self) -> None:
        if self.core:
            self.core.config = self.config
            try:
                self.core.push_hardware_config()
            except Exception as e:
                self.log_message("WARN", f"Could not push hardware config: {e}")
            self.log_message("INFO", "Configuration updated and applied.")

    def _open_help(self) -> None:
        if not hasattr(self, "help_dlg") or self.help_dlg is None:
            self.help_dlg = HelpGuideDialog(night_mode=self.night_mode, parent=self)
        elif hasattr(self.help_dlg, "set_night_mode"):
            self.help_dlg.set_night_mode(self.night_mode)
        if self.help_dlg.isMinimized():
            self.help_dlg.showNormal()
        else:
            self.help_dlg.show()
        self.help_dlg.raise_()
        self.help_dlg.activateWindow()

    def _open_goto_dialog(self) -> None:
        if not hasattr(self, "goto_window") or self.goto_window is None:
            self.goto_window = GoToDialog(core=self.core, config=self.config, night_mode=self.night_mode, parent=self)
        elif hasattr(self.goto_window, "set_night_mode"):
            self.goto_window.set_night_mode(self.night_mode)
        if self.goto_window.isMinimized():
            self.goto_window.showNormal()
        else:
            self.goto_window.show()
        self.goto_window.raise_()
        self.goto_window.activateWindow()

    def _open_sky_tour(self) -> None:
        if self.tour_window is None:
            self.tour_window = TonightSkyTourDialog(self.core, self.config, night_mode=self.night_mode, parent=self, weather_service=getattr(self, 'weather_service', None))
        elif hasattr(self, 'weather_service') and self.weather_service and self.weather_service.latest_data:
            self.tour_window.update_weather_display(self.weather_service.latest_data)
        if self.tour_window.isMinimized():
            self.tour_window.showNormal()
        else:
            self.tour_window.show()
        self.tour_window.raise_()
        self.tour_window.activateWindow()

    def _on_stream_rate_changed(self, index: int) -> None:
        if index == 0:  # Fast Live (25 Hz)
            self.timer.setInterval(40)
        else:           # Normal (1s)
            self.timer.setInterval(1000)

    def _clear_console(self) -> None:
        if hasattr(self, "_console_history"):
            self._console_history.clear()
        self.console_text.clear()

    def _open_serial_monitor(self) -> None:
        if not hasattr(self, "serial_monitor_dlg") or self.serial_monitor_dlg is None:
            self.serial_monitor_dlg = SerialMonitorDialog(self.core, night_mode=self.night_mode, parent=self)
        self.serial_monitor_dlg.show()
        self.serial_monitor_dlg.raise_()
        self.serial_monitor_dlg.activateWindow()

    # --------------------------------------------------------------------------
    # Serial Link Management
    # --------------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        if HAS_PYSERIAL_LOCAL and serial and hasattr(serial, "tools"):
            try:
                ports = [p.device for p in serial.tools.list_ports.comports()]
                if ports:
                    self.port_combo.addItems(ports)
                    cur_port = self.config.get("serial_port", "")
                    if cur_port in ports:
                        self.port_combo.setCurrentText(cur_port)
                else:
                    self.port_combo.addItem("(No COM ports found)")
            except Exception:
                self.port_combo.addItem("(Port scan failed)")
        else:
            self.port_combo.addItem("(pyserial missing)")

    def _toggle_connection(self) -> None:
        if not self.core:
            return

        if self.core.link and self.core.link.is_open:
            self.core.disconnect()
            self.btn_connect.setText("Connect")
            self.btn_connect.setProperty("class", "primary")
            self.btn_connect.style().unpolish(self.btn_connect)
            self.btn_connect.style().polish(self.btn_connect)
        else:
            simulate = self.chk_simulate.isChecked()
            port = self.port_combo.currentText()
            if "(No COM" in port or "(pyserial" in port or not port:
                port = ""

            ok = self.core.connect(port=port, simulate=simulate)
            if ok:
                self.btn_connect.setText("Disconnect")
                self.btn_connect.setProperty("class", "")
                self.btn_connect.style().unpolish(self.btn_connect)
                self.btn_connect.style().polish(self.btn_connect)

    # --------------------------------------------------------------------------
    # Periodic Tick & High-Speed Telemetry Engine (40 ms = 25 FPS)
    # --------------------------------------------------------------------------

    def _on_tick(self) -> None:
        if not self.core:
            return

# Location sync is triggered on-demand via the 'Sync Location' button

        # 1. Drain event queue & link messages
        while not self.core.event_queue.empty():
            try:
                ev_type, msg = self.core.event_queue.get_nowait()
                self.log_message(ev_type, msg)
                if ev_type in ("WARNING", "ERROR"):
                    play_audio_cue("warning", self.audio_enabled)
                elif ev_type == "SYNC" or "SYNC successful" in msg:
                    play_audio_cue("sync", self.audio_enabled)
            except Exception:
                break

        if self.core.link and hasattr(self.core.link, "async_messages"):
            while not self.core.link.async_messages.empty():
                try:
                    async_msg = self.core.link.async_messages.get_nowait()
                    self.log_message("HARDWARE", async_msg)
                except Exception:
                    break

        # 2. Connection indicators
        self._update_connection_indicators()
        if not (self.core.link and self.core.link.is_open):
            if self.btn_connect.text() != "Connect":
                self.btn_connect.setText("Connect")
                self.btn_connect.setProperty("class", "primary")
                self.btn_connect.style().unpolish(self.btn_connect)
                self.btn_connect.style().polish(self.btn_connect)

        stel_conn = bool(self.stellarium and self.stellarium.is_client_connected)

        # Auto-sync location from Stellarium whenever connected
        if stel_conn and not getattr(self, "_prev_stellarium_connected", False):
            self.log_message("INFO", "Stellarium connected: synchronizing observer coordinates...")
            self._sync_location_from_stellarium(quiet=True)
            if hasattr(self, "weather_service") and self.weather_service:
                self.weather_service.fetch_async()
        self._prev_stellarium_connected = stel_conn

        # Tracking state
        cur_rate = getattr(self.core, "tracking_rate", "Sidereal").upper()
        if self.core.tracking_enabled:
            self.btn_track.setText("Tracking: ON")
            self.btn_track.setStyleSheet("background-color: #5C0B0B; border-color: #801010; color: #FFAAAA; font-weight: 700;" if self.night_mode else "background-color: #1F3F28; border-color: #31683E; color: #C8E6C9; font-weight: 700;")
        else:
            self.btn_track.setText("Tracking: OFF")
            self.btn_track.setStyleSheet("background-color: #1A0303; border-color: #4D0A0A; color: #FF4D4D;" if self.night_mode else "")

        # Cable-Wrap Status Monitoring (Accurate Physical Angle & Real Strain Limits)
        if hasattr(self, "lbl_cable_wrap") and hasattr(self.core, "get_cable_wrap"):
            wrap_deg, wrap_turns = self.core.get_cable_wrap()
            abs_turns = abs(wrap_turns)
            if abs_turns >= 1.0:
                status = "STRAIN"
                color = "#FF2222" if self.night_mode else "#FF4D4D"
            elif abs_turns >= 0.75:
                status = "CAUTION"
                color = "#FF8844" if self.night_mode else "#FFE082"
            else:
                status = "OK"
                color = "#FFAAAA" if self.night_mode else "#88C0FF"

            self.lbl_cable_wrap.setText(f"Cable: {wrap_turns:+.2f} turns [{status}]")
            self.lbl_cable_wrap.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")

        # 3. Microsecond-Accurate Astronomy Clocks
        cur_t = self.core.get_time()
        lat_deg = float(self.config.get("latitude_deg", 12.84))
        lon_deg = float(self.config.get("longitude_deg", 80.15))

        is_fast = hasattr(self, 'combo_stream_rate') and (self.combo_stream_rate.currentIndex() == 0)
        hms_dec = 2 if is_fast else 0
        dms_dec = 1 if is_fast else 0

        self.val_utc.setText(cur_t.strftime("%Y-%m-%d %H:%M:%S UTC"))
        self.val_local.setText(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        jd_val = julian_date(cur_t) if julian_date else 2451545.0
        self.val_jd.setText(f"{jd_val:.6f}" if is_fast else f"{jd_val:.4f}")

        lst_hours = (lst_deg(jd_val, lon_deg) / 15.0) % 24.0 if lst_deg else 0.0
        self.val_lst.setText(hours_to_hms(lst_hours, decimals=hms_dec))

        # 4. Instantaneous Mount Coordinates Calculations
        alt_deg, az_deg = self.core.get_telescope_altaz()

        # Compute instant apparent RA/Dec from physical Alt/Az
        use_refr = bool(self.config.get("apply_refraction", True))
        if altaz_to_radec:
            ra_date, dec_date = altaz_to_radec(alt_deg, az_deg, lat_deg, lon_deg, cur_t, apply_refraction=use_refr)
        else:
            ra_date, dec_date = 0.0, 0.0

        if precess_date_to_j2000:
            ra_j2000, dec_j2000 = precess_date_to_j2000(ra_date, dec_date, cur_t)
        else:
            ra_j2000, dec_j2000 = ra_date, dec_date

        ha_hours = (lst_hours - (ra_date / 15.0)) % 24.0
        parallactic = calculate_parallactic_angle(ha_hours, dec_date, lat_deg)

        # Performance optimization: cache heavy galactic, ecliptic, constellation lookups
        now_ts = time.time()
        need_heavy = (now_ts - self._last_heavy_calc_time >= 1.0)
        if need_heavy or self._last_mount_j2000 is None:
            self._last_heavy_calc_time = now_ts
            self._cached_gal = radec_to_galactic(ra_j2000, dec_j2000)
            self._cached_ecl = radec_to_ecliptic(ra_j2000, dec_j2000)
            self._cached_constellation_mount = get_constellation(ra_j2000, dec_j2000)
            self._last_mount_j2000 = (ra_j2000, dec_j2000)

        gal_l, gal_b = self._cached_gal
        ecl_l, ecl_b = self._cached_ecl
        constellation_mount = self._cached_constellation_mount

        # Update Detailed Mount Parameters Table
        self.val_m_j2000.setText(f"{deg_to_hms(ra_j2000, decimals=hms_dec)} / {deg_to_dms(dec_j2000, signed=True, decimals=dms_dec)}")
        self.val_m_jnow.setText(f"{deg_to_hms(ra_date, decimals=hms_dec)} / {deg_to_dms(dec_date, signed=True, decimals=dms_dec)}")
        self.val_m_hadec.setText(f"{hours_to_hms(ha_hours, decimals=hms_dec)} / {deg_to_dms(dec_date, signed=True, decimals=dms_dec)} (apparent)")
        self.val_m_altaz.setText(f"{deg_to_dms(az_deg, signed=True, decimals=dms_dec)} / {deg_to_dms(alt_deg, signed=True, decimals=dms_dec)} (apparent)")
        self.val_m_gal.setText(f"{deg_to_dms(gal_l, signed=True, decimals=dms_dec)} / {deg_to_dms(gal_b, signed=True, decimals=dms_dec)}")
        self.val_m_ecl.setText(f"{deg_to_dms(ecl_l, signed=True, decimals=dms_dec)} / {deg_to_dms(ecl_b, signed=True, decimals=dms_dec)}")
        self.val_m_parallactic.setText(f"{parallactic:+05.1f}° ({deg_to_dms(parallactic, signed=True, decimals=dms_dec)})")
        self.val_m_constellation.setText(constellation_mount)

        # Motor step counters & slew arrival detection
        if self.core.link and self.core.link.latest_telemetry:
            t = self.core.link.latest_telemetry
            is_moving = bool(t.moving)
            if self._was_moving and not is_moving and self._was_slewing:
                play_audio_cue("slew_complete", self.audio_enabled)
                self._was_slewing = False
            if is_moving:
                self._was_slewing = True
            self._was_moving = is_moving

            moving_flag = " [MOVING]" if is_moving else " [LOCKED]"
            self.val_m_steps.setText(f"Az: {t.az_steps:,}  Alt: {t.alt_steps:,}  Foc: {t.foc_steps:,}{moving_flag}")
            self.lbl_foc_pos.setText(f"Position: {t.foc_steps:,} steps")

        # 5. Tracked Target Calculations (Continuous fast updating)
        target_alt_radar = None
        target_az_radar = None

        if self.core.current_target_radec:
            ra_tgt_cfg, dec_tgt_cfg = self.core.current_target_radec

            is_tgt_j2000 = getattr(self.core, "current_target_is_j2000", (self.config.get("epoch", "J2000") == "J2000"))
            if is_tgt_j2000:
                ra_tgt_2000, dec_tgt_2000 = ra_tgt_cfg, dec_tgt_cfg
                if precess_j2000_to_date:
                    ra_tgt_date, dec_tgt_date = precess_j2000_to_date(ra_tgt_2000, dec_tgt_2000, cur_t)
                else:
                    ra_tgt_date, dec_tgt_date = ra_tgt_2000, dec_tgt_2000
            else:
                ra_tgt_date, dec_tgt_date = ra_tgt_cfg, dec_tgt_cfg
                if precess_date_to_j2000:
                    ra_tgt_2000, dec_tgt_2000 = precess_date_to_j2000(ra_tgt_date, dec_tgt_date, cur_t)
                else:
                    ra_tgt_2000, dec_tgt_2000 = ra_tgt_date, dec_tgt_date

            # Target Alt/Az updates continuously down to fractions of an arcsecond as Earth turns
            if radec_to_altaz:
                t_alt, t_az = radec_to_altaz(ra_tgt_date, dec_tgt_date, lat_deg, lon_deg, cur_t, apply_refraction=use_refr)
                target_alt_radar = t_alt
                target_az_radar = t_az
                self.val_t_altaz.setText(f"{deg_to_dms(t_az, signed=True, decimals=dms_dec)} / {deg_to_dms(t_alt, signed=True, decimals=dms_dec)} (apparent)")

            self.val_t_status.setText("TRACKING ACTIVE" if self.core.tracking_enabled else "TARGET LOCKED / IDLE")
            self.val_t_j2000.setText(f"{deg_to_hms(ra_tgt_2000, decimals=hms_dec)} / {deg_to_dms(dec_tgt_2000, signed=True, decimals=dms_dec)}")
            self.val_t_jnow.setText(f"{deg_to_hms(ra_tgt_date, decimals=hms_dec)} / {deg_to_dms(dec_tgt_date, signed=True, decimals=dms_dec)}")

            # Performance optimization: cache ephemeris & constellation for target
            tgt_key = (round(ra_tgt_2000, 4), round(dec_tgt_2000, 4), round(lat_deg, 2))
            if need_heavy or tgt_key != self._cached_target_key:
                self._cached_target_key = tgt_key
                self._cached_constellation_target = get_constellation(ra_tgt_2000, dec_tgt_2000)
                self._cached_rise_transit_set = calculate_ephemeris(ra_tgt_date, dec_tgt_date, lat_deg)

            self.val_t_constellation.setText(self._cached_constellation_target)
            rise, transit, setting = self._cached_rise_transit_set
            self.val_t_ephemeris.setText(f"Rise: {rise} | Transit: {transit} | Set: {setting}")
            rate_title = getattr(self.core, "tracking_rate", "Sidereal").title()
            if self.core.tracking_enabled:
                self.val_t_tracking.setText(f"Active ({rate_title}) - Tracking Engaged")
            else:
                self.val_t_tracking.setText(f"{rate_title} Alt-Az Microstep Differential")
        else:
            self.val_t_status.setText("No Active Target (Awaiting Stellarium Command)")
            self.val_t_j2000.setText("None")
            self.val_t_jnow.setText("None")
            self.val_t_altaz.setText("None")
            self.val_t_constellation.setText("None")
            self.val_t_ephemeris.setText("--:-- | --:-- | --:--")
            rate_title = getattr(self.core, "tracking_rate", "Sidereal").title() if self.core else "Sidereal"
            if self.core and self.core.tracking_enabled:
                self.val_t_tracking.setText(f"Active ({rate_title}) - Standby for Target")
            else:
                self.val_t_tracking.setText(f"Standby ({rate_title})")

        # 6. Tracking Telemetry & Live Heartbeat Monitoring
        if self.core.tracking_enabled and self.core.current_target_radec:
            sec_ago = time.time() - getattr(self.core, 'tracking_last_pulse_time', 0.0)
            pulse_icon = "●" if sec_ago < 0.8 else "○"
            count = getattr(self.core, 'tracking_pulses_count', 0)
            d_az = getattr(self.core, 'tracking_total_steps_az', 0)
            d_alt = getattr(self.core, 'tracking_total_steps_alt', 0)
            self.val_t_pulses.setText(
                f"{pulse_icon} {count} pulses sent (ΔAz: {d_az:+d}, ΔAlt: {d_alt:+d} steps) | Last nudge: {sec_ago:.1f}s ago"
            )
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #8CD68C;")
        else:
            self.val_t_pulses.setText("Tracking Inactive (0 pulses)")
            self.val_t_pulses.setStyleSheet("font-size: 11px; font-weight: 500; color: #661515;" if self.night_mode else "font-size: 11px; font-weight: 500; color: #ABB2BF;")

        # Stellarium Live Follow status
        if hasattr(self, 'follower') and self.follower and self.follower.is_active:
            if self.follower.is_connected:
                t_name = self.follower.target_name or "Active Selection"
                t_type = self.follower.target_type.upper() or "TARGET"
                self.val_t_follow_status.setText(f"ACTIVE: Following {t_name} [{t_type}] @ 2 Hz")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047;")
                if "SATELLITE" in t_type or "SPACECRAFT" in t_type:
                    self.val_t_status.setText(f"TRACKING SATELLITE: {t_name}")
                    self.val_t_tracking.setText("Continuous LEO Satellite Vector (2 Hz)")
            else:
                self.val_t_follow_status.setText("Awaiting Stellarium API (Port 8090 - In Stellarium: F2 -> Plugins -> Remote Control)")
                self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #FF8844;" if self.night_mode else "font-size: 11px; font-weight: 600; color: #D69E35;")
        else:
            self.val_t_follow_status.setText("Standby")
            self.val_t_follow_status.setStyleSheet("font-size: 11px; font-weight: 500; color: #661515;" if self.night_mode else "font-size: 11px; font-weight: 500; color: #ABB2BF;")

        # 7. Sun Position & Keep-Out
        sun_alt_radar = None
        sun_az_radar = None
        if sun_radec and radec_to_altaz:
            s_ra, s_dec = sun_radec(cur_t)
            s_alt, s_az = radec_to_altaz(s_ra, s_dec, lat_deg, lon_deg, cur_t)
            sun_alt_radar = s_alt
            sun_az_radar = s_az

            if separation_deg:
                sep = separation_deg(ra_date, dec_date, s_ra, s_dec)
                keepout = float(self.config.get("sun_keepout_deg", 15.0))
                has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
                if sep < keepout:
                    if has_filter:
                        self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [SOLAR FILTER ACTIVE]")
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FF8888; background: #330505; padding: 2px 6px; border-radius: 2px;" if self.night_mode else "font-size: 10px; font-weight: 800; color: #FFE082; background: #3E3218; padding: 2px 6px; border-radius: 2px;")
                    else:
                        self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}° [DANGER < {keepout:.0f}°]")
                        self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 800; color: #FF2222; background: #300000; padding: 2px 6px; border-radius: 2px;" if self.night_mode else "font-size: 10px; font-weight: 800; color: #FF6666; background: #4D1818; padding: 2px 6px; border-radius: 2px;")
                else:
                    self.lbl_sun_sep.setText(f"Sun Angular Separation: {sep:.1f}°")
                    self.lbl_sun_sep.setStyleSheet("font-size: 10px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 10px; font-weight: 700; color: #8CD68C;")

                if self.core.current_target_radec:
                    t_sep = separation_deg(ra_tgt_date, dec_tgt_date, s_ra, s_dec)
                    self.val_t_sunsep.setText(f"{t_sep:.1f}° ({'Safe' if t_sep >= keepout else 'DANGER'})")
                else:
                    self.val_t_sunsep.setText(f"Mount Separation: {sep:.1f}°")

        # 7. Update Enlarged Sky Radar
        self.radar_widget.set_scope_altaz(alt_deg, az_deg)
        self.radar_widget.set_target_altaz(target_alt_radar, target_az_radar)
        self.radar_widget.set_sun_altaz(sun_alt_radar, sun_az_radar, float(self.config.get("sun_keepout_deg", 15.0)))

    def log_message(self, level: str, message: str) -> None:
        now_str = dt.datetime.now().strftime("%H:%M:%S")
        if not hasattr(self, "_console_history"):
            self._console_history = []
        self._console_history.append((now_str, level.upper(), message))
        if len(self._console_history) > 2000:
            self._console_history = self._console_history[-1000:]
        self._append_console_entry(now_str, level.upper(), message)

        # Date-wise application activity logging in canonical logs/ directory
        try:
            from telescope_bridge import PointingLogger
            log_dir = PointingLogger.get_canonical_log_dir()
            today_str = dt.datetime.now().strftime("%Y-%m-%d")
            app_log_file = os.path.join(log_dir, f"app_{today_str}.log")
            timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(app_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{level.upper()}] {message}\n")
        except Exception:
            pass

    def _append_console_entry(self, now_str: str, level: str, message: str) -> None:
        if self.night_mode:
            color_map = {
                "INFO": "#FF4D4D",
                "GOTO": "#FF6666",
                "SYNC": "#CC2929",
                "WARNING": "#FF8844",
                "ERROR": "#FF2222",
                "HARDWARE": "#AA2222",
                "STELLARIUM_CONNECTED": "#FF6666",
                "STELLARIUM_DISCONNECTED": "#FF4444"
            }
            color = color_map.get(level, "#FF4D4D")
            time_col = "#7A1010"
            msg_col = "#FF7777"
        else:
            color_map = {
                "INFO": "#5B9DD9",
                "GOTO": "#43A047",
                "SYNC": "#8E72B2",
                "WARNING": "#D69E35",
                "ERROR": "#CC4444",
                "HARDWARE": "#7A8492",
                "STELLARIUM_CONNECTED": "#43A047",
                "STELLARIUM_DISCONNECTED": "#CC4444"
            }
            color = color_map.get(level, "#ABB2BF")
            time_col = "#555D6B"
            msg_col = "#DCE2EB"

        html = f"<span style='color: {time_col};'>[{now_str}]</span> " \
               f"<span style='color: {color}; font-weight: bold;'>[{level}]</span> " \
               f"<span style='color: {msg_col};'>{message}</span>"

        self.console_text.append(html)
        if self.chk_autoscroll.isChecked():
            cursor = self.console_text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.console_text.setTextCursor(cursor)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        app = QApplication.instance()
        if app and hasattr(self, "_global_shortcut_filter") and self._global_shortcut_filter:
            try:
                app.removeEventFilter(self._global_shortcut_filter)
            except Exception:
                pass
        if hasattr(self, "goto_window") and self.goto_window and self.goto_window.isVisible():
            self.goto_window.close()
        if hasattr(self, "tour_window") and self.tour_window and self.tour_window.isVisible():
            self.tour_window.close()
        if hasattr(self, 'follower') and self.follower:
            self.follower.stop()
        if hasattr(self, 'web_server') and self.web_server:
            try:
                self.web_server.stop()
            except Exception:
                pass
        if self.core:
            self.core.stop_tracking_thread()
            self.core.disconnect()
        if self.stellarium and hasattr(self.stellarium, "stop"):
            self.stellarium.stop()
        event.accept()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
