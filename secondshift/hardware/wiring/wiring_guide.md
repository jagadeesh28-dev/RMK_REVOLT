# HERMES PHYSICAL WIRING & HARNESS GUIDE
**Document ID:** `WIRING-HERMES-01`  
**Classification:** Bench Fabrication & Assembly Instructions  
**Maximum Current Capacity:** 40A DC  

---

## 1. Power Bus Wiring & Conductor Specifications

1. **Battery String Connections:**
   - Wire Gauge: **10 AWG High-Strand Flexible Silicone Wire** ($200^\circ\text{C}$ rated, copper strand count $\ge 1050$).
   - Termination: Heavy-duty tin-plated copper ring terminals (M6 bolt size), double-crimped and sealed with dual-wall adhesive heat-shrink tubing.
   - Tightening Torque: $4.5\text{ N}\cdot\text{m}$ for M6 brass terminals using calibrated torque driver.

2. **Ground & Return Path:**
   - Star-ground topology: Single common ground point located immediately at the battery negative terminal before the INA226 current shunt.
   - Logic ground (ESP32, ADS1115, LM393) isolated from power return via single-point ground trace on PCB.

3. **Power Switching Stage:**
   - 4x Dual N-Channel Half-Bridge boards connected in series.
   - Power traces: 2oz copper pour with solder-tin reinforcement ($8\text{ mm}$ width) capable of carrying $25\text{A}$ continuous with temperature rise $\Delta T \le 12^\circ\text{C}$.

---

## 2. Sensor & Low-Voltage Signal Wiring

1. **Voltage Tap Harness:**
   - 22 AWG twisted-pair shielded cable running from cell terminals to ADS1115 differential inputs.
   - Inline fast-blow fuses ($500\text{ mA}$, glass $5\times 20\text{ mm}$) placed within $50\text{ mm}$ of each positive terminal tap to prevent wire harness fires in event of bench accidental shorts.

2. **Temperature Harness:**
   - 4x DS18B20 digital probes wired in parallel on 3-conductor shielded cable (`VDD`, `DQ`, `GND`).
   - Thermally bonded to the center of each cell case using thermally conductive epoxy (Arctic Alumina, thermal conductivity $> 7.5\text{ W/m}\cdot\text{K}$) and covered with high-temperature Kapton tape.

3. **Independent Safety Sensor Harness:**
   - KSD9700 bimetallic thermal switches mechanically clamped to the main inter-cell busbars between Cell 2 and Cell 3 (highest thermal concentration).
   - High-temperature PTFE insulated wiring ($18\text{ AWG}$) directly in series with the contactor coil.

---

## 3. Pre-Power-Up Verification Checklist

Prior to connecting any live battery module to the bench, the technician must execute:
- [ ] **Visual Inspection:** Verify no loose copper strands, solder bridges, or uninsulated conductor sections.
- [ ] **Continuity & Short Check:** Verify resistance between $+12.8\text{V}$ Bus and GND is $> 100\text{ k}\Omega$ with all switches open.
- [ ] **E-Stop Verification:** Depress Emergency Push Button; verify contactor coil voltage drops from $12\text{V}$ to $0\text{V}$ with DMM.
- [ ] **Comparator Threshold Check:** Inject synthetic $3.75\text{V}$ from bench power supply into LM393 input; verify comparator output trips low and opens relay.
- [ ] **Watchdog Test:** Power ESP32 with debug firmware holding GPIO 18 low; verify contactor opens within $250\text{ ms}$.
