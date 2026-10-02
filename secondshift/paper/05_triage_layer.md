# Section 4: Stage 0 Deterministic Triage Layer

## 4.1 Motivation & Industrial Role

In second-life aggregation facilities, subjecting physically damaged, severely depleted, or internally shorted battery modules to high-current diagnostic pulses introduces severe fire hazards and wastes diagnostic throughput. Stage 0 **TRIAGE** acts as a millisecond-scale deterministic admissibility barrier. It evaluates passive, non-invasive electrical and thermal telemetry before any programmable load or power contactor is engaged.

## 4.2 Deterministic Admissibility Rules (TR-01 through TR-09)

A battery module is classified as `ADMISSIBLE` if and only if it simultaneously satisfies all nine deterministic screening criteria:

| Rule ID | Physical Property Evaluated | Threshold Condition | Physical Rationale & Failure Mode |
| :--- | :--- | :---: | :--- |
| **TR-01** | Minimum Terminal Voltage | $V_{\text{term}} \ge 2.00\text{ V/cell}$ | Severe over-discharge; copper dendrite dissolution hazard. |
| **TR-02** | Maximum Terminal Voltage | $V_{\text{term}} \le 3.65\text{ V/cell}$ (LFP) | Overcharge excursion; cathode lattice breakdown and gassing. |
| **TR-03** | Ambient Surface Temperature | $15.0^\circ\text{C} \le T_{\text{surf}} \le 45.0^\circ\text{C}$ | Safe testing thermal envelope; prevents lithium plating at low T. |
| **TR-04** | Module Thermal Gradient | $\Delta T_{\max} \le 5.0^\circ\text{C}$ | Severe inter-cell imbalance or localized hotspot. |
| **TR-05** | Self-Discharge Voltage Drift | $|dV/dt|_{\text{rest}} \le 15.0\text{ mV/hr}$ | Internal micro-short circuit or high parasitic consumption. |
| **TR-06** | Series Inter-Cell Spread | $\Delta V_{\text{cell}} \le 150\text{ mV}$ | Severe series degradation or bypass failure. |
| **TR-07** | Visual / Enclosure Swelling | $\Delta h_{\text{swell}} \le 2.0\text{ mm}$ | Pouch delamination or severe pouch gassing. |
| **TR-08** | Casing Insulation Resistance | $R_{\text{iso}} \ge 500\text{ k}\Omega$ | High-voltage breakdown to chassis ground. |
| **TR-09** | Open-Circuit Contact Impedance | $R_{\text{term}} \le 10.0\text{ m}\Omega$ | Terminal corrosion, loose busbar weld, or fractured tab. |

## 4.3 Computational Complexity & Execution Latency

The complete evaluation of rules TR-01 through TR-09 executes in $t_{\text{triage}} \le 2.5\text{ s}$ on the embedded microcontroller. By rejecting overtly defective modules deterministically, TRIAGE eliminates $100\%$ of unnecessary high-current testing on hazardous cells, protecting both the physical testbed instrumentation and facility operators.
