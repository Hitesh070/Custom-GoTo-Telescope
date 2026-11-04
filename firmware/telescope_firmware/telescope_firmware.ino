/*
  telescope_firmware.ino
  3-Axis Alt-Az GoTo Telescope Mount Controller with Motorised Focus
  Hardware: Arduino Uno (ATmega328P), 3x 28BYJ-48 5V Steppers with ULN2003 drivers.
  
  Pin Assignments:
    Azimuth:  IN1=D2, IN2=D3, IN3=D4, IN4=D5  -> AccelStepper(HALF4WIRE, 2, 4, 3, 5)
    Altitude: IN1=D6, IN2=D7, IN3=D8, IN4=D9  -> AccelStepper(HALF4WIRE, 6, 8, 7, 9)
    Focus:    IN1=D10, IN2=D11, IN3=D12, IN4=A0 -> AccelStepper(HALF4WIRE, 10, 12, 11, A0)
    Altitude Home Switch: A1 (INPUT_PULLUP, pressed = LOW)
    Azimuth Home Switch:  A2 (INPUT_PULLUP, pressed = LOW)
    USB Serial: D0/D1 at 115200 baud. D13 unused.
*/

#include <AccelStepper.h>

// =============================================================================
// TUNABLES AND CONSTANTS
// =============================================================================

// Default speeds and accelerations (steps/s and steps/s^2)
const float AZ_MAX_SPEED_DEFAULT    = 226.0f;
const float ALT_MAX_SPEED_DEFAULT   = 226.0f;
const float FOC_MAX_SPEED_DEFAULT   = 300.0f;

const float AZ_ACCEL_DEFAULT        = 100.0f;
const float ALT_ACCEL_DEFAULT       = 100.0f;
const float FOC_ACCEL_DEFAULT       = 150.0f;

// Calibration scale (used ONLY to compute boot default limits; PC overrides with L command)
const float STEPS_PER_DEG_AZ        = 113.22f;
const float STEPS_PER_DEG_ALT       = 113.22f;

// Default soft limits in logical steps (computed at boot)
// Azimuth default +/-200 deg -> round(200 * 113.22) = 22644
// Altitude default 0..85 deg -> round(85 * 113.22) = 9624
const long DEFAULT_AZ_LIMIT_MIN     = -22644L;
const long DEFAULT_AZ_LIMIT_MAX     =  22644L;
const long DEFAULT_ALT_LIMIT_MIN    =      0L;
const long DEFAULT_ALT_LIMIT_MAX    =   9624L;

// Focus absolute travel limit (-6000 .. +6000 relative to power-up position)
const long FOC_LIMIT_STEPS          = 6000L;

// Homing parameters
const float HOME_SPEED              = 250.0f;
const long  HOME_MAX_STEPS_ALT      = 30000L;
const long  HOME_MAX_STEPS_AZ       = 100000L;
const int   HOME_DIR_ALT            = -1;     // toward switch at 0 deg (negative direction)
const int   HOME_DIR_AZ             = -1;     // negative direction
const long  HOME_CLEAR_STEPS        = 2000L;  // max steps to back off an already-pressed switch
const uint8_t HOME_DEBOUNCE_COUNT   = 5;      // consecutive loop readings required for trigger

// Watchdog and power management
const unsigned long SERIAL_WATCHDOG_MS    = 5000UL;   // stop motors if serial silent for 5s while moving
const unsigned long IDLE_DISABLE_AZ_MS   = 20000UL;  // disable Az coils after 20s idle (0 to disable)
const unsigned long IDLE_DISABLE_ALT_MS  = 0UL;      // off by default for Alt to prevent optical tube sag on unbalanced OTA

// Home switch pin definitions
const uint8_t PIN_ALT_HOME = A1;
const uint8_t PIN_AZ_HOME  = A2;

// =============================================================================
// STEPPER MOTOR INSTANCES
// =============================================================================

// AccelStepper HALF4WIRE constructor requires pin order (IN1, IN3, IN2, IN4)
AccelStepper azStepper(AccelStepper::HALF4WIRE, 2, 4, 3, 5);
AccelStepper altStepper(AccelStepper::HALF4WIRE, 6, 8, 7, 9);
AccelStepper focStepper(AccelStepper::HALF4WIRE, 10, 12, 11, A0);

// =============================================================================
// STATE VARIABLES
// =============================================================================

// Backlash compensation and logical position tracking (Section 5.2)
int8_t  azLastDir       = -1;
long    azComp          = 0;
long    azBacklash      = 0;

int8_t  altLastDir      = -1;
long    altComp         = 0;
long    altBacklash     = 0;

// Dynamic soft limits (set by L command)
long    azLimitMin      = DEFAULT_AZ_LIMIT_MIN;
long    azLimitMax      = DEFAULT_AZ_LIMIT_MAX;
long    altLimitMin     = DEFAULT_ALT_LIMIT_MIN;
long    altLimitMax     = DEFAULT_ALT_LIMIT_MAX;

// Configured maximum speeds for coordinated multi-axis constant velocity
float   azConfiguredMaxSpeed  = AZ_MAX_SPEED_DEFAULT;
float   altConfiguredMaxSpeed = ALT_MAX_SPEED_DEFAULT;

// Telemetry status
uint8_t homedBits       = 0; // bit 0 = Altitude homed, bit 1 = Azimuth homed

// Power management state
bool          azOutputsEnabled   = true;
bool          altOutputsEnabled  = true;
bool          focOutputsEnabled  = false;
unsigned long azIdleStartTime    = 0;
unsigned long altIdleStartTime   = 0;

// Watchdog state
unsigned long lastSerialRxTime   = 0;
bool          watchdogTriggered  = false;

// Homing state machine
enum HomingAxis { HOME_NONE = 0, HOME_ALT, HOME_AZ };
enum HomingState { HOMING_IDLE = 0, HOMING_CLEARING, HOMING_APPROACHING };

HomingAxis   homingAxis          = HOME_NONE;
HomingState  homingState         = HOMING_IDLE;
long         homingStartPos      = 0;
uint8_t      homingDebounce      = 0;
uint8_t      homingClearDebounce = 0;

// Serial reception buffer
char    rxBuf[64];
uint8_t rxIndex    = 0;
bool    rxOverflow = false;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

// Returns the logical position of an axis
inline long getLogicalAz() {
  return azStepper.currentPosition() - azComp;
}

inline long getLogicalAlt() {
  return altStepper.currentPosition() - altComp;
}

// Ensure motor coils are energized before starting motion
void enableAzOutputs() {
  if (!azOutputsEnabled) {
    azStepper.enableOutputs();
    azOutputsEnabled = true;
  }
  azIdleStartTime = 0;
}

void enableAltOutputs() {
  if (!altOutputsEnabled) {
    altStepper.enableOutputs();
    altOutputsEnabled = true;
  }
  altIdleStartTime = 0;
}

// Emergency stop for all axes
void emergencyStop() {
  azStepper.setCurrentPosition(azStepper.currentPosition());
  altStepper.setCurrentPosition(altStepper.currentPosition());
  focStepper.setCurrentPosition(focStepper.currentPosition());
  focStepper.disableOutputs();
  focOutputsEnabled = false;

  homingAxis = HOME_NONE;
  homingState = HOMING_IDLE;
}

// Parse signed long from string with strict pointer advancement
bool parseNextLong(char* &p, long &outVal) {
  while (*p == ' ') p++;
  if (*p == '\0') return false;
  char* endPtr = nullptr;
  outVal = strtol(p, &endPtr, 10);
  if (endPtr == p) return false;
  p = endPtr;
  return true;
}

// =============================================================================
// COMMAND PROCESSOR
// =============================================================================

void processCommand(char* line) {
  while (*line == ' ') line++;
  if (*line == '\0') return;

  char cmd = *line++;

  switch (cmd) {
    // -------------------------------------------------------------------------
    // G <az> <alt> : Move azimuth and altitude to logical absolute step targets
    // -------------------------------------------------------------------------
    case 'G': {
      long targetAz = 0, targetAlt = 0;
      if (!parseNextLong(line, targetAz) || !parseNextLong(line, targetAlt)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (homingAxis != HOME_NONE) {
        Serial.println(F("ERR BUSY"));
        return;
      }

      if (targetAz < azLimitMin || targetAz > azLimitMax ||
          targetAlt < altLimitMin || targetAlt > altLimitMax) {
        Serial.println(F("ERR LIMIT"));
        return;
      }

      enableAzOutputs();
      enableAltOutputs();

      // Azimuth backlash and move calculation (Section 5.2)
      long curAzLog = getLogicalAz();
      int8_t newDirAz = (targetAz > curAzLog) ? +1 : ((targetAz < curAzLog) ? -1 : azLastDir);
      azLastDir = newDirAz;
      azComp = (azLastDir > 0) ? azBacklash : 0;

      // Altitude backlash and move calculation (Section 5.2)
      long curAltLog = getLogicalAlt();
      int8_t newDirAlt = (targetAlt > curAltLog) ? +1 : ((targetAlt < curAltLog) ? -1 : altLastDir);
      altLastDir = newDirAlt;
      altComp = (altLastDir > 0) ? altBacklash : 0;

      // Coordinated constant-velocity multi-axis vector scaling
      long distAz = labs((targetAz + azComp) - azStepper.currentPosition());
      long distAlt = labs((targetAlt + altComp) - altStepper.currentPosition());
      long distMax = (distAz > distAlt) ? distAz : distAlt;

      if (distMax > 0) {
        float speedAz = azConfiguredMaxSpeed * ((float)distAz / (float)distMax);
        float speedAlt = altConfiguredMaxSpeed * ((float)distAlt / (float)distMax);
        azStepper.setMaxSpeed((speedAz < 10.0f) ? 10.0f : speedAz);
        altStepper.setMaxSpeed((speedAlt < 10.0f) ? 10.0f : speedAlt);
      } else {
        azStepper.setMaxSpeed(azConfiguredMaxSpeed);
        altStepper.setMaxSpeed(altConfiguredMaxSpeed);
      }

      azStepper.moveTo(targetAz + azComp);
      altStepper.moveTo(targetAlt + altComp);

      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // F <delta> : Relative focus move by delta steps
    // -------------------------------------------------------------------------
    case 'F': {
      long delta = 0;
      if (!parseNextLong(line, delta)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      long curTarget = (focStepper.distanceToGo() != 0) ? focStepper.targetPosition() : focStepper.currentPosition();
      long newTarget = curTarget + delta;

      if (newTarget < -FOC_LIMIT_STEPS || newTarget > FOC_LIMIT_STEPS) {
        Serial.println(F("ERR LIMIT"));
        return;
      }

      focStepper.enableOutputs();
      focOutputsEnabled = true;
      focStepper.moveTo(newTarget);
      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // H <az> <alt> : Set logical position counters without moving (homing/SYNC)
    // -------------------------------------------------------------------------
    case 'H': {
      long newAz = 0, newAlt = 0;
      if (!parseNextLong(line, newAz) || !parseNextLong(line, newAlt)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      // Stop any motion on both axes
      enableAzOutputs();
      enableAltOutputs();
      azComp = (azLastDir > 0) ? azBacklash : 0;
      azStepper.setCurrentPosition(newAz + azComp);

      altComp = (altLastDir > 0) ? altBacklash : 0;
      altStepper.setCurrentPosition(newAlt + altComp);

      // If homing was running, cancel it
      homingAxis = HOME_NONE;
      homingState = HOMING_IDLE;

      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // B <az> <alt> : Set backlash steps for azimuth and altitude (0..2000)
    // -------------------------------------------------------------------------
    case 'B': {
      long bAz = 0, bAlt = 0;
      if (!parseNextLong(line, bAz) || !parseNextLong(line, bAlt)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (bAz < 0 || bAz > 2000 || bAlt < 0 || bAlt > 2000) {
        Serial.println(F("ERR PARSE"));
        return;
      }

      // Update Azimuth backlash
      if (azStepper.distanceToGo() == 0 && homingAxis != HOME_AZ) {
        long logical = getLogicalAz();
        azBacklash = bAz;
        azComp = (azLastDir > 0) ? azBacklash : 0;
        azStepper.setCurrentPosition(logical + azComp);
      } else {
        azBacklash = bAz;
      }

      // Update Altitude backlash
      if (altStepper.distanceToGo() == 0 && homingAxis != HOME_ALT) {
        long logical = getLogicalAlt();
        altBacklash = bAlt;
        altComp = (altLastDir > 0) ? altBacklash : 0;
        altStepper.setCurrentPosition(logical + altComp);
      } else {
        altBacklash = bAlt;
      }

      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // L <azmin> <azmax> <altmin> <altmax> : Set soft limits in logical steps
    // -------------------------------------------------------------------------
    case 'L': {
      long azMinVal = 0, azMaxVal = 0, altMinVal = 0, altMaxVal = 0;
      if (!parseNextLong(line, azMinVal) || !parseNextLong(line, azMaxVal) ||
          !parseNextLong(line, altMinVal) || !parseNextLong(line, altMaxVal)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (azMinVal > azMaxVal || altMinVal > altMaxVal) {
        Serial.println(F("ERR PARSE"));
        return;
      }

      azLimitMin  = azMinVal;
      azLimitMax  = azMaxVal;
      altLimitMin = altMinVal;
      altLimitMax = altMaxVal;

      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // V <az> <alt> <foc> : Set max speeds in steps/s (10..1500)
    // -------------------------------------------------------------------------
    case 'V': {
      long vAz = 0, vAlt = 0, vFoc = 0;
      if (!parseNextLong(line, vAz) || !parseNextLong(line, vAlt) || !parseNextLong(line, vFoc)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (vAz < 10 || vAz > 1500 || vAlt < 10 || vAlt > 1500 || vFoc < 10 || vFoc > 1500) {
        Serial.println(F("ERR PARSE"));
        return;
      }

      azConfiguredMaxSpeed = (float)vAz;
      altConfiguredMaxSpeed = (float)vAlt;
      azStepper.setMaxSpeed(azConfiguredMaxSpeed);
      altStepper.setMaxSpeed(altConfiguredMaxSpeed);
      focStepper.setMaxSpeed((float)vFoc);
      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // A <az> <alt> <foc> : Set accelerations in steps/s^2 (10..3000)
    // -------------------------------------------------------------------------
    case 'A': {
      long aAz = 0, aAlt = 0, aFoc = 0;
      if (!parseNextLong(line, aAz) || !parseNextLong(line, aAlt) || !parseNextLong(line, aFoc)) {
        Serial.println(F("ERR PARSE"));
        return;
      }
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (aAz < 10 || aAz > 3000 || aAlt < 10 || aAlt > 3000 || aFoc < 10 || aFoc > 3000) {
        Serial.println(F("ERR PARSE"));
        return;
      }

      azStepper.setAcceleration((float)aAz);
      altStepper.setAcceleration((float)aAlt);
      focStepper.setAcceleration((float)aFoc);
      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // Z ALT | Z AZ : Start background homing on limit switch
    // -------------------------------------------------------------------------
    case 'Z': {
      while (*line == ' ') line++;
      char axisToken[8];
      uint8_t tIdx = 0;
      while (*line != ' ' && *line != '\0' && tIdx < sizeof(axisToken) - 1) {
        axisToken[tIdx++] = *line++;
      }
      axisToken[tIdx] = '\0';
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (strcmp(axisToken, "F") == 0) {
        focStepper.setCurrentPosition(0);
        Serial.println(F("OK"));
        return;
      }

      HomingAxis reqAxis = HOME_NONE;
      if (strcmp(axisToken, "ALT") == 0) {
        reqAxis = HOME_ALT;
      } else if (strcmp(axisToken, "AZ") == 0) {
        reqAxis = HOME_AZ;
      } else {
        Serial.println(F("ERR PARSE"));
        return;
      }

      if (homingAxis != HOME_NONE) {
        Serial.println(F("ERR BUSY"));
        return;
      }

      homingAxis = reqAxis;
      uint8_t pin = (homingAxis == HOME_ALT) ? PIN_ALT_HOME : PIN_AZ_HOME;
      AccelStepper* s = (homingAxis == HOME_ALT) ? &altStepper : &azStepper;

      if (homingAxis == HOME_ALT) {
        enableAltOutputs();
      } else {
        enableAzOutputs();
      }

      homingStartPos = s->currentPosition();
      homingDebounce = 0;
      homingClearDebounce = 0;

      // Check if switch is already pressed (active LOW)
      if (digitalRead(pin) == LOW) {
        // Move in opposite direction to release switch
        homingState = HOMING_CLEARING;
        float clearSpeed = (homingAxis == HOME_ALT) ? (-HOME_DIR_ALT * HOME_SPEED) : (-HOME_DIR_AZ * HOME_SPEED);
        s->setSpeed(clearSpeed);
      } else {
        // Normal approach toward switch
        homingState = HOMING_APPROACHING;
        float approachSpeed = (homingAxis == HOME_ALT) ? (HOME_DIR_ALT * HOME_SPEED) : (HOME_DIR_AZ * HOME_SPEED);
        s->setSpeed(approachSpeed);
      }

      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // S : Emergency Stop
    // -------------------------------------------------------------------------
    case 'S': {
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }
      emergencyStop();
      Serial.println(F("OK"));
      break;
    }

    // -------------------------------------------------------------------------
    // P : Telemetry query
    // -------------------------------------------------------------------------
    case 'P': {
      while (*line == ' ') line++;
      if (*line != '\0') {
        Serial.println(F("ERR PARSE"));
        return;
      }

      long azLog  = getLogicalAz();
      long altLog = getLogicalAlt();
      long focPos = focStepper.currentPosition();

      uint8_t moving = (azStepper.distanceToGo() != 0 ||
                        altStepper.distanceToGo() != 0 ||
                        focStepper.distanceToGo() != 0 ||
                        homingAxis != HOME_NONE) ? 1 : 0;

      Serial.print(F("P "));
      Serial.print(azLog);
      Serial.print(' ');
      Serial.print(altLog);
      Serial.print(' ');
      Serial.print(focPos);
      Serial.print(' ');
      Serial.print(moving);
      Serial.print(' ');
      Serial.println(homedBits);
      break;
    }

    default:
      Serial.println(F("ERR PARSE"));
      break;
  }
}

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  Serial.begin(115200);

  // Home switch pins with internal pull-up resistors
  pinMode(PIN_ALT_HOME, INPUT_PULLUP);
  pinMode(PIN_AZ_HOME, INPUT_PULLUP);

  // Initialize speeds and accelerations
  azStepper.setMaxSpeed(AZ_MAX_SPEED_DEFAULT);
  azStepper.setAcceleration(AZ_ACCEL_DEFAULT);

  altStepper.setMaxSpeed(ALT_MAX_SPEED_DEFAULT);
  altStepper.setAcceleration(ALT_ACCEL_DEFAULT);

  focStepper.setMaxSpeed(FOC_MAX_SPEED_DEFAULT);
  focStepper.setAcceleration(FOC_ACCEL_DEFAULT);

  // Focus stepper coils start disabled
  focStepper.disableOutputs();
  focOutputsEnabled = false;

  lastSerialRxTime = millis();
  watchdogTriggered = false;

  // Signal ready to host PC
  Serial.println(F("READY"));
}

// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  // 1. Step motor execution on every pass without blocking
  if (homingAxis == HOME_ALT) {
    altStepper.runSpeed();
    azStepper.run();
    focStepper.run();
  } else if (homingAxis == HOME_AZ) {
    azStepper.runSpeed();
    altStepper.run();
    focStepper.run();
  } else {
    azStepper.run();
    altStepper.run();
    focStepper.run();
  }

  // 2. Homing state machine execution
  if (homingAxis != HOME_NONE) {
    AccelStepper* s = (homingAxis == HOME_ALT) ? &altStepper : &azStepper;
    uint8_t pin     = (homingAxis == HOME_ALT) ? PIN_ALT_HOME : PIN_AZ_HOME;
    long maxSteps   = (homingAxis == HOME_ALT) ? HOME_MAX_STEPS_ALT : HOME_MAX_STEPS_AZ;
    long stepsMoved = labs(s->currentPosition() - homingStartPos);

    if (homingState == HOMING_CLEARING) {
      if (digitalRead(pin) == HIGH) {
        homingClearDebounce++;
        if (homingClearDebounce >= HOME_DEBOUNCE_COUNT) {
          // Switch is now clear; reverse direction to approach switch
          homingState = HOMING_APPROACHING;
          homingDebounce = 0;
          homingStartPos = s->currentPosition();
          float approachSpeed = (homingAxis == HOME_ALT) ? (HOME_DIR_ALT * HOME_SPEED) : (HOME_DIR_AZ * HOME_SPEED);
          s->setSpeed(approachSpeed);
        }
      } else {
        homingClearDebounce = 0;
      }

      if (stepsMoved >= HOME_CLEAR_STEPS) {
        // Failed to clear switch within limit
        s->setCurrentPosition(s->currentPosition());
        if (homingAxis == HOME_ALT) {
          Serial.println(F("ERR HOME ALT"));
        } else {
          Serial.println(F("ERR HOME AZ"));
        }
        homingAxis = HOME_NONE;
        homingState = HOMING_IDLE;
      }
    } else if (homingState == HOMING_APPROACHING) {
      if (digitalRead(pin) == LOW) {
        homingDebounce++;
        if (homingDebounce >= HOME_DEBOUNCE_COUNT) {
          // Switch triggered! Zero position at trigger point
          s->setCurrentPosition(0);
          if (homingAxis == HOME_ALT) {
            altComp = 0;
            altLastDir = -1;
            homedBits |= 1; // Bit 0 = Altitude homed
          } else {
            azComp = 0;
            azLastDir = -1;
            homedBits |= 2; // Bit 1 = Azimuth homed
          }
          homingAxis = HOME_NONE;
          homingState = HOMING_IDLE;
        }
      } else {
        homingDebounce = 0;
      }

      if (stepsMoved >= maxSteps) {
        // Exceeded travel without encountering switch
        s->setCurrentPosition(s->currentPosition());
        if (homingAxis == HOME_ALT) {
          Serial.println(F("ERR HOME ALT"));
        } else {
          Serial.println(F("ERR HOME AZ"));
        }
        homingAxis = HOME_NONE;
        homingState = HOMING_IDLE;
      }
    }
  }

  // 3. Focus coil power management: disable outputs when move finishes
  if (focOutputsEnabled && focStepper.distanceToGo() == 0) {
    focStepper.disableOutputs();
    focOutputsEnabled = false;
  }

  // 4. Azimuth and Altitude idle power management (Section 5.6)
  unsigned long now = millis();

  // Azimuth idle timeout
  if (IDLE_DISABLE_AZ_MS > 0) {
    if (azStepper.distanceToGo() != 0 || homingAxis == HOME_AZ) {
      azIdleStartTime = 0;
    } else {
      if (azIdleStartTime == 0) {
        azIdleStartTime = now;
      } else if (azOutputsEnabled && (now - azIdleStartTime >= IDLE_DISABLE_AZ_MS)) {
        azStepper.disableOutputs();
        azOutputsEnabled = false;
      }
    }
  }

  // Altitude idle timeout (disabled by default to prevent tube sag on unbalanced mounts)
  if (IDLE_DISABLE_ALT_MS > 0) {
    if (altStepper.distanceToGo() != 0 || homingAxis == HOME_ALT) {
      altIdleStartTime = 0;
    } else {
      if (altIdleStartTime == 0) {
        altIdleStartTime = now;
      } else if (altOutputsEnabled && (now - altIdleStartTime >= IDLE_DISABLE_ALT_MS)) {
        altStepper.disableOutputs();
        altOutputsEnabled = false;
      }
    }
  }

  // 5. Serial communication: read incoming bytes non-blockingly
  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c < 0) break;

    lastSerialRxTime = millis();
    watchdogTriggered = false;

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      if (rxOverflow) {
        Serial.println(F("ERR PARSE"));
        rxIndex = 0;
        rxOverflow = false;
      } else if (rxIndex > 0) {
        rxBuf[rxIndex] = '\0';
        processCommand(rxBuf);
        rxIndex = 0;
      }
      // Empty lines ignored
    } else {
      if (rxIndex < sizeof(rxBuf) - 1) {
        rxBuf[rxIndex++] = (char)c;
      } else {
        rxOverflow = true;
      }
    }
  }

  // 6. Serial Watchdog (Section 5.5)
  // If moving or homing and no serial traffic for SERIAL_WATCHDOG_MS, stop all motors
  bool isMoving = (azStepper.distanceToGo() != 0 ||
                   altStepper.distanceToGo() != 0 ||
                   focStepper.distanceToGo() != 0 ||
                   homingAxis != HOME_NONE);

  if (isMoving && !watchdogTriggered) {
    if (millis() - lastSerialRxTime > SERIAL_WATCHDOG_MS) {
      emergencyStop();
      watchdogTriggered = true;
      Serial.println(F("WATCHDOG"));
    }
  }
}

/*
================================================================================
ARDUINO FIRMWARE SERIAL COMMAND QUICK REFERENCE
================================================================================
Baud rate: 115200 8N1, ASCII newline ('\n') terminated.

Commands from PC:
  G <az> <alt>          Move azimuth & altitude to logical absolute step targets.
                        Replies: "OK", "ERR LIMIT", "ERR BUSY", "ERR PARSE"
  F <delta>             Relative focus step move (-6000..+6000 bounds). Coils turn off after move.
                        Replies: "OK", "ERR LIMIT", "ERR PARSE"
  H <az> <alt>          Set logical position counters immediately without moving (SYNC/Zero).
                        Replies: "OK", "ERR PARSE"
  B <az> <alt>          Set backlash steps (0..2000). Updates comp offset.
                        Replies: "OK", "ERR PARSE"
  L <azmin> <azmax> <altmin> <altmax>
                        Set soft limits in logical steps.
                        Replies: "OK", "ERR PARSE"
  V <az> <alt> <foc>    Set maximum speeds in steps/s (10..1500).
                        Replies: "OK", "ERR PARSE"
  A <az> <alt> <foc>    Set accelerations in steps/s^2 (10..3000).
                        Replies: "OK", "ERR PARSE"
  Z ALT | Z AZ          Initiate background homing on limit switch.
                        Replies: "OK", "ERR BUSY", "ERR PARSE"
  S                     Emergency stop all 3 axes, cancel homing immediately.
                        Replies: "OK", "ERR PARSE"
  P                     Query telemetry. Reply format:
                        "P <azLog> <altLog> <focPos> <moving 0|1> <homed_bitmask>"
                        (homed_bitmask: bit 0 = Alt homed, bit 1 = Az homed)

Asynchronous Notifications (printed by Arduino spontaneously):
  READY                 Emitted once at microcontroller boot/reset.
  ERR HOME ALT          Altitude homing failed (travel limit exceeded or switch didn't clear).
  ERR HOME AZ           Azimuth homing failed.
  WATCHDOG              Motors stopped due to >5000 ms serial silence while in motion.
================================================================================
*/
