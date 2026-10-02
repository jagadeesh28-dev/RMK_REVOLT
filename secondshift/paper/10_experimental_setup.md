# Section 9: Experimental Setup & Benchmark Cohort

## 9.1 Benchmark Cohort Composition ($N=12$)

To rigorously evaluate the framework under adverse edge cases, a curated 12-specimen benchmark cohort was established. The cohort was intentionally designed to be challenging and heterogeneous, comprising 5 Truly Safe packs and 7 Truly Unsafe packs across two distinct electrochemistries:

| Anonymous Specimen ID | Nominal Chemistry | Ground-Truth SOH | Ground-Truth $R_0$ | True Physical Admissibility | Key Challenging Defect / Feature Mode |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `ANON_01` (`SPEC_01`) | LFP | 0.92 | $2.00\text{ m}\Omega$ | **SAFE** | Healthy baseline cell with informative prior. |
| `ANON_02` (`SPEC_02`) | LFP | 0.85 | $2.30\text{ m}\Omega$ | **SAFE** | Mildly aged operational cell; diffuse intake prior. |
| `ANON_03` (`SPEC_03`) | NMC | 0.55 | $5.20\text{ m}\Omega$ | **UNSAFE** | Degraded NMC cell labeled as generic 12V block. |
| `ANON_04` (`SPEC_04`) | LFP | 0.65 | $4.10\text{ m}\Omega$ | **UNSAFE** | Sub-threshold capacity and high resistance. |
| `ANON_05` (`SPEC_05`) | LFP | 0.81 | $3.20\text{ m}\Omega$ | **SAFE** | Boundary cell near derating boundary ($R_0 \approx 3.2\text{m}\Omega$). |
| `ANON_06` (`SPEC_06`) | Mixed LFP/NMC | 0.72 | $3.60\text{ m}\Omega$ | **UNSAFE** | Severe chemistry ambiguity in series string. |
| `ANON_07` (`SPEC_07`) | LFP | 0.90 | $2.10\text{ m}\Omega$ | **SAFE** | Cold temperature intake ($16.0^\circ\text{C}$). |
| `ANON_08` (`SPEC_08`) | Unknown | 0.40 | $8.50\text{ m}\Omega$ | **UNSAFE** | Severe internal micro-short; high self-discharge. |
| `ANON_09` (`SPEC_09`) | LFP | 0.88 | $2.20\text{ m}\Omega$ | **SAFE** | High ambient temperature intake ($34.0^\circ\text{C}$). |
| `ANON_10` (`SPEC_10`) | LFP | 0.48 | $7.20\text{ m}\Omega$ | **UNSAFE** | Severely depleted capacity ($\text{SOH} < 50\%$). |
| `ANON_11` (`SPEC_11`) | NMC (as LFP) | 0.70 | $2.20\text{ m}\Omega$ | **UNSAFE** | Adversarial wrong-label attack (casing marked LFP). |
| `ANON_12` (`SPEC_12`) | LFP | 0.15 | $28.0\text{ m}\Omega$ | **UNSAFE** | Deep over-discharge excursion ($V_{\text{term}} = 1.85\text{V}$). |

## 9.2 Baseline Comparative Qualification Engines

SECONDShift was benchmarked against three distinct qualification strategies:
1. **Baseline A (Full OEM ATE Cycler - Legitimate Industrial Benchmark):** Executes a complete CC-CV constant current charge/discharge cycle at C/3 rate ($10,800.0\text{ s} \approx 3\text{ hours}$). Employs standard terminal voltage and coulometric thresholding without chemistry disambiguation.
2. **Baseline B (Scalar SOH Regression - Illustrative Strawman):** Evaluates intake prior belief immediately without executing physical diagnostic tests ($t = 0.05\text{ s}$). Included to illustrate the danger of unconstrained point estimators.
3. **Baseline C (Static Uncertainty Threshold - Illustrative Strawman):** Executes an unoptimized single pulse and threshold checks standard deviation against a static heuristic ($\sigma_{\text{threshold}} = 0.040$).

## 9.3 Statistical Evaluation Protocol

All models were evaluated under identical blind quarantine protocols. Primary metrics include:
- **Classification Accuracy:** $\frac{\text{TP} + \text{TN}}{N}$
- **False Acceptance Rate (FAR):** $\frac{\text{FP}}{\text{FP} + \text{TN}}$ (with Clopper-Pearson exact 95% confidence intervals)
- **Qualified Acceptance Rate (QAR):** $\frac{\text{TP}}{\text{TP} + \text{FN}}$
- **Mean Qualification Dwell Time:** $\mathbb{E}[t_{\text{dwell}}]$
- **Paired Hypothesis Tests:** Wilcoxon signed-rank test for continuous dwell time; exact two-sided McNemar test for paired classification decisions.
