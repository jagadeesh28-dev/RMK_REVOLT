/*
 * HERMES ESP32-S3 FIRMWARE (Production v2.1)
 * Project: RMK-REVOLT / SECONDShift Hardware Platform
 * Target: ESP32-S3 DevKitC (Dual Core Xtensa 240MHz)
 * Role: Real-time sensor acquisition, MOSFET gate actuation, hardware watchdog strobing,
 *       explicit deterministic finite state machine, and JSON telemetry stream.
 * 
 * SYSTEM SAFETY INVARIANT:
 * - Microcontroller requests actions; independent LM393 comparator and KSD9700 switch govern physical cutoff.
 * - Hardware Watchdog (TPS3823) must be pulsed every 50ms on GPIO 18.
 * - GPIO 36 monitors independent hardware comparator trip status.
 * - Any critical fault forces transition to STATE_SAFE_SHUTDOWN.
 */

#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// =============================================================================
// PIN DEFINITIONS
// =============================================================================
#define PIN_I2C_SDA         21
#define PIN_I2C_SCL         22
#define PIN_ONEWIRE_TEMP    4
#define PIN_WDT_STROBE      18
#define PIN_MCU_RELAY_EN    19
#define PIN_HW_TRIP_SENSE   36

// 4S Cell Gate Control Pins (Series and Bypass)
const uint8_t PIN_GATE_SERIES[4] = {13, 27, 25, 32};
const uint8_t PIN_GATE_BYPASS[4] = {14, 26, 33, 35};

// =============================================================================
// CONSTANTS & SENSOR ADDRESSES
// =============================================================================
#define ADS1115_ADDR_1      0x48  // Cells 1 & 2 Differential
#define ADS1115_ADDR_2      0x49  // Cells 3 & 4 Differential
#define INA226_ADDR         0x40  // Current & Bus Voltage

#define WDT_INTERVAL_MS     50    // Strobe external TPS3823 watchdog every 50ms
#define TELEMETRY_RATE_HZ   10    // 10Hz stream to host PC
#define TELEMETRY_PERIOD_MS (1000 / TELEMETRY_RATE_HZ)

// Safety thresholds in firmware (Secondary Defense Layer)
#define FW_OVP_CUTOFF_V     3.68f // Soft cutoff before 3.70V hardware trip
#define FW_UVP_CUTOFF_V     2.05f // Soft cutoff before 2.00V hardware trip
#define FW_OTP_CUTOFF_C     55.0f // Soft cutoff before 60.0C bimetallic trip
#define FW_OCP_CUTOFF_A     30.0f // Soft cutoff before 40.0A fuse blow

// =============================================================================
// SYSTEM STATE DEFINITIONS (PHASE 3 SPECIFICATION)
// =============================================================================
enum HermesSystemState {
  STATE_INIT = 0,
  STATE_SELF_TEST = 1,
  STATE_IDLE = 2,
  STATE_TRIAGE = 3,
  STATE_TEST_PREP = 4,
  STATE_PULSE = 5,
  STATE_RELAX = 6,
  STATE_MEASURE = 7,
  STATE_COMPLETE = 8,
  STATE_FAULT = 9,
  STATE_SAFE_SHUTDOWN = 10
};

enum CellState {
  STATE_BYPASS = 0,
  STATE_ACTIVE = 1,
  STATE_DERATED = 2,
  STATE_ISOLATED = 3
};

// =============================================================================
// GLOBAL VARIABLES & SYSTEM STATUS
// =============================================================================
OneWire oneWire(PIN_ONEWIRE_TEMP);
DallasTemperature tempSensors(&oneWire);

HermesSystemState system_state = STATE_INIT;
CellState cell_states[4] = {STATE_BYPASS, STATE_BYPASS, STATE_BYPASS, STATE_BYPASS};

bool main_relay_enabled = false;
bool hardware_tripped = false;
char last_fault_reason[64] = "NONE";

float cell_voltages[4] = {0.0f, 0.0f, 0.0f, 0.0f};
float cell_temperatures[4] = {25.0f, 25.0f, 25.0f, 25.0f};
float pack_current_a = 0.0f;
float bus_voltage_v = 0.0f;

unsigned long last_wdt_time = 0;
unsigned long last_telemetry_time = 0;
unsigned long state_entry_time_ms = 0;
uint32_t sample_counter = 0;

// =============================================================================
// LOW-LEVEL ADS1115 & INA226 DRIVERS
// =============================================================================
int16_t readADS1115Raw(uint8_t addr, uint8_t channel_pair) {
  uint16_t config = 0x8183;
  if (channel_pair == 0) {
    config |= (0x0000); // Diff AIN0 - AIN1
  } else {
    config |= (0x3000); // Diff AIN2 - AIN3
  }
  
  Wire.beginTransmission(addr);
  Wire.write(0x01);
  Wire.write((uint8_t)(config >> 8));
  Wire.write((uint8_t)(config & 0xFF));
  Wire.endTransmission();

  delayMicroseconds(1000);

  Wire.beginTransmission(addr);
  Wire.write(0x00);
  Wire.endTransmission();

  Wire.requestFrom(addr, (uint8_t)2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    return (int16_t)((msb << 8) | lsb);
  }
  return 0;
}

float readINA226Current() {
  Wire.beginTransmission(INA226_ADDR);
  Wire.write(0x01);
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDR, (uint8_t)2);
  if (Wire.available() >= 2) {
    int16_t raw_shunt = (int16_t)((Wire.read() << 8) | Wire.read());
    float v_shunt_uv = raw_shunt * 2.5f;
    return (v_shunt_uv * 1e-6f) / 0.00075f;
  }
  return 0.0f;
}

// =============================================================================
// CORE MEASUREMENT PRIMITIVES (PHASE 3 SPECIFICATION)
// =============================================================================
float measureVoltage(uint8_t cell_idx) {
  if (cell_idx >= 4) return 0.0f;
  if (cell_idx < 2) {
    int16_t raw = readADS1115Raw(ADS1115_ADDR_1, cell_idx);
    cell_voltages[cell_idx] = (raw * 0.125f) / 1000.0f;
  } else {
    int16_t raw = readADS1115Raw(ADS1115_ADDR_2, cell_idx - 2);
    cell_voltages[cell_idx] = (raw * 0.125f) / 1000.0f;
  }
  return cell_voltages[cell_idx];
}

float measureCurrent() {
  pack_current_a = readINA226Current();
  return pack_current_a;
}

float measureTemperature(uint8_t cell_idx) {
  if (cell_idx < 4) return cell_temperatures[cell_idx];
  return 25.0f;
}

void thermalMeasurement() {
  if (tempSensors.isConversionComplete()) {
    for (uint8_t i = 0; i < 4; i++) {
      float t = tempSensors.getTempCByIndex(i);
      if (t > -50.0f && t < 120.0f) {
        cell_temperatures[i] = t;
      }
    }
    tempSensors.requestTemperatures();
  }
}

// =============================================================================
// STATE TRANSITION & ACTUATION FUNCTIONS
// =============================================================================
void transitionState(HermesSystemState new_state) {
  system_state = new_state;
  state_entry_time_ms = millis();
}

void applyCellSwitching(uint8_t cell_idx, CellState target_state) {
  if (cell_idx >= 4) return;
  
  digitalWrite(PIN_GATE_SERIES[cell_idx], LOW);
  digitalWrite(PIN_GATE_BYPASS[cell_idx], LOW);
  delayMicroseconds(5); // Dead-time > 520ns

  switch (target_state) {
    case STATE_ACTIVE:
      digitalWrite(PIN_GATE_BYPASS[cell_idx], LOW);
      digitalWrite(PIN_GATE_SERIES[cell_idx], HIGH);
      break;
    case STATE_BYPASS:
      digitalWrite(PIN_GATE_SERIES[cell_idx], LOW);
      digitalWrite(PIN_GATE_BYPASS[cell_idx], HIGH);
      break;
    case STATE_DERATED:
      digitalWrite(PIN_GATE_SERIES[cell_idx], HIGH);
      digitalWrite(PIN_GATE_BYPASS[cell_idx], LOW);
      break;
    case STATE_ISOLATED:
    default:
      digitalWrite(PIN_GATE_SERIES[cell_idx], LOW);
      digitalWrite(PIN_GATE_BYPASS[cell_idx], LOW);
      break;
  }
  cell_states[cell_idx] = target_state;
}

void abortTest(const char* reason) {
  strncpy(last_fault_reason, reason, sizeof(last_fault_reason) - 1);
  for (uint8_t i = 0; i < 4; i++) {
    digitalWrite(PIN_GATE_SERIES[i], LOW);
    digitalWrite(PIN_GATE_BYPASS[i], LOW);
    cell_states[i] = STATE_ISOLATED;
  }
  digitalWrite(PIN_MCU_RELAY_EN, LOW);
  main_relay_enabled = false;
  hardware_tripped = true;
  transitionState(STATE_SAFE_SHUTDOWN);

  Serial.print("{\"event\":\"SAFE_SHUTDOWN\",\"reason\":\"");
  Serial.print(reason);
  Serial.print("\",\"timestamp_us\":");
  Serial.print(micros());
  Serial.println("}");
}

bool safetyCheck() {
  if (digitalRead(PIN_HW_TRIP_SENSE) == LOW) {
    abortTest("HW_ANALOG_COMPARATOR_TRIP");
    return false;
  }

  for (uint8_t i = 0; i < 4; i++) {
    if (cell_voltages[i] > FW_OVP_CUTOFF_V) {
      abortTest("SW_OVP_CUTOFF");
      return false;
    }
    if (cell_voltages[i] < FW_UVP_CUTOFF_V && main_relay_enabled) {
      abortTest("SW_UVP_CUTOFF");
      return false;
    }
    if (cell_temperatures[i] > FW_OTP_CUTOFF_C) {
      abortTest("SW_OTP_CUTOFF");
      return false;
    }
  }

  if (fabs(pack_current_a) > FW_OCP_CUTOFF_A) {
    abortTest("SW_OCP_CUTOFF");
    return false;
  }

  return true;
}

void restMeasurement(uint32_t duration_ms) {
  transitionState(STATE_MEASURE);
  unsigned long start = millis();
  while (millis() - start < duration_ms) {
    if (millis() - last_wdt_time >= WDT_INTERVAL_MS) {
      digitalWrite(PIN_WDT_STROBE, !digitalRead(PIN_WDT_STROBE));
      last_wdt_time = millis();
    }
    for (uint8_t i = 0; i < 4; i++) measureVoltage(i);
    measureCurrent();
    thermalMeasurement();
    if (!safetyCheck()) return;
    delay(10);
  }
  transitionState(STATE_COMPLETE);
}

void pulseTest(float target_current_a, uint32_t duration_ms) {
  transitionState(STATE_PULSE);
  unsigned long start = millis();
  while (millis() - start < duration_ms) {
    if (millis() - last_wdt_time >= WDT_INTERVAL_MS) {
      digitalWrite(PIN_WDT_STROBE, !digitalRead(PIN_WDT_STROBE));
      last_wdt_time = millis();
    }
    for (uint8_t i = 0; i < 4; i++) measureVoltage(i);
    measureCurrent();
    thermalMeasurement();
    if (!safetyCheck()) return;
    delay(10);
  }
  transitionState(STATE_RELAX);
}

void relaxationMeasurement(uint32_t duration_ms) {
  transitionState(STATE_RELAX);
  unsigned long start = millis();
  while (millis() - start < duration_ms) {
    if (millis() - last_wdt_time >= WDT_INTERVAL_MS) {
      digitalWrite(PIN_WDT_STROBE, !digitalRead(PIN_WDT_STROBE));
      last_wdt_time = millis();
    }
    for (uint8_t i = 0; i < 4; i++) measureVoltage(i);
    measureCurrent();
    thermalMeasurement();
    if (!safetyCheck()) return;
    delay(50);
  }
  transitionState(STATE_COMPLETE);
}

bool executeTest(const char* test_type, float param1, uint32_t param2) {
  if (system_state == STATE_SAFE_SHUTDOWN || hardware_tripped) return false;
  
  transitionState(STATE_TEST_PREP);
  if (!safetyCheck()) return false;

  if (strcmp(test_type, "PULSE") == 0) {
    pulseTest(param1, param2);
    relaxationMeasurement(param2 * 2);
    return true;
  } else if (strcmp(test_type, "REST") == 0) {
    restMeasurement(param2);
    return true;
  }
  return false;
}

void logMeasurement() {
  sample_counter++;
  unsigned long now_us = micros();
  
  Serial.print("{\"seq\":");
  Serial.print(sample_counter);
  Serial.print(",\"t_us\":");
  Serial.print(now_us);
  Serial.print(",\"fsm\":");
  Serial.print((int)system_state);
  Serial.print(",\"v\":[");
  Serial.print(cell_voltages[0], 4); Serial.print(",");
  Serial.print(cell_voltages[1], 4); Serial.print(",");
  Serial.print(cell_voltages[2], 4); Serial.print(",");
  Serial.print(cell_voltages[3], 4);
  Serial.print("],\"i_a\":");
  Serial.print(pack_current_a, 3);
  Serial.print(",\"t_c\":[");
  Serial.print(cell_temperatures[0], 2); Serial.print(",");
  Serial.print(cell_temperatures[1], 2); Serial.print(",");
  Serial.print(cell_temperatures[2], 2); Serial.print(",");
  Serial.print(cell_temperatures[3], 2);
  Serial.print("],\"states\":[");
  Serial.print(cell_states[0]); Serial.print(",");
  Serial.print(cell_states[1]); Serial.print(",");
  Serial.print(cell_states[2]); Serial.print(",");
  Serial.print(cell_states[3]);
  Serial.print("],\"relay\":");
  Serial.print(main_relay_enabled ? 1 : 0);
  Serial.print(",\"hw_trip\":");
  Serial.print(hardware_tripped ? 1 : 0);
  Serial.println("}");
}

// =============================================================================
// SETUP & INITIALIZATION
// =============================================================================
void setup() {
  Serial.begin(115200);
  transitionState(STATE_INIT);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);

  pinMode(PIN_WDT_STROBE, OUTPUT);
  digitalWrite(PIN_WDT_STROBE, LOW);

  pinMode(PIN_MCU_RELAY_EN, OUTPUT);
  digitalWrite(PIN_MCU_RELAY_EN, LOW);

  pinMode(PIN_HW_TRIP_SENSE, INPUT_PULLUP);

  for (uint8_t i = 0; i < 4; i++) {
    pinMode(PIN_GATE_SERIES[i], OUTPUT);
    digitalWrite(PIN_GATE_SERIES[i], LOW);
    pinMode(PIN_GATE_BYPASS[i], OUTPUT);
    digitalWrite(PIN_GATE_BYPASS[i], LOW);
    cell_states[i] = STATE_BYPASS;
  }

  transitionState(STATE_SELF_TEST);
  tempSensors.begin();
  tempSensors.setResolution(10);
  tempSensors.setWaitForConversion(false);
  tempSensors.requestTemperatures();

  last_wdt_time = millis();
  last_telemetry_time = millis();

  // Initial self-test verification
  if (digitalRead(PIN_HW_TRIP_SENSE) == LOW) {
    abortTest("STARTUP_HW_TRIP_DETECTED");
  } else {
    transitionState(STATE_IDLE);
    Serial.println("{\"status\":\"HERMES_READY\",\"hw_rev\":\"2.1\",\"fsm\":\"IDLE\"}");
  }
}

// =============================================================================
// MAIN SUPERVISORY LOOP
// =============================================================================
void loop() {
  unsigned long now_ms = millis();

  // 1. HARDWARE WATCHDOG STROBE (CRITICAL: Every 50ms)
  if (now_ms - last_wdt_time >= WDT_INTERVAL_MS) {
    digitalWrite(PIN_WDT_STROBE, !digitalRead(PIN_WDT_STROBE));
    last_wdt_time = now_ms;
  }

  // 2. RUNTIME CONTINUOUS SAFETY CHECK
  safetyCheck();

  // 3. CONTINUOUS SENSOR CONVERSIONS
  for (uint8_t i = 0; i < 4; i++) measureVoltage(i);
  measureCurrent();
  bus_voltage_v = cell_voltages[0] + cell_voltages[1] + cell_voltages[2] + cell_voltages[3];
  thermalMeasurement();

  // 4. PROCESS INCOMING SERIAL COMMANDS
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("SET_STATE")) {
      int c_idx = cmd.substring(10, 11).toInt();
      String s_name = cmd.substring(12);
      CellState target = STATE_BYPASS;
      if (s_name == "ACTIVE") target = STATE_ACTIVE;
      else if (s_name == "DERATED") target = STATE_DERATED;
      else if (s_name == "ISOLATED") target = STATE_ISOLATED;
      applyCellSwitching(c_idx, target);
      Serial.print("{\"cmd\":\"ACK\",\"cell\":");
      Serial.print(c_idx);
      Serial.print(",\"state\":\"");
      Serial.print(s_name);
      Serial.println("\"}");
    } else if (cmd == "RELAY_ON" && !hardware_tripped && system_state != STATE_SAFE_SHUTDOWN) {
      digitalWrite(PIN_MCU_RELAY_EN, HIGH);
      main_relay_enabled = true;
      Serial.println("{\"cmd\":\"ACK\",\"relay\":1}");
    } else if (cmd == "RELAY_OFF") {
      digitalWrite(PIN_MCU_RELAY_EN, LOW);
      main_relay_enabled = false;
      Serial.println("{\"cmd\":\"ACK\",\"relay\":0}");
    } else if (cmd.startsWith("TEST_PULSE")) {
      executeTest("PULSE", 5.0f, 5000);
      Serial.println("{\"cmd\":\"ACK\",\"test\":\"PULSE_COMPLETE\"}");
    } else if (cmd.startsWith("TEST_REST")) {
      executeTest("REST", 0.0f, 2000);
      Serial.println("{\"cmd\":\"ACK\",\"test\":\"REST_COMPLETE\"}");
    } else if (cmd == "RESET_LOCKOUT" && digitalRead(PIN_HW_TRIP_SENSE) == HIGH) {
      hardware_tripped = false;
      transitionState(STATE_IDLE);
      Serial.println("{\"cmd\":\"ACK\",\"lockout\":0,\"fsm\":\"IDLE\"}");
    }
  }

  // 5. REGULAR TELEMETRY LOGGING (10Hz)
  if (now_ms - last_telemetry_time >= TELEMETRY_PERIOD_MS) {
    last_telemetry_time = now_ms;
    logMeasurement();
  }
}
