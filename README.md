# Custom GoTo Telescope Mount

A 3-axis Alt-Az motorized telescope GoTo mount controller with motorized focusing, built using an **Arduino Uno**, **28BYJ-48 5V stepper motors**, **ULN2003 drivers**, and a **Python Bridge** interfacing directly with **Stellarium**.

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
* **Limit/Home Switches:** Optional physical switches on A1 (Alt) and A2 (Az) with internal pullups.

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

## Features

- **Stellarium Integration:** Native implementation of the Stellarium Telescope Server binary protocol. Select any star/planet in Stellarium and click `Ctrl+1` (or "Current object") to slew.
- **Accurate Coordinate Transformation:** Real-time celestial coordinate conversions (RA/Dec JNow to Topocentric Alt/Az) using local sidereal time and location coordinates.
- **Smooth Motion Profiles:** Uses `AccelStepper` with tuned trapezoidal acceleration to prevent stalling and mechanical jerks.
- **Safety Limits & Sun Keep-out:**
  - Altitude bounds checking (0° to 85° soft limits).
  - Software azimuth limit stops.
  - Active Sun keepout radius protection (refuses slews within keepout angle).
- **Software Backlash Compensation:** Configurable backlash correction steps applied automatically upon axis direction reversals.
- **Motor Idle Power Saving:** Automatic coil shutoff on idle to keep motors and drivers cool.

---

## Getting Started

### 1. Arduino Firmware
1. Open [`telescope_firmware.ino`](telescope_firmware.ino) in the Arduino IDE.
2. Install the **AccelStepper** library (via Library Manager).
3. Connect the Arduino Uno over USB, select the COM port, and click **Upload**.

### 2. Python Bridge Setup
1. Ensure Python 3.8+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Edit [`telescope_config.json`](telescope_config.json) to set your local geographic coordinates:
   ```json
   {
     "latitude_deg": 12.84,
     "longitude_deg": 80.15,
     "serial_port": "COM3"
   }
   ```
4. Run the bridge:
   ```bash
   python telescope_bridge.py
   ```
   *(Add `--simulate` to run and test without physical hardware attached).*

### 3. Stellarium Setup
1. Open Stellarium and go to **Configuration (`F2`) -> Plugins -> Telescope Control -> Enable**.
2. Under Telescopes, click **Add (+)**:
   - Telescope controlled by: **External software or a remote computer**
   - Host: `127.0.0.1`
   - Port: `10001`
3. Click **Connect**. Your telescope reticle will appear on screen!

---

## Documentation
* Detailed build guides, mechanical schematics, and calibration instructions can be found in the [`Documentation/`](Documentation/) directory.
