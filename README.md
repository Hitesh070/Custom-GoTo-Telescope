# Custom GoTo Telescope Mount v3.0

A complete 3-axis Alt-Az motorized telescope GoTo mount controller with motorized focusing, built using an **Arduino Uno**, **28BYJ-48 5V stepper motors**, **ULN2003 drivers**, and a **Python Bridge** interfacing directly with **Stellarium Desktop**.

---

## Architecture Overview

```
+---------------------+           TCP (Port 10001)           +---------------------+
|                     | -----------------------------------> |                     |
|  Stellarium Desktop |   Stellarium Telescope Protocol      | telescope_bridge.py |
|                     | <----------------------------------- |                     |
+---------------------+                                      +----------+----------+
                                                                        |
                                                           USB Serial   | 115200 Baud
                                                           ASCII Cmds   v
                                                             +---------------------+
                                                             |   Arduino Uno MCU   |
                                                             | (firmware.ino)      |
                                                             +----------+----------+
                                                                        |
                                                    +-------------------+-------------------+
                                                    |                   |                   |
                                                    v                   v                   v
                                                Azimuth             Altitude             Focus
                                              (28BYJ-48)          (28BYJ-48)          (28BYJ-48)
                                              + ULN2003           + ULN2003           + ULN2003
```

---

## Hardware & Wiring

* **Microcontroller:** Arduino Uno (ATmega328P)
* **Motors:** 3x 28BYJ-48 5V Unipolar Stepper Motors (Azimuth, Altitude, Focus)
* **Motor Drivers:** 3x ULN2003 Darlington Transistor Arrays
* **Limit/Home Switches:** Microswitches on A1 (Alt) and A2 (Az) with internal pullups.

### Arduino Pinout

| Function | Arduino Pins | Mode / Notes |
| :--- | :--- | :--- |
| **Azimuth Motor** | D2, D3, D4, D5 | AccelStepper `HALF4WIRE` (Pins 2, 4, 3, 5) |
| **Altitude Motor** | D6, D7, D8, D9 | AccelStepper `HALF4WIRE` (Pins 6, 8, 7, 9) |
| **Focus Motor** | D10, D11, D12, A0 | AccelStepper `HALF4WIRE` (Pins 10, 12, 11, A0) |
| **Alt Home Switch** | A1 | `INPUT_PULLUP`, Active LOW (Pressed = GND) |
| **Az Home Switch** | A2 | `INPUT_PULLUP`, Active LOW (Pressed = GND) |
| **Serial Comms** | D0 (RX), D1 (TX) | USB Serial at 115200 baud |

> **Power Note:** Always power the ULN2003 driver boards with a dedicated external **5V (2A+) power supply** rather than drawing power from the Arduino's 5V pin. Tie external ground and Arduino ground together.

---

## AstroGoTo v3.0 Features & Enhancements

Version 3.0 delivers advanced astrometric precision and smarter kinematics:

* **Atmospheric Refraction Correction:** Incorporates standard Saemundsson (1986) & Bennett (1982) refraction modeling with barometric pressure and temperature scaling, alongside a 5-pass fixed-point numerical inverter (< 0.0001 arcsec error). Objects near the horizon (where refraction can lift starlight by up to $0.5^\circ$) are targeted with sub-arcsecond fidelity.
* **Multi-Rate Astronomical Kinematics:** Selectable tracking rates directly from the UI:
  * **Sidereal Rate ($1.000\times$, $15.041^{\prime\prime}/\text{s}$):** Standard celestial rate for stars, nebulae, and deep sky targets.
  * **Lunar Rate ($0.9635\times$, $14.492^{\prime\prime}/\text{s}$):** Compensates for the Moon's eastward orbital motion ($\approx 0.549^\circ/\text{hr}$), keeping the Moon centered indefinitely in high-power eyepieces.
  * **Solar Rate ($0.9973\times$, $15.000^{\prime\prime}/\text{s}$):** Solar diurnal rate for Sun tracking with certified solar filter.
  * **King Rate:** Refraction-adjusted sidereal tracking rate accounting for the altitude refraction gradient.
* **Cable-Wrap Prevention & Shortest-Path Slew Engine:**
  * Tracks cumulative signed azimuth turns from $0^\circ$ True North.
  * Shortest-path route planning evaluates legal branches within $[-200^\circ, +200^\circ]$, favoring angles that relieve cable twist.
  * Real-time UI cable strain indicator and one-click **Unwind (0°)** button to safely untangle cables.
* **Dynamic Backlash Fast-Takeup:** Automatically accounts for mechanical slop on direction reversals so tracking and meridian crossings never lag.
* **Motorized Auto-Focus Routine (Parabolic V-Curve):** Automated star focus sweep measuring star contrast/FWHM and parking the drawtube at the critical focus zone (CFZ).
* **Predictive Time-of-Flight Intercept:** Fixed-point contraction mapping arrival-time prediction eliminates the classic 15–20 arcminute slew lag on long hops.
* **Dynamic Satellite Tracking:** Continuous velocity-lead feedforward tracking of the ISS and satellites via Stellarium Remote Control API (Port 8090).
* **Enlarged Polar Celestial Radar:** Real-time visual celestial sphere displaying physical telescope pointing, active target reticle, Sun danger keep-out zone, and compass bearings.
* **Standalone Windows Executable:** Single-file `dist/AstroGoTo.exe` with embedded high-resolution black hole icon and assets.

---

## Getting Started

### 1. Arduino Firmware
1. Open [`telescope_firmware.ino`](telescope_firmware.ino) in the Arduino IDE.
2. Install the **AccelStepper** library (via Library Manager).
3. Connect the Arduino Uno over USB, select the COM port, and click **Upload**.

### 2. Running AstroGoTo v3.0
Download the standalone executable from [GitHub Releases](https://github.com/Hitesh070/Custom-GoTo-Telescope/releases), or run from source:
```bash
python telescope_ui_qt.py
```
*(Or double-click `run_app.bat` or launch `dist/AstroGoTo.exe`)*.

To run the bridge in headless mode (console-only with Tkinter fallback via `--tk`):
```bash
python telescope_bridge.py
```
*(Add `--simulate` to test without physical hardware attached; run `--selftest` to execute the automated verification suite).*

### 3. Stellarium Setup
1. Open Stellarium and go to **Configuration (`F2`) -> Plugins -> Telescope Control -> Enable**.
2. Under Telescopes, click **Add (+)**:
   - Telescope controlled by: **External software or a remote computer**
   - Host: `127.0.0.1`
   - Port: `10001`
3. Click **Connect**. Your telescope reticle will appear on screen!
4. Select any celestial object and press **Ctrl + 1** to slew.

---

## Verification Suite
The codebase includes a comprehensive 16-point verification suite:
```bash
python telescope_bridge.py --selftest
```
All 16 astrometric and kinematics tests pass cleanly out of the box.
