# SECONDShift System Limitations & Operational Boundaries

## 1. Operating Envelope Boundaries

The physical prototype and software algorithms are designed and verified strictly within the following operational envelope:

| Parameter | Minimum | Nominal | Maximum | Enforcement Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Pack Terminal Voltage** | $10.0\text{ V}$ | $12.8\text{ V}$ | $14.6\text{ V}$ | LM393 Window Comparator & TRIAGE |
| **Individual Cell Voltage** | $2.50\text{ V}$ | $3.20\text{ V}$ | $3.65\text{ V}$ | ADS1115 16-bit differential ADC |
| **Continuous Discharge Current** | $0.0\text{ A}$ | $5.0\text{ A}$ | $10.0\text{ A}$ | INA226 current shunt & MOSFET PWM |
| **Pulse Discharge Current** | $0.0\text{ A}$ | $10.0\text{ A}$ | $20.0\text{ A}$ ($<10\text{ s}$) | 40A fast-acting fuse & IR2104 driver |
| **Cell Surface Temperature** | $15.0^\circ\text{C}$ | $25.0^\circ\text{C}$ | $45.0^\circ\text{C}$ | DS18B20 digital 1-Wire sensors |
| **Hardware Thermal Cutoff** | — | — | $60.0^\circ\text{C} \pm 3^\circ\text{C}$ | KSD9700 Bimetallic snap switch |

---

## 2. Chemical & Electrochemical Scope Boundaries

1. **Pre-Trained Chemistries:**
   The Bayesian likelihood models are parameterized specifically for **Lithium Iron Phosphate (LFP)** and **Lithium Nickel Manganese Cobalt Oxide (NMC)** chemistries.
2. **Exotic & Emerging Chemistries:**
   Chemistries such as Lithium Cobalt Oxide (LCO), Lithium Titanate (LTO), Sodium-Ion (Na-ion), and Solid-State are currently modeled as part of the $\mathcal{M} = \text{UNKNOWN}$ hypothesis class. 
   **Invariance Rule:** The system will never guess an unmodeled chemistry; it will classify the specimen as `AMBIGUOUS` / `UNKNOWN` and route it to `HOLD / RECYCLE`.
3. **Chemistry Disambiguation Ambiguity at Mid-SOC:**
   At intermediate states of charge ($\text{SOC} \approx 40\%-60\%$), cell open-circuit voltages can overlap between aged NMC and fresh LFP. When resting OCV alone is inconclusive, disambiguation requires active current pulses ($\Delta V / \Delta I$ and relaxation kinetics). If testing budget is exhausted before confidence reaches $99.0\%$, the system abstains.

---

## 3. Strict Non-Claims & Safety Exclusions

In accordance with responsible engineering practice and project constraints:

1. **No Claim of Commercial Safety Certification:**
   SECONDShift is an advanced university research prototype. It does **not** claim compliance with commercial functional safety standards (ISO 26262 ASIL-D, IEC 61508 SIL-3, UL 1973, or IEC 62619).
2. **No Claim of "Thermal Runaway Prevention":**
   SECONDShift implements **autonomous over-temperature cutoff** and **electrical overload mitigation**. It does **not** claim to prevent thermal runaway caused by internal dendritic short circuits, mechanical puncture, crushing, or high-temperature external fires.
3. **No Direct High-Voltage EV Pack Operation:**
   The physical bench operates under Safety Extra-Low Voltage (SELV, $<60\text{ V}$ DC). It must **never** be connected directly to high-voltage automotive battery packs ($400\text{V} - 800\text{V}$) without certified galvanic isolation, pre-charge contactors, and high-voltage interlock loops (HVIL).

---

## 4. Hardware GO Operational Policy

To prevent any dangerous deployment of misidentified cells in field stationary storage:

$$\begin{aligned}
\mathbf{Hardware\ GO\ Policy:} &\quad \text{GRANTED strictly and only for confirmed single-source LFP fleets} \\
&\quad \text{where } P(\text{LFP} \mid \mathbf{y}) \ge 0.99 \text{ and } P(\text{Failure} \mid \mathbf{y}) \le 1.0\%. \\
\mathbf{Mixed / Tagless\ Intakes:} &\quad \text{Strictly locked to } \mathbf{HOLD / RECYCLE}.
\end{aligned}$$
