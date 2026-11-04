"""
tour_dialog.py
Curated celestial target catalog and real-time observation planning dialog.
"""

from __future__ import annotations
import math
import datetime as dt
import threading
import json
import urllib.request
from typing import Optional, Dict, Any, List, Tuple
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QMessageBox, QSplitter, QTextEdit, QWidget, QButtonGroup
)
from src.core.astrometry import deg_to_hms, deg_to_dms, hours_to_hms, radec_to_galactic, radec_to_ecliptic, calculate_parallactic_angle, calculate_ephemeris
from src.core.catalog import TONIGHT_BEST_CATALOG
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE
try:
    from telescope_bridge import (
        sun_radec, moon_radec, planet_radec, radec_to_altaz, altaz_to_radec, separation_deg,
        precess_date_to_j2000, precess_j2000_to_date, lst_deg
    )
except ImportError:
    sun_radec = moon_radec = planet_radec = radec_to_altaz = altaz_to_radec = separation_deg = precess_date_to_j2000 = precess_j2000_to_date = lst_deg = None

class TonightSkyTourDialog(QDialog):
    """Tonight's Best Interactive Sky Tour & Curated Celestial Catalog.
    Computes real-time Alt/Az, filters visible targets (>15°), recommends
    eyepieces matching 20x, 30x, and 40x magnifications, and provides one-click GoTo.
    """

    def __init__(self, core: Any, config: Dict[str, Any], night_mode: bool = False, parent: Optional[QWidget] = None, main_window: Optional[Any] = None, weather_service: Optional[Any] = None):
        # Pass parent=None to QDialog so Windows OS does NOT create an owned-window relationship.
        # An owned window in Windows is permanently pinned on top of its owner in the Z-order.
        # Using parent=None with Qt.WindowType.Window creates true independent peer windows
        # where clicking either window immediately raises and pops it above the other!
        super().__init__(None, Qt.WindowType.Window)
        self.main_window = main_window or parent
        self.core = core
        self.config = config
        self.night_mode = night_mode
        self.weather_service = weather_service or (getattr(self.main_window, 'weather_service', None) if self.main_window else None)
        self.weather_data: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Tonight's Best Sky Tour & Curated Catalog")
        self.resize(980, 660)
        self.setMinimumSize(820, 520)
        self.setModal(False)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)

        self.current_category = "Visible"
        self.filter_text = ""
        self.sort_mode = "Altitude"
        self.selected_item = None
        self._items_data: List[Dict[str, Any]] = []

        self._build_ui()
        if self.weather_service:
            self.weather_service.weather_updated.connect(self.update_weather_display)
            if self.weather_service.latest_data:
                self.update_weather_display(self.weather_service.latest_data)
            else:
                self.weather_service.fetch_async()

        try:
            self._refresh_all_targets(force_recalc=True)
        except Exception:
            pass

        # 1-second target recalculation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(1000)

        # Fast 50ms (20 Hz) real-time mount coordinate tracking timer
        self.mount_pos_timer = QTimer(self)
        self.mount_pos_timer.timeout.connect(self._update_mount_pos_fast)
        self.mount_pos_timer.start(50)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Header banner
        header_card = QFrame()
        header_card.setProperty("class", "card")
        header_lay = QHBoxLayout(header_card)
        header_lay.setContentsMargins(12, 8, 12, 8)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("TONIGHT'S BEST INTERACTIVE SKY TOUR & CURATED CATALOG")
        lbl_title.setProperty("class", "title")
        v_head.addWidget(lbl_title)

        self.lbl_sub = QLabel("Live Astronomical Visibility | Curated Messier, Caldwell, Solar System & Double Stars")
        self.lbl_sub.setProperty("class", "subtitle")
        v_head.addWidget(self.lbl_sub)
        header_lay.addLayout(v_head)
        header_lay.addStretch()

        self.lbl_mount_summary = QLabel("Mount: Az 0.0°, Alt 0.0°")
        self.lbl_mount_summary.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 15px; font-weight: 800; color: #5AA9FF; padding: 2px 8px; border-radius: 4px;"
            if not self.night_mode else
            "font-family: 'Consolas', monospace; font-size: 15px; font-weight: 800; color: #FF4D4D; padding: 2px 8px; border-radius: 4px;"
        )
        header_lay.addWidget(self.lbl_mount_summary)
        main_layout.addWidget(header_card)

        # Live Meteorological Transparency & Meteorological Deck
        self.weather_card = QFrame()
        self.weather_card.setProperty("class", "card")
        w_lay = QHBoxLayout(self.weather_card)
        w_lay.setContentsMargins(12, 6, 12, 6)
        w_lay.setSpacing(14)

        self.lbl_weather_badge = QLabel("[WEATHER: CHECKING...]")
        self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFAAAA;" if self.night_mode else "font-size: 11px; font-weight: 800; color: #5AA9FF;")
        w_lay.addWidget(self.lbl_weather_badge)

        self.lbl_weather_condition = QLabel("Sky: --")
        self.lbl_weather_condition.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #DCE2EB;")
        w_lay.addWidget(self.lbl_weather_condition)

        self.lbl_weather_seeing = QLabel("Seeing: --")
        self.lbl_weather_seeing.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF8888;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #FFE082;")
        w_lay.addWidget(self.lbl_weather_seeing)

        self.lbl_weather_metrics = QLabel("Temp: --.-°C  |  Humidity: --%  |  Wind: --.- km/h  |  Visibility: --.- km")
        self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #FF8888;" if self.night_mode else "font-family: 'Consolas', monospace; font-size: 11px; color: #C8D1DC;")
        w_lay.addWidget(self.lbl_weather_metrics)

        w_lay.addStretch()

        self.btn_refresh_weather = QPushButton("Refresh")
        self.btn_refresh_weather.setToolTip("Query live Open-Meteo cloud cover and meteorological conditions")
        self.btn_refresh_weather.clicked.connect(self._refresh_weather_clicked)
        w_lay.addWidget(self.btn_refresh_weather)

        main_layout.addWidget(self.weather_card)

        # 2. Controls & Filter Bar
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "card")
        ctrl_lay = QHBoxLayout(ctrl_card)
        ctrl_lay.setContentsMargins(10, 6, 10, 6)
        ctrl_lay.setSpacing(8)

        lbl_cat = QLabel("Filter:")
        lbl_cat.setStyleSheet("font-weight: 700;")
        ctrl_lay.addWidget(lbl_cat)

        self.btn_grp = QButtonGroup(self)
        self.tab_buttons: Dict[str, QPushButton] = {}
        tabs = [
            ("Visible", "Tonight's Visible"),
            ("Solar System", "Planets & Moon"),
            ("Deep Sky", "Deep Sky (Messier)"),
            ("Double Star", "Double Stars & Giants"),
            ("All", "All Targets (34)"),
        ]
        for cat_key, cat_label in tabs:
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            if cat_key == "Visible":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=cat_key: self._set_category(k))
            self.btn_grp.addButton(btn)
            self.tab_buttons[cat_key] = btn
            ctrl_lay.addWidget(btn)

        ctrl_lay.addSpacing(10)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search name or constellation...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setMaximumWidth(200)
        ctrl_lay.addWidget(self.search_box)

        # Sort mode combo
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Sort: Highest Altitude (Best Seeing)", "Altitude")
        self.sort_combo.addItem("Sort: Brightest Magnitude", "Magnitude")
        self.sort_combo.addItem("Sort: Name (A-Z)", "Name")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        ctrl_lay.addWidget(self.sort_combo)

        main_layout.addWidget(ctrl_card)

        # 3. Main Splitter: Left Table | Right Details & Eyepiece Card
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table widget - disable inline cell editing so double-click slews without renaming!
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Target Name", "Category", "Const", "Mag", "Altitude", "Azimuth", "Visibility"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 50)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 115)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.doubleClicked.connect(lambda idx: self._start_slew())
        splitter.addWidget(self.table)

        # Wire global shortcuts in tour window so Ctrl+N toggles night vision even when tour window has focus
        sc_night = QShortcut(QKeySequence("Ctrl+N"), self)
        sc_night.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc_night.activated.connect(self._toggle_night_from_tour)

        # Right Side: Object Details & Eyepiece Guide Card
        detail_card = QFrame()
        detail_card.setProperty("class", "card")
        detail_card.setMinimumWidth(320)
        detail_lay = QVBoxLayout(detail_card)
        detail_lay.setContentsMargins(14, 12, 14, 12)
        detail_lay.setSpacing(8)

        lbl_det_title = QLabel("TARGET DETAILS & POSITION")
        lbl_det_title.setProperty("class", "section-header")
        detail_lay.addWidget(lbl_det_title)

        self.lbl_target_name = QLabel("No Target Selected")
        self.lbl_target_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFFFFF;" if not self.night_mode else "font-size: 15px; font-weight: 800; color: #FF6666;")
        detail_lay.addWidget(self.lbl_target_name)

        self.lbl_target_meta = QLabel("Select an object from the tour list")
        self.lbl_target_meta.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #991F1F;")
        detail_lay.addWidget(self.lbl_target_meta)

        # Coordinates & Seeing Grid
        self.coords_card = QFrame()
        self.coords_card.setStyleSheet("background-color: #12151B; border: 1px solid #2B313D; border-radius: 3px;" if not self.night_mode else "background-color: #080101; border: 1px solid #330808; border-radius: 3px;")
        coords_card = self.coords_card
        coords_lay = QGridLayout(coords_card)
        coords_lay.setContentsMargins(8, 6, 8, 6)
        coords_lay.setSpacing(4)

        coords_lay.addWidget(QLabel("Altitude / Az:"), 0, 0)
        self.lbl_det_altaz = QLabel("-- / --")
        self.lbl_det_altaz.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #5AA9FF;" if not self.night_mode else "font-family: 'Consolas'; font-weight: 700; color: #FF4D4D;")
        coords_lay.addWidget(self.lbl_det_altaz, 0, 1)

        coords_lay.addWidget(QLabel("RA / Dec:"), 1, 0)
        self.lbl_det_radec = QLabel("-- / --")
        self.lbl_det_radec.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #DCE2EB;" if not self.night_mode else "font-family: 'Consolas'; font-weight: 700; color: #FF3333;")
        coords_lay.addWidget(self.lbl_det_radec, 1, 1)

        coords_lay.addWidget(QLabel("Slew Duration:"), 2, 0)
        self.lbl_det_slew = QLabel("--")
        self.lbl_det_slew.setStyleSheet("font-weight: 700; color: #8CD68C;" if not self.night_mode else "font-weight: 700; color: #FFAAAA;")
        coords_lay.addWidget(self.lbl_det_slew, 2, 1)

        coords_lay.addWidget(QLabel("Sun Distance:"), 3, 0)
        self.lbl_det_sun = QLabel("--")
        self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #8CD68C;" if not self.night_mode else "font-weight: 700; color: #FFAAAA;")
        coords_lay.addWidget(self.lbl_det_sun, 3, 1)

        detail_lay.addWidget(coords_card)

        # Astronomical Description Text
        self.txt_desc = QTextEdit()
        self.txt_desc.setReadOnly(True)
        self.txt_desc.setStyleSheet("background-color: #0E1015; border: 1px solid #242832; color: #A0ABB8; font-size: 11px;" if not self.night_mode else "background-color: #060101; border: 1px solid #2E0505; color: #FF6666; font-size: 11px;")
        detail_lay.addWidget(self.txt_desc)

        # Action GoTo Button
        self.btn_slew = QPushButton("Slew to Target (GoTo)")
        self.btn_slew.setProperty("class", "primary")
        self.btn_slew.setEnabled(False)
        self.btn_slew.setToolTip("Command telescope to slew to this target and start sidereal tracking")
        self.btn_slew.clicked.connect(self._start_slew)
        detail_lay.addWidget(self.btn_slew)

        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # 4. Bottom status bar
        bot_lay = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #8892A0;" if not self.night_mode else "font-size: 11px; color: #991F1F;")
        bot_lay.addWidget(self.lbl_status)
        bot_lay.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bot_lay.addWidget(btn_close)
        main_layout.addLayout(bot_lay)

    def _set_category(self, cat: str) -> None:
        self.current_category = cat
        self._refresh_table_view()

    def _on_search_changed(self, text: str) -> None:
        self.filter_text = text.strip().lower()
        self._refresh_table_view()

    def _on_sort_changed(self, idx: int) -> None:
        self.sort_mode = self.sort_combo.currentData() or "Altitude"
        self._refresh_table_view()

    def _on_timer_tick(self) -> None:
        self._refresh_all_targets(force_recalc=False)

    def _refresh_all_targets(self, force_recalc: bool = False) -> None:
        if not self.core:
            return

        t_now = self.core.get_time()
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))
        use_refr = bool(self.config.get("apply_refraction", True))
        is_j2000_mode = (self.config.get("epoch", "J2000") == "J2000")

        # Solar position for keepout
        s_ra, s_dec = sun_radec(t_now) if sun_radec else (0.0, 0.0)
        keepout_limit = float(self.config.get("sun_keepout_deg", 15.0))

        # Mount current Alt/Az
        m_alt, m_az = self.core.get_telescope_altaz()
        self.lbl_mount_summary.setText(f"Mount: Az {m_az:.1f}°, Alt {m_alt:.1f}°")

        calc_list: List[Dict[str, Any]] = []

        for item in TONIGHT_BEST_CATALOG:
            entry = dict(item)
            # Calculate coordinates
            if entry.get("is_dynamic", False):
                dyn_body = entry.get("dynamic_body", "")
                if dyn_body == "Moon" and moon_radec:
                    ra_date, dec_date = moon_radec(t_now)
                    ra_2k, dec_2k = precess_date_to_j2000(ra_date, dec_date, t_now) if precess_date_to_j2000 else (ra_date, dec_date)
                elif dyn_body in ("Venus", "Mars", "Jupiter", "Saturn") and planet_radec:
                    ra_2k, dec_2k = planet_radec(dyn_body, t_now)
                    ra_date, dec_date = precess_j2000_to_date(ra_2k, dec_2k, t_now) if precess_j2000_to_date else (ra_2k, dec_2k)
                else:
                    ra_2k, dec_2k = entry["ra"], entry["dec"]
                    ra_date, dec_date = precess_j2000_to_date(ra_2k, dec_2k, t_now) if precess_j2000_to_date else (ra_2k, dec_2k)
                entry["ra_j2000"] = ra_2k
                entry["dec_j2000"] = dec_2k
                entry["ra_date"] = ra_date
                entry["dec_date"] = dec_date
                entry["calc_ra"] = ra_2k if is_j2000_mode else ra_date
                entry["calc_dec"] = dec_2k if is_j2000_mode else dec_date
            else:
                ra_2k, dec_2k = entry["ra"], entry["dec"]
                if precess_j2000_to_date:
                    ra_date, dec_date = precess_j2000_to_date(ra_2k, dec_2k, t_now)
                else:
                    ra_date, dec_date = ra_2k, dec_2k
                entry["ra_j2000"] = ra_2k
                entry["dec_j2000"] = dec_2k
                entry["ra_date"] = ra_date
                entry["dec_date"] = dec_date
                entry["calc_ra"] = ra_2k if is_j2000_mode else ra_date
                entry["calc_dec"] = dec_2k if is_j2000_mode else dec_date

            # Alt / Az calculation: always uses apparent of-date coordinates
            if radec_to_altaz:
                alt, az = radec_to_altaz(ra_date, dec_date, lat, lon, t_now, apply_refraction=use_refr)
            else:
                alt, az = 0.0, 0.0

            entry["alt"] = alt
            entry["az"] = az

            # Compass quadrant
            quadrants = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                         "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            q_idx = int(((az + 11.25) % 360.0) / 22.5)
            entry["compass"] = quadrants[q_idx]

            # Sun separation
            sep_sun = separation_deg(ra_date, dec_date, s_ra, s_dec) if separation_deg else 99.0
            entry["sun_sep"] = sep_sun

            # Visibility classification
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if sep_sun < keepout_limit and not has_filter:
                entry["visibility"] = "SUN DANGER"
                entry["is_visible"] = False
            elif alt > 15.0:
                entry["visibility"] = f"VISIBLE ({alt:.0f}°)"
                entry["is_visible"] = True
            elif alt >= 0.0:
                entry["visibility"] = f"LOW ({alt:.0f}°)"
                entry["is_visible"] = False
            else:
                entry["visibility"] = "BELOW HORIZON"
                entry["is_visible"] = False

            calc_list.append(entry)

        self._items_data = calc_list
        self._refresh_table_view()

    def _refresh_table_view(self) -> None:
        filtered: List[Dict[str, Any]] = []

        for item in self._items_data:
            # Category filter
            if self.current_category == "Visible" and not item["is_visible"]:
                continue
            elif self.current_category == "Solar System" and item["category"] != "Solar System":
                continue
            elif self.current_category == "Deep Sky" and item["category"] != "Deep Sky":
                continue
            elif self.current_category == "Double Star" and item["category"] != "Double Star":
                continue

            # Text search filter
            if self.filter_text:
                haystack = f"{item['name']} {item['type']} {item['constellation']}".lower()
                if self.filter_text not in haystack:
                    continue

            filtered.append(item)

        # Sorting
        if self.sort_mode == "Altitude":
            filtered.sort(key=lambda x: x["alt"], reverse=True)
        elif self.sort_mode == "Magnitude":
            filtered.sort(key=lambda x: x["mag"])
        elif self.sort_mode == "Name":
            filtered.sort(key=lambda x: x["name"])

        # Populate table
        prev_selected_name = self.selected_item["name"] if self.selected_item else None
        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))

        row_to_reselect = -1
        for row, it in enumerate(filtered):
            def _make_item(val: str, it_ref: Optional[Dict[str, Any]] = None) -> QTableWidgetItem:
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if it_ref:
                    item.setData(Qt.ItemDataRole.UserRole, it_ref)
                return item

            # Target Name
            self.table.setItem(row, 0, _make_item(it["name"], it))

            # Category / Type
            self.table.setItem(row, 1, _make_item(it["type"]))

            # Constellation
            self.table.setItem(row, 2, _make_item(it["constellation"]))

            # Magnitude
            mag_str = f"{it['mag']:+.1f}" if it['mag'] <= 0 else f"{it['mag']:.1f}"
            self.table.setItem(row, 3, _make_item(mag_str))

            # Altitude
            alt_item = _make_item(f"{it['alt']:+.1f}°")
            if it["alt"] > 15.0:
                alt_item.setForeground(QColor("#43A047") if not self.night_mode else QColor("#FF4D4D"))
            elif it["alt"] >= 0.0:
                alt_item.setForeground(QColor("#D69E35") if not self.night_mode else QColor("#AA3333"))
            else:
                alt_item.setForeground(QColor("#77808D") if not self.night_mode else QColor("#551111"))
            self.table.setItem(row, 4, alt_item)

            # Azimuth
            self.table.setItem(row, 5, _make_item(f"{it['az']:05.1f}° {it['compass']}"))

            # Visibility with live cloud-cover awareness
            vis_raw = it["visibility"]
            cloud_pct = self.weather_data.get("cloud_cover", 0) if self.weather_data else 0
            if "VISIBLE" in vis_raw:
                if cloud_pct >= 80:
                    vis_text = f"OBSCURED ({cloud_pct}% CLOUD)"
                    vis_col = QColor("#FF6666") if self.night_mode else QColor("#D69E35")
                elif cloud_pct >= 50:
                    vis_text = f"VISIBLE ({cloud_pct}% CLOUD)"
                    vis_col = QColor("#FF9944") if self.night_mode else QColor("#D6B535")
                else:
                    vis_text = vis_raw
                    vis_col = QColor("#FF4D4D") if self.night_mode else QColor("#43A047")
            elif "SUN" in vis_raw:
                vis_text = vis_raw
                vis_col = QColor("#FF2222") if self.night_mode else QColor("#E53935")
            elif "LOW" in vis_raw:
                vis_text = vis_raw
                vis_col = QColor("#AA3333") if self.night_mode else QColor("#D69E35")
            else:
                vis_text = vis_raw
                vis_col = QColor("#551111") if self.night_mode else QColor("#77808D")

            vis_item = _make_item(vis_text)
            vis_item.setForeground(vis_col)
            self.table.setItem(row, 6, vis_item)

            if prev_selected_name and it["name"] == prev_selected_name:
                row_to_reselect = row

        self.table.blockSignals(False)

        if row_to_reselect >= 0:
            self.table.selectRow(row_to_reselect)
        elif len(filtered) > 0 and self.selected_item is None:
            self.table.selectRow(0)

        # Update status message
        vis_count = sum(1 for it in self._items_data if it["is_visible"])
        self.lbl_status.setText(f"Showing {len(filtered)} objects ({vis_count} visible above 15° horizon)")

    def _on_row_selected(self) -> None:
        rows = self.table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        item_0 = self.table.item(row, 0)
        if not item_0:
            return
        data = item_0.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        self.selected_item = data
        self._update_details_panel(data)

    def _update_details_panel(self, it: Dict[str, Any]) -> None:
        self.lbl_target_name.setText(it["name"])
        self.lbl_target_meta.setText(f"{it['type']} | Constellation: {it['constellation']} | Visual Mag: {it['mag']:+.1f}")

        # Coordinates
        self.lbl_det_altaz.setText(f"Alt {it['alt']:+.1f}°, Az {it['az']:.1f}° ({it['compass']})")
        self.lbl_det_radec.setText(f"RA {it['calc_ra']:.2f}°, Dec {it['calc_dec']:+.2f}°")

        # Slew estimate
        m_alt, m_az = self.core.get_telescope_altaz()
        d_alt = abs(it["alt"] - m_alt)
        d_az = abs((it["az"] - m_az + 180.0) % 360.0 - 180.0)
        slew_dist = math.sqrt(d_alt * d_alt + d_az * d_az)
        slew_sec = slew_dist / 2.0 # Approx 2 deg/s constant velocity slew
        self.lbl_det_slew.setText(f"{slew_dist:.1f}° angular offset (~{slew_sec:.0f}s slew)")

        # Sun distance
        has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
        if it["sun_sep"] < float(self.config.get("sun_keepout_deg", 15.0)):
            if has_filter:
                self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}° [FILTER ATTACHED]")
                self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FFE082;" if not self.night_mode else "font-weight: 700; color: #FF9999;")
            else:
                self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}° [DANGER < 15°]")
                self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FF6666;" if not self.night_mode else "font-weight: 700; color: #FF2222;")
        else:
            self.lbl_det_sun.setText(f"{it['sun_sep']:.1f}°")
            self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FFAAAA;" if self.night_mode else "font-weight: 700; color: #8CD68C;")

        self.txt_desc.setText(it["description"])
        self.btn_slew.setEnabled(True)

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)
        if hasattr(self, "lbl_mount_summary"):
            self.lbl_mount_summary.setStyleSheet(
                "font-family: 'Consolas', monospace; font-size: 15px; font-weight: 800; color: #FF4D4D; padding: 2px 8px; border-radius: 4px;"
                if enabled else
                "font-family: 'Consolas', monospace; font-size: 15px; font-weight: 800; color: #5AA9FF; padding: 2px 8px; border-radius: 4px;"
            )
        if hasattr(self, "lbl_target_name"):
            self.lbl_target_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #FF6666;" if enabled else "font-size: 15px; font-weight: 800; color: #FFFFFF;")
        if hasattr(self, "lbl_target_meta"):
            self.lbl_target_meta.setStyleSheet("font-size: 11px; color: #991F1F;" if enabled else "font-size: 11px; color: #8892A0;")
        if hasattr(self, "coords_card"):
            self.coords_card.setStyleSheet("background-color: #080101; border: 1px solid #330808; border-radius: 3px;" if enabled else "background-color: #12151B; border: 1px solid #2B313D; border-radius: 3px;")
        if hasattr(self, "lbl_det_altaz"):
            self.lbl_det_altaz.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #FF4D4D;" if enabled else "font-family: 'Consolas'; font-weight: 700; color: #5AA9FF;")
        if hasattr(self, "lbl_det_radec"):
            self.lbl_det_radec.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #FF3333;" if enabled else "font-family: 'Consolas'; font-weight: 700; color: #DCE2EB;")
        if hasattr(self, "lbl_det_slew"):
            self.lbl_det_slew.setStyleSheet("font-weight: 700; color: #FFAAAA;" if enabled else "font-weight: 700; color: #8CD68C;")
        if hasattr(self, "txt_desc"):
            self.txt_desc.setStyleSheet("background-color: #060101; border: 1px solid #2E0505; color: #FF6666; font-size: 11px;" if enabled else "background-color: #0E1015; border: 1px solid #242832; color: #A0ABB8; font-size: 11px;")
        if hasattr(self, "lbl_status"):
            self.lbl_status.setStyleSheet("font-size: 11px; color: #991F1F;" if enabled else "font-size: 11px; color: #8892A0;")
        if hasattr(self, "lbl_det_sun"):
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if self.selected_item and self.selected_item.get("sun_sep", 99.0) < float(self.config.get("sun_keepout_deg", 15.0)):
                if has_filter:
                    self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FF9999;" if enabled else "font-weight: 700; color: #FFE082;")
                else:
                    self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FF2222;" if enabled else "font-weight: 700; color: #FF6666;")
            else:
                self.lbl_det_sun.setStyleSheet("font-weight: 700; color: #FFAAAA;" if enabled else "font-weight: 700; color: #8CD68C;")
        self._style_weather_card()
        try:
            self._refresh_all_targets(force_recalc=True)
        except Exception:
            pass

    def _update_mount_pos_fast(self) -> None:
        """Fast 50ms real-time mount Az/Alt coordinate update."""
        if self.core and hasattr(self.core, "get_telescope_altaz"):
            m_alt, m_az = self.core.get_telescope_altaz()
            if hasattr(self, "lbl_mount_summary"):
                self.lbl_mount_summary.setText(f"Mount: Az {m_az:.1f}°, Alt {m_alt:.1f}°")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        if hasattr(self, "mount_pos_timer") and self.mount_pos_timer.isActive():
            self.mount_pos_timer.stop()
        event.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "timer") and not self.timer.isActive():
            self.timer.start(1000)
        if hasattr(self, "mount_pos_timer") and not self.mount_pos_timer.isActive():
            self.mount_pos_timer.start(50)

    def _refresh_weather_clicked(self) -> None:
        if self.weather_service:
            self.weather_service.fetch_async()
        elif self.main_window and hasattr(self.main_window, "weather_service") and self.main_window.weather_service:
            self.main_window.weather_service.fetch_async()
        if hasattr(self, "lbl_weather_badge"):
            self.lbl_weather_badge.setText("[CHECKING...]")

    def update_weather_display(self, data: Dict[str, Any]) -> None:
        self.weather_data = data
        cloud = data.get("cloud_cover", 0)
        temp = data.get("temperature_c", 0.0)
        hum = data.get("humidity_pct", 0)
        wind = data.get("wind_kmh", 0.0)
        vis_km = data.get("visibility_km", 10.0)
        condition = data.get("condition", "Clear Sky" if cloud < 20 else ("Overcast" if cloud >= 80 else "Cloudy"))
        badge = data.get("badge", "[WEATHER]")
        transparency = data.get("transparency", "Normal")

        if hasattr(self, "lbl_weather_badge"):
            self.lbl_weather_badge.setText(f"{badge} {cloud}% CLOUD")
        if hasattr(self, "lbl_weather_condition"):
            self.lbl_weather_condition.setText(f"Sky: {condition}")
        if hasattr(self, "lbl_weather_seeing"):
            self.lbl_weather_seeing.setText(f"Seeing: {transparency}")
        if hasattr(self, "lbl_weather_metrics"):
            self.lbl_weather_metrics.setText(f"Temp: {temp:.1f}°C  |  Humidity: {hum}%  |  Wind: {wind:.1f} km/h  |  Visibility: {vis_km:.1f} km")

        self._style_weather_card()
        self._refresh_table_view()

    def _style_weather_card(self) -> None:
        if not hasattr(self, "weather_card"):
            return
        if self.night_mode:
            self.weather_card.setStyleSheet("background-color: #240505; border: 1px solid #5C0B0B; border-radius: 4px; padding: 4px;")
            if hasattr(self, "lbl_weather_badge"):
                self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFAAAA;")
            if hasattr(self, "lbl_weather_condition"):
                self.lbl_weather_condition.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666;")
            if hasattr(self, "lbl_weather_seeing"):
                self.lbl_weather_seeing.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF8888;")
            if hasattr(self, "lbl_weather_metrics"):
                self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #FF8888;")
        else:
            self.weather_card.setStyleSheet("background-color: #172433; border: 1px solid #2B4B6E; border-radius: 4px; padding: 4px;")
            if hasattr(self, "lbl_weather_badge"):
                self.lbl_weather_badge.setStyleSheet("font-size: 11px; font-weight: 800; color: #5AA9FF;")
            if hasattr(self, "lbl_weather_condition"):
                self.lbl_weather_condition.setStyleSheet("font-size: 11px; font-weight: 700; color: #DCE2EB;")
            if hasattr(self, "lbl_weather_seeing"):
                self.lbl_weather_seeing.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFE082;")
            if hasattr(self, "lbl_weather_metrics"):
                self.lbl_weather_metrics.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #C8D1DC;")

    def _toggle_night_from_tour(self) -> None:
        if self.main_window and hasattr(self.main_window, "toggle_night_mode"):
            self.main_window.toggle_night_mode()
        else:
            self.set_night_mode(not self.night_mode)

    def _query_stellarium_target(self, item: Dict[str, Any]) -> Optional[Tuple[float, float, bool]]:
        """Queries Stellarium Remote Control HTTP API (port 8090) for target coordinates.
        If Stellarium is connected and recognizes the target:
          - Selects and centers the object in Stellarium via /api/main/focus.
          - Returns (raJ2000, decJ2000, True) so the mount slews to Stellarium's exact coordinate.
        Returns None if Stellarium is unreachable or target is unrecognized.
        """
        import urllib.request
        import urllib.parse
        import json
        import re

        host = self.config.get("stellarium_host", "127.0.0.1")
        port = 8090
        if hasattr(self.core, "follower") and self.core.follower:
            host = self.core.follower.host
            port = self.core.follower.port

        candidates: List[str] = []
        if item.get("dynamic_body"):
            dyn = item["dynamic_body"]
            candidates.append(dyn)
            if dyn.lower() == "moon":
                candidates.append("moon")

        raw_name = item.get("name", "")
        for pm in re.findall(r'\((.*?)\)', raw_name):
            for part in pm.split('&'):
                clean = part.strip()
                if re.match(r'^(M\d+|NGC\s*\d+|IC\s*\d+|Alpha\s+\w+|Beta\s+\w+|Gamma\s+\w+)', clean, re.IGNORECASE):
                    candidates.append(clean)
                    candidates.append(clean.replace(" ", ""))

        prefix = raw_name.split('(')[0].strip()
        if prefix:
            if '&' in prefix:
                for sub in prefix.split('&'):
                    sub_c = sub.strip()
                    if sub_c:
                        candidates.append(sub_c)
            candidates.append(prefix)
            simplified = re.sub(r'\b(Nebula|Cluster|Galaxy|Great)\b', '', prefix, flags=re.IGNORECASE).strip()
            if simplified and simplified != prefix:
                candidates.append(simplified)

        candidates.append(raw_name)

        seen = set()
        uniq_candidates: List[str] = []
        for c in candidates:
            c_low = c.lower()
            if c_low not in seen:
                seen.add(c_low)
                uniq_candidates.append(c)

        for candidate in uniq_candidates:
            try:
                enc = urllib.parse.quote(candidate)
                url = f"http://{host}:{port}/api/objects/info?name={enc}&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "CustomGoTo/3.2"})
                with urllib.request.urlopen(req, timeout=0.35) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data and "raJ2000" in data and "decJ2000" in data:
                            ra_j2k = float(data["raJ2000"])
                            dec_j2k = float(data["decJ2000"])

                            try:
                                focus_url = f"http://{host}:{port}/api/main/focus"
                                payload = urllib.parse.urlencode({"target": candidate, "mode": "center"}).encode("utf-8")
                                focus_req = urllib.request.Request(focus_url, data=payload, headers={"User-Agent": "CustomGoTo/3.2"})
                                urllib.request.urlopen(focus_req, timeout=0.25)
                            except Exception:
                                pass

                            return ra_j2k, dec_j2k, True
            except Exception:
                continue

        return None

    def _start_slew(self) -> None:
        if not self.selected_item or not self.core:
            return

        it = self.selected_item
        is_j2000_mode = (self.config.get("epoch", "J2000") == "J2000")

        # 1. Coordinate synchronization with Stellarium Remote Control (port 8090)
        # If Stellarium is connected, fetch the exact micro-arcsecond coordinates that
        # Stellarium itself uses, and center the target in Stellarium.
        # This completely eliminates target discrepancy between Stellarium Ctrl+1 and Tonight's Best.
        stellarium_coords = self._query_stellarium_target(it)
        if stellarium_coords is not None:
            slew_ra, slew_dec, slew_j2000 = stellarium_coords
        else:
            slew_ra = it["calc_ra"]
            slew_dec = it["calc_dec"]
            slew_j2000 = is_j2000_mode

        # Authorize target in follower if active
        if hasattr(self.core, "follower") and self.core.follower:
            target_auth = it.get("dynamic_body") or it["name"]
            self.core.follower.authorize_target(target_auth)

        # Notify main window that a slew has started so arrival chime can fire
        target_win = self.main_window or self.parent()
        if target_win and hasattr(target_win, "_was_slewing"):
            target_win._was_slewing = True

        ok = self.core.on_goto_requested(slew_ra, slew_dec, is_j2000=slew_j2000, target_name=it["name"])
        if ok:
            src_tag = "Stellarium sync" if stellarium_coords is not None else "High-precision catalog"
            self.lbl_status.setText(f"GoTo active: Slewing to {it['name']} [{src_tag}]... (Mount active)")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF4D4D;" if self.night_mode else "font-size: 11px; font-weight: 700; color: #43A047;")
        else:
            self.lbl_status.setText(f"GoTo rejected: Safety limits or solar keepout for {it['name']}.")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF4D4D;")


# ==============================================================================
# TARGET GOTO & CELESTIAL CATALOG DIALOG
# ==============================================================================
