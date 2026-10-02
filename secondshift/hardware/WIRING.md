# HERMES Hardware Wiring & Harness Specification

```
====================================================================================================
DOCUMENT: HERMES Physical Wiring, Grounding & Electrical Assembly Guide
WIRE RATINGS: 10 AWG Silicone (Power Path, 40A Continuous) | 24 AWG Shielded (Instrumentation)
GROUNDING TOPOLOGY: Single-Point Star Ground (Chassis Earth Isolated)
PROTECTION: 40A Bolt-Down Main Fuse + 500mA Inline Fast-Blow Sense Fuses
====================================================================================================
```

---

## 1. Grounding Architecture (Single-Point Star Ground)

To prevent ground loops, sensor noise injection, and common-mode measurement offsets, the system enforces a strict **Single-Point Star Ground** topology:

```
                          [BATTERY PACK NEGATIVE TERMINAL]
                                         |
                                         v
                            +--------------------------+
                            |     STAR GROUND BUS      |
                            |   (Heavy Copper Lug M6)  |
                            +--------------------------+
                             /            |           \
                            /             |            \
                           v              v             v
                    [POWER STAGE]   [ANALOG SENSE]  [DIGITAL / MCU]
                    - Shunt Low     - ADS1115 GND   - ESP32 GND
                    - Load MOSFETs  - TL431 Ref GND - 5V Reg GND
                    - Heatsink Fan  - LM393 Pin 4   - Opto Return
```

### Grounding Invariants:
1. **Never Daisy-Chain Grounds:** Digital switching return currents from the ESP32 and PWM drivers must **never** flow through the analog measurement ground path.
2. **Current Shunt Placement:** The $1.0\text{ m}\Omega$ current shunt is placed directly between the load return and the Star Ground point.
3. **Chassis Isolation:** The aluminum chassis enclosure is connected to Earth ground (mains PE); test electronics float relative to Earth to prevent ground loops.

---

## 2. Power Harness Specifications

| Circuit Section | Wire Gauge | Insulation | Current Rating | Color Code | Termination |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Battery (+) to 40A Fuse** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Red | M6 Ring Lug (Crimped & Heat-shrunk) |
| **40A Fuse to Contactor COM** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Red | 6.3mm QC Spade / M5 Ring |
| **Contactor NO to Load Bank** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Red | M5 Ring Lug |
| **Load Resistor to MOSFET D** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Orange | Soldered / High-temp terminal |
| **MOSFET Source to Shunt (+)** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Black | M6 Lug to Shunt Pad |
| **Shunt (-) to Star Ground** | 10 AWG | Silicone ($200^\circ\text{C}$) | $40\text{ A}$ | Black | M6 Copper Star Stud |
| **Auxiliary +12V Power Bus** | 18 AWG | PVC ($105^\circ\text{C}$) | $5\text{ A}$ | Yellow | Ferrule to Screw Terminal |
| **Auxiliary Ground Return** | 18 AWG | PVC ($105^\circ\text{C}$) | $5\text{ A}$ | Black | Ferrule to Star Ground |

---

## 3. Instrumentation & Sense Harness

All voltage sensing taps connect directly to individual cell terminals through **inline 500mA fast-acting glass fuses** located within $50\text{ mm}$ of the battery terminals. This prevents any wiring harness fire in the event of an accidental wire pinch or short to ground.

| Channel | Source Terminal | Sense Wire Gauge | In-line Protection | Destination |
| :--- | :--- | :--- | :--- | :--- |
| **Cell 1 (+)** | Battery Module Pin 1 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #1 Channel AIN0 |
| **Cell 1 (-)** | Battery Module Pin 0 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #1 Channel AIN1 |
| **Cell 2 (+)** | Battery Module Pin 2 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #1 Channel AIN2 |
| **Cell 2 (-)** | Battery Module Pin 1 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #1 Channel AIN3 |
| **Cell 3 (+)** | Battery Module Pin 3 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #2 Channel AIN0 |
| **Cell 3 (-)** | Battery Module Pin 2 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #2 Channel AIN1 |
| **Cell 4 (+)** | Battery Module Pin 4 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #2 Channel AIN2 |
| **Cell 4 (-)** | Battery Module Pin 3 | 24 AWG Twisted Pair | 500mA Fast Fuse | ADS1115 #2 Channel AIN3 |
| **INA226 Shunt (+)**| Low-side Shunt In | 24 AWG Shielded Pair | 500mA Fast Fuse | INA226 $V_{\text{IN}+}$ |
| **INA226 Shunt (-)**| Low-side Shunt Out | 24 AWG Shielded Pair | 500mA Fast Fuse | INA226 $V_{\text{IN}-}$ |
| **DS18B20 1-Wire** | Pack Surface Sensor | 24 AWG 3-Core Shielded | — | ESP32 GPIO 4 + 4.7kΩ Pullup |

---

## 4. Pre-Power-Up Verification Checklist

Before connecting any live battery module to the HERMES platform, the validation engineer must execute and sign off the following checklist:

- [ ] **Check 1: Visual Continuity & Insulation:** Inspect all 10 AWG high-current crimps and silicone insulation. Verify heat-shrink covers all exposed copper.
- [ ] **Check 2: Star Ground Isolation:** Using a DMM in continuity mode, verify resistance between Star Ground and chassis earth is $>10\text{ M}\Omega$ (isolated).
- [ ] **Check 3: Fuse Verification:** Confirm 40A Midi bolt-down fuse is securely tightened ($4.5\text{ Nm}$) and all five 500mA sense fuses are installed in fuse holders.
- [ ] **Check 4: Flyback Diode Polarity:** Confirm 1N4007 diode cathode (striped end) connects to $+12\text{V}$ auxiliary and anode connects to contactor coil drive transistor collector.
- [ ] **Check 5: Emergency Stop Functionality:** Verify depressing the red mushroom E-Stop button breaks continuity to contactor coil drive.
- [ ] **Check 6: Sense Tap Polarity:** With a laboratory power supply set to $12.8\text{V}$ connected to the pack input, verify ADS1115 inputs measure positive differential voltages ($+3.20\text{V}$ per cell).
