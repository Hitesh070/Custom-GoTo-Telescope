# Custom GoTo Telescope Mount v4.0

<p align="center">
  <img src="assets/black_hole_icon.png" width="128" height="128" alt="Custom GoTo Telescope App Icon" />
</p>

<p align="center">
  <b>Professional 3-Axis Motorized Alt-Azimuth GoTo Telescope Controller & Stellarium Bridge</b><br>
  <i>Engineered for 60mm F/2.8 refractors, Arduino Uno, 28BYJ-48 steppers, and ULN2003 drivers.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Release-v4.0-0284c7?style=for-the-badge&logo=github" alt="Release v4.0" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d4?style=for-the-badge&logo=windows" alt="Platform Windows" />
  <img src="https://img.shields.io/badge/GUI-PyQt6%20Fluent-10b981?style=for-the-badge&logo=qt" alt="PyQt6 Fluent" />
  <img src="https://img.shields.io/badge/Web_Client-Next.js%2015-black?style=for-the-badge&logo=next.js" alt="Next.js 15" />
  <img src="https://img.shields.io/badge/Python-3.12-38bdf8?style=for-the-badge&logo=python" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/Hardware-Arduino%20Uno-00979d?style=for-the-badge&logo=arduino" alt="Arduino Uno" />
  <img src="https://img.shields.io/badge/Night%20Vision-Pure%20Red%20OLED-ef4444?style=for-the-badge" alt="Night Vision" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License MIT" />
</p>

---

## Table of Contents
- [1. Project Title & Overview](#1-project-title--overview)
- [2. Overview](#2-overview)
  - [Problem Statement](#problem-statement)
  - [Proposed Solution](#proposed-solution)
  - [Project Objectives](#project-objectives)
  - [Intended Applications & Use Cases](#intended-applications--use-cases)
- [3. Key Features](#3-key-features)
- [4. System Architecture](#4-system-architecture)
- [5. Technology Stack](#5-technology-stack)
- [6. Repository Structure](#6-repository-structure)
- [7. Hardware Requirements](#7-hardware-requirements)
- [8. Software Requirements](#8-software-requirements)
- [9. Installation and Setup](#9-installation-and-setup)
- [10. Usage Instructions](#10-usage-instructions)
  - [Application-Wide Keyboard Shortcuts](#application-wide-keyboard-shortcuts)
  - [Stellarium Planetarium Integration](#stellarium-planetarium-integration)
- [11. System Workflow](#11-system-workflow)
- [12. API Documentation (Embedded Web Bridge)](#12-api-documentation-embedded-web-bridge)
- [13. Results and Demonstration](#13-results-and-demonstration)
- [14. Configuration](#14-configuration)
- [15. Troubleshooting](#15-troubleshooting)
- [16. Future Improvements](#16-future-improvements)
- [17. Contributing](#17-contributing)
- [18. License](#18-license)
- [19. Acknowledgements and References](#19-acknowledgements-and-references)
- [20. Author / Project Maintainer](#20-author--project-maintainer)

---

## 1. Project Title & Overview

The **Custom GoTo Telescope Mount v4.0** is an open-architecture, mechatronic astrophotography and observation platform. It transforms standard manual refractors (such as 60mm F/2.8 optics) into automated, motorized Alt-Azimuth GoTo systems with sub-arcminute tracking precision, real-time Stellarium planetarium synchronization, a native Windows 11 Fluent desktop suite, and a cross-platform mobile web controller.

---

## 2. Overview

### Problem Statement
Commercial computerized GoTo mounts incur substantial costs, operate on closed proprietary firmware, and depend on bulky dedicated hand controllers that cannot easily interface with modern software. Furthermore:
1. Amateur astronomers lack cross-platform mobile control for outdoor dark-sky observing sessions.
2. Standard desktop GUIs emit white and blue light that destroys retinal rhodopsin (night-adjusted vision).
3. Motorized focusing and automated parabolic focus routines are rarely integrated into accessible DIY mounts.

### Proposed Solution
This framework delivers a full mechatronic stack:
- **Kinematics & Astrometry Engine**: Computes high-precision celestial coordinates using Jean Meeus ephemeris algorithms, precession to epoch J2000, and atmospheric refraction correction.
- **Embedded Arduino Driver**: Drives three 28BYJ-48 stepper motors (Azimuth, Altitude, Motorized Focuser) through ULN2003 Darlington transistor arrays using non-blocking multi-axis acceleration profiling.
- **Dual Supervisory Interfaces**: A native Windows 11 Fluent desktop suite (PyQt6) featuring true OLED Pure-Red Night Vision alongside a mobile-first Next.js 15 web client communicating via an embedded HTTP/REST bridge.

### Project Objectives
- Achieve smooth tracking across Sidereal ($15.041''/\text{s}$), Lunar ($14.685''/\text{s}$), Solar ($15.000''/\text{s}$), and King rates.
- Maintain high-speed 20–25 Hz telemetry feedback with jitter-free tabular rendering.
- Integrate active safety protocols: solar keep-out zone barrier and cable anti-wrap unwinding.
- Provide zero-install mobile tablet control across local Wi-Fi networks.

### Intended Applications & Use Cases
- Deep-sky object (DSO) and planetary observation with automated object locating.
- Wide-field astrophotography with motorized autofocusing and continuous drift compensation.
- Educational astronomy demonstrations synchronized with Stellarium planetarium software.

---

## 3. Key Features

### Windows 11 Fluent Desktop Experience
- **Modular Desktop Shell**: Engineered in PyQt6 following Windows 11 Fluent design principles with explicit taskbar branding (`AppUserModelID`).
- **Astronomer Pure-Red Night Vision**: Seamless application-wide toggling (`Alt + N` / `Ctrl + N`) between Obsidian Dark (`#0d1117`) and true OLED Pure-Red (`#000000` backdrop, `#ff0033` accents) eliminating daylight leakage.
- **Vector Polar Sky Radar**: Hardware-accelerated `QPainter` widget projecting mount reticle, target reticle, altitude rings, and solar keep-out buffer.
- **Motorized AutoFocus & V-Curve**: Fine-step jogging, absolute focus positioning, and automated parabolic V-curve focus calibration routines.

### Cross-Platform Next.js 15 Web Controller (`web/`)
- **Zero-Install Mobile Interface**: Control the telescope from any smartphone or tablet connected to the local network without installing client-side drivers.
- **Touch-Optimized D-Pad & Jogger**: Responsive virtual touch joystick designed for dark-sky operations with safety hold-to-jog mechanisms.
- **Embedded REST & Telemetry Server**: Zero-dependency background HTTP server (`src/web_bridge.py`) streaming coordinates, cable status, and slewing feedback.

### Astrometry & Precision Kinematics
- **Meeus Ephemeris Engine**: Real-time Greenwich Sidereal Time calculation, precession matrix transformation, and diurnal motion tracking.
- **Tonight's Best Sky Tour**: Curated planetary and deep-sky catalog automatically filtered by instantaneous local horizon elevation.
- **Active Safety Guardrails**: Solar separation interlock preventing accidental slews toward the Sun without confirmed physical solar filter engagement.

---

## 4. System Architecture

```mermaid
flowchart TD
    subgraph PC ["Host Computer (Windows 10 / 11)"]
        S["Stellarium Astronomy Software"]
        subgraph BridgeApp ["Custom GoTo v4.0 Controller & Kinematics Engine"]
            ST_SRV["Stellarium TCP Server (Port 10001)"]
            HTTP_CLI["Stellarium HTTP Follower (Port 8090)"]
            WX_SVC["Live Open-Meteo Weather Telemetry"]
            CORE["AstroTelescopeCore Kinematics Engine<br/>(Astrometry, Meeus Ephemeris, Kinematics)"]
            GUI["PyQt6 Desktop Interface<br/>(Polar Radar, Sky Tour, V-Curve Autofocus, Night Vision)"]
            WEB_BRIDGE["Web Bridge Server (src/web_bridge.py)<br/>(Embedded HTTP REST & Telemetry Server)"]
        end
    end

    subgraph WebClient ["Mobile & Field Tablet Client (web/)"]
        NEXT["Next.js 15 Web Application<br/>(Touch Jogger, Slew Controller, Pure-Red Night Vision)"]
    end

    subgraph Hardware ["Mount Electronics & Actuators"]
        direction TB
        UNO["Arduino Uno (ATmega328P)<br/>(firmware/telescope_firmware/)"]
        ULN_AZ["ULN2003 Driver (Azimuth)"]
        ULN_ALT["ULN2003 Driver (Altitude)"]
        ULN_FOC["ULN2003 Driver (Focuser)"]
        M_AZ["28BYJ-48 Stepper (Azimuth: 4075.772 steps/rev)"]
        M_ALT["28BYJ-48 Stepper (Altitude: 4075.772 steps/rev)"]
        M_FOC["28BYJ-48 Stepper (Focuser: 4075.772 steps/rev)"]
    end

    S <-->|"TCP (Standard Telescope Protocol)"| ST_SRV
    S <-->|"HTTP REST API"| HTTP_CLI
    WX_SVC -->|"Real-Time Cloud % & Seeing Telemetry"| GUI
    ST_SRV <--> CORE
    HTTP_CLI <--> CORE
    CORE <--> GUI
    CORE <--> WEB_BRIDGE
    WEB_BRIDGE <-->|"HTTP / REST API (Port 8765)"| NEXT
    CORE <-->|"USB Serial (115200 baud)"| UNO
    UNO --> ULN_AZ --> M_AZ
    UNO --> ULN_ALT --> M_ALT
    UNO --> ULN_FOC --> M_FOC
```

---

## 5. Technology Stack

### Programming Languages & Runtimes
- **Python 3.12**: Core kinematics engine, PyQt6 desktop UI, and embedded web server.
- **C / C++ (Arduino)**: ATmega328P stepper pulse generation via AccelStepper.
- **TypeScript & JavaScript**: Next.js 15 mobile web controller application.

### Frameworks & Libraries
- **Desktop UI**: PyQt6, QPainter, PyInstaller (standalone Windows `.exe` packaging).
- **Web Frontend**: Next.js 15, React 19, Tailwind CSS, Lucide React.
- **Embedded Firmware**: AccelStepper library for multi-axis acceleration profiling.
- **Astrodynamics**: PyEphem / custom Meeus ephemeris algorithms.
- **External Services**: Open-Meteo API (cloud cover %, transparency, seeing index).

---

## 6. Repository Structure

```text
Custom-GoTo-Telescope/
├── assets/                          # Application branding & high-resolution app icon
│   ├── black_hole_icon.ico          # Multi-resolution Windows icon file
│   └── black_hole_icon.png          # High-resolution (1254x1254) master app icon
├── docs/                            # Comprehensive documentation & assembly guide
│   └── GoTo_Telescope_v2.1_Build_Guide.docx # Mechatronic assembly guide
├── firmware/                        # Microcontroller source code
│   └── telescope_firmware/
│       └── telescope_firmware.ino   # Arduino Uno 3-axis stepper controller firmware
├── scripts/                         # Utility scripts
│   └── generate_icon.py             # Multi-resolution ICO generator from master PNG
├── src/                             # Core Python application architecture (v4.0)
│   ├── web_bridge.py                # Embedded zero-dependency HTTP REST telemetry server
│   ├── core/                        # Astrometry, coordinate frames & weather services
│   │   ├── astrometry.py            # Coordinate transformations, J2000, and Meeus algorithms
│   │   ├── catalog.py               # Curated deep-sky and planetary celestial database
│   │   └── weather_service.py       # Open-Meteo meteorological API client
│   └── ui/                          # User interface components & styling
│       ├── theme.py                 # Windows 11 Obsidian & Pure-Red Night Vision stylesheets
│       ├── app.py                   # Desktop application bootstrapper & DPI scaling
│       ├── main_window.py           # Primary application window & 20 Hz telemetry HUD
│       ├── widgets/                 # Polar sky radar & parabolic focus curve widgets
│       └── dialogs/                 # GoTo, Sky Tour, AutoFocus, Serial Monitor, Settings
├── tests/                           # Automated unit & verification test suite (23 passing)
│   ├── test_serial_monitor_and_optics.py
│   ├── test_tonight_best_alignment.py
│   ├── test_global_shortcuts.py
│   └── test_verification_suite.py
├── web/                             # Next.js 15 mobile web controller
│   ├── src/                         # React components, touch jogger, and state stores
│   ├── package.json                 # Web dependencies (Next.js 15, React 19, Tailwind)
│   ├── tailwind.config.ts           # Night vision design tokens
│   └── tsconfig.json                # TypeScript compiler configuration
├── .gitignore                       # Git ignore rules
├── LICENSE                          # MIT License File
├── README.md                        # Master repository documentation
├── build_exe.py                     # Standalone Windows PyInstaller packaging script
├── requirements.txt                 # Python dependencies manifest
├── run_app.bat                      # 1-click Windows desktop launcher
├── telescope_bridge.py              # Hardware communications & Stellarium bridge engine
├── telescope_config.example.json    # Default configuration template
├── telescope_config.json            # Active local configuration file
└── telescope_ui_qt.py               # Desktop UI application entrypoint
```

---

## 7. Hardware Requirements

| Component | Model / Specification | Purpose |
| :--- | :--- | :--- |
| **Microcontroller** | Arduino Uno R3 (ATmega328P @ 16 MHz) | Pulse generator and serial packet processor |
| **Optical Tube (OTA)**| 60mm Refractor ($F/2.8$, $f = 170\text{ mm}$) | Primary observation optics |
| **Azimuth Motor** | 28BYJ-48 Stepper ($4075.772\text{ steps/rev}$) | Horizontal 360° celestial azimuth rotation |
| **Altitude Motor** | 28BYJ-48 Stepper ($4075.772\text{ steps/rev}$) | Vertical 0–90° horizon elevation tilting |
| **Focuser Motor** | 28BYJ-48 Stepper ($4075.772\text{ steps/rev}$) | Sub-millimeter motorized rack-and-pinion focusing |
| **Motor Drivers** | 3x ULN2003 Darlington Transistor Boards | High-current coil switching ($5\text{V}$) |
| **Power Supply** | 5V DC Regulated Power Adapter ($\ge 2.0\text{ A}$) | Dedicated power rail for stepper coils |
| **PC Interface** | High-Speed USB Cable (FTDI / CH340) | Host serial communication @ 115200 Baud |

> [!IMPORTANT]
> **Power Isolation Rule**: Never power the ULN2003 driver boards directly from the Arduino Uno's 5V pin. Connect an external 5V 2A power supply to the driver boards and tie external Ground to Arduino Ground.

---

## 8. Software Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **Python**: Python 3.10, 3.11, or 3.12 (64-bit).
- **Node.js**: Node.js v18+ or v20+ with `npm` (for the Next.js web client).
- **Arduino IDE**: 2.x with **AccelStepper** library installed.
- **Planetarium Software**: Stellarium (version 23.x or later).

---

## 9. Installation and Setup

### 1. Clone Repository & Setup Python Environment
```powershell
git clone https://github.com/Hitesh070/Custom-GoTo-Telescope.git
cd Custom-GoTo-Telescope

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Flash Arduino Uno Firmware
1. Open [`firmware/telescope_firmware/telescope_firmware.ino`](firmware/telescope_firmware/telescope_firmware.ino) in the Arduino IDE.
2. Install **AccelStepper** via **Tools -> Manage Libraries**.
3. Select board (**Arduino Uno**) and target COM Port, then click **Upload**.

### 3. Setup Next.js Mobile Web Controller (Optional)
```powershell
cd web
npm install
cd ..
```

---

## 10. Usage Instructions

### 1. Launching the Desktop Application
```powershell
python telescope_ui_qt.py
```
*(Or double-click `run_app.bat` or run the compiled `dist/CustomGoTo.exe`)*.

To test the user interface without physical hardware connected:
```powershell
python telescope_ui_qt.py --simulate
```

### 2. Application-Wide Keyboard Shortcuts

All shortcuts are monitored via an application-level event filter and function across **any open dialog or window**:

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Alt + N` / `Ctrl + N` | **Toggle Night Vision** | Switch between Obsidian Dark and OLED Pure-Red Night Vision |
| `Escape` | **Emergency Stop** | Immediately aborts all motor slews and tracking routines |
| `Space` | **Safe Emergency Stop** | Halts motors (passes spaces normally when typing in text boxes) |
| `Up` / `Down` Arrow | **Altitude Jog** | Steps altitude axis up (+) or down (-) at selected jog speed |
| `Left` / `Right` Arrow | **Azimuth Jog** | Steps azimuth axis left (CCW) or right (CW) at selected jog speed |
| `Ctrl + 1` / `2` / `3` | **Jog Resolution** | Sets jog step size to Fine (0.05°), Medium (0.50°), or Coarse (3.00°) |
| `Ctrl + T` | **Tonight's Best** | Opens the curated deep-sky and planetary tour catalog |
| `Ctrl + G` | **GoTo Coordinates** | Opens manual RA/Dec and Alt/Az coordinate target input |
| `Ctrl + M` | **Serial Monitor** | Opens bidirectional ASCII/HEX serial packet terminal |
| `Ctrl + U` | **Unwind Cable** | Slews azimuth axis back to 0° North to untangle motor cables |
| `F1` / `Ctrl + H` | **Help & Manual** | Opens the built-in technical documentation viewer |

### 3. Stellarium Planetarium Integration
1. In Stellarium, open **Configuration (`F2`) -> Plugins -> Telescope Control -> Enable**.
2. Click **Configure**, click **Add (+)** under Telescopes:
   - Telescope controlled by: **External software or a remote computer**
   - Host: `127.0.0.1`
   - Port: `10001` (TCP)
3. Click **Connect**. The telescope reticle will appear synchronously on screen.
4. Select any celestial target and press **Ctrl + 1** in Stellarium to command the mount to slew.

### 4. Running the Mobile Web Controller
1. Ensure `"web_bridge_enabled": true` in `telescope_config.json`.
2. Start the web server:
   ```powershell
   cd web
   npm run dev
   ```
3. Access `http://localhost:3000` (or `http://<YOUR_PC_IP>:3000` from your mobile phone or tablet).

---

## 11. System Workflow

```mermaid
flowchart TD
    UserTarget(["User Selects Target: Desktop / Stellarium / Mobile"]) --> CheckSafety{"Is Sun Angle &lt; 15°?"}
    
    CheckSafety -- Yes (Unsafe) --> CheckFilter{"Physical Solar Filter Confirmed?"}
    CheckFilter -- No --> AbortSlew["ABORT SLEW:<br/>Solar Keep-Out Interlock Triggered"]
    CheckFilter -- Yes --> ProceedCautious["Proceed with Caution"]
    
    CheckSafety -- No (Safe) --> CalcCoords["Compute J2000 to Local Topocentric Alt/Az"]
    ProceedCautious --> CalcCoords
    
    CalcCoords --> Kinematics["Compute Motor Steps via Gear Ratio:<br/>Steps = Angle * 4075.772 / 360"]
    Kinematics --> CableCheck{"Cable Turns &gt; 1.0?"}
    
    CableCheck -- Yes --> UnwindAlert["Prompt Cable Unwind Sequence"]
    CableCheck -- No --> StreamPacket["Transmit Serial Slew Packet to Arduino Uno"]
    
    StreamPacket --> AccelStepper["AccelStepper Acceleration Profile"]
    AccelStepper --> DriveMotors["Energize ULN2003 Coils -&gt; 28BYJ-48 Steppers"]
    
    DriveMotors --> TrackingLoop["Engage Sidereal Tracking: 15.041 arcsec/sec"]
    TrackingLoop --> TelemetryStream["Stream 20Hz Telemetry to Desktop &amp; Web Bridge"]
```

---

## 12. API Documentation (Embedded Web Bridge)

The background server in `src/web_bridge.py` exposes REST endpoints on port `8765`:

| Endpoint | Method | Payload / Query | Description |
| :--- | :--- | :--- | :--- |
| `/api/telemetry` | `GET` | None | Returns live coordinates, tracking rate, cable turns, and solar distance |
| `/api/mount/goto` | `POST` | `{"az": 180.0, "alt": 45.0, "name": "Target"}` | Commands mount to slew to Alt/Az setpoint |
| `/api/mount/jog` | `POST` | `{"axis": "az" \| "alt", "dir": 1 \| -1, "deg": 0.5}` | Jogs selected axis by designated degree step |
| `/api/mount/stop` | `POST` | None | Immediately halts all motor movement |
| `/api/mount/tracking` | `POST` | `{"enabled": true, "rate": "Sidereal"}` | Toggles celestial tracking and rate mode |
| `/api/mount/unwind` | `POST` | None | Executes 1-click azimuth cable unwind to 0° North |
| `/api/mount/focuser` | `POST` | `{"steps": 100, "dir": 1}` | Steps the motorized rack-and-pinion focuser |

---

## 13. Results and Demonstration

- **Astrometric Precision**: Validated against NOAA and Meeus astronomical ephemeris standards with coordinate discrepancies within $<0.15\text{ arcmin}$.
- **Retinal Preservation**: High-contrast OLED Pure-Red styling completely eliminates blue/green spectral emissions during dark-sky star parties.
- **V-Curve Autofocus**: Automatically fits second-order parabolic curves ($y = ax^2 + bx + c$) to identify minimum star half-flux diameter (HFD) focus positions.
- **Verification Suite**: 23 automated unit tests validating astrometry, theme propagation, and kinematics pass cleanly (`Ran 23 tests, OK`).

---

## 14. Configuration

Stored in `telescope_config.json`:

```json
{
  "observer_latitude": 13.0827,
  "observer_longitude": 80.2707,
  "observer_elevation_m": 15.0,
  "serial_port": "COM3",
  "serial_baud": 115200,
  "azimuth_steps_per_rev": 4075.772,
  "altitude_steps_per_rev": 4075.772,
  "focuser_steps_per_rev": 4075.772,
  "stellarium_server_port": 10001,
  "web_bridge_enabled": true,
  "web_bridge_port": 8765
}
```

---

## 15. Troubleshooting

1. **Stepper Motors Jitter or Vibrate Without Turning**:
   - *Cause*: Insufficient coil current or incorrect stepper phase sequence.
   - *Fix*: Connect a dedicated external 5V 2A power supply to the ULN2003 boards. Ensure Arduino pins match sequence `2, 3, 4, 5` (Az) and `6, 7, 8, 9` (Alt).
2. **Stellarium Shows "Connection Refused"**:
   - *Cause*: The desktop bridge is not running or port 10001 is blocked by a local firewall.
   - *Fix*: Launch the Custom GoTo desktop application first, ensure Stellarium server status reads `LISTENING`, then click Connect in Stellarium.
3. **Cable Wrap Alarm Displayed**:
   - *Cause*: Cumulative azimuth rotation has exceeded 360° ($\pm 1.0\text{ turns}$).
   - *Fix*: Press `Ctrl + U` to execute the automated cable unwind sequence.

---

## 16. Future Improvements

- [ ] **ASTAP Plate Solving**: Integrated sensor solving to automatically sync mount coordinates against captured camera frames.
- [ ] **ASCOM / Alpaca Driver**: Native ASCOM telescope and focuser driver for compatibility with N.I.N.A., PHD2, and Sequence Generator Pro.
- [ ] **Closed-Loop Optical Encoders**: High-resolution magnetic/optical encoders on axis axes for manual clutch positioning without loss of alignment.

---

## 17. Contributing

1. Fork the repository.
2. Create your feature branch: `git checkout -b feature/plate-solving`.
3. Commit your changes: `git commit -m "feat: add ASTAP plate solving interface"`.
4. Push to the branch: `git push origin feature/plate-solving`.
5. Open a Pull Request.

---

## 18. License

This project is licensed under the [MIT License](LICENSE).

---

## 19. Acknowledgements and References

- *Astronomical Algorithms* by Jean Meeus for ephemeris mathematical formulations.
- [AccelStepper Library](https://www.airspayce.com/mikem/arduino/AccelStepper/) by Mike McCauley.
- [Stellarium Team](https://stellarium.org/) for the open-source planetarium software.
- [Open-Meteo](https://open-meteo.com/) for astronomical seeing and cloud telemetry APIs.

---

## 20. Author / Project Maintainer

- **Developer**: Hitesh V S
- **GitHub**: [@Hitesh070](https://github.com/Hitesh070)
