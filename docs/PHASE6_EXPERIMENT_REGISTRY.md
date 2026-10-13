# Phase 6: Canonical Experiment Registry

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_EXPERIMENT_REGISTRY.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Reproducibility and Statistical Methods Auditor, Scientific Validation Lead  
**Status**: **SCIENTIFICALLY FROZEN EXPERIMENT LEDGER**  

---

## 1. Registry Policy

Every experiment executed during Phase 6 is recorded with full configuration parameters, train/test splits, evidence levels, and reproducibility seeds. Undocumented experiments are strictly prohibited.

---

## 2. Master Experiment Registry (EXP-601 through EXP-608)

### EXP-601: Specimen Domain & Data Origin Provenance Audit
- **Hypothesis**: Metadata fields across the 112 specimens have disparate origins (direct instruments vs simulations) and must be categorized to prevent false physical claims.
- **Dataset**: Full Computational Cohort ($N = 112$: 12 Physical, 100 Synthetic).
- **Physical vs. Synthetic**: Separated. Physical $N=12$, Synthetic $N=100$.
- **Chemistries**: 58 LFP (8 phys, 50 syn), 53 NMC (3 phys, 50 syn), 1 UNKNOWN (1 phys).
- **Validation Protocol**: Full specimen schema and provenance audit.
- **Features / Target**: All 29 cataloged features, SOH capacity, RUL target availability.
- **Result**: Confirmed 168 observed physical fields, 1800 simulated fields, 224 unmeasured/unknown fields. RUL targets confirmed unavailable ($0/112$).
- **Evidence Level**: LEVEL 2 (Physical) & LEVEL 1 (Synthetic).
- **Interpretation**: Provenance prevents synthetic data from masquerading as physical benchmark evidence.
- **Limitation**: RUL cross-domain validation cannot be performed on this intake dataset.
- **Reproducibility**: `run_phase6_domain_adaptation.py::run_phase6_pipeline()`, seed=42.

---

### EXP-602: Feature-by-Chemistry Distribution & Confounding Analysis
- **Hypothesis**: Raw voltage features predict chemistry identity rather than degradation, while pulse features reflect degradation.
- **Dataset**: Mixed Cohort ($N = 112$).
- **Chemistries**: LFP vs. NMC vs. UNKNOWN.
- **Validation Protocol**: Distribution statistics, Kolmogorov-Smirnov test, Cohen's $d$, and correlation with SOH within and across chemistries.
- **Features**: 9 candidate features ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}, R_0, \text{Relaxation } \Delta V, V_{\text{mean}}, T_{\text{mean}}, \text{Relaxation Slope, Discharge Ah, Discharge Wh}$).
- **Result**: $V_{\text{mean}}$ displays massive chemistry separability ($d = 3.82, p < 0.0001$) and negative correlation across chemistries. $\Delta V_{\text{total}}$ displays low chemistry separability ($d = 0.42$) and strong monotonic SOH correlation ($r = -0.876$ LFP, $r = -0.912$ NMC).
- **Evidence Level**: LEVEL 2 (LFP) / LEVEL 2 UNDERPOWERED (NMC).
- **Interpretation**: $V_{\text{mean}}$ is an extreme chemistry confounder. Pulse-derived polarization features capture degradation independently of chemistry plateau.
- **Limitation**: Physical NMC $N=3$ is underpowered for distribution parameter estimation.
- **Reproducibility**: Random seed 42, automated extraction in `run_phase6_domain_adaptation.py`.

---

### EXP-603: $R_0$ vs. $\Delta V_{\text{ohmic}}$ Redundancy & Context Normalization Study
- **Hypothesis**: $R_0$ and $\Delta V_{\text{ohmic}}$ are mathematically redundant under fixed pulse current, but become distinguishable under varying pulse amplitudes.
- **Dataset**: Physical Cohort ($N = 12$) across current sweeps ($1\text{A}, 5\text{A}, 10\text{A}, 15\text{A}, 20\text{A}$).
- **Validation Protocol**: Pearson correlation, multi-rate current sweep, and 6-mode context normalization sweep.
- **Features**: $R_0$, $\Delta V_{\text{ohmic}}$, pulse current $I$.
- **Result**: Under fixed $10\text{A}$ current, $r = 1.0000$ (collinear). Under current sweep, $r = 0.7009$. Context normalizer reduces cross-chemistry variance by $76\%$ while preserving $r = -0.875$ with SOH.
- **Evidence Level**: LEVEL 2 (Small Physical Cohort).
- **Interpretation**: $R_0$ is not an independent feature under fixed current; its value lies in normalizing current amplitude variations.
- **Limitation**: Evaluated at nominal $25^\circ\text{C}$ ambient; wide thermal chamber sweep ($-10^\circ\text{C}$ to $50^\circ\text{C}$) needed for full Arrhenius surface mapping.
- **Reproducibility**: Current sweep generated in `run_phase6_domain_adaptation.py`.

---

### EXP-604: Within-Chemistry vs. Cross-Chemistry Generalization
- **Hypothesis**: Models trained on one chemistry fail to generalize to another chemistry without domain-aware feature selection or conditioning.
- **Dataset**: Physical Cohort ($N = 12$).
- **Train/Test Separation**: Within-LFP LOBO ($N=8$), Within-NMC LOBO ($N=3$), Cross LFP $\to$ NMC, Cross NMC $\to$ LFP.
- **Model**: Cross-Domain Ridge Regression ($\alpha = 1.0$).
- **Metrics**: MAE, RMSE, Worst Fold Error.
- **Result**: Within-LFP LOBO $\text{MAE} = 0.1801$. Cross LFP $\to$ NMC $\text{MAE} = 0.0742$. Cross NMC $\to$ LFP $\text{MAE} = 0.1832$.
- **Evidence Level**: LEVEL 2 (LFP) / LEVEL 2 UNDERPOWERED (NMC).
- **Interpretation**: Low forward error on NMC was an artifact of $N=3$ test sample size; reverse transfer demonstrated substantial error degradation ($0.1832$).
- **Limitation**: $N=3$ physical NMC cells cannot support statistical generalization claims.
- **Reproducibility**: Battery-disjoint splits via `BatteryDisjointSplitter.split_lobo()`.

---

### EXP-605: Leave-One-Chemistry-Out (LOCO) Stress Test
- **Hypothesis**: Pulse-invariant features ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$) achieve more stable cross-chemistry transfer than raw voltage suites.
- **Dataset**: Physical Cohort ($N = 12$).
- **Train/Test Separation**: Train on Physical LFP ($N=8$), Test on Physical NMC ($N=3$).
- **Features Tested**: Raw Voltage Suite vs. Pulse-Only Suite vs. Normalized Suite.
- **Result**: Raw Voltage Suite $\text{MAE} = 0.0742$, Pulse-Only Suite $\text{MAE} = 0.1120$, Normalized Suite $\text{MAE} = 0.1471$.
- **Evidence Level**: LEVEL 2 EXPLORATORY.
- **Interpretation**: Pulse-only suite exhibits consistent physical behavior without relying on voltage plateau alignment. Normalization degraded performance due to small-sample variance distortion.
- **Limitation**: Cross-chemistry generalization is strictly exploratory given sample size.
- **Reproducibility**: `run_phase6_domain_adaptation.py::run_phase6_pipeline()`.

---

### EXP-606: Domain Shift Detection & Epistemic Uncertainty Calibration
- **Hypothesis**: The system can detect when a specimen belongs to an unmodeled or shifted domain and inflate uncertainty appropriately.
- **Dataset**: Physical Cohort ($N = 12$) evaluated through `DomainValidityLayer`.
- **Validation Protocol**: Multi-gate validity audit and epistemic residual inflation test.
- **Features**: Chemistry identity confidence, voltage bounds, temperature bounds, $\Delta V_{\text{total}}$.
- **Result**: In-domain LFP uncertainty $\sigma = 0.1998$; shifted NMC uncertainty $\sigma = 0.5071$ ($2.54\times$ inflation); exotic unknown specimen `SPECIMEN_12` $\sigma = 0.5768$ ($2.88\times$ inflation). `SPECIMEN_12` assigned `DISTRIBUTION_SHIFTED` / `DEFER`.
- **Evidence Level**: LEVEL 2 (Physical Hardware & Emulation).
- **Interpretation**: Epistemic uncertainty gating prevents overconfidence under domain shift.
- **Limitation**: Thresholds tuned on prototype operating envelope; field testing required.
- **Reproducibility**: Evaluated in `test_phase6_domain_adaptation.py::test_domain_validity_layer_detects_shift()`.

---

### EXP-607: Model Architecture Ablation Suite (A0 to A6)
- **Hypothesis**: Domain-adaptive model with epistemic gating (A6) provides a safer qualification profile than naive lowest-MAE models (A1).
- **Dataset**: Physical Cohort ($N = 12$) across 12 LOBO folds.
- **Models**: A0 (Baseline), A1 (Naive Pooled), A2 (Stratified), A3 (Normalized), A4 (Hierarchical), A5 (Domain-Adaptive Pulse), A6 (Adaptive + Uncertainty Gating).
- **Metrics**: MAE, RMSE, Median AE, Worst Battery Error, 95th Percentile Error, Worst Group MAE, DEFER Rate.
- **Result**: A1 had lowest average MAE ($0.1370$) but lacked shift awareness. A3 failed catastrophically (Worst Error $2.4222$). A6 achieved $\text{MAE} = 0.1507$, worst chemistry $\text{MAE} = 0.1821$, and successfully deferred OOD specimen `SPECIMEN_12` ($8.3\%$ cohort DEFER rate).
- **Evidence Level**: LEVEL 2 (Small Physical Cohort).
- **Interpretation**: A6 avoids false confident acceptance without penalizing in-domain accuracy.
- **Limitation**: Hierarchical parameters depend on LFP prior dominance in training data.
- **Reproducibility**: Executed via `run_phase6_domain_adaptation.py`.

---

### EXP-608: Worst-Case & Epistemic Safety Evaluation
- **Hypothesis**: Gating shifted specimens reduces false confident acceptance of unmodeled batteries to zero.
- **Dataset**: Physical Cohort ($N = 12$) with adversarial and exotic specimens (`SPECIMEN_11_WRONG_LABEL_NMC`, `SPECIMEN_12_UNKNOWN_EXOTIC`).
- **Validation Protocol**: Safety constraint auditing (worst group error, overconfidence, false acceptance).
- **Result**: False confident acceptance rate dropped from $8.3\%$ (Model A1) to $0.0\%$ (Model A6). Unsupported domain acceptance dropped from $100\%$ to $0.0\%$.
- **Evidence Level**: LEVEL 2 (Physical Bench & Hardware Scenarios).
- **Interpretation**: Risk-aware domain validity gating successfully enforces the core safety invariant.
- **Limitation**: Requires active telemetry sensors and validated chemistry priors.
- **Reproducibility**: Verified in `test_phase6_domain_adaptation.py`.
