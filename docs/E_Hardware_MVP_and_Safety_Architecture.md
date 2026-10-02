# ARTIFACT E: Hardware MVP, Bill of Materials & Safety Architecture
**Project:** RMK-REVOLT — EV Battery Circularity Challenge  
**Hardware Class:** 4-Cell Low-Voltage LFP System (12.8V nominal, 20Ah–50Ah lab prototype)  
**Target Hardware Budget:** ₹10,000 – ₹20,000 INR

---

## 1. Safety Architecture: Hard Safety Layer vs Decision Layer

A non-negotiable architectural rule governs RMK-REVOLT:
$$\mathbf{THE\ AI\ /\ DECISION\ ALGORITHM\ CANNOT\ OVERRIDE\ HARD\ HARDWARE\ SAFETY.}$$

```
   ┌───────────────────────────────────────────────────────────────┐
   │                     HARD SAFETY LAYER                         │
   │  - Hardware Analog Comparators (LM393)                        │
   │  - Fast Pyrofuse / Fast-Blow Ceramic Fuse (40A)               │
   │  - Hardware Thermal Bimetallic Switch (65°C Cutoff)           │
   │  - Hardware Watchdog Timer (External TPS3823)                 │
   │                                                               │
   │  [Any Fault: OVP > 3.70V, UVP < 2.0V, OTP > 60°C, OCP > 45A]   │
   │                               │                               │
   │                               ▼                               │
   │               [ IMMEDIATE HARD SHUTDOWN RELAY ]               │
   └───────────────────────────────┬───────────────────────────────┘
                                   │ (Enables Power Bus only if SAFE)
                                   ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                  INTELLIGENT DECISION LAYER                   │
   │  - Microcontroller: ESP32-S3 (Dual Xtensa 240MHz)             │
   │  - Sensing: 16-Bit ADS1115 (ADC) + INA226 (Current Shunt)     │
   │  - Actuation: Half-Bridge Gate Drivers (IR2104) + Power MOSFETs│
   │  - Algorithms: TRIAGE Gates, SECONDShift VOI, HERMES Controller│
   └───────────────────────────────────────────────────────────────┘
```

### Fail-Safe State Matrix:
| Fault Type | Hardware Trigger / Detector | Immediate Hard Action | Decision Engine Action | Recovery Protocol |
| :--- | :--- | :--- | :--- | :--- |
| **Over-Voltage (OVP)** | $V_{cell} \ge 3.70$ V (Analog Ref) | De-energize Series Contactor | Log OVP Event $\to$ Set Module state to `ISOLATED` | Manual reset button only |
| **Under-Voltage (UVP)** | $V_{cell} \le 2.00$ V (Analog Ref) | Open Load Gate | Disallow Discharge $\to$ Set `ISOLATED` | Controlled trickle charger |
| **Over-Current (OCP)** | $I \ge 45.0$ A ($>50\text{ ms}$) | Hardware Fast Fuse blows | Log OCP $\to$ Open all switches | Fuse replacement & inspect |
| **Over-Temp (OTP)** | $T_{cell} \ge 60^\circ\text{C}$ (NTC / Switch) | Trip Series Relay | Command `ISOLATED` $\to$ Engage cooling | Cool below 40°C & inspect |
| **Sensor Disconnect** | $V_{read} = 0.0$ V or Pull-up High | Hardware Window Trip | Freeze action $\to$ Transition string to `BYPASS` | Check wiring & re-calibrate |
| **MOSFET Gate Short** | Gate-Drain punch-through | Desaturation / Fuse Trip | Isolate affected string module | Board repair / swap module |

---

## 2. Hardware Architecture & Pin-Level Implementation

### System Block Diagram:
```
           [ 12.8V PACK BUS: 4S LFP CELLS ]
     ┌───────────┬───────────┬───────────┬───────────┐
     │ Cell 1    │ Cell 2    │ Cell 3    │ Cell 4    │
     │ 3.2V LFP  │ 3.2V LFP  │ 3.2V LFP  │ 3.2V LFP  │
     └─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┘
           │           │           │           │
     ┌─────▼─────┬─────▼─────┬─────▼─────┬─────▼─────┐
     │ H.E.R.M.E.S Switchboard: 4x Dual N-Ch Power MOSFETs   │
     │ (Top: Series conduction | Bottom: Bypass path)        │
     └─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┘
           │           │           │           │
     ┌─────▼───────────▼───────────▼───────────▼─────┐
     │ Isolated High/Low Side Gate Drivers (IR2104)  │
     └───────────────────────┬───────────────────────┘
                             │ (PWM & GPIO Control)
     ┌───────────────────────▼───────────────────────┐
     │        CENTRAL CONTROLLER: ESP32-S3           │
     │  - I2C Bus 1: 4x ADS1115 (Differential Volt)  │
     │  - I2C Bus 2: INA226 (Pack Current Shunt)     │
     │  - 1-Wire Bus: 4x DS18B20 (Cell Temperatures) │
     │  - SPI / UART: Telemetry & Host PC Interface  │
     └───────────────────────────────────────────────┘
```

### Pin-Level Wiring Map:
| ESP32-S3 Pin | Peripheral / Signal | Function | Electrical Interface |
| :--- | :--- | :--- | :--- |
| **GPIO 21** | I2C SDA (Sensors) | ADS1115 ADC data + INA226 Current | 3.3V Logic, 4.7k$\Omega$ pullup |
| **GPIO 22** | I2C SCL (Sensors) | ADS1115 ADC clock + INA226 Clock | 3.3V Logic, 4.7k$\Omega$ pullup |
| **GPIO 4** | 1-Wire DQ (Temp) | 4x DS18B20 digital thermal sensors | 3.3V Logic, 4.7k$\Omega$ pullup |
| **GPIO 13** | Gate_1_Series | Cell 1 Series MOSFET Gate | Via IR2104 Gate Driver (12V Gate) |
| **GPIO 14** | Gate_1_Bypass | Cell 1 Bypass MOSFET Gate | Via IR2104 Gate Driver (12V Gate) |
| **GPIO 27** | Gate_2_Series | Cell 2 Series MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 26** | Gate_2_Bypass | Cell 2 Bypass MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 25** | Gate_3_Series | Cell 3 Series MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 33** | Gate_3_Bypass | Cell 3 Bypass MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 32** | Gate_4_Series | Cell 4 Series MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 35** | Gate_4_Bypass | Cell 4 Bypass MOSFET Gate | Via IR2104 Gate Driver |
| **GPIO 18** | HARD_SHUTDOWN_IN | Emergency Stop Loop Sense | Hardware Interrupt Pin |
| **GPIO 19** | RELAY_MAIN_EN | Main Pack Contactor Enable | Active High 3.3V $\to$ Relay Driver |

---

## 3. Bill of Materials (BOM) — Indian Rupee Procurement

Target budget: **₹10,000 – ₹20,000**. Sourced from accessible Indian vendors (Robu.in, ElectronicsComp, MakerBazar).

| Component Description | Part Number / Model | Quantity | Unit Price (INR) | Total Cost (INR) | Sourced Vendor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Main Microcontroller Board** | ESP32-S3 DevKitC (16MB Flash, 8MB PSRAM) | 1 | ₹850 | ₹850 | Robu.in |
| **Precision Voltage ADC** | ADS1115 16-Bit 4-Channel I2C ADC Module | 2 | ₹320 | ₹640 | ElectronicsComp |
| **Pack Current & Power Sensor** | INA226 Bi-Directional High-Side Sensor + 100A 75mV Shunt | 1 | ₹420 | ₹420 | Robu.in |
| **Digital Temperature Sensors** | DS18B20 Waterproof Stainless Probe (1-Wire) | 4 | ₹110 | ₹440 | MakerBazar |
| **Power MOSFETs (Switching)** | IRLB8721 N-Channel (30V, 62A, $R_{ds(on)} = 8.7\text{ m}\Omega$) | 8 | ₹65 | ₹520 | ElectronicsComp |
| **MOSFET Gate Drivers** | IR2104 Half-Bridge Gate Driver ICs | 4 | ₹55 | ₹220 | ElectronicsComp |
| **Main DC Contactor / Relay** | 12V 40A Automotive Heavy Duty Sealed Relay | 2 | ₹180 | ₹360 | Robu.in |
| **Analog Comparator Board** | LM393 Dual Differential Comparator (Hardware OVP/UVP) | 2 | ₹45 | ₹90 | MakerBazar |
| **Safety Fuses & Holders** | 40A Midi Bolt-Down Fast-Blow DC Fuses | 3 | ₹60 | ₹180 | ElectronicsComp |
| **Emergency Push Button** | 22mm Industrial E-Stop Twist-to-Reset Button | 1 | ₹250 | ₹250 | Amazon India |
| **DC Electronic Load / Test Resistors** | 100W 1$\Omega$ Wirewound Aluminum Clad Power Resistors | 4 | ₹220 | ₹880 | Robu.in |
| **4S LFP Cells (Lab Equivalents)** | 3.2V 25Ah/50Ah Prismatic or 32700 Cylindrical 4S Pack | 4 | ₹2,200 | ₹8,800 | BatteryJunction / Robu |
| **Custom PCB Fabrication** | 2-Layer 2oz Copper Power Board (JLCPCB / PCBWay) | 1 | ₹1,800 | ₹1,800 | JLCPCB India Delivery |
| **Wiring, Enclosure & Terminals** | 10 AWG Silicone Wire, Copper Busbars, Terminal Blocks | 1 set | ₹1,200 | ₹1,200 | Local Electrical Market |
| **TOTAL HARDWARE PROTOTYPE COST** | | | | **₹16,650** | **WITHIN BUDGET** |

---

## 4. Staged Hardware Validation Protocol (Levels 0 to 7)

To prevent catastrophic battery damage, hardware testing strictly proceeds in stages:

- **LEVEL 0: Sensor & ADC Calibration (Zero Live Current)**
  - Validate ADS1115 against 6.5-digit bench DMM across 0.0V–4.0V reference voltages. Target: Max voltage error $\le 2.0\text{ mV}$.
  - Validate INA226 zero-current offset and thermal sensor readings at room ambient.

- **LEVEL 1: Single Inactive Cell Passive Measurement**
  - Connect one safe 3.2V cell. Verify open-circuit voltage reading, rest relaxation drift calculation, and noise floor.

- **LEVEL 2: Single-Channel Switching & Gate Driver Test**
  - Verify IR2104 high-side and low-side gate drive waveform with an oscilloscope (dead-time insertion $\ge 500\text{ ns}$ to prevent shoot-through).

- **LEVEL 3: Controlled Load Step on Single Cell**
  - Switch on 100W power resistor (5A discharge). Verify immediate ohmic drop $\Delta V$ corresponds to true $R_0$.

- **LEVEL 4: Dynamic Bypass Demonstration (Two-Cell String)**
  - Run Cell 1 in series with Cell 2. Send command to BYPASS Cell 1.
  - Verify Cell 1 terminal current drops to zero while string current continues through bypass MOSFET without sparking or arc-over.

- **LEVEL 5: Four-Module Pack Assembly & Thermal Step**
  - Assemble full 4S (12.8V) pack. Apply 15A continuous discharge for 5 minutes.
  - Monitor temperature rise with thermistors and FLIR thermal imaging; verify convective heat dissipation model $h_{eff}$.

- **LEVEL 6: Hardware Safety Interlock Trip Validation**
  - Inject synthetic over-voltage and thermal trip signals into LM393 comparator.
  - Verify hard relay disconnects the load within $<15\text{ ms}$, independent of ESP32 firmware state.

- **LEVEL 7: Full Adaptive Decision Loop Execution**
  - Introduce heterogeneous cells (1 healthy, 1 suspicious, 1 degraded).
  - Execute full automated sequence: TRIAGE $\to$ SECONDShift pulse test $\to$ Decision Engine $\to$ H.E.R.M.E.S. active/derate/bypass reconfiguration.
