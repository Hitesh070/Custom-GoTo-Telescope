"""
settings_dialog.py
Hardware kinematics, observer location, and connection configuration dialog.
"""

from __future__ import annotations
import os
from typing import Optional, Dict, Any
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox,
    QDialogButtonBox, QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QMessageBox,
    QTabWidget, QWidget
)
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE

class SettingsDialog(QDialog):
    """Configuration editor with instant validation and JSON save."""

    def __init__(self, config: Dict[str, Any], night_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.night_mode = night_mode
        self.setWindowTitle("Telescope Configuration & Alignment Settings")
        self.resize(520, 560)
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self._build_ui()

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        tabs = self.tabs

        tab_site = QWidget()
        form_site = QFormLayout(tab_site)
        form_site.setSpacing(10)

        self.spin_lat = QDoubleSpinBox()
        self.spin_lat.setRange(-90.0, 90.0)
        self.spin_lat.setDecimals(4)
        self.spin_lat.setValue(float(self.config.get("latitude_deg", 12.84)))
        form_site.addRow("Latitude (° North):", self.spin_lat)

        self.spin_lon = QDoubleSpinBox()
        self.spin_lon.setRange(-180.0, 180.0)
        self.spin_lon.setDecimals(4)
        self.spin_lon.setValue(float(self.config.get("longitude_deg", 80.15)))
        form_site.addRow("Longitude (° East):", self.spin_lon)

        btn_sync_loc = QPushButton("Sync Location from Stellarium (Port 8090)")
        btn_sync_loc.setToolTip("Pulls active observer coordinates automatically from Stellarium Remote Control")
        btn_sync_loc.clicked.connect(self._sync_location_from_stellarium)
        form_site.addRow("", btn_sync_loc)

        self.chk_refraction = QCheckBox("Apply Atmospheric Refraction (Bennett model)")
        self.chk_refraction.setChecked(bool(self.config.get("apply_refraction", True)))
        self.chk_refraction.setToolTip("Compensates for atmospheric bending of starlight so reticle aligns perfectly with eyepiece view")
        form_site.addRow("Atmosphere Correction:", self.chk_refraction)

        self.combo_epoch = QComboBox()
        self.combo_epoch.addItems(["J2000", "JNow"])
        self.combo_epoch.setCurrentText(self.config.get("epoch", "J2000"))
        form_site.addRow("Stellarium Epoch:", self.combo_epoch)

        self.txt_host = QLineEdit(str(self.config.get("stellarium_host", "127.0.0.1")))
        form_site.addRow("Stellarium Server IP:", self.txt_host)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(int(self.config.get("stellarium_port", 10001)))
        form_site.addRow("Stellarium Port:", self.spin_port)

        tabs.addTab(tab_site, "Site & Network")

        tab_motors = QWidget()
        form_motors = QFormLayout(tab_motors)
        form_motors.setSpacing(10)

        self.spin_step_az = QDoubleSpinBox()
        self.spin_step_az.setRange(1.0, 10000.0)
        self.spin_step_az.setDecimals(2)
        self.spin_step_az.setValue(float(self.config.get("steps_per_deg_az", 113.22)))
        form_motors.addRow("Steps / Degree (Azimuth):", self.spin_step_az)

        self.spin_step_alt = QDoubleSpinBox()
        self.spin_step_alt.setRange(1.0, 10000.0)
        self.spin_step_alt.setDecimals(2)
        self.spin_step_alt.setValue(float(self.config.get("steps_per_deg_alt", 113.22)))
        form_motors.addRow("Steps / Degree (Altitude):", self.spin_step_alt)

        self.spin_speed_az = QSpinBox()
        self.spin_speed_az.setRange(50, 1500)
        self.spin_speed_az.setValue(int(self.config.get("speed_az", 226)))
        form_motors.addRow("Max Speed Az (steps/s):", self.spin_speed_az)

        self.spin_speed_alt = QSpinBox()
        self.spin_speed_alt.setRange(50, 1500)
        self.spin_speed_alt.setValue(int(self.config.get("speed_alt", 226)))
        form_motors.addRow("Max Speed Alt (steps/s):", self.spin_speed_alt)

        self.spin_accel_az = QSpinBox()
        self.spin_accel_az.setRange(20, 2000)
        self.spin_accel_az.setValue(int(self.config.get("accel_az", 100)))
        form_motors.addRow("Acceleration Az (steps/s²):", self.spin_accel_az)

        self.spin_accel_alt = QSpinBox()
        self.spin_accel_alt.setRange(20, 2000)
        self.spin_accel_alt.setValue(int(self.config.get("accel_alt", 100)))
        form_motors.addRow("Acceleration Alt (steps/s²):", self.spin_accel_alt)

        tabs.addTab(tab_motors, "Motors & Kinematics")

        tab_safety = QWidget()
        form_safety = QFormLayout(tab_safety)
        form_safety.setSpacing(10)

        self.spin_backlash_az = QSpinBox()
        self.spin_backlash_az.setRange(0, 10000)
        self.spin_backlash_az.setValue(int(self.config.get("backlash_az", 0)))
        form_safety.addRow("Backlash Steps (Azimuth):", self.spin_backlash_az)

        self.spin_backlash_alt = QSpinBox()
        self.spin_backlash_alt.setRange(0, 10000)
        self.spin_backlash_alt.setValue(int(self.config.get("backlash_alt", 0)))
        form_safety.addRow("Backlash Steps (Altitude):", self.spin_backlash_alt)

        self.spin_alt_min = QDoubleSpinBox()
        self.spin_alt_min.setRange(-10.0, 45.0)
        self.spin_alt_min.setValue(float(self.config.get("alt_min_deg", 0.0)))
        form_safety.addRow("Altitude Min Limit (°):", self.spin_alt_min)

        self.spin_alt_max = QDoubleSpinBox()
        self.spin_alt_max.setRange(60.0, 90.0)
        self.spin_alt_max.setValue(float(self.config.get("alt_max_deg", 85.0)))
        form_safety.addRow("Altitude Max Limit (°):", self.spin_alt_max)

        self.spin_sun_keepout = QDoubleSpinBox()
        self.spin_sun_keepout.setRange(0.0, 45.0)
        self.spin_sun_keepout.setValue(float(self.config.get("sun_keepout_deg", 15.0)))
        form_safety.addRow("Sun Keepout Zone (°):", self.spin_sun_keepout)

        self.chk_az_home = QCheckBox("Azimuth Switch Installed")
        self.chk_az_home.setChecked(bool(self.config.get("az_home_switch", False)))
        form_safety.addRow("", self.chk_az_home)

        tabs.addTab(tab_safety, "Backlash & Safety")

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Configuration")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def _sync_location_from_stellarium(self) -> None:
        import urllib.request, json
        host = self.txt_host.text().strip() or "127.0.0.1"
        url = f"http://{host}:8090/api/main/status"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CustomGoTo-Bridge/4.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    loc = data.get("location", {})
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    name = loc.get("name") or loc.get("role") or "Stellarium Site"
                    if lat is not None and lon is not None:
                        self.spin_lat.setValue(float(lat))
                        self.spin_lon.setValue(float(lon))
                        QMessageBox.information(
                            self, "Location Synced",
                            f"Successfully synced observer location from Stellarium:\n\n"
                            f"Site: {name}\n"
                            f"Latitude: {float(lat):.4f}°\n"
                            f"Longitude: {float(lon):.4f}°"
                        )
                        return
            QMessageBox.warning(self, "Sync Failed", "Stellarium responded but location data was missing.")
        except Exception as e:
            QMessageBox.warning(
                self, "Connection Error",
                f"Could not reach Stellarium on port 8090:\n{e}\n\n"
                f"Make sure Stellarium is open and Remote Control plugin is enabled:\n"
                f"In Stellarium: F2 -> Plugins -> Remote Control -> Load at startup."
            )

    def _save_settings(self) -> None:
        self.config["latitude_deg"] = self.spin_lat.value()
        self.config["longitude_deg"] = self.spin_lon.value()
        self.config["apply_refraction"] = self.chk_refraction.isChecked()
        self.config["epoch"] = self.combo_epoch.currentText()
        self.config["stellarium_host"] = self.txt_host.text().strip()
        self.config["stellarium_port"] = self.spin_port.value()

        self.config["steps_per_deg_az"] = self.spin_step_az.value()
        self.config["steps_per_deg_alt"] = self.spin_step_alt.value()
        self.config["speed_az"] = self.spin_speed_az.value()
        self.config["speed_alt"] = self.spin_speed_alt.value()
        self.config["accel_az"] = self.spin_accel_az.value()
        self.config["accel_alt"] = self.spin_accel_alt.value()

        self.config["backlash_az"] = self.spin_backlash_az.value()
        self.config["backlash_alt"] = self.spin_backlash_alt.value()
        self.config["alt_min_deg"] = self.spin_alt_min.value()
        self.config["alt_max_deg"] = self.spin_alt_max.value()
        self.config["sun_keepout_deg"] = self.spin_sun_keepout.value()
        self.config["az_home_switch"] = self.chk_az_home.isChecked()

        if hasattr(self.config, "save"):
            self.config.save()
        self.accept()


# ==============================================================================
# AUTOMATIC FOCUS (V-CURVE) & CALIBRATION DIALOG
# ==============================================================================
