# HERMES Hardware Architecture Specification

```
====================================================================================================
PLATFORM: HERMES v1 (Hardware Execution, Relaying, Measurement & Embedded Safety)
CLASS: Low-Voltage Multi-Cell Battery Testbed (4S1P LFP, 12.8V Nominal, 20Ah Format)
SAFETY LEVEL: Safety Extra-Low Voltage (SELV < 60V DC)
INDEPENDENT SAFETY: Analog Solid-State & Bimetallic Loop (Series Galvanic Interlock)
====================================================================================================
```

---

## 1. Topological Architecture

HERMES v1 is partitioned into three galvanically isolated and mutually protective functional blocks:

```
+--------------------------------------------------------------------------------------------------+
|                                    BLOCK 1: POWER PATH                                           |
|                                                                                                  |
|   [4S BATTERY MODULE] (10.0V - 14.6V)                                                            |
|          |                                                                                       |
|     [40A MIDI FUSE] (Primary short-circuit protection)                                           |
|          |                                                                                       |
|     [JD1912 40A AUTOMOTIVE RELAY / CONTACTOR]                                                   |
|          |                                                                                       |
|     +----+----+-------------------------------------+                                            |
|     |         |                                     |                                            |
|  [BYPASS]  [SERIES CELL STAGES 1-4]            [ELECTRONIC LOAD]                                 |
|  (IRLB8721) (IRLB8721 + IR2104 Driver)         (2x IRLB8721 + 100W 1.0Ω Chassis Resistor)        |
|     |         |                                     |                                            |
|     +----+----+-------------------------------------+                                            |
|          |                                                                                       |
|     [INA226 1mΩ CURRENT SHUNT]                                                                   |
|          |                                                                                       |
|        (GND)                                                                                     |
+--------------------------------------------------------------------------------------------------+
                                           ^
                                           | Contactor Coil Drive
+--------------------------------------------------------------------------------------------------+
|                               BLOCK 2: INDEPENDENT HARDWARE SAFETY CHAIN                         |
|                                                                                                  |
|   +12V Aux Supply                                                                                |
|          |                                                                                       |
|   [EMERGENCY STOP BUTTON] (Normally Closed, mechanical mushroom detent)                          |
|          |                                                                                       |
|   [KSD9700 THERMAL CUTOFF] (Normally Closed, 60°C bimetallic snap switch on cell busbar)         |
|          |                                                                                       |
|   [LM393 DUAL ANALOG WINDOW COMPARATOR] (10.0V UVP / 14.8V OVP via TL431 2.50V Ref)             |
|          |                                                                                       |
|   [TPS3823-33 HARDWARE WATCHDOG IC] (Active HIGH /RESET, 200ms timeout strobe from ESP32)       |
|          |                                                                                       |
|   [2N7002 MCU REQUEST SWITCH] (Gate driven by ESP32 GPIO 19)                                     |
|          |                                                                                       |
|   (CONTACTOR COIL TERMINAL +) -----> [Coil - to GND with 1N4007 Flyback Diode]                   |
+--------------------------------------------------------------------------------------------------+
                                           ^
                                           | Telemetry & Pulse Control
+--------------------------------------------------------------------------------------------------+
|                               BLOCK 3: EMBEDDED CONTROL & MEASUREMENT                            |
|                                                                                                  |
|   ESP32-S3-WROOM-1 (Dual-Core Xtensa LX7 @ 240MHz)                                               |
|     |                                                                                            |
|     +---> I2C Bus 1 (400kHz): ADS1115 #1 (Cells 1-2), ADS1115 #2 (Cells 3-4), INA226 (Current)  |
|     +---> 1-Wire Bus (GPIO 4): DS18B20 #1 (Cell surface), DS18B20 #2 (Ambient heatsink)         |
|     +---> PWM Timer (GPIO 18): IRLB8721 Electronic Load Gate Modulation (0 - 10A regulated)      |
|     +---> WDI Strobe (GPIO 21): 50ms periodic heartbeat to TPS3823                              |
|     +---> Fault ISR (GPIO 5): Hardware trip feedback from LM393 output (Active LOW)              |
|     +---> USB-CDC Serial: 115,200 baud JSON Telemetry & Command API to Python SECONDShift Host   |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Subsystem Functional Breakdown

### 2.1 Power Stage & Electronic Load
- **Current Sinking Capacity:** 0.0A to 10.0A continuous, up to 20.0A for short pulses ($\le 10\text{ s}$).
- **Energy Dissipation Stage:** Aluminum-housed 100W 1.0Ω wirewound power resistor clamped to an extruded heatsink with forced-air cooling.
- **Power Transistors:** Two parallel Vishay IRLB8721 N-channel MOSFETs ($V_{DS} = 30\text{V}, I_D = 62\text{A}, R_{DS(\text{on})} = 8.7\text{ m}\Omega$). Logic-level gate driving via IR2104 ensures gate saturation at $10\text{V}$ auxiliary supply.

### 2.2 Precision Analog Instrumentation
- **Cell Voltages:** Dual ADS1115 16-bit Sigma-Delta ADCs configured in differential mode across resistive dividers ($0.1\%$ metal-film resistors, 25ppm/°C). Resolution: $125\ \mu\text{V/LSB}$, full scale accuracy: $\pm 0.1\%$.
- **Current Shunt:** INA226 high-side/low-side monitor across a $1.0\text{ m}\Omega$ Vishay WSLP2512 surface mount resistor ($1\%$ tolerance, $3\text{W}$ rated). Current resolution: $2.5\ \mu\text{V} / 1\text{ m}\Omega = 2.5\text{ mA/LSB}$.
- **Temperature Sensing:** Dual Maxim Integrated DS18B20 1-Wire sensors with $0.0625^\circ\text{C}$ resolution and $\pm 0.5^\circ\text{C}$ calibrated accuracy between $-10^\circ\text{C}$ and $+85^\circ\text{C}$.

---

## 3. Physical Operating Specifications

| Parameter | Minimum | Nominal | Maximum | Units | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Operating Pack Voltage** | $10.0$ | $12.8$ | $14.6$ | V | Normal 4S LFP operating window |
| **Max Safe Terminal Voltage** | $9.8$ | — | $14.8$ | V | Independent analog trip thresholds |
| **Continuous Discharge Current** | $0.0$ | $5.0$ | $10.0$ | A | Regulated by electronic load |
| **Pulse Current ($\le 10\text{ s}$)**| $0.0$ | $10.0$ | $20.0$ | A | Current limited by fuse and 1.0Ω resistor |
| **Operating Temperature** | $15.0$ | $25.0$ | $45.0$ | °C | Forced convection active |
| **Thermal Cutoff Setpoint** | $57.0$ | $60.0$ | $63.0$ | °C | KSD9700 physical bimetallic trip |
| **Contactor Drop Time** | $8.0$ | $11.8$ | $15.0$ | ms | Measured on physical oscilloscope |
| **Total Build Cost** | — | **₹16,775** | **₹20,000** | INR | Complete bill of materials |
