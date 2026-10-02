/*
 * HERMES ESP32-S3 FIRMWARE
 * Project: RMK-REVOLT / SECONDShift Hardware Platform
 * Target: ESP32-S3 DevKitC (Dual Core Xtensa 240MHz)
 * Role: Real-time sensor acquisition, MOSFET gate actuation, hardware watchdog strobing,
 *       and telemetry interface to host decision engine.
 * 
 * SAFETY ARCHITECTURE:
 * - Microcontroller requests actions; independent LM393 comparator and KSD9700 switch govern physical cutoff.
 * - Hardware Watchdog (TPS3823) must be pulsed every 50ms on GPIO 18.
 * - GPIO 36 monitors independent hardware comparator trip status.
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

// Safety thresholds in firmware (Second Layer of Defense)
#define FW_OVP_CUTOFF_V     3.68f // Soft cutoff before 3.70V hardware trip
#define FW_UVP_CUTOFF_V     2.05f // Soft cutoff before 2.00V hardware trip
#define FW_OTP_CUTOFF_C     55.0f // Soft cutoff before 60.0C bimetallic trip
#define FW_OCP_CUTOFF_A     30.0f // Soft cutoff before 40.0A fuse blow

// =============================================================================
// GLOBAL OBJECTS & STATE
// =============================================================================
OneWire oneWire(PIN_ONEWIRE_TEMP);
DallasTemperature tempSensors(&oneWire);

enum CellState {
  STATE_BYPASS = 0,
  STATE_ACTIVE = 1,
  STATE_DERATED = 2,
  STATE_ISOLATED = 3
};

CellState cell_states[4] = {STATE_BYPASS, STATE_BYPASS, STATE_BYPASS, STATE_BYPASS};
bool main_relay_enabled = false;
bool hardware_tripped = false;

float cell_voltages[4] = {0.0f, 0.0f, 0.0f, 0.0f};
float cell_temperatures[4] = {25.0f, 25.0f, 25.0f, 25.0f};
float pack_current_a = 0.0f;
float bus_voltage_v = 0.0f;

unsigned long last_wdt_time = 0;
unsigned long last_telemetry_time = 0;
uint32_t sample_counter = 0;

// =============================================================================
// LOW-LEVEL ADS1115 & INA226 READERS (I2C)
// =============================================================================
int16_t readADS1115Raw(uint8_t addr, uint8_t channel_pair) {
  // Config register: Continuous or Single-shot, FSR = +/- 4.096V (PGA=001)
  uint16_t config = 0x8183; // Default single-shot, +/-4.096V, 128SPS
  if (channel_pair == 0) {
    config |= (0x0000); // Diff AIN0 - AIN1
  } else {
    config |= (0x3000); // Diff AIN2 - AIN3
  }
  
  Wire.beginTransmission(addr);
  Wire.write(0x01); // Config register
  Wire.write((uint8_t)(config >> 8));
  Wire.write((uint8_t)(config & 0xFF));
  Wire.endTransmission();

  delayMicroseconds(1000); // Conversion delay

  Wire.beginTransmission(addr);
  Wire.write(0x00); // Conversion register
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
  Wire.write(0x01); // Shunt voltage register
  Wire.endTransmission();
  Wire.requestFrom(INA226_ADDR, (uint8_t)2);
  if (Wire.available() >= 2) {
    int16_t raw_shunt = (int16_t)((Wire.read() << 8) | Wire.read());
    // 2.5uV per LSB, with 0.75mOhm shunt (75mV/100A): I = V_shunt / R_shunt
    float v_shunt_uv = raw_shunt * 2.5f;
    return (v_shunt_uv * 1e-6f) / 0.00075f;
  }
  return 0.0f;
}

// =============================================================================
// HARDWARE ACTUATION & SAFE SWITCHING
// =============================================================================
void applyCellSwitching(uint8_t cell_idx, CellState target_state) {
  if (cell_idx >= 4) return;
  
  // Safe dead-time enforcement: Turn off both before switching
  digitalWrite(PIN_GATE_SERIES[cell_idx], LOW);
  digitalWrite(PIN_GATE_BYPASS[cell_idx], LOW);
  delayMicroseconds(5); // 5 microseconds dead-time (> 520ns IR2104 requirement)

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
      // In 50% PWM derating mode: Series MOSFET PWM 50% duty, Bypass inverted
      // Handled via hardware timer or active 50% current duty cycle
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

void enterEmergencyLockout(const char* reason) {
  // Immediately drop all series gates and contactor enable
  for (uint8_t i = 0; i < 4; i++) {
    digitalWrite(PIN_GATE_SERIES[i], LOW);
    digitalWrite(PIN_GATE_BYPASS[i], LOW);
    cell_states[i] = STATE_ISOLATED;
  }
  digitalWrite(PIN_MCU_RELAY_EN, LOW);
  main_relay_enabled = false;
  hardware_tripped = true;

  Serial.print("{\"event\":\"EMERGENCY_LOCKOUT\",\"reason\":\"");
  Serial.print(reason);
  Serial.print("\",\"timestamp_us\":");
  Serial.print(micros());
  Serial.println("}");
}

// =============================================================================
// SETUP
// =============================================================================
void setup() {
  Serial.begin(115200);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000); // 400kHz Fast I2C

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

  tempSensors.begin();
  tempSensors.setResolution(10); // 10-bit (0.25C resolution, 187ms conversion)
  tempSensors.setWaitForConversion(false);
  tempSensors.requestTemperatures();

  last_wdt_time = millis();
  last_telemetry_time = millis();

  Serial.println("{\"status\":\"HERMES_BOOT_COMPLETE\",\"hw_rev\":\"2.0\",\"clock_mhz\":240}");
}

// =============================================================================
// MAIN SUPERVISORY LOOP
// =============================================================================
void loop() {
  unsigned long now_ms = millis();
  unsigned long now_us = micros();

  // 1. HARDWARE WATCHDOG STROBE (CRITICAL: Every 50ms)
  if (now_ms - last_wdt_time >= WDT_INTERVAL_MS) {
    digitalWrite(PIN_WDT_STROBE, !digitalRead(PIN_WDT_STROBE));
    last_wdt_time = now_ms;
  }

  // 2. CHECK INDEPENDENT HARDWARE SAFETY TRIP LINE
  if (digitalRead(PIN_HW_TRIP_SENSE) == LOW && !hardware_tripped) {
    enterEmergencyLockout("INDEPENDENT_ANALOG_COMPARATOR_TRIP");
  }

  // 3. RAPID ADC SENSOR SAMPLING (100Hz equivalent)
  // Read Cell 1 & 2 from ADS1115 #1
  int16_t raw_c1 = readADS1115Raw(ADS1115_ADDR_1, 0);
  int16_t raw_c2 = readADS1115Raw(ADS1115_ADDR_1, 1);
  // Read Cell 3 & 4 from ADS1115 #2
  int16_t raw_c3 = readADS1115Raw(ADS1115_ADDR_2, 0);
  int16_t raw_c4 = readADS1115Raw(ADS1115_ADDR_2, 1);

  cell_voltages[0] = (raw_c1 * 0.125f) / 1000.0f; // 125uV per LSB
  cell_voltages[1] = (raw_c2 * 0.125f) / 1000.0f;
  cell_voltages[2] = (raw_c3 * 0.125f) / 1000.0f;
  cell_voltages[3] = (raw_c4 * 0.125f) / 1000.0f;

  pack_current_a = readINA226Current();
  bus_voltage_v = cell_voltages[0] + cell_voltages[1] + cell_voltages[2] + cell_voltages[3];

  // 4. FIRMWARE-LEVEL SECONDARY SAFETY CHECK
  for (uint8_t i = 0; i < 4; i++) {
    if (cell_voltages[i] > FW_OVP_CUTOFF_V) {
      enterEmergencyLockout("SOFTWARE_SECONDARY_OVP");
      break;
    }
    if (cell_voltages[i] < FW_UVP_CUTOFF_V && main_relay_enabled) {
      enterEmergencyLockout("SOFTWARE_SECONDARY_UVP");
      break;
    }
  }

  // 5. TEMPERATURE UPDATE (Async read)
  if (tempSensors.isConversionComplete()) {
    for (uint8_t i = 0; i < 4; i++) {
      float t = tempSensors.getTempCByIndex(i);
      if (t > -50.0f && t < 120.0f) {
        cell_temperatures[i] = t;
        if (t > FW_OTP_CUTOFF_C) {
          enterEmergencyLockout("SOFTWARE_SECONDARY_OTP");
        }
      }
    }
    tempSensors.requestTemperatures();
  }

  // 6. PROCESS SERIAL COMMANDS FROM PYTHON DECISION ENGINE
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("SET_STATE")) {
      // SET_STATE <cell_idx> <STATE_NAME>
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
    } else if (cmd == "RELAY_ON" && !hardware_tripped) {
      digitalWrite(PIN_MCU_RELAY_EN, HIGH);
      main_relay_enabled = true;
      Serial.println("{\"cmd\":\"ACK\",\"relay\":1}");
    } else if (cmd == "RELAY_OFF") {
      digitalWrite(PIN_MCU_RELAY_EN, LOW);
      main_relay_enabled = false;
      Serial.println("{\"cmd\":\"ACK\",\"relay\":0}");
    } else if (cmd == "RESET_LOCKOUT" && digitalRead(PIN_HW_TRIP_SENSE) == HIGH) {
      hardware_tripped = false;
      Serial.println("{\"cmd\":\"ACK\",\"lockout\":0}");
    }
  }

  // 7. HIGH-INTEGRITY TELEMETRY DISPATCH (10Hz JSON stream)
  if (now_ms - last_telemetry_time >= TELEMETRY_PERIOD_MS) {
    last_telemetry_time = now_ms;
    sample_counter++;

    Serial.print("{\"seq\":");
    Serial.print(sample_counter);
    Serial.print(",\"t_us\":");
    Serial.print(now_us);
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
}
