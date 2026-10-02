# HERMES Hardware Specification

## 1. Physical Platform Overview

The **HERMES** (*Hardware Execution, Relaying, Measurement & Embedded Safety*) platform is a dedicated, low-voltage, bench-safe qualification testbed for multi-cell lithium-ion battery modules.

### Operating Envelope & Limits
- **Form Factor:** 4S1P LFP Battery Module (12.8V Nominal, 20Ah Nominal Capacity) / Equivalent Emulated Low-Voltage Modules.
- **Operating Voltage Range:** $10.0\text{ V}$ to $14.6\text{ V}$ (Continuous), $15.0\text{ V}$ absolute maximum.
- **Continuous Test Current:** Up to $10.0\text{ A}$ discharge, $5.0\text{ A}$ charge.
- **Pulse Test Current:** Up to $20.0\text{ A}$ (duration $\le 10\text{ s}$).
- **Operating Temperature Range:** $15^\circ\text{C}$ to $45^\circ\text{C}$ ambient; hardware cutoff at $60^\circ\text{C}$.
- **Electrical Safety Category:** Safety Extra-Low Voltage (SELV, $<60\text{ V}$ DC). Safe for open-bench educational and research operation.

---

## 2. Bill of Materials (BOM) Summary

The total prototype build cost is **₹16,775 INR** (within the ₹20,000 INR budget). Key components specified in [BOM.md](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/hardware/bom/BOM.md):

| Category | Component Part Number | Key Specifications | Interface | Safety Function | Cost (INR) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Compute** | ESP32-S3-WROOM-1 | Dual Xtensa LX7 @ 240MHz, 8MB Flash, 512KB SRAM | USB-C, SPI, I2C, GPIO | Measurement orchestration & telemetry | ₹650 |
| **Analog ADC** | ADS1115 | 16-bit Sigma-Delta ADC, programmable gain ($\pm 0.1\%$ FS) | I2C (0x48) | Precision module & cell voltage sensing | ₹280 |
| **Current Sense** | INA226 + 1mΩ Shunt | 16-bit bi-directional current/power monitor, 0.1% accuracy | I2C (0x40) | Current pulse monitoring & Coulomb counting | ₹350 |
| **Temperature** | DS18B20 (x2) | 1-Wire digital thermometer, $\pm 0.5^\circ\text{C}$ accuracy | 1-Wire (GPIO 4) | Surface thermal rise & ambient reference | ₹180 |
| **Hard Safety** | LM393 Dual Comparator | Dual open-collector analog comparator, 1.3µs response | Pure Analog | Autonomous over/under-voltage contactor trip | ₹45 |
| **Thermal Cutoff** | KSD9700 (60°C NC) | Bimetallic thermal switch, snap-action, 250V 5A rated | Direct Series | Autonomous contactor drop on cell overheat | ₹60 |
| **Watchdog** | TPS3823-33DBVT | Hardware supervisory IC, $200\text{ ms}$ fixed timeout | WDI (GPIO 21) | Drops contactor if firmware freezes | ₹120 |
| **Power Switch** | JD1912 12V 40A Relay | Automotive NO contactor, coil 12V 160mA | Coil Series Circuit | Primary galvanic disconnect | ₹180 |
| **Electronic Load**| IRLB8721 MOSFET (x2) | Logic-level N-Ch MOSFET (30V, 62A, $8.7\text{ m}\Omega$) + Heatsink | PWM (GPIO 18) | Programmable pulse current sink | ₹450 |
| **Load Resistor**| 100W 1.0Ω Aluminum Resistor | Wirewound chassis-mount, 5% tolerance | Power Circuit | Current limiting & heat dissipation | ₹450 |
| **Protection Fuse**| Midi / Bolt-down 40A Fuse | Fast-acting automotive blade fuse, 32VDC | Battery Terminal | Catastrophic short-circuit protection | ₹80 |

---

## 3. Independent Hardware Safety Chain

The physical safety layer operates **without any firmware, software, cloud, or wireless dependencies**.

```
                +-----------------------------------------+
                |        BATTERY PACK POSITIVE (12.8V)     |
                +-----------------------------------------+
                                     |
                                [40A FUSE]
                                     |
                                     v
                  +-------------------------------------+
                  |   CONTACTOR NO CONTACT (JD1912)     |
                  +-------------------------------------+
                                     |
                                     v
                              [LOAD STAGE]
                                     |
                                  (GND)

====================== COIL ENERGIZATION SAFETY CHAIN ======================

  +12V Auxiliary Supply
           |
     [EMERGENCY STOP (NC)]
           |
     [KSD9700 60°C THERMAL SNAP SWITCH (NC)]
           |
     [LM393 OVER-VOLTAGE TRANSISTOR SWITCH (NC)] (Trips if V > 14.8V)
           |
     [LM393 UNDER-VOLTAGE TRANSISTOR SWITCH (NC)] (Trips if V < 10.0V)
           |
     [TPS3823 HARDWARE WATCHDOG /RESET (ACTIVE HIGH)]
           |
     [ESP32 REQUEST PERMIT TRANSISTOR (GPIO 19)]
           |
           +-----------------------(CONTACTOR COIL)
                                         |
                                       (GND)
```

### Safety Chain Invariants:
1. **Series Logic:** All safety conditions are wired in **strict electrical series**. If any single sensor detects an excursion (or if wire breaks), current to the contactor coil is interrupted, dropping the contactor open within $<15\text{ ms}$.
2. **Watchdog Dropout:** The TPS3823 requires a positive transition on pin 21 every $\le 200\text{ ms}$. If the ESP32 code crashes, locks in an infinite loop, or loses power, the watchdog line goes low and de-energizes the contactor.
3. **Threshold Accuracy:** The LM393 voltage references are set by $0.1\%$ precision metal-film resistor dividers with a TL431 $2.500\text{ V}$ shunt reference.

---

## 4. ESP32-S3 Microcontroller Pinout Mapping

| ESP32-S3 GPIO | Function | Signal Direction | Connected Subsystem |
| :--- | :--- | :--- | :--- |
| **GPIO 1** | I2C SDA | Bidirectional | ADS1115 (0x48), INA226 (0x40) |
| **GPIO 2** | I2C SCL | Output (Clock) | ADS1115 (0x48), INA226 (0x40) |
| **GPIO 4** | 1-Wire DQ | Bidirectional | DS18B20 Cell & Ambient Temperature Sensors |
| **GPIO 18** | Load PWM Gate | Output | IR2104 Gate Driver / IRLB8721 Load MOSFET |
| **GPIO 19** | Contactor Request | Output | 2N7002 Gate (Requires series hardware permissive) |
| **GPIO 21** | Watchdog WDI | Output (Strobe) | TPS3823 WDI pin (50ms toggle heartbeat) |
| **GPIO 5** | Analog Trip State | Input (Interrupt) | LM393 Output Monitor (Active LOW on trip) |
| **GPIO 6** | E-Stop Sense | Input | Emergency Stop auxiliary contact status |
| **GPIO 7** | Status LED Green | Output | "System Normal / Ready" indicator |
| **GPIO 8** | Status LED Red | Output | "Fault / Safety Trip" indicator |

---

## 5. Thermal & Power Dissipation Engineering

- **Maximum Pulse Energy:** A $20\text{ A}$ discharge pulse at $12\text{ V}$ for $10\text{ s}$ dissipates $2400\text{ J}$ ($240\text{ W}$ peak).
- **MOSFET Protection:** Two IRLB8721 MOSFETs in parallel share the thermal load, mounted on an extruded aluminum heatsink ($1.5^\circ\text{C/W}$) with a forced-air $12\text{V}$ cooling fan.
- **Junction Temperature Margin:** Under worst-case $10\text{s}$ pulse, MOSFET junction temperature rises by $\Delta T_j \le 18.5^\circ\text{C}$, maintaining $T_j < 65^\circ\text{C}$ against a rated $175^\circ\text{C}$ threshold.
- **Continuous Shunt Dissipation:** At $10\text{ A}$, the $1\text{ m}\Omega$ current shunt dissipates $P = I^2 R = 100 \times 0.001 = 0.10\text{ W}$, well within the $3\text{ W}$ rating of the Vishay WSLP2512 surface-mount resistor.
