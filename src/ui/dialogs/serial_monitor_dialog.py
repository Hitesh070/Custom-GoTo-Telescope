"""
serial_monitor_dialog.py
Raw bidirectional serial packet and command terminal dialog.
"""

from __future__ import annotations
import datetime as dt
from typing import Optional, Any
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QCheckBox, QWidget
)
from src.ui.theme import SCIENTIFIC_STYLE, NIGHT_VISION_STYLE

class SerialMonitorDialog(QDialog):
    """Real-time interactive Serial Monitor displaying raw TX/RX communications with Arduino."""

    def __init__(self, core: Any, night_mode: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.core = core
        self.night_mode = night_mode
        self.setWindowTitle("Arduino Serial Monitor - Testing")
        self.setStyleSheet(NIGHT_VISION_STYLE if night_mode else SCIENTIFIC_STYLE)
        self.resize(720, 500)
        self._history: List[str] = []
        self._history_idx = -1
        self._build_ui()

        # Connect to core serial monitor listener
        self._listener = self._on_raw_serial
        if self.core:
            self.core.register_serial_monitor(self._listener)

    def closeEvent(self, event: Any) -> None:
        if self.core:
            self.core.unregister_serial_monitor(self._listener)
        super().closeEvent(event)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Top Control Strip
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.chk_filter_p = QCheckBox("Hide 'P' Polls")
        self.chk_filter_p.setChecked(True)
        self.chk_filter_p.setToolTip("Hides high-frequency 300ms position telemetry polls (P / P 0 0 ...) to reduce noise")
        top_bar.addWidget(self.chk_filter_p)

        self.chk_autoscroll = QCheckBox("Auto-Scroll")
        self.chk_autoscroll.setChecked(True)
        top_bar.addWidget(self.chk_autoscroll)

        self.chk_pause = QCheckBox("Pause")
        self.chk_pause.setToolTip("Temporarily freeze log view to inspect received frames")
        top_bar.addWidget(self.chk_pause)

        top_bar.addStretch()

        btn_clear = QPushButton("Clear Monitor")
        btn_clear.clicked.connect(self._clear_monitor)
        top_bar.addWidget(btn_clear)

        layout.addLayout(top_bar)

        # High-Contrast Monospace Terminal
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.document().setMaximumBlockCount(4000)
        self.terminal.setStyleSheet(
            "background-color: #0A0D12; color: #DCE2EB; font-family: 'Consolas', 'JetBrains Mono', monospace; "
            "font-size: 12px; border: 1px solid #2B3340; border-radius: 4px; padding: 6px;"
            if not self.night_mode else
            "background-color: #120000; color: #FFAAAA; font-family: 'Consolas', monospace; "
            "font-size: 12px; border: 1px solid #550000; border-radius: 4px; padding: 6px;"
        )
        layout.addWidget(self.terminal, stretch=1)

        # Bottom Command Entry Strip
        cmd_box = QHBoxLayout()
        cmd_box.setSpacing(8)

        self.lbl_prompt = QLabel("Command:")
        self.lbl_prompt.setStyleSheet("font-weight: 700; color: #8892A0;" if not self.night_mode else "font-weight: 700; color: #AA2222;")
        cmd_box.addWidget(self.lbl_prompt)

        self.txt_cmd = QLineEdit()
        self.txt_cmd.setPlaceholderText("Enter firmware command (e.g. P, S, H, V 226, G 1000 500) and press Enter")
        self.txt_cmd.returnPressed.connect(self._send_custom_command)
        cmd_box.addWidget(self.txt_cmd, stretch=1)

        self.btn_send = QPushButton("Send")
        if self.night_mode:
            self.btn_send.setStyleSheet("QPushButton { background-color: #5C0B0B; border: 1px solid #801010; color: #FFAAAA; font-weight: 700; padding: 5px 16px; border-radius: 3px; } QPushButton:hover { background-color: #730E0E; }")
        else:
            self.btn_send.setStyleSheet("QPushButton { background-color: #1E4472; border: 1px solid #336FA5; color: #FFFFFF; font-weight: 700; padding: 5px 16px; border-radius: 3px; } QPushButton:hover { background-color: #285A96; }")
        self.btn_send.clicked.connect(self._send_custom_command)
        cmd_box.addWidget(self.btn_send)

        layout.addLayout(cmd_box)

    def set_night_mode(self, enabled: bool) -> None:
        self.night_mode = enabled
        self.setStyleSheet(NIGHT_VISION_STYLE if enabled else SCIENTIFIC_STYLE)
        if hasattr(self, "terminal"):
            self.terminal.setStyleSheet(
                "background-color: #120000; color: #FFAAAA; font-family: 'Consolas', monospace; "
                "font-size: 12px; border: 1px solid #550000; border-radius: 4px; padding: 6px;"
                if enabled else
                "background-color: #0A0D12; color: #DCE2EB; font-family: 'Consolas', 'JetBrains Mono', monospace; "
                "font-size: 12px; border: 1px solid #2B3340; border-radius: 4px; padding: 6px;"
            )
        if hasattr(self, "lbl_prompt"):
            self.lbl_prompt.setStyleSheet("font-weight: 700; color: #AA2222;" if enabled else "font-weight: 700; color: #8892A0;")
        if hasattr(self, "btn_send"):
            if enabled:
                self.btn_send.setStyleSheet("QPushButton { background-color: #5C0B0B; border: 1px solid #801010; color: #FFAAAA; font-weight: 700; padding: 5px 16px; border-radius: 3px; } QPushButton:hover { background-color: #730E0E; }")
            else:
                self.btn_send.setStyleSheet("QPushButton { background-color: #1E4472; border: 1px solid #336FA5; color: #FFFFFF; font-weight: 700; padding: 5px 16px; border-radius: 3px; } QPushButton:hover { background-color: #285A96; }")

    def _clear_monitor(self) -> None:
        self.terminal.clear()

    def _send_custom_command(self) -> None:
        cmd = self.txt_cmd.text().strip()
        if not cmd:
            return
        self.txt_cmd.clear()
        self._history.append(cmd)
        self._history_idx = len(self._history)

        if not self.core or not self.core.link or not self.core.link.is_open:
            self._append_html("<span style='color: #FF5252;'>[SYSTEM] Hardware link not connected!</span>")
            return

        # Execute command synchronously in short thread so UI does not stutter
        def _exec():
            try:
                self.core.link.send(cmd)
            except Exception as e:
                self._append_html(f"<span style='color: #FF5252;'>[ERROR] {e}</span>")

        threading.Thread(target=_exec, daemon=True, name="SerialMonitorSend").start()

    def _on_raw_serial(self, direction: str, line: str) -> None:
        if self.chk_pause.isChecked():
            return

        is_p = (line.strip() == "P") or (direction == "RX" and line.startswith("P "))
        if is_p and self.chk_filter_p.isChecked():
            return

        now_str = dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if direction == "TX":
            color = "#00E5FF" if not self.night_mode else "#FF6666"
            prefix = "&gt;&gt;"
        elif "ERR" in line:
            color = "#FF3D00" if not self.night_mode else "#FF2222"
            prefix = "&lt;&lt;"
        else:
            color = "#00E676" if not self.night_mode else "#FF9999"
            prefix = "&lt;&lt;"

        html = f"<span style='color: #888888;'>[{now_str}]</span> <b style='color: {color};'>{direction} {prefix}</b> <span style='color: {color};'>{line}</span>"
        QtCore.QMetaObject.invokeMethod(self, "_append_html", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(str, html))

    @QtCore.pyqtSlot(str)
    def _append_html(self, html: str) -> None:
        self.terminal.append(html)
        if self.chk_autoscroll.isChecked():
            sb = self.terminal.verticalScrollBar()
            sb.setValue(sb.maximum())
