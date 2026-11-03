"""
build_exe.py
Build script to compile AstroGoTo standalone Windows .exe with Black Hole icon
"""

import os
import subprocess
import sys

def build():
    print("=" * 60)
    print("Building AstroGoTo Standalone Executable")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AstroGoTo",
        "--onefile",
        "--windowed",
        "--icon=assets/black_hole_icon.ico",
        "--add-data=assets;assets",
        "--add-data=telescope_config.example.json;.",
        "--clean",
        "telescope_ui_qt.py"
    ]

    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("Executable located at: dist/AstroGoTo.exe")
        print("=" * 60)
    else:
        print("\nBuild failed with exit code:", res.returncode)

if __name__ == "__main__":
    build()
