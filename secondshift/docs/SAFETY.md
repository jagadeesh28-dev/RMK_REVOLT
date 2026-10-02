# SECONDShift Safety Architecture & Independent Hardware Safety Layer

## 1. Safety Core Principles

The design of SECONDShift is governed by two axiomatic safety rules:
1. **Safety Constraint Dominance:**
   $$\text{SAFETY CONSTRAINT} \gg \text{ECONOMIC OPTIMIZATION}$$
   Economic value, testing speed, and diagnostic costs are subordinated to the strict enforcement of safety margins.
2. **Autonomous Hardware Authority:**
   The software supervisory layer (Python and ESP32) can only **request** test execution; it possesses **zero authority** to override the analog safety hardware.

---

## 2. Independent Hardware Safety Subsystem (Layer 0)

The independent safety chain operates completely out-of-band from any microcontrollers, digital buses, or software routines.

```
+--------------------------------------------------------------------------------+
|                         INDEPENDENT ANALOG SAFETY CHAIN                        |
+--------------------------------------------------------------------------------+
|  +12V Auxiliary Supply                                                         |
|         |                                                                      |
|    [Emergency Stop (Mushroom NC)]                                              |
|         |                                                                      |
|    [KSD9700 Thermal Switch (60°C NC, direct cell contact)]                    |
|         |                                                                      |
|    [LM393 Window Comparator (Open-collector drive, 10.0V - 14.8V window)]      |
|         |                                                                      |
|    [TPS3823 Supervisory IC (200ms watchdog timeout)]                          |
|         |                                                                      |
|    [ESP32 Contactor Permissive Drive]                                          |
|         |                                                                      |
|    (JD1912 40A Contactor Coil) ---> Disconnects Load within 15 ms             |
+--------------------------------------------------------------------------------+
```

### Safety Chain Hardware Components:
1. **LM393 Analog Window Comparator:**
   - Evaluates pack terminal voltage via a precision $0.1\%$ resistive divider against a TL431 $2.500\text{ V}$ reference.
   - Trips and opens coil ground if $V < 10.0\text{ V}$ (deep discharge / cell reversal hazard) or $V > 14.8\text{ V}$ (over-voltage / plating hazard).
   - Response latency: $1.3\ \mu\text{s}$.
2. **KSD9700 Bimetallic Snap Switch:**
   - Spring-loaded bimetallic disc clamped directly to cell pack busbar with thermal compound.
   - Snaps open at $60^\circ\text{C} \pm 3^\circ\text{C}$, physically interrupting contactor coil current.
   - Pure mechanical contact: Immune to electrical transients, latch-up, or firmware failures.
3. **TPS3823 Watchdog Supervisory IC:**
   - Requires dynamic edge toggle on WDI every $\le 200\text{ ms}$.
   - If ESP32 firmware hangs, enters a deadlock, or loses clock oscillation, `/RESET` pulls low and collapses coil drive.

---

## 3. Hardware Safety Chain Verification Plan (Tests A–F)

Before any cell or emulator is connected, the physical safety chain undergoes six mandatory qualification tests:

| Test ID | Safety Subsystem | Injected Fault Condition | Expected System Response | Acceptance Threshold |
| :--- | :--- | :--- | :--- | :--- |
| **TEST-A** | Over-Voltage Cutoff | External DC supply sweeps terminal voltage to $15.0\text{ V}$. | LM393 trips; contactor opens. | Trip voltage between $14.75\text{ V}$ and $14.85\text{ V}$. Drop time $<20\text{ ms}$. |
| **TEST-B** | Under-Voltage Cutoff | DC supply drops voltage to $9.8\text{ V}$. | LM393 trips; contactor opens. | Trip voltage between $9.95\text{ V}$ and $10.05\text{ V}$. Drop time $<20\text{ ms}$. |
| **TEST-C** | Thermal Cutoff | Hot-air heat gun gently warms KSD9700 sensor to $62^\circ\text{C}$. | Switch contacts snap open; coil de-energizes. | Trip occurs between $58^\circ\text{C}$ and $63^\circ\text{C}$. Zero current flow. |
| **TEST-D** | Emergency Stop | Manual depression of red E-Stop mushroom button during $5\text{ A}$ pulse. | Physical circuit broken; contactor drops immediately. | Current drops to $0.0\text{ A}$ in $<15\text{ ms}$. Arc extinguished. |
| **TEST-E** | Watchdog Strobe Timeout | ESP32 software deliberately halts WDI strobing pin. | TPS3823 asserts `/RESET`; coil drops. | Disconnection occurs between $180\text{ ms}$ and $220\text{ ms}$ post-halt. |
| **TEST-F** | Software Override Attempt | ESP32 GPIO 19 forced HIGH while terminal voltage is held at $15.2\text{ V}$. | Contactor remains completely de-energized. | Contactor voltage remains $0.0\text{ V}$; coil current = $0.0\text{ mA}$. |

---

## 4. Software Safety Barrier & Epistemic Abstention

### 4.1 Quantitative Safety Barrier Limit
The software decision barrier enforces:
$$P(\text{Failure} \mid \mathbf{y}) \le \alpha_{\text{max}} = 0.01 \quad (1.0\%)$$
Where failure risk integrates over both state distribution ($\text{SOH}, R_0$) and chemistry identity uncertainty ($\mathcal{M} = \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$):
$$P(\text{Failure} \mid \mathbf{y}) = \sum_{M \in \mathcal{M}} P(\text{Failure} \mid \mathbf{y}, M) P(M \mid \mathbf{y})$$

### 4.2 Epistemic Refusal Rules
To prevent false confidence under ambiguous chemistry:
1. **Rule 1:** Direct `OPERATE` is **strictly forbidden** if chemistry state is `PROBABLE` or `AMBIGUOUS`.
2. **Rule 2:** If after diagnostic tests, $P(\text{UNKNOWN} \mid \mathbf{y}) > 0.10$ or ambiguity cannot be resolved, the battery transitions directly to:
   $$\text{UNKNOWN CHEMISTRY} \implies \text{HOLD / RECYCLE}$$
3. **Rule 3:** The system never forces a classification when data is insufficient.
