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

QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: #161b22;
    border-left: 1px solid #30363d;
    border-bottom: 1px solid #30363d;
    border-top-right-radius: 5px;
    width: 16px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #161b22;
    border-left: 1px solid #30363d;
    border-bottom-right-radius: 5px;
    width: 16px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #21262d;
}

QProgressBar {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    text-align: center;
    color: #e6edf3;
    font-weight: 600;
    font-size: 11px;
    min-height: 16px;
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 5px;
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

/* Observatory dashboard layer */
QWidget#appCanvas {
    background-color: #0a1018;
}

QFrame.header-deck {
    background-color: #0f1924;
    border: 1px solid #233446;
    border-radius: 14px;
}

QFrame.card {
    background-color: #101a25;
    border: 1px solid #253748;
    border-radius: 12px;
}

QLabel#brandMark {
    background-color: #12302f;
    color: #74e0ca;
    border: 1px solid #28645d;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 800;
}

QLabel.title {
    color: #f3f7fb;
    font-size: 18px;
    letter-spacing: 1px;
}

QLabel.subtitle, QLabel#eyebrow, QLabel#portLabel {
    color: #8fa2b5;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}

QFrame#connectionStrip {
    background-color: #0b131d;
    border: 1px solid #223244;
    border-radius: 10px;
}

QFrame#safetyBanner {
    background-color: #342512;
    border: 1px solid #72511f;
    border-radius: 10px;
}

QLabel#safetyTag {
    color: #ffd27a;
    background-color: #5a3d16;
    border: 1px solid #956720;
    border-radius: 8px;
    font-size: 9px;
    font-weight: 800;
    padding: 5px 8px;
}

QScrollArea#controlDock, QScrollArea#controlDock > QWidget,
QScrollArea#controlDock > QWidget > QWidget {
    background: transparent;
    border: none;
}

QLabel.section-header {
    color: #67cfbd;
    border-bottom: 1px solid #29433f;
    padding-bottom: 7px;
}

QLabel.hero-val {
    color: #70d7c3;
}

QLabel.table-val {
    font-size: 13px;
}

QTabWidget#telemetryTabs::pane {
    background-color: transparent;
    border: none;
}

QTabWidget#telemetryTabs QTabBar::tab {
    background-color: #0b131d;
    border: 1px solid #223244;
    border-radius: 8px;
    padding: 8px 13px;
    margin-right: 5px;
}

QTabWidget#telemetryTabs QTabBar::tab:selected {
    background-color: #12302f;
    border-color: #28645d;
    color: #76ddc8;
}

QPushButton {
    background-color: #172433;
    border: 1px solid #304357;
    border-radius: 8px;
    padding: 7px 11px;
}

QPushButton:hover {
    background-color: #203346;
    border-color: #4a8f8a;
}

QPushButton[class="primary"], QPushButton[class="sync-btn"] {
    background-color: #155d58;
    border: 1px solid #298b7e;
    color: #f2fffc;
}

QPushButton[class="primary"]:hover, QPushButton[class="sync-btn"]:hover {
    background-color: #1b766d;
    border-color: #50c5af;
}

QPushButton[class="stop-btn"] {
    background-color: #842d32;
    border: 1px solid #d15e62;
    border-radius: 9px;
    color: #ffffff;
    font-weight: 800;
}

QPushButton[class="stop-btn"]:hover {
    background-color: #a73a41;
    border-color: #ff898a;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0b131d;
    border: 1px solid #2a3d50;
    border-radius: 8px;
    padding: 6px 9px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #42a898;
}

QTextEdit, QPlainTextEdit {
    background-color: #080e15;
    border: 1px solid #223244;
    border-radius: 9px;
}

QFrame#navigationRail {
    background-color: #0e1721;
    border: 1px solid #223344;
    border-radius: 12px;
}

QLabel#navEyebrow, QLabel#metricKey {
    color: #8298ab;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
}

QPushButton[class="nav-button"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #aebdca;
    min-height: 34px;
    padding: 7px 10px;
    text-align: left;
}

QPushButton[class="nav-button"]:hover {
    background-color: #172635;
    border-color: #283e50;
    color: #edf6fb;
}

QPushButton[class="nav-button"]:checked {
    background-color: #17322f;
    border-color: #2d635b;
    color: #7be0cb;
    font-weight: 700;
}

QFrame#navDivider {
    border: none;
    border-top: 1px solid #263749;
    margin: 9px 2px;
}

QLabel#shortcutHint {
    color: #72869a;
    font-size: 10px;
    line-height: 1.6;
    padding: 8px;
}

QLabel#pageTitle {
    color: #eff5fa;
    font-size: 21px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: #8fa2b5;
    font-size: 11px;
}

QLabel#liveBadge {
    background-color: #12302c;
    border: 1px solid #286457;
    border-radius: 9px;
    color: #77dfc7;
    font-size: 9px;
    font-weight: 800;
    padding: 6px 10px;
}

QFrame#metricCard {
    background-color: #101a25;
    border: 1px solid #283b4d;
    border-radius: 10px;
}

QLabel#metricValue {
    font-size: 20px;
}

/* Full-screen mission console */
QWidget#appCanvas { background-color: #080f18; }
QFrame.header-deck {
    background-color: #0d1823;
    border: 1px solid #213648;
    border-radius: 11px;
}
QFrame#connectionStrip {
    background-color: #0a141e;
    border: 1px solid #1d3243;
    border-radius: 8px;
}
QFrame.card {
    background-color: #0e1924;
    border: 1px solid #203546;
    border-radius: 9px;
}
QLabel.title { font-family: 'Bahnschrift', 'Segoe UI Variable', 'Segoe UI'; font-size: 17px; letter-spacing: 1.1px; }
QLabel.subtitle { color: #8299ac; font-size: 9px; letter-spacing: 1.2px; }
QLabel.section-header {
    color: #78caff;
    font-size: 10px;
    letter-spacing: 1.1px;
    border-bottom: 1px solid #1d3a4d;
    padding-bottom: 5px;
}
QLabel#panelHeading { border-bottom: none; padding-bottom: 0; }
QLabel.table-key { color: #8298aa; font-size: 10px; font-weight: 600; }
QLabel.table-val { color: #e2edf5; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px; font-weight: 600; }
QLabel#brandMark { background: #102d39; color: #8ce2ff; border: 1px solid #1b6176; border-radius: 10px; }
QLabel#eyebrow, QLabel#portLabel { color: #83a0b5; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
QLabel#livePulse {
    background-color: #0e2e29;
    border: 1px solid #1c6355;
    border-radius: 9px;
    color: #73e1bd;
    font-size: 9px;
    font-weight: 800;
    padding: 6px 9px;
}
QLabel#safetyTag { background-color: #543716; border: 1px solid #9b6a2d; color: #ffd187; }
QFrame#safetyBanner { background-color: #2b2116; border: 1px solid #614621; border-radius: 8px; }
QPushButton {
    background-color: #142433;
    border: 1px solid #2a4356;
    border-radius: 6px;
    color: #d1e0ea;
    font-size: 10px;
    padding: 5px 8px;
}
QPushButton:hover { background-color: #1b3447; border-color: #4b92aa; }
QPushButton[class="primary"], QPushButton[class="sync-btn"] { background-color: #126257; border: 1px solid #269987; color: #effffb; }
QPushButton[class="primary"]:hover, QPushButton[class="sync-btn"]:hover { background-color: #197d70; border-color: #58d7bf; }
QPushButton[class="stop-btn"] { background-color: #8d303c; border: 1px solid #d15f68; border-radius: 7px; color: white; font-weight: 800; }
QPushButton[class="stop-btn"]:hover { background-color: #ad3d49; border-color: #ff9096; }
QPushButton.pill-btn { background-color: #101d29; border: 1px solid #263b4e; border-radius: 13px; padding: 3px 7px; font-size: 9px; }
QPushButton.pill-btn:checked { background-color: #173c52; border-color: #3d8ab0; color: #a3ddfa; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #09121b; border: 1px solid #294052; border-radius: 6px; padding: 4px 7px; }
QTextEdit, QPlainTextEdit { background-color: #070d14; border: 1px solid #1d3141; border-radius: 7px; }
QTabBar::tab:selected { color: #77cfff; border-bottom: 2px solid #58b9ef; }
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

QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: #1a0003;
    border-left: 1px solid #4a000a;
    border-bottom: 1px solid #4a000a;
    border-top-right-radius: 5px;
    width: 16px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #1a0003;
    border-left: 1px solid #4a000a;
    border-bottom-right-radius: 5px;
    width: 16px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #330006;
}

QProgressBar {
    background-color: #1a0003;
    border: 1px solid #55000a;
    border-radius: 6px;
    text-align: center;
    color: #ff3344;
    font-weight: 600;
    font-size: 11px;
    min-height: 16px;
}

QProgressBar::chunk {
    background-color: #880011;
    border-radius: 5px;
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

/* Observatory dashboard layer */
QWidget#appCanvas {
    background-color: #000000;
}

QFrame.header-deck {
    background-color: #050001;
    border: 1px solid #351018;
    border-radius: 14px;
}

QFrame.card {
    background-color: #080002;
    border: 1px solid #37121a;
    border-radius: 12px;
}

QLabel#brandMark {
    background-color: #190004;
    color: #ff6576;
    border: 1px solid #5c101c;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 800;
}

QLabel.title {
    color: #ff7884;
    font-size: 18px;
    letter-spacing: 1px;
}

QLabel.subtitle, QLabel#eyebrow, QLabel#portLabel {
    color: #8a3038;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}

QFrame#connectionStrip {
    background-color: #030001;
    border: 1px solid #351018;
    border-radius: 10px;
}

QFrame#safetyBanner {
    background-color: #180004;
    border: 1px solid #5d1018;
    border-radius: 10px;
}

QLabel#safetyTag {
    color: #ff8790;
    background-color: #37070f;
    border: 1px solid #721624;
    border-radius: 8px;
    font-size: 9px;
    font-weight: 800;
    padding: 5px 8px;
}

QScrollArea#controlDock, QScrollArea#controlDock > QWidget,
QScrollArea#controlDock > QWidget > QWidget {
    background: transparent;
    border: none;
}

QLabel.section-header {
    color: #ff4c5e;
    border-bottom: 1px solid #42111a;
    padding-bottom: 7px;
}

QLabel.hero-val {
    color: #ff334f;
}

QLabel.table-val {
    font-size: 13px;
}

QTabWidget#telemetryTabs::pane {
    background-color: transparent;
    border: none;
}

QTabWidget#telemetryTabs QTabBar::tab {
    background-color: #030001;
    border: 1px solid #351018;
    border-radius: 8px;
    padding: 8px 13px;
    margin-right: 5px;
}

QTabWidget#telemetryTabs QTabBar::tab:selected {
    background-color: #26070d;
    border-color: #7e1a29;
    color: #ff6576;
}

QPushButton {
    background-color: #120205;
    border: 1px solid #4c1720;
    border-radius: 8px;
    padding: 7px 11px;
}

QPushButton:hover {
    background-color: #26070d;
    border-color: #a32b3b;
}

QPushButton[class="primary"], QPushButton[class="sync-btn"] {
    background-color: #4c0914;
    border: 1px solid #9b2637;
    color: #ff9ba4;
}

QPushButton[class="primary"]:hover, QPushButton[class="sync-btn"]:hover {
    background-color: #690d1d;
    border-color: #e23c52;
    color: #ffffff;
}

QPushButton[class="stop-btn"] {
    background-color: #650812;
    border: 1px solid #e1293e;
    border-radius: 9px;
    color: #ffffff;
    font-weight: 800;
}

QPushButton[class="stop-btn"]:hover {
    background-color: #8a0c1b;
    border-color: #ff5365;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #030001;
    border: 1px solid #47141c;
    border-radius: 8px;
    padding: 6px 9px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #ad2638;
}

QTextEdit, QPlainTextEdit {
    background-color: #020001;
    border: 1px solid #351018;
    border-radius: 9px;
}

QFrame#navigationRail {
    background-color: #050001;
    border: 1px solid #351018;
    border-radius: 12px;
}

QLabel#navEyebrow, QLabel#metricKey {
    color: #8b343d;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
}

QPushButton[class="nav-button"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #b35b64;
    min-height: 34px;
    padding: 7px 10px;
    text-align: left;
}

QPushButton[class="nav-button"]:hover {
    background-color: #190308;
    border-color: #4e121b;
    color: #ff9aa3;
}

QPushButton[class="nav-button"]:checked {
    background-color: #27070d;
    border-color: #701724;
    color: #ff6c7c;
    font-weight: 700;
}

QFrame#navDivider {
    border: none;
    border-top: 1px solid #351018;
    margin: 9px 2px;
}

QLabel#shortcutHint {
    color: #71313a;
    font-size: 10px;
    line-height: 1.6;
    padding: 8px;
}

QLabel#pageTitle {
    color: #ffabb2;
    font-size: 21px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: #9a454d;
    font-size: 11px;
}

QLabel#liveBadge {
    background-color: #1c0308;
    border: 1px solid #641320;
    border-radius: 9px;
    color: #ff6576;
    font-size: 9px;
    font-weight: 800;
    padding: 6px 10px;
}

QFrame#metricCard {
    background-color: #080002;
    border: 1px solid #351018;
    border-radius: 10px;
}

QLabel#metricValue {
    font-size: 20px;
}

/* Full-screen night-vision mission console */
QWidget#appCanvas { background-color: #000000; }
QFrame.header-deck { background-color: #050001; border: 1px solid #351018; border-radius: 11px; }
QFrame#connectionStrip { background-color: #030001; border: 1px solid #351018; border-radius: 8px; }
QFrame.card { background-color: #080002; border: 1px solid #37121a; border-radius: 9px; }
QLabel.title { font-family: 'Bahnschrift', 'Segoe UI Variable', 'Segoe UI'; font-size: 17px; letter-spacing: 1.1px; color: #ff7884; }
QLabel.subtitle { color: #8a3038; font-size: 9px; letter-spacing: 1.2px; }
QLabel.section-header { color: #ff596a; font-size: 10px; letter-spacing: 1.1px; border-bottom: 1px solid #42111a; padding-bottom: 5px; }
QLabel#panelHeading { border-bottom: none; padding-bottom: 0; }
QLabel.table-key { color: #8b343d; font-size: 10px; font-weight: 600; }
QLabel.table-val { color: #ffb4bb; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px; font-weight: 600; }
QLabel#brandMark { background: #190004; color: #ff7884; border: 1px solid #5c101c; border-radius: 10px; }
QLabel#eyebrow, QLabel#portLabel { color: #8b343d; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
QLabel#livePulse { background-color: #190309; border: 1px solid #681524; border-radius: 9px; color: #ff6576; font-size: 9px; font-weight: 800; padding: 6px 9px; }
QLabel#safetyTag { background-color: #37070f; border: 1px solid #721624; color: #ff8790; }
QFrame#safetyBanner { background-color: #180004; border: 1px solid #5d1018; border-radius: 8px; }
QPushButton { background-color: #120205; border: 1px solid #4c1720; border-radius: 6px; color: #ffb4bb; font-size: 10px; padding: 5px 8px; }
QPushButton:hover { background-color: #26070d; border-color: #a32b3b; }
QPushButton[class="primary"], QPushButton[class="sync-btn"] { background-color: #4c0914; border: 1px solid #9b2637; color: #ff9ba4; }
QPushButton[class="primary"]:hover, QPushButton[class="sync-btn"]:hover { background-color: #690d1d; border-color: #e23c52; color: #ffffff; }
QPushButton[class="stop-btn"] { background-color: #650812; border: 1px solid #e1293e; border-radius: 7px; color: white; font-weight: 800; }
QPushButton[class="stop-btn"]:hover { background-color: #8a0c1b; border-color: #ff5365; }
QPushButton.pill-btn { background-color: #100205; border: 1px solid #47141c; border-radius: 13px; padding: 3px 7px; font-size: 9px; }
QPushButton.pill-btn:checked { background-color: #3b0710; border-color: #8e1d30; color: #ff7c89; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #030001; border: 1px solid #47141c; border-radius: 6px; padding: 4px 7px; }
QTextEdit, QPlainTextEdit { background-color: #020001; border: 1px solid #351018; border-radius: 7px; }
QTabBar::tab:selected { color: #ff6576; border-bottom: 2px solid #d23147; }
"""


def apply_theme_to_widget(widget: QWidget, night_mode: bool) -> None:
    """Applies the appropriate stylesheet and palette to any widget or dialog."""
    if night_mode:
        widget.setStyleSheet(NIGHT_VISION_STYLE)
    else:
        widget.setStyleSheet(SCIENTIFIC_STYLE)
