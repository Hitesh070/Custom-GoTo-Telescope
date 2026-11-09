"""
theme.py
Design System & Modern Stylesheets for the Custom GoTo Telescope Mount Desktop App.
Includes Windows 11 Obsidian Dark Theme and Pure-Red Dark-Sky Night Vision Theme.
"""

from __future__ import annotations
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QWidget


# ==============================================================================
# WINDOWS 11 MODERN OBSIDIAN DARK THEME
# ==============================================================================

SCIENTIFIC_STYLE = """
QMainWindow, QDialog {
    background-color: #0b1018;
    color: #e7edf5;
}

QWidget {
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #d2d9e4;
    font-size: 12px;
}

/* Elevated Card Surfaces with Windows 11 Rounded Geometry */
QFrame.card {
    background-color: #111a26;
    border: 1px solid #263448;
    border-radius: 10px;
    padding: 8px;
}

QFrame.header-deck {
    background-color: #101722;
    border-bottom: 1px solid #27364a;
}

QLabel {
    color: #c9d1d9;
}

QLabel.title {
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.5px;
}

QLabel.subtitle {
    font-size: 11px;
    color: #8b949e;
}

QLabel.section-header {
    font-size: 12px;
    font-weight: 700;
    color: #69b9f5;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #27364a;
}

/* Precision Monospace Telemetry Typography */
QLabel.table-key {
    font-size: 12px;
    font-weight: 600;
    color: #8b949e;
    padding: 3px 0px;
}

QLabel.table-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    padding: 3px 0px;
}

QLabel.hero-label {
    font-size: 11px;
    font-weight: 700;
    color: #8b949e;
    text-transform: uppercase;
}

QLabel.hero-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
    color: #38bdf8;
}

QLabel.mono-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #ffffff;
}

QLabel.status-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 12px;
}

/* Interactive Buttons */
QPushButton {
    background-color: #192536;
    color: #d7e1ee;
    border: 1px solid #30435c;
    border-radius: 7px;
    padding: 7px 13px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #22334a;
    border-color: #5d8fbd;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #101925;
}

QPushButton:disabled {
    background-color: #121a24;
    color: #484f58;
    border-color: #21262d;
}

QPushButton.btn-primary {
    background-color: #1769aa;
    border-color: #3c9de0;
    color: #ffffff;
}

QPushButton[class="primary"] {
    background-color: #1769aa;
    border: 1px solid #3c9de0;
    color: #ffffff;
    font-weight: 700;
}

QPushButton[class="primary"]:hover {
    background-color: #2081c9;
    border-color: #78c5f5;
}

QPushButton[class="stop-btn"] {
    background-color: #8e2830;
    border: 1px solid #df5961;
    color: #ffffff;
    font-weight: 800;
}

QPushButton[class="stop-btn"]:hover {
    background-color: #b5343e;
    border-color: #ff8a8f;
}

QPushButton[class="sync-btn"] {
    background-color: #1769aa;
    border: 1px solid #3c9de0;
    color: #ffffff;
}

QPushButton.btn-primary:hover {
    background-color: #388bfd;
    border-color: #58a6ff;
}

QPushButton.btn-primary:pressed {
    background-color: #1158c7;
}

QPushButton.btn-danger {
    background-color: #b62324;
    border-color: #f85149;
    color: #ffffff;
    font-weight: 700;
}

QPushButton.btn-danger:hover {
    background-color: #da3633;
    border-color: #ff7b72;
}

QPushButton.btn-danger:pressed {
    background-color: #8e1519;
}

QPushButton.btn-success {
    background-color: #238636;
    border-color: #2ea043;
    color: #ffffff;
}

QPushButton.btn-success:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QPushButton.btn-action {
    background-color: #21262d;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 5px 10px;
}

QPushButton.btn-action:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #ffffff;
}

QPushButton.jog-btn {
    background-color: #1f2633;
    border: 1px solid #303e54;
    border-radius: 6px;
    color: #c9d1d9;
    font-weight: 700;
    font-size: 14px;
}

QPushButton.jog-btn:hover {
    background-color: #29354a;
    border-color: #38bdf8;
    color: #ffffff;
}

QPushButton.jog-btn:pressed {
    background-color: #151d2a;
    border-color: #0284c7;
}

/* Speed and Rate Pills */
QPushButton.pill-btn {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 4px 10px;
    font-size: 11px;
}

QPushButton.pill-btn:hover {
    background-color: #21262d;
    border-color: #58a6ff;
}

QPushButton.pill-btn:checked {
    background-color: #1f6feb;
    border-color: #58a6ff;
    color: #ffffff;
    font-weight: 700;
}

/* Inputs & Form Controls */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0b121c;
    color: #ffffff;
    border: 1px solid #2b3c52;
    border-radius: 7px;
    padding: 6px 9px;
    selection-background-color: #1f6feb;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #4ca9e6;
}

QComboBox {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #58a6ff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #dce2eb;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    outline: none;
}

QCheckBox, QRadioButton {
    color: #c9d1d9;
    spacing: 6px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #30363d;
    border-radius: 3px;
    background-color: #0d1117;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #1f6feb;
    border-color: #58a6ff;
}

/* Text Editors & Console */
QTextEdit, QPlainTextEdit {
    background-color: #090c10;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
    padding: 6px;
}

/* Modern Tab Widget */
QTabWidget::pane {
    border: 1px solid #2b3c52;
    border-radius: 8px;
    background-color: #111a26;
    top: -1px;
}

QTabBar::tab {
    background-color: #0b1018;
    color: #8b949e;
    border: 1px solid #2b3c52;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 3px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #111a26;
    color: #75c7fb;
    border-bottom: 2px solid #4ca9e6;
}

QTabBar::tab:hover:!selected {
    background-color: #161b22;
    color: #c9d1d9;
}

/* Table View */
QTableWidget, QTableView {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    gridline-color: #21262d;
    border-radius: 6px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    font-weight: 700;
    font-size: 11px;
    padding: 5px;
    border: none;
    border-bottom: 1px solid #30363d;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #0d1117;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #0d1117;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #30363d;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""


# ==============================================================================
# PURE-RED DARK-SKY NIGHT VISION THEME (ASTRONOMICAL PRESERVATION)
# ==============================================================================

NIGHT_VISION_STYLE = """
QMainWindow, QDialog {
    background-color: #000000;
    color: #ff3344;
}

QWidget {
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #ff3344;
    font-size: 12px;
}

QFrame.card {
    background-color: #080001;
    border: 1px solid #3c1018;
    border-radius: 10px;
    padding: 8px;
}

QFrame.header-deck {
    background-color: #050001;
    border-bottom: 1px solid #4a000a;
}

QLabel {
    color: #ff3344;
}

QLabel.title {
    font-size: 16px;
    font-weight: 700;
    color: #ff4d5a;
    letter-spacing: 0.5px;
}

QLabel.subtitle {
    font-size: 11px;
    color: #990014;
}

QLabel.section-header {
    font-size: 12px;
    font-weight: 700;
    color: #ff4d5a;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #4a000a;
}

QLabel.table-key {
    font-size: 12px;
    font-weight: 600;
    color: #990014;
    padding: 3px 0px;
}

QLabel.table-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #ff4d5a;
    padding: 3px 0px;
}

QLabel.hero-label {
    font-size: 11px;
    font-weight: 700;
    color: #990014;
    text-transform: uppercase;
}

QLabel.hero-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 700;
    color: #ff0022;
}

QLabel.mono-val {
    font-family: 'Consolas', 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #ff3344;
}

/* Buttons in Night Vision */
QPushButton {
    background-color: #150306;
    color: #ff3344;
    border: 1px solid #541722;
    border-radius: 7px;
    padding: 7px 13px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #260007;
    border-color: #ff0022;
    color: #ff4d5a;
}

QPushButton:pressed {
    background-color: #050001;
}

QPushButton:disabled {
    background-color: #050001;
    color: #4a000a;
    border-color: #1a0003;
}

QPushButton[class="primary"] {
    background-color: #4a0b14;
    border: 1px solid #9b2637;
    color: #ff8792;
    font-weight: 700;
}

QPushButton[class="primary"]:hover {
    background-color: #64101c;
    border-color: #e23c52;
    color: #ffffff;
}

QPushButton[class="stop-btn"] {
    background-color: #650812;
    border: 1px solid #e1293e;
    color: #ffffff;
    font-weight: 800;
}

QPushButton[class="stop-btn"]:hover {
    background-color: #8a0c1b;
    border-color: #ff5365;
}

QPushButton[class="sync-btn"] {
    background-color: #4a0b14;
    border: 1px solid #9b2637;
    color: #ff8792;
}

QPushButton.btn-primary {
    background-color: #4a000a;
    border-color: #800014;
    color: #ff6677;
}

QPushButton.btn-primary:hover {
    background-color: #660010;
    border-color: #ff0022;
    color: #ffffff;
}

QPushButton.btn-danger {
    background-color: #660000;
    border-color: #ff0000;
    color: #ffffff;
    font-weight: 700;
}

QPushButton.btn-danger:hover {
    background-color: #880000;
    border-color: #ff3333;
}

QPushButton.btn-success {
    background-color: #330006;
    border-color: #66000e;
    color: #ff4d5a;
}

QPushButton.btn-action {
    background-color: #120003;
    border: 1px solid #4a000a;
    color: #ff3344;
    padding: 5px 10px;
}

QPushButton.jog-btn {
    background-color: #150003;
    border: 1px solid #4a000a;
    border-radius: 6px;
    color: #ff3344;
    font-weight: 700;
    font-size: 14px;
}

QPushButton.jog-btn:hover {
    background-color: #260007;
    border-color: #ff0022;
    color: #ff4d5a;
}

QPushButton.jog-btn:pressed {
    background-color: #0a0002;
}

QPushButton.pill-btn {
    background-color: #0a0002;
    border: 1px solid #4a000a;
    border-radius: 12px;
    padding: 4px 10px;
    font-size: 11px;
}

QPushButton.pill-btn:checked {
    background-color: #660010;
    border-color: #ff0022;
    color: #ffffff;
    font-weight: 700;
}

QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #000000;
    color: #ff4d5a;
    border: 1px solid #4a000a;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #660010;
}

QComboBox {
    background-color: #0a0002;
    color: #ff3344;
    border: 1px solid #4a000a;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
}

QComboBox::down-arrow {
    border-top: 5px solid #ff0022;
}

QComboBox QAbstractItemView {
    background-color: #0a0002;
    color: #ff4d4d;
    border: 1px solid #4a000a;
    selection-background-color: #4a000a;
    selection-color: #ffffff;
    outline: none;
}

QCheckBox, QRadioButton {
    color: #ff3344;
}

QCheckBox::indicator, QRadioButton::indicator {
    border: 1px solid #4a000a;
    background-color: #000000;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #660010;
    border-color: #ff0022;
}

QTextEdit, QPlainTextEdit {
    background-color: #000000;
    color: #ff3344;
    border: 1px solid #4a000a;
    border-radius: 6px;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
}

QTabWidget::pane {
    border: 1px solid #4a000a;
    background-color: #0a0002;
}

QTabBar::tab {
    background-color: #000000;
    color: #990014;
    border: 1px solid #4a000a;
    border-bottom: none;
    padding: 7px 16px;
}

QTabBar::tab:selected {
    background-color: #0a0002;
    color: #ff0022;
    border-bottom: 2px solid #ff0022;
}

QTableWidget, QTableView {
    background-color: #000000;
    color: #ff3344;
    border: 1px solid #4a000a;
    gridline-color: #260006;
    selection-background-color: #4a000a;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #0a0002;
    color: #ff3344;
    border-bottom: 1px solid #4a000a;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #000000;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #4a000a;
    border-radius: 4px;
}
"""


def apply_theme_to_widget(widget: QWidget, night_mode: bool) -> None:
    """Applies the appropriate stylesheet and palette to any widget or dialog."""
    if night_mode:
        widget.setStyleSheet(NIGHT_VISION_STYLE)
    else:
        widget.setStyleSheet(SCIENTIFIC_STYLE)
