"""
goto_dialog.py
Target coordinate entry and celestial object lookup dialog.
"""

from __future__ import annotations
import math
from typing import Optional, Dict, Any
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup, QMessageBox, QWidget
)
from src.core.astrometry import deg_to_hms, deg_to_dms
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE
try:
    from telescope_bridge import radec_to_altaz, altaz_to_radec
except ImportError:
    radec_to_altaz = altaz_to_radec = None

class GoToDialog(QDialog):
    """Allows selecting a celestial target or entering custom RA/Dec for GoTo slewing at constant velocity."""

    PRESETS = [
        ("Sirius (Alpha CMa)", 101.287, -16.716),
        ("Vega (Alpha Lyr)", 279.234, 38.783),
        ("Betelgeuse (Alpha Ori)", 88.793, 7.407),
        ("Rigel (Beta Ori)", 78.634, -8.201),
        ("Polaris (Alpha UMi)", 37.954, 89.264),
        ("Arcturus (Alpha Boo)", 213.915, 19.182),
        ("Capella (Alpha Aur)", 79.172, 45.998),
        ("Aldebaran (Alpha Tau)", 68.980, 16.509),
        ("Antares (Alpha Sco)", 247.352, -26.432),
        ("Andromeda Galaxy (M31)", 10.684, 41.269),
        ("Orion Nebula (M42)", 83.822, -5.391),
        ("Pleiades Cluster (M45)", 56.750, 24.116),
        ("Hercules Cluster (M13)", 250.422, 36.460),
    ]

    def __init__(self, core: Any = None, config: Optional[Dict[str, Any]] = None, night_mode: bool = False, parent: Optional[QWidget] = None, *args, **kwargs):
        if parent is None and "parent" in kwargs:
            parent = kwargs["parent"]
        if core is None and "core" in kwargs:
            core = kwargs["core"]
        if config is None and "config" in kwargs:
            config = kwargs["config"]
        super().__init__(parent)
        self.core = core
        self.config = config or {}
        self.night_mode = night_mode
        self.setWindowTitle("Manual GoTo Target & Celestial Catalog")
        self.resize(480, 360)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("SELECT CELESTIAL TARGET OR ENTER COORDINATES")
        lbl_title.setProperty("class", "section-header")
        layout.addWidget(lbl_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_presets = QComboBox()
        self.combo_presets.addItem("Custom Target Coordinates...", None)
        presets_to_add = [(name, ra, dec, True) for name, ra, dec in self.PRESETS]
        if sun_radec and self.core:
            try:
                t_now = self.core.get_time()
                s_ra, s_dec = sun_radec(t_now)
                presets_to_add.append(("Sun (Solar Filter Required)", round(s_ra, 4), round(s_dec, 4), False))
            except Exception:
                pass
        for item in presets_to_add:
            name, ra, dec, is_j2000 = item
            self.combo_presets.addItem(f"{name} (RA {ra:.1f}°, Dec {dec:+.1f}°)", (ra, dec, is_j2000))
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        form.addRow("Target Catalog:", self.combo_presets)

        self.spin_ra = QDoubleSpinBox()
        self.spin_ra.setRange(0.0, 360.0)
        self.spin_ra.setDecimals(4)
        self.spin_ra.setSuffix("°")
        self.spin_ra.setValue(101.287)
        self.spin_ra.valueChanged.connect(self._recalc_preview)
        form.addRow("Right Ascension (RA):", self.spin_ra)

        self.spin_dec = QDoubleSpinBox()
        self.spin_dec.setRange(-90.0, 90.0)
        self.spin_dec.setDecimals(4)
        self.spin_dec.setSuffix("°")
        self.spin_dec.setValue(-16.716)
        self.spin_dec.valueChanged.connect(self._recalc_preview)
        form.addRow("Declination (Dec):", self.spin_dec)

        layout.addLayout(form)

        # Status & Safety Preview Card
        card = QFrame()
        card.setProperty("class", "card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(12, 10, 12, 10)
        card_lay.setSpacing(4)

        self.lbl_preview_altaz = QLabel("Target Alt / Az: --")
        self.lbl_preview_altaz.setStyleSheet("font-size: 11px; font-weight: 700; color: #5B9DD9;")
        card_lay.addWidget(self.lbl_preview_altaz)

        self.lbl_preview_safety = QLabel("Safety: --")
        self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 600; color: #ABB2BF;")
        card_lay.addWidget(self.lbl_preview_safety)

        self.lbl_preview_duration = QLabel("Constant Slew Duration: --")
        self.lbl_preview_duration.setStyleSheet("font-size: 11px; font-weight: 600; color: #8CD68C;")
        card_lay.addWidget(self.lbl_preview_duration)

        layout.addWidget(card)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        self.btn_slew = QPushButton("Start GoTo Slew")
        self.btn_slew.setProperty("class", "primary")
        self.btn_slew.clicked.connect(self._start_slew)
        btn_box.addWidget(self.btn_slew)

        layout.addLayout(btn_box)

        # Trigger initial selection
        self.combo_presets.setCurrentIndex(1)

    def _on_preset_selected(self, idx: int) -> None:
        data = self.combo_presets.currentData()
        if data:
            ra, dec, is_j2000 = data
            self.is_current_preset_j2000 = is_j2000
            self.spin_ra.blockSignals(True)
            self.spin_dec.blockSignals(True)
            self.spin_ra.setValue(ra)
            self.spin_dec.setValue(dec)
            self.spin_ra.blockSignals(False)
            self.spin_dec.blockSignals(False)
        else:
            self.is_current_preset_j2000 = (self.config.get("epoch", "J2000") == "J2000")
        self._recalc_preview()

    def _recalc_preview(self) -> None:
        if not self.core:
            return
        ra = self.spin_ra.value()
        dec = self.spin_dec.value()
        t = self.core.get_time()
        lat = float(self.config.get("latitude_deg", 12.84))
        lon = float(self.config.get("longitude_deg", 80.15))

        is_j2000 = getattr(self, "is_current_preset_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        if is_j2000 and precess_j2000_to_date:
            ra_date, dec_date = precess_j2000_to_date(ra, dec, t)
        else:
            ra_date, dec_date = ra, dec

        use_refr = bool(self.config.get("apply_refraction", True))
        alt, az = radec_to_altaz(ra_date, dec_date, lat, lon, t, apply_refraction=use_refr) if radec_to_altaz else (45.0, 180.0)
        self.lbl_preview_altaz.setText(f"Target Alt / Az: {alt:+.1f}° / {az:.1f}° (apparent)")

        alt_min = float(self.config.get("alt_min_deg", 0.0))
        alt_max = float(self.config.get("alt_max_deg", 85.0))
        keepout = float(self.config.get("sun_keepout_deg", 15.0))

        s_ra, s_dec = sun_radec(t) if sun_radec else (0.0, 0.0)
        sun_sep = separation_deg(ra_date, dec_date, s_ra, s_dec) if separation_deg else 90.0

        is_safe = True
        err_msg = ""
        if alt < alt_min:
            is_safe = False
            err_msg = f"Target Below Horizon ({alt:.1f}° < {alt_min:.0f}°)"
        elif alt > alt_max:
            is_safe = False
            err_msg = f"Target Exceeds Max Elevation ({alt:.1f}° > {alt_max:.0f}°)"
        elif sun_sep < keepout:
            has_filter = getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)
            if has_filter:
                self.lbl_preview_safety.setText(f"Safety: SOLAR OBSERVATION (Sun separation: {sun_sep:.1f}° - Filter Active)")
                self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFE082;")
                self.btn_slew.setEnabled(True)
            else:
                self.lbl_preview_safety.setText(f"Safety: CAUTION - Sun separation {sun_sep:.1f}° < {keepout:.0f}° (Solar Filter Required)")
                self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFB74D;")
                self.btn_slew.setEnabled(True)

        if is_safe and (sun_sep >= keepout or getattr(self.core, 'solar_filter_confirmed', False) or self.config.get("solar_filter_installed", False)):
            self.lbl_preview_safety.setText(f"Safety: OK (Above horizon, Sun separation: {sun_sep:.1f}°)")
            self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 600; color: #8CD68C;")
            self.btn_slew.setEnabled(True)
        elif not is_safe:
            self.lbl_preview_safety.setText(f"Safety: BLOCKED - {err_msg}")
            self.lbl_preview_safety.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF6666;")
            self.btn_slew.setEnabled(False)

        # Calculate slew distance and coordinated duration (max of axes)
        cur_alt, cur_az = self.core.get_telescope_altaz()
        diff_az = abs(az - cur_az)
        if diff_az > 180.0:
            diff_az = 360.0 - diff_az
        diff_alt = abs(alt - cur_alt)

        steps_deg_az = float(self.config.get("steps_per_deg_az", 113.22))
        speed_steps_az = float(self.config.get("speed_az", 226))
        speed_deg_s_az = speed_steps_az / steps_deg_az if steps_deg_az > 0 else 2.0

        steps_deg_alt = float(self.config.get("steps_per_deg_alt", 113.22))
        speed_steps_alt = float(self.config.get("speed_alt", 226))
        speed_deg_s_alt = speed_steps_alt / steps_deg_alt if steps_deg_alt > 0 else 2.0

        dur_az = diff_az / speed_deg_s_az if speed_deg_s_az > 0 else 0.0
        dur_alt = diff_alt / speed_deg_s_alt if speed_deg_s_alt > 0 else 0.0
        dur_s = max(dur_az, dur_alt)

        self.lbl_preview_duration.setText(
            f"Distance: Az {diff_az:.1f}°, Alt {diff_alt:.1f}° | Slew Duration: {dur_s:.1f}s"
        )

    def _start_slew(self) -> None:
        if not self.core or not self.core.link or not self.core.link.is_open:
            QMessageBox.warning(self, "Hardware Not Connected", "Please connect to Arduino or Simulator first.")
            return
        ra = self.spin_ra.value()
        dec = self.spin_dec.value()

        t = self.core.get_time()
        s_ra, s_dec = sun_radec(t) if sun_radec else (0.0, 0.0)
        sun_sep = separation_deg(ra, dec, s_ra, s_dec) if separation_deg else 90.0
        keepout = float(self.config.get("sun_keepout_deg", 15.0))

        solar_ok = False
        if sun_sep < keepout:
            # Check if the user physically checked the Solar Filter Attached box on the GUI
            parent_win = self.parent()
            has_gui_filter = False
            if hasattr(parent_win, 'chk_solar_filter') and parent_win.chk_solar_filter:
                has_gui_filter = parent_win.chk_solar_filter.isChecked()

            if not has_gui_filter:
                # Solar filter attached box is unchecked: ALWAYS show warning dialog before slewing to Sun!
                confirmed = False
                if hasattr(parent_win, '_prompt_solar_warning'):
                    confirmed = parent_win._prompt_solar_warning(sun_sep)
                elif self.core and self.core.solar_warning_callback:
                    confirmed = self.core.solar_warning_callback(sun_sep)
                if not confirmed:
                    return
                solar_ok = True
            else:
                solar_ok = True

        is_j2000 = getattr(self, "is_current_preset_j2000", (self.config.get("epoch", "J2000") == "J2000"))
        ok = self.core.on_goto_requested(ra, dec, is_j2000=is_j2000, solar_confirmed=solar_ok)
        if ok and hasattr(self.core, "follower") and self.core.follower:
            target_preset = self.combo_presets.currentText()
            self.core.follower.authorize_target(target_preset)
        if ok:
            self.accept()
        else:
            QMessageBox.warning(self, "GoTo Rejected", "GoTo command was rejected by mount safety interlocks.")


# ==============================================================================
# MAIN APPLICATION WINDOW (Version 2.0 - Scientific Clean Layout)
# ==============================================================================
