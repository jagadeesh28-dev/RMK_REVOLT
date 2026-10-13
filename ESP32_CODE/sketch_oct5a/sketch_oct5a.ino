/*
 * ================================================================
 *                         RMK REVOLT
 *       ESP32 BATTERY TELEMETRY + LOAD CONTROL NODE
 * ================================================================
 *
 * Hardware:
 *   ESP32
 *   INA219
 *   DS18B20
 *   INZL44N MOSFET
 *   DC Motor / Load
 *
 * Pin Configuration:
 *   INA219 SDA       -> GPIO 21
 *   INA219 SCL       -> GPIO 22
 *   DS18B20 DATA     -> GPIO 4
 *   INZL44N GATE     -> GPIO 25
 *
 * ================================================================
 *
 * IMPORTANT:
 * This firmware is the physical telemetry and load-control layer.
 * It does NOT perform SOH/RUL prediction.
 *
 * ================================================================
 */

#include <Wire.h>
#include <Adafruit_INA219.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ================================================================
//             PRIVATE NETWORK CONFIGURATION (SECRETS)
// ================================================================
// To customize for your local Wi-Fi, create "secrets.h" alongside this
// sketch (see secrets.h.example). "secrets.h" is ignored by Git.
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #define WIFI_SSID         "SYNQRA_HOST"
  #define WIFI_PASSWORD     "jagadeeshking"
  #define BACKEND_HOST      "192.168.137.1"
  #define BACKEND_PORT      8088
  #define DEVICE_ID         "NEXUS-ESP32-01"
  #define DEVICE_API_TOKEN  "NEXUS_SECURE_BENCH_TOKEN_V1"
#endif


// ================================================================
//                       PIN CONFIGURATION
// ================================================================

#define I2C_SDA_PIN       21
#define I2C_SCL_PIN       22

#define DS18B20_PIN       4

#define MOSFET_GATE_PIN   25


// ================================================================
//                       HARDWARE OBJECTS
// ================================================================

Adafruit_INA219 ina219;

OneWire oneWire(DS18B20_PIN);

DallasTemperature temperatureSensor(&oneWire);


// ================================================================
//                       SAFETY LIMITS
// ================================================================
//
// PROTOTYPE VALUES ONLY.
// These must be validated for the actual battery chemistry
// before real battery qualification experiments.
//
// ================================================================

// 2S Li-ion nominal ≈ 7.4 V
const float BATTERY_UNDERVOLTAGE = 6.40;
const float BATTERY_OVERVOLTAGE  = 8.50;

// Temperature
const float MAX_TEMPERATURE_C = 60.0;

// Prototype current protection limit
const float MAX_CURRENT_A = 2.50;


// ================================================================
//                       LOAD TEST TIMING
// ================================================================

const unsigned long LOAD_ON_TIME_MS  = 5000;
const unsigned long LOAD_OFF_TIME_MS = 3000;


// ================================================================
//                       SENSOR TIMING
// ================================================================

const unsigned long SENSOR_INTERVAL_MS = 1000;


// ================================================================
//                       STARTUP DELAY
// ================================================================

const unsigned long STARTUP_STABILIZATION_MS = 3000;


// ================================================================
//                 SAFETY CONFIRMATION COUNTS
// ================================================================

const int UV_CONFIRM_COUNT = 3;
const int OV_CONFIRM_COUNT = 3;
const int OC_CONFIRM_COUNT = 3;
const int OT_CONFIRM_COUNT = 3;


// ================================================================
//                  SENSOR CONFIRMATION COUNT
// ================================================================

const int SENSOR_INVALID_CONFIRM_COUNT = 3;


// ================================================================
//             RECOVERY HYSTERESIS & QUALIFICATION CONSTANTS
// ================================================================
//
// To prevent chattering/oscillations between FAULT and IDLE,
// recovery requires valid healthy sensor data meeting strict
// hysteresis boundaries for RECOVERY_CONFIRM_COUNT consecutive samples.
//
const float BATTERY_UNDERVOLTAGE_RECOVERY = 6.55; // 150 mV hysteresis (trip: 6.40 V)
const float BATTERY_OVERVOLTAGE_RECOVERY  = 8.35; // 150 mV hysteresis (trip: 8.50 V)
const float MAX_TEMPERATURE_RECOVERY_C    = 55.0; // 5.0 °C hysteresis (trip: 60.0 °C)
const float MAX_CURRENT_RECOVERY_A        = 0.10; // Load must be de-energized (trip: 2.50 A)
const int   RECOVERY_CONFIRM_COUNT        = 5;    // 5 consecutive 1-second samples (5s dwell)



// ================================================================
//                       SYSTEM STATES
// ================================================================

enum SystemState
{
  STATE_IDLE,
  STATE_RUNNING,
  STATE_COOLDOWN,
  STATE_FAULT
};

SystemState systemState = STATE_IDLE;


// ================================================================
//                       RAW MEASUREMENTS
// ================================================================

float rawVoltage_V = 0.0;
float rawCurrent_A = 0.0;
float rawPower_W   = 0.0;


// ================================================================
//                    ACCEPTED MEASUREMENTS
// ================================================================

float batteryVoltage = 0.0;
float current_A      = 0.0;
float power_W        = 0.0;
float temperature_C  = 0.0;


// ================================================================
//                    PREVIOUS MEASUREMENTS
// ================================================================

float previousVoltage = 0.0;
float previousCurrent = 0.0;
float previousPower   = 0.0;
float previousTemp    = 0.0;


// ================================================================
//                       SENSOR STATUS
// ================================================================

bool sensorValid = false;
bool faultSensor = false;


// ================================================================
//                       MOSFET STATUS
// ================================================================

bool mosfetState = false;


// ================================================================
//                    FAULT STATUS FLAGS
// ================================================================
//
// These were missing in the previous version and caused
// your compilation errors.
//
// ================================================================

bool faultUnderVoltage   = false;
bool faultOverVoltage    = false;
bool faultOverCurrent    = false;
bool faultOverTemperature = false;


// ================================================================
//                         TIMERS
// ================================================================

unsigned long bootTime = 0;

unsigned long lastSensorRead = 0;

unsigned long stateStartTime = 0;


// ================================================================
//                       TEST COUNTER
// ================================================================

unsigned long testCycleCount = 0;

// ================================================================
//                       TELEMETRY SEQUENCE
// ================================================================

unsigned long telemetrySequence = 0;


// ================================================================
//                 FAULT INFORMATION & AUDIT HISTORY
// ================================================================

String faultReason = "NONE";
String lastFaultReason = "NONE";
bool faultRecovered = false;
unsigned long faultEntryTime = 0;
unsigned long faultClearTime = 0;
int recoverySampleCount = 0;



// ================================================================
//                     SAFETY COUNTERS
// ================================================================

int undervoltageCount = 0;

int overvoltageCount = 0;

int overcurrentCount = 0;

int overtempCount = 0;


// ================================================================
//                    SENSOR ERROR COUNTER
// ================================================================

int sensorInvalidCount = 0;


// ================================================================
//                       WI-FI FSM STATES & TIMERS
// ================================================================

enum WifiState
{
  WIFI_STATE_BOOT,
  WIFI_STATE_CONNECTING,
  WIFI_STATE_CONNECTED,
  WIFI_STATE_TELEMETRY_READY,
  WIFI_STATE_RECONNECTING,
  WIFI_STATE_OFFLINE
};

WifiState wifiState = WIFI_STATE_BOOT;
unsigned long lastWifiCheck = 0;
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000;
unsigned long wifiConnectStartTime = 0;
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 12000;
int wifiReconnectCount = 0;


// ================================================================
//                       FUNCTION DECLARATIONS
// ================================================================

void setMOSFET(bool state);

void readSensors();

void checkSafety();

void enterFault(String reason);

void clearFault();

bool isFaultRecoverable(const String &reason);

bool isPhysicalConditionHealthy();

void checkFaultRecovery();

void printTelemetry();

void printCSVHeader();

void printCSV();

void processSerialCommand();

void startAutomaticTest();

void stopAutomaticTest();

String getStateName();

void initWiFi();

void updateWiFiFSM();

void sendTelemetryHTTP(const String &jsonPayload);

String buildTelemetryJSON();


// ================================================================
//                            SETUP
// ================================================================

void setup()
{
  Serial.begin(115200);

  delay(1000);

  bootTime = millis();


  Serial.println();
  Serial.println("================================================");
  Serial.println("                RMK REVOLT");
  Serial.println("       BATTERY TELEMETRY NODE v4 (WI-FI ENABLED)");
  Serial.println("================================================");
  Serial.println();


  // ==============================================================
  // MOSFET
  // ==============================================================

  pinMode(
    MOSFET_GATE_PIN,
    OUTPUT
  );

  // FAIL-SAFE STARTUP
  setMOSFET(false);

  Serial.println(
    "[OK] MOSFET initialized OFF"
  );


  // ==============================================================
  // I2C
  // ==============================================================

  Wire.begin(
    I2C_SDA_PIN,
    I2C_SCL_PIN
  );


  // ==============================================================
  // INA219
  // ==============================================================

  Serial.println(
    "[INFO] Initializing INA219..."
  );


  if (!ina219.begin())
  {
    Serial.println(
      "[FAULT] INA219 NOT DETECTED"
    );

    faultSensor = true;

    enterFault(
      "INA219_NOT_DETECTED"
    );
  }
  else
  {
    Serial.println(
      "[OK] INA219 detected"
    );

    /*
     * Standard Adafruit INA219 calibration.
     *
     * Verify this against the actual INA219 board
     * and shunt resistor before high-current testing.
     */

    ina219.setCalibration_32V_2A();

    Serial.println(
      "[OK] INA219 configured"
    );
  }


  // ==============================================================
  // DS18B20
  // ==============================================================

  Serial.println(
    "[INFO] Initializing DS18B20..."
  );

  temperatureSensor.begin();


  int deviceCount =
    temperatureSensor.getDeviceCount();


  if (deviceCount == 0)
  {
    Serial.println(
      "[FAULT] DS18B20 NOT DETECTED"
    );

    faultSensor = true;

    enterFault(
      "DS18B20_NOT_DETECTED"
    );
  }
  else
  {
    Serial.print(
      "[OK] DS18B20 detected: "
    );

    Serial.print(
      deviceCount
    );

    Serial.println(
      " device(s)"
    );
  }


  // ==============================================================
  // CSV HEADER
  // ==============================================================

  printCSVHeader();


  // ==============================================================
  // INITIAL STATE
  // ==============================================================

  if (!faultSensor)
  {
    systemState = STATE_IDLE;

    stateStartTime = millis();

    Serial.println();
    Serial.println(
      "[SYSTEM] STARTUP STABILIZATION"
    );

    Serial.println(
      "[SYSTEM] Waiting 3 seconds..."
    );
  }
  else
  {
    systemState = STATE_FAULT;
  }


  // ==============================================================
  // COMMAND HELP
  // ==============================================================

  Serial.println();

  Serial.println(
    "Commands:"
  );

  Serial.println(
    "  ON      - Load ON"
  );

  Serial.println(
    "  OFF     - Load OFF"
  );

  Serial.println(
    "  AUTO    - Automatic load test"
  );

  Serial.println(
    "  STOP    - Stop automatic test"
  );

  Serial.println(
    "  STATUS  - Current telemetry"
  );

  Serial.println(
    "  CLEAR   - Clear fault"
  );

  Serial.println(
    "  HELP    - Command list"
  );

  Serial.println();

  // ==============================================================
  // NON-BLOCKING WI-FI INITIALIZATION
  // ==============================================================
  initWiFi();
}


// ================================================================
//                            LOOP
// ================================================================

void loop()
{
  // ==============================================================
  // NON-BLOCKING WI-FI STATE MACHINE & RECONNECT SUPERVISOR
  // ==============================================================
  updateWiFiFSM();

  // ==============================================================
  // SERIAL COMMANDS
  // ==============================================================

  processSerialCommand();


  // ==============================================================
  // SENSOR SAMPLING
  // ==============================================================

  if (
    millis() - lastSensorRead >=
    SENSOR_INTERVAL_MS
  )
  {
    lastSensorRead = millis();

    readSensors();

    if (systemState != STATE_FAULT)
    {
      checkSafety();
    }
    else
    {
      checkFaultRecovery();
    }

    printTelemetry();
  }


  // ==============================================================
  // RUNNING STATE
  // ==============================================================

  if (
    systemState == STATE_RUNNING
  )
  {
    unsigned long elapsed =
      millis() - stateStartTime;


    if (
      elapsed >= LOAD_ON_TIME_MS
    )
    {
      setMOSFET(false);

      systemState =
        STATE_COOLDOWN;

      stateStartTime =
        millis();

      testCycleCount++;


      Serial.print(
        "[CYCLE] Completed cycle: "
      );

      Serial.println(
        testCycleCount
      );
    }
  }


  // ==============================================================
  // COOLDOWN STATE
  // ==============================================================

  else if (
    systemState == STATE_COOLDOWN
  )
  {
    unsigned long elapsed =
      millis() - stateStartTime;


    if (
      elapsed >= LOAD_OFF_TIME_MS
    )
    {
      setMOSFET(true);

      systemState =
        STATE_RUNNING;

      stateStartTime =
        millis();
    }
  }

  // ==============================================================
  // FAULT STATE FAIL-SAFE SUPERVISOR
  // ==============================================================

  else if (
    systemState == STATE_FAULT
  )
  {
    if (mosfetState)
    {
      setMOSFET(false);
    }
  }
}



// ================================================================
//                       MOSFET CONTROL
// ================================================================

void setMOSFET(bool state)
{
  mosfetState = state;


  if (state)
  {
    digitalWrite(
      MOSFET_GATE_PIN,
      HIGH
    );
  }
  else
  {
    digitalWrite(
      MOSFET_GATE_PIN,
      LOW
    );
  }
}


// ================================================================
//                       SENSOR READING
// ================================================================

void readSensors()
{
  // ==============================================================
  // INA219
  // ==============================================================

  float voltage =
    ina219.getBusVoltage_V();

  float shuntVoltage_mV =
    ina219.getShuntVoltage_mV();

  float current_mA =
    ina219.getCurrent_mA();

  float power_mW =
    ina219.getPower_mW();


  // ==============================================================
  // CONVERT UNITS
  // ==============================================================

  float measuredCurrent_A =
    current_mA / 1000.0;

  float measuredPower_W =
    power_mW / 1000.0;


  // ==============================================================
  // DS18B20
  // ==============================================================

  temperatureSensor.requestTemperatures();

  float temp =
    temperatureSensor.getTempCByIndex(0);


  // ==============================================================
  // STORE RAW VALUES
  // ==============================================================

  rawVoltage_V =
    voltage;

  rawCurrent_A =
    measuredCurrent_A;

  rawPower_W =
    measuredPower_W;


  // ==============================================================
  // VALIDATION
  // ==============================================================

  bool valid = true;

  String invalidReason = "";


  // --------------------------------------------------------------
  // INA219 NaN / INF
  // --------------------------------------------------------------

  if (
    isnan(voltage) ||
    isnan(measuredCurrent_A) ||
    isnan(measuredPower_W) ||
    isinf(voltage) ||
    isinf(measuredCurrent_A) ||
    isinf(measuredPower_W)
  )
  {
    valid = false;

    invalidReason =
      "INA219_NAN_INF";
  }


  // --------------------------------------------------------------
  // DS18B20
  // --------------------------------------------------------------

  if (
    temp == DEVICE_DISCONNECTED_C ||
    isnan(temp) ||
    isinf(temp)
  )
  {
    valid = false;

    invalidReason =
      "DS18B20_INVALID";
  }


  // --------------------------------------------------------------
  // Voltage range
  // --------------------------------------------------------------

  if (
    voltage < 0.0 ||
    voltage > 40.0
  )
  {
    valid = false;

    invalidReason =
      "INA219_VOLTAGE_RANGE";
  }


  // --------------------------------------------------------------
  // Current range
  // --------------------------------------------------------------

  if (
    fabs(measuredCurrent_A) > 10.0
  )
  {
    valid = false;

    invalidReason =
      "INA219_CURRENT_RANGE";
  }


  // --------------------------------------------------------------
  // Temperature range
  // --------------------------------------------------------------

  if (
    temp < -55.0 ||
    temp > 125.0
  )
  {
    valid = false;

    invalidReason =
      "DS18B20_RANGE";
  }


  // ==============================================================
  // INVALID SAMPLE
  // ==============================================================

  if (!valid)
  {
    sensorInvalidCount++;


    Serial.print(
      "[WARNING] Invalid sensor sample #"
    );

    Serial.print(
      sensorInvalidCount
    );

    Serial.print(
      " : "
    );

    Serial.println(
      invalidReason
    );


    /*
     * A single invalid measurement does NOT
     * cause an immediate shutdown.
     */

    if (
      sensorInvalidCount >=
      SENSOR_INVALID_CONFIRM_COUNT
    )
    {
      sensorValid = false;

      faultSensor = true;


      Serial.println(
        "[SAFETY] Sensor failure confirmed"
      );
    }


    return;
  }


  // ==============================================================
  // VALID SAMPLE
  // ==============================================================

  sensorInvalidCount = 0;

  sensorValid = true;

  faultSensor = false;


  // ==============================================================
  // NEAR-ZERO VOLTAGE
  // ==============================================================

  if (
    voltage < 0.1
  )
  {
    Serial.println(
      "[WARNING] INA219 near-zero voltage transient ignored"
    );

    /*
     * Keep the previous accepted voltage/current/power.
     */

    return;
  }


  // ==============================================================
  // ACCEPT MEASUREMENT
  // ==============================================================

  previousVoltage =
    batteryVoltage;

  previousCurrent =
    current_A;

  previousPower =
    power_W;

  previousTemp =
    temperature_C;


  batteryVoltage =
    voltage;

  current_A =
    measuredCurrent_A;

  power_W =
    measuredPower_W;

  temperature_C =
    temp;
}


// ================================================================
//                       SAFETY SUPERVISOR
// ================================================================

void checkSafety()
{
  // ==============================================================
  // SENSOR FAILURE
  // ==============================================================

  if (
    !sensorValid
  )
  {
    enterFault(
      "SENSOR_INVALID"
    );

    return;
  }


  // ==============================================================
  // STARTUP STABILIZATION
  // ==============================================================

  if (
    millis() - bootTime <
    STARTUP_STABILIZATION_MS
  )
  {
    return;
  }


  // ==============================================================
  // INVALID BATTERY VOLTAGE
  // ==============================================================

  if (
    batteryVoltage < 0.1
  )
  {
    return;
  }


  // ==============================================================
  // UNDER VOLTAGE
  // ==============================================================

  if (
    batteryVoltage <
    BATTERY_UNDERVOLTAGE
  )
  {
    undervoltageCount++;
  }
  else
  {
    undervoltageCount = 0;
  }


  if (
    undervoltageCount >=
    UV_CONFIRM_COUNT
  )
  {
    faultUnderVoltage = true;

    enterFault(
      "UNDER_VOLTAGE"
    );

    return;
  }


  // ==============================================================
  // OVER VOLTAGE
  // ==============================================================

  if (
    batteryVoltage >
    BATTERY_OVERVOLTAGE
  )
  {
    overvoltageCount++;
  }
  else
  {
    overvoltageCount = 0;
  }


  if (
    overvoltageCount >=
    OV_CONFIRM_COUNT
  )
  {
    faultOverVoltage = true;

    enterFault(
      "OVER_VOLTAGE"
    );

    return;
  }


  // ==============================================================
  // OVER CURRENT
  // ==============================================================

  if (
    current_A >
    MAX_CURRENT_A
  )
  {
    overcurrentCount++;
  }
  else
  {
    overcurrentCount = 0;
  }


  if (
    overcurrentCount >=
    OC_CONFIRM_COUNT
  )
  {
    faultOverCurrent = true;

    enterFault(
      "OVER_CURRENT"
    );

    return;
  }


  // ==============================================================
  // OVER TEMPERATURE
  // ==============================================================

  if (
    temperature_C >=
    MAX_TEMPERATURE_C
  )
  {
    overtempCount++;
  }
  else
  {
    overtempCount = 0;
  }


  if (
    overtempCount >=
    OT_CONFIRM_COUNT
  )
  {
    faultOverTemperature = true;

    enterFault(
      "OVER_TEMPERATURE"
    );

    return;
  }
}


// ================================================================
//                       ENTER FAULT
// ================================================================

void enterFault(String reason)
{
  // --------------------------------------------------------------
  // IMMEDIATE FAIL-SAFE
  // --------------------------------------------------------------

  setMOSFET(false);


  // --------------------------------------------------------------
  // LATCH & AUDIT HISTORY
  // --------------------------------------------------------------

  systemState = STATE_FAULT;

  faultReason = reason;
  lastFaultReason = reason;
  faultRecovered = false;
  faultEntryTime = millis();
  recoverySampleCount = 0;


  // --------------------------------------------------------------
  // RESET COUNTERS
  // --------------------------------------------------------------

  undervoltageCount = 0;

  overvoltageCount = 0;

  overcurrentCount = 0;

  overtempCount = 0;


  // --------------------------------------------------------------
  // LOG
  // --------------------------------------------------------------

  Serial.println();

  Serial.println(
    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  );

  Serial.println(
    "             SAFETY FAULT"
  );

  Serial.print(
    "Reason: "
  );

  Serial.println(
    reason
  );

  Serial.println(
    "MOSFET forced OFF"
  );

  Serial.println(
    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  );

  Serial.println();
}


// ================================================================
//                   FAULT CLASSIFICATION & RECOVERY
// ================================================================

bool isFaultRecoverable(const String &reason)
{
  if (reason == "UNDER_VOLTAGE")      return true;
  if (reason == "OVER_VOLTAGE")       return true;
  if (reason == "OVER_CURRENT")       return true;
  if (reason == "OVER_TEMPERATURE")   return true;
  if (reason == "SENSOR_INVALID")     return true;

  // Latched faults requiring manual inspection:
  // - "INA219_NOT_DETECTED"
  // - "DS18B20_NOT_DETECTED"
  // - "HARDWARE_TRIP_LATCHED"
  // - "EMERGENCY_STOP"
  // - Unknown/unclassified faults
  return false;
}

bool isPhysicalConditionHealthy()
{
  // 1. Sensor validity check
  if (!sensorValid || faultSensor)
  {
    return false;
  }

  // 2. Voltage hysteresis check
  if (batteryVoltage < BATTERY_UNDERVOLTAGE_RECOVERY ||
      batteryVoltage > BATTERY_OVERVOLTAGE_RECOVERY)
  {
    return false;
  }

  // 3. Current check (load must be de-energized)
  if (fabs(current_A) > MAX_CURRENT_RECOVERY_A)
  {
    return false;
  }

  // 4. Temperature hysteresis check
  if (temperature_C > MAX_TEMPERATURE_RECOVERY_C)
  {
    return false;
  }

  return true;
}

void checkFaultRecovery()
{
  if (systemState != STATE_FAULT)
  {
    return;
  }

  // 1. Latched faults require manual operator clearance or hardware fix
  if (!isFaultRecoverable(faultReason))
  {
    recoverySampleCount = 0;
    return;
  }

  // 2. Check physical conditions against hysteresis boundaries
  if (isPhysicalConditionHealthy())
  {
    recoverySampleCount++;

    Serial.print("[RECOVERY] Healthy sample: ");
    Serial.print(recoverySampleCount);
    Serial.print(" / ");
    Serial.println(RECOVERY_CONFIRM_COUNT);

    if (recoverySampleCount >= RECOVERY_CONFIRM_COUNT)
    {
      // Safe state recovery: FAULT -> IDLE
      lastFaultReason = faultReason;
      faultReason = "NONE";
      faultRecovered = true;
      faultClearTime = millis();
      recoverySampleCount = 0;

      // CRITICAL SAFETY INVARIANT: Load MUST remain OFF
      setMOSFET(false);

      systemState = STATE_IDLE;
      stateStartTime = millis();

      // Reset trip counters and flags
      undervoltageCount = 0;
      overvoltageCount = 0;
      overcurrentCount = 0;
      overtempCount = 0;
      sensorInvalidCount = 0;
      faultUnderVoltage = false;
      faultOverVoltage = false;
      faultOverCurrent = false;
      faultOverTemperature = false;
      faultSensor = false;

      Serial.println();
      Serial.println("========================================");
      Serial.println("[RECOVERY] FAULT CONDITION CLEARED & QUALIFIED");
      Serial.print("[RECOVERY] Prior Fault: ");
      Serial.println(lastFaultReason);
      Serial.println("[SYSTEM] State transitioned: FAULT -> IDLE");
      Serial.println("[SAFETY] MOSFET forced OFF (Safe State Enforced)");
      Serial.println("========================================");
      Serial.println();
    }
  }
  else
  {
    if (recoverySampleCount > 0)
    {
      Serial.println("[RECOVERY] Condition violated during qualification. Counter reset.");
      recoverySampleCount = 0;
    }
  }
}


// ================================================================
//                       CLEAR FAULT
// ================================================================

void clearFault()
{
  Serial.println();

  Serial.println(
    "[CLEAR] Checking system..."
  );

  // Fresh sensor measurement
  readSensors();

  if (!isPhysicalConditionHealthy())
  {
    Serial.println(
      "[CLEAR] FAILED: physical conditions still active or out of recovery bounds"
    );
    return;
  }

  // If fault was a boot-time hardware absence, verify sensor is now responding
  if (faultReason == "INA219_NOT_DETECTED")
  {
    if (!ina219.begin())
    {
      Serial.println("[CLEAR] FAILED: INA219 still not responding on I2C bus");
      return;
    }
    ina219.setCalibration_32V_2A();
  }
  else if (faultReason == "DS18B20_NOT_DETECTED")
  {
    temperatureSensor.begin();
    if (temperatureSensor.getDeviceCount() == 0)
    {
      Serial.println("[CLEAR] FAILED: DS18B20 still not responding on 1-Wire bus");
      return;
    }
  }

  // Reset all fault flags
  faultUnderVoltage = false;
  faultOverVoltage = false;
  faultOverCurrent = false;
  faultOverTemperature = false;
  faultSensor = false;

  lastFaultReason = faultReason;
  faultReason = "NONE";
  faultRecovered = true;
  faultClearTime = millis();
  recoverySampleCount = 0;

  // Reset counters
  undervoltageCount = 0;
  overvoltageCount = 0;
  overcurrentCount = 0;
  overtempCount = 0;
  sensorInvalidCount = 0;

  // MOSFET OFF
  setMOSFET(false);

  // IDLE
  systemState = STATE_IDLE;
  stateStartTime = millis();

  Serial.println(
    "[CLEAR] Fault cleared manually"
  );

  Serial.println(
    "[SYSTEM] IDLE (MOSFET OFF)"
  );

  Serial.println();
}


// ================================================================
//                       STATE NAME
// ================================================================

String getStateName()
{
  switch (systemState)
  {
    case STATE_IDLE:
      return "IDLE";

    case STATE_RUNNING:
      return "RUNNING";

    case STATE_COOLDOWN:
      return "COOLDOWN";

    case STATE_FAULT:
      return "FAULT";

    default:
      return "UNKNOWN";
  }
}


// ================================================================
//                       CANONICAL JSON BUILDER
// ================================================================

String buildTelemetryJSON()
{
  String json = "{";
  json += "\"schema_version\":\"1.0.0\",";
  json += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  json += "\"sequence\":" + String(telemetrySequence) + ",";
  json += "\"timestamp_ms\":" + String(millis()) + ",";
  json += "\"state\":\"" + getStateName() + "\",";
  json += "\"raw_voltage_V\":" + String(rawVoltage_V, 3) + ",";
  json += "\"voltage_V\":" + String(batteryVoltage, 3) + ",";
  json += "\"raw_current_A\":" + String(rawCurrent_A, 3) + ",";
  json += "\"current_A\":" + String(current_A, 3) + ",";
  json += "\"raw_power_W\":" + String(rawPower_W, 3) + ",";
  json += "\"power_W\":" + String(power_W, 3) + ",";
  json += "\"temperature_C\":" + String(temperature_C, 2) + ",";
  json += "\"mosfet\":" + String(mosfetState ? "true" : "false") + ",";
  json += "\"cycle_count\":" + String(testCycleCount) + ",";
  json += "\"sensor_valid\":" + String(sensorValid ? "true" : "false") + ",";
  json += "\"fault\":\"" + faultReason + "\",";
  json += "\"last_fault\":\"" + lastFaultReason + "\",";
  json += "\"fault_recovered\":" + String(faultRecovered ? "true" : "false") + ",";
  json += "\"recovery_count\":" + String(recoverySampleCount) + ",";
  json += "\"fault_entry_ms\":" + String(faultEntryTime) + ",";
  json += "\"fault_clear_ms\":" + String(faultClearTime) + ",";
  json += "\"mosfet_state\":\"" + String(mosfetState ? "ON" : "OFF") + "\",";
  json += "\"hardware_fault\":" + String((faultReason != "NONE") ? "true" : "false") + ",";
  json += "\"uv_count\":" + String(undervoltageCount) + ",";
  json += "\"ov_count\":" + String(overvoltageCount) + ",";
  json += "\"oc_count\":" + String(overcurrentCount) + ",";
  json += "\"ot_count\":" + String(overtempCount) + ",";
  json += "\"sensor_error_count\":" + String(sensorInvalidCount) + ",";
  json += "\"wifi_rssi\":" + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0);
  json += "}";
  return json;
}


// ================================================================
//                       TELEMETRY TRANSMISSION
// ================================================================

void printTelemetry()
{
  telemetrySequence++;

  String jsonPayload = buildTelemetryJSON();

  // 1. Dual-stream: Print to USB Serial (115200) for local logging & HIL Runner
  Serial.println(jsonPayload);

  // 2. Dual-stream: Transmit over Wi-Fi HTTP POST to Backend
  sendTelemetryHTTP(jsonPayload);
}


// ================================================================
//                       CSV HEADER
// ================================================================

void printCSVHeader()
{
  Serial.println(
    "timestamp_ms,"
    "state,"
    "raw_voltage_V,"
    "voltage_V,"
    "raw_current_A,"
    "current_A,"
    "raw_power_W,"
    "power_W,"
    "temperature_C,"
    "mosfet,"
    "cycle_count,"
    "sensor_valid,"
    "fault"
  );
}


// ================================================================
//                       CSV OUTPUT
// ================================================================

void printCSV()
{
  Serial.print(
    millis()
  );

  Serial.print(",");


  Serial.print(
    getStateName()
  );

  Serial.print(",");


  Serial.print(
    rawVoltage_V,
    3
  );

  Serial.print(",");


  Serial.print(
    batteryVoltage,
    3
  );

  Serial.print(",");


  Serial.print(
    rawCurrent_A,
    3
  );

  Serial.print(",");


  Serial.print(
    current_A,
    3
  );

  Serial.print(",");


  Serial.print(
    rawPower_W,
    3
  );

  Serial.print(",");


  Serial.print(
    power_W,
    3
  );

  Serial.print(",");


  Serial.print(
    temperature_C,
    2
  );

  Serial.print(",");


  Serial.print(
    mosfetState
      ? 1
      : 0
  );

  Serial.print(",");


  Serial.print(
    testCycleCount
  );

  Serial.print(",");


  Serial.print(
    sensorValid
      ? 1
      : 0
  );

  Serial.print(",");


  Serial.println(
    faultReason
  );
}


// ================================================================
//                    START AUTOMATIC TEST
// ================================================================

void startAutomaticTest()
{
  // --------------------------------------------------------------
  // FAULT CHECK
  // --------------------------------------------------------------

  if (
    systemState ==
    STATE_FAULT
  )
  {
    Serial.println(
      "[AUTO] REJECTED: system is in FAULT"
    );

    return;
  }


  // --------------------------------------------------------------
  // Fresh measurement
  // --------------------------------------------------------------

  readSensors();

  checkSafety();


  // --------------------------------------------------------------
  // Check safety result
  // --------------------------------------------------------------

  if (
    systemState ==
    STATE_FAULT
  )
  {
    Serial.println(
      "[AUTO] REJECTED: safety condition failed"
    );

    return;
  }


  // --------------------------------------------------------------
  // Clear stale fault text
  // --------------------------------------------------------------

  faultReason =
    "NONE";


  // --------------------------------------------------------------
  // Reset timer
  // --------------------------------------------------------------

  stateStartTime =
    millis();


  // --------------------------------------------------------------
  // Start load
  // --------------------------------------------------------------

  setMOSFET(true);


  systemState =
    STATE_RUNNING;


  Serial.println();

  Serial.println(
    "[AUTO] Starting load test"
  );

  Serial.println(
    "[AUTO] Motor ON for 5 seconds"
  );
}


// ================================================================
//                    STOP AUTOMATIC TEST
// ================================================================

void stopAutomaticTest()
{
  setMOSFET(false);


  systemState =
    STATE_IDLE;


  stateStartTime =
    millis();


  Serial.println(
    "[AUTO] Test stopped"
  );

  Serial.println(
    "[SYSTEM] IDLE"
  );
}


// ================================================================
//                    SERIAL COMMAND HANDLER
// ================================================================

void processSerialCommand()
{
  if (
    !Serial.available()
  )
  {
    return;
  }


  String command =
    Serial.readStringUntil('\n');


  command.trim();

  command.toUpperCase();


  // ==============================================================
  // ON
  // ==============================================================

  if (
    command == "ON"
  )
  {
    if (
      systemState ==
      STATE_FAULT
    )
    {
      Serial.println(
        "[COMMAND] REJECTED: system in FAULT"
      );

      return;
    }


    readSensors();

    checkSafety();


    if (
      systemState !=
      STATE_FAULT
    )
    {
      faultReason =
        "NONE";


      setMOSFET(true);


      systemState =
        STATE_RUNNING;


      stateStartTime =
        millis();


      Serial.println(
        "[COMMAND] MOSFET ON"
      );
    }
  }


  // ==============================================================
  // OFF
  // ==============================================================

  else if (
    command == "OFF"
  )
  {
    setMOSFET(false);


    systemState =
      STATE_IDLE;


    stateStartTime =
      millis();


    Serial.println(
      "[COMMAND] MOSFET OFF"
    );
  }


  // ==============================================================
  // AUTO
  // ==============================================================

  else if (
    command == "AUTO"
  )
  {
    startAutomaticTest();
  }


  // ==============================================================
  // STOP
  // ==============================================================

  else if (
    command == "STOP"
  )
  {
    stopAutomaticTest();
  }


  // ==============================================================
  // STATUS
  // ==============================================================

  else if (
    command == "STATUS"
  )
  {
    readSensors();

    printTelemetry();
  }


  // ==============================================================
  // CLEAR
  // ==============================================================

  else if (
    command == "CLEAR"
  )
  {
    clearFault();
  }


  // ==============================================================
  // HELP
  // ==============================================================

  else if (
    command == "HELP"
  )
  {
    Serial.println();

    Serial.println(
      "========== RMK REVOLT COMMANDS =========="
    );

    Serial.println(
      "ON      - Turn load ON"
    );

    Serial.println(
      "OFF     - Turn load OFF"
    );

    Serial.println(
      "AUTO    - Automatic load test"
    );

    Serial.println(
      "STOP    - Stop automatic test"
    );

    Serial.println(
      "STATUS  - Print telemetry"
    );

    Serial.println(
      "CLEAR   - Clear safety fault"
    );

    Serial.println(
      "HELP    - Show commands"
    );

    Serial.println(
      "========================================="
    );

    Serial.println();
  }


  // ==============================================================
  // UNKNOWN
  // ==============================================================

  else
  {
    Serial.print(
      "[COMMAND] Unknown: "
    );

    Serial.println(
      command
    );
  }
}


// ================================================================
//                       WI-FI DRIVERS & STATE MACHINE
// ================================================================

void initWiFi()
{
  Serial.println("[WIFI] Initializing Station interface...");
  WiFi.mode(WIFI_STA);

  // Security Invariant: WIFI_PASSWORD is never echoed to Serial logs
  Serial.print("[WIFI] Connecting to SSID: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  wifiState = WIFI_STATE_CONNECTING;
  wifiConnectStartTime = millis();
}

void updateWiFiFSM()
{
  // CRITICAL ARCHITECTURAL RULE:
  // This state machine is 100% non-blocking. It NEVER blocks sensor sampling,
  // safety supervisor checks, or MOSFET cutoffs.
  unsigned long now = millis();

  switch (wifiState)
  {
    case WIFI_STATE_CONNECTING:
      if (WiFi.status() == WL_CONNECTED)
      {
        wifiState = WIFI_STATE_CONNECTED;
        Serial.println();
        Serial.println("[WIFI] State: CONNECTED");
        Serial.print("[WIFI] IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("[WIFI] RSSI: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
        Serial.println();
      }
      else if (now - wifiConnectStartTime >= WIFI_CONNECT_TIMEOUT_MS)
      {
        wifiState = WIFI_STATE_OFFLINE;
        Serial.println();
        Serial.println("[WIFI] Connection timeout. Operating in OFFLINE mode.");
        Serial.println("[WIFI] Local hardware safety supervisor remains active.");
        Serial.println();
      }
      break;

    case WIFI_STATE_CONNECTED:
      if (WiFi.status() != WL_CONNECTED)
      {
        wifiState = WIFI_STATE_RECONNECTING;
        wifiReconnectCount++;
        wifiConnectStartTime = now;
        Serial.println();
        Serial.println("[WIFI] Lost connection! Entering RECONNECTING state.");
        Serial.println("[WIFI] Local safety supervisor remains authoritative.");
        Serial.println();
        WiFi.reconnect();
      }
      break;

    case WIFI_STATE_RECONNECTING:
      if (WiFi.status() == WL_CONNECTED)
      {
        wifiState = WIFI_STATE_CONNECTED;
        Serial.println();
        Serial.println("[WIFI] Reconnected successfully to backend.");
        Serial.print("[WIFI] IP: ");
        Serial.println(WiFi.localIP());
        Serial.println();
      }
      else if (now - wifiConnectStartTime >= WIFI_CONNECT_TIMEOUT_MS)
      {
        wifiConnectStartTime = now;
        WiFi.reconnect();
      }
      break;

    case WIFI_STATE_OFFLINE:
      if (now - lastWifiCheck >= WIFI_CHECK_INTERVAL_MS)
      {
        lastWifiCheck = now;
        if (WiFi.status() == WL_CONNECTED)
        {
          wifiState = WIFI_STATE_CONNECTED;
        }
        else
        {
          wifiState = WIFI_STATE_CONNECTING;
          wifiConnectStartTime = now;
          WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        }
      }
      break;

    default:
      break;
  }
}

void sendTelemetryHTTP(const String &jsonPayload)
{
  if (WiFi.status() != WL_CONNECTED)
  {
    return;
  }

  HTTPClient http;
  String targetUrl = "http://" + String(BACKEND_HOST) + ":" + String(BACKEND_PORT) + "/api/telemetry";

  http.begin(targetUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-Device-Token", DEVICE_API_TOKEN);
  http.setTimeout(250); // Bound timeout to 250ms to prevent loop jitter

  int httpResponseCode = http.POST(jsonPayload);

  if (httpResponseCode > 0)
  {
    if (httpResponseCode == 200 || httpResponseCode == 201)
    {
      String responseBody = http.getString();
      // Inspect for highest-priority supervisory commands from backend
      if (responseBody.indexOf("\"action\":\"STOP\"") >= 0 || responseBody.indexOf("\"STOP\"") >= 0)
      {
        setMOSFET(false);
        systemState = STATE_IDLE;
        Serial.println("[WIFI_CMD] Supervisory STOP command executed immediately");
      }
      else if (responseBody.indexOf("\"action\":\"CLEAR\"") >= 0)
      {
        clearFault();
      }
    }
  }

  http.end();
}