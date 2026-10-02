# Dataset Forensics: Complete Specimen Inventory & Subgroup Analysis

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-DATA-FORENSICS`  
**Dataset Quarantined Path:** `secondshift/data/raw/ground_truth_registry.json`  
**Evaluation Standard:** Independent Dataset Forensic Audit  
**Date of Audit:** October 2, 2026  

---

## 1. Population Overview & Scale Acknowledgment

$$\mathbf{CRITICAL\ ACKNOWLEDGMENT:\ N = 12\ IS\ A\ SMALL\ BENCHMARK\ PROTOTYPE}$$

The reference dataset consists of **12 distinct laboratory specimens** (`SPECIMEN_01` to `SPECIMEN_12`).
- This dataset is an initial **hardware-in-the-loop laboratory benchmark** designed to evaluate algorithmic edge cases and safety barrier trip mechanisms.
- **It does NOT represent a statistically powered, fleet-scale commercial qualification cohort.**
- Any claims of "fleet-scale validation" apply strictly to the pooled Monte Carlo synthetic cohort ($N=300$) in simulation, not to this 12-specimen reference dataset.

---

## 2. Complete 12-Specimen Inventory

| ID | Specimen Identifier | True Chem | Tagged / Prior Chem | SOH | $R_0$ (m$\Omega$) | Resting $V_{\text{oc}}$ (V) | Temp ($^\circ$C) | Self-Discharge Drift | Ground Truth Safety Class | Target Action | SECONDShift Action | Baseline A Action |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| **01** | `SPECIMEN_01_HEALTHY_LFP` | LFP | KNOWN_LFP_FLEET | 0.94 | 1.9 | 13.17 V (3.29V/c) | 25.0 | 0.8 mV/hr | Pristine Grade-A 4S LFP Module | **OPERATE** | **OPERATE** | OPERATE |
| **02** | `SPECIMEN_02_HEALTHY_LFP_ALT` | LFP | KNOWN_LFP_FLEET | 0.92 | 2.1 | 13.16 V (3.29V/c) | 25.2 | 1.1 mV/hr | Fresh Grade-A Reference Module | **OPERATE** | **OPERATE** | OPERATE |
| **03** | `SPECIMEN_03_MODERATE_LFP` | LFP | KNOWN_LFP_FLEET | 0.81 | 2.6 | 13.15 V (3.29V/c) | 25.0 | 2.0 mV/hr | Fleet retired (800 cycles); uniform | **OPERATE** | **DERATE** | OPERATE |
| **04** | `SPECIMEN_04_MARGINAL_LFP` | LFP | KNOWN_LFP_FLEET | 0.73 | 3.2 | 13.14 V (3.29V/c) | 25.5 | 3.2 mV/hr | Boundary retirement (high cycle aging) | **OPERATE** | **DERATE** | OPERATE |
| **05** | `SPECIMEN_05_DERATED_LFP` | LFP | KNOWN_LFP_FLEET | 0.67 | 3.8 | 13.13 V (3.28V/c) | 26.0 | 4.5 mV/hr | Degraded capacity (thermal cycling); safe @0.5C | **DERATE** | **RETIRE** | DERATE |
| **06** | `SPECIMEN_06_HIGH_RES_LFP` | LFP | KNOWN_LFP_FLEET | 0.70 | 5.8 | 13.14 V (3.29V/c) | 25.0 | 3.8 mV/hr | Excessive internal/contact resistance | **RETIRE** | **RETIRE** | RETIRE |
| **07** | `SPECIMEN_07_MICROSHORT_LFP` | LFP | KNOWN_LFP_FLEET | 0.48 | 18.5 | 13.08 V (3.27V/c) | 27.2 | 22.0 mV/hr | Internal dendritic microshort hazard | **RETIRE** | **RETIRE** | RETIRE |
| **08** | `SPECIMEN_08_OVERDISCHARGED_LFP`| LFP | KNOWN_LFP_FLEET | 0.21 | 85.0 | 8.40 V (2.10V/c) | 25.0 | 45.0 mV/hr | Deep overdischarge; copper dissolution risk | **RETIRE** | **RETIRE** | RETIRE |
| **09** | `SPECIMEN_09_TAGLESS_NMC_FRESH` | NMC | TAGLESS_MIXED | 0.88 | 1.6 | 15.01 V (3.75V/c) | 24.8 | 1.2 mV/hr | Fresh NMC module with unverified label | **RETIRE** | **RETIRE** | **OPERATE** |
| **10** | `SPECIMEN_10_TAGLESS_NMC_AGED` | NMC | TAGLESS_MIXED | 0.68 | 2.4 | 15.00 V (3.75V/c) | 25.1 | 2.8 mV/hr | Aged NMC module; unlabelled | **RETIRE** | **RETIRE** | **DERATE** |
| **11** | `SPECIMEN_11_WRONG_LABEL_NMC` | NMC | KNOWN_LFP_FLEET | 0.82 | 1.8 | 15.00 V (3.75V/c) | 25.0 | 1.5 mV/hr | Adversarial counterfeit LFP label on NMC | **RETIRE** | **RETIRE** | **OPERATE** |
| **12** | `SPECIMEN_12_UNKNOWN_EXOTIC` | UNKNOWN | UNKNOWN | 0.50 | 12.0 | 12.00 V (3.00V/c) | 25.0 | 8.0 mV/hr | Unmodeled experimental sodium hybrid | **RETIRE** | **RETIRE** | RETIRE |

---

## 3. Subgroup Distributions & Sub-population Analysis

### 3.1. Chemistry Distribution
- **Lithium Iron Phosphate (LFP):** 8 specimens ($66.7\%$)
- **Nickel Manganese Cobalt (NMC):** 3 specimens ($25.0\%$)
- **Unmodeled Exotic / Unknown:** 1 specimen ($8.3\%$)

### 3.2. Ground Truth Safety & Decision Class Balance
- **Truly Safe for Second-Life Deployment:** **5 specimens ($41.67\%$)**
  - Safe for Full Unconstrained OPERATE ($SOH \ge 0.70, R_0 \le 3.5\text{ m}\Omega$, LFP): 4 specimens (01, 02, 03, 04)
  - Safe strictly for Derated 0.5C Duty ($SOH \ge 0.65, R_0 \le 4.0\text{ m}\Omega$, LFP): 1 specimen (05)
- **Truly Unsafe / Inadmissible for LFP Deployment:** **7 specimens ($58.33\%$)**
  - Excessive Impedance ($R_0 > 4.7\text{ m}\Omega$): 1 specimen (06)
  - Latent Internal Microshort (Self-discharge $>15\text{ mV/hr}$): 1 specimen (07)
  - Severe Overdischarge / Copper Dissolution ($V_{\text{term}} < 10.0\text{V}$): 1 specimen (08)
  - Chemistry Incompatible / Thermal Mismatch (NMC on LFP line): 3 specimens (09, 10, 11)
  - Unmodeled Chemistry (Sodium hybrid): 1 specimen (12)

### 3.3. SOH & Degradation Range
- **SOH Range:** $[0.21, 0.94]$
  - Healthy ($SOH \ge 0.80$): 5 specimens ($41.7\%$)
  - Marginal / Derated ($0.65 \le SOH < 0.80$): 4 specimens ($33.3\%$)
  - Severely Depleted ($SOH < 0.65$): 3 specimens ($25.0\%$)
- **Internal Resistance ($R_0$) Range:** $[1.6\text{ m}\Omega, 85.0\text{ m}\Omega]$
  - Normal ($R_0 \le 3.5\text{ m}\Omega$): 8 specimens ($66.7\%$)
  - Moderately Elevated ($3.5 < R_0 \le 5.0\text{ m}\Omega$): 1 specimen ($8.3\%$)
  - Severely Degraded ($R_0 > 5.0\text{ m}\Omega$): 3 specimens ($25.0\%$)

### 3.4. State of Charge (SOC) & Temperature Range
- **Temperature Distribution on Bench:** All 12 specimens evaluated at ambient room temperature ($25.0^\circ\text{C} \pm 1.2^\circ\text{C}$).
  - *Limitation:* The benchmark does **not** test physical sub-zero temperatures ($-10^\circ\text{C}$) or physical extreme heat ($>45^\circ\text{C}$). Temperature sensitivity is evaluated only in simulation (`run_chemistry_attacks.py`).
- **Resting SOC Distribution:**
  - Fresh / Moderate LFP specimens (01-07): Resting on the flat central plateau ($SOC \approx 50\% - 60\%$, $V_{\text{cell}} \approx 3.28\text{V} - 3.29\text{V}$).
  - Overdischarged specimen (08): Fully depleted ($SOC \approx 0\%$, $V_{\text{cell}} = 2.10\text{V}$).
  - NMC specimens (09-11): Initial rest voltages at $3.75\text{V}$/cell ($SOC \approx 60\% - 70\%$).

---

## 4. Key Limitations of the Dataset

1. **Small Sample Size ($N=12$):** Although the 12 specimens cover a diverse taxonomy of failure modes (thermal cycling, aging, microshorts, overdischarge, counterfeit tags, unmodeled chemistries), $N=12$ is insufficient to establish population-level asymptotic bounds.
2. **Deterministic Triage Interaction:** Notice that for `SPECIMEN_09`, `SPECIMEN_10`, and `SPECIMEN_11`, the resting cell voltage was $3.75\text{V}$, right at the boundary of Stage 0 rule TR-04 ($V > 3.75\text{V}$). In benchmark testing where noise bumped voltage slightly above $3.75\text{V}$, TR-04 caught them passively. In the extended chemistry attack suite (`run_chemistry_attacks.py`), resting SOC was varied down to $3.45\text{V}$ where Triage passes and pulse slope disambiguation is required.
3. **No Independent Training/Calibration Set:** There is no separate calibration split. The likelihood parameters in `chemistry_engine.py` were specified from literature prior to evaluating this benchmark.
