"""
app.py
Application bootstrapper, high-DPI scaling configuration, Windows taskbar icon registration,
and main execution loop.
"""

from __future__ import annotations
import sys
import os
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.ui.main_window import AstroTelescopeWindow
try:
    from telescope_bridge import BridgeCore, StellariumServer, Config
except ImportError:
    BridgeCore = None
    StellariumServer = None
    Config = None


def launch_app(simulate: bool = False, config_path: str = "telescope_config.json") -> None:
    """Initializes and runs the Custom GoTo Telescope Controller application."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("astro.goto.telescope.controller.v3")
        except Exception:
            pass

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setApplicationName("Custom GoTo")

    # Set window icon if available
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "black_hole_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    cfg = Config(config_path) if Config else {}
    if simulate:
        cfg["simulate"] = True

    core = None
    stellarium_server = None
    if BridgeCore:
        core = BridgeCore(config=cfg)
        core.start_tracking_thread()

    if StellariumServer and core:
        stellarium_server = StellariumServer(
            host=cfg.get("stellarium_host", "127.0.0.1"),
            port=int(cfg.get("stellarium_port", 10001)),
            core=core
        )
        stellarium_server.start()

    window = AstroTelescopeWindow(core=core, stellarium=stellarium_server, config=cfg)
    window.show()

    if cfg.get("simulate", False) and core:
        core.connect(simulate=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    sim = "--simulate" in sys.argv
    launch_app(simulate=sim)
