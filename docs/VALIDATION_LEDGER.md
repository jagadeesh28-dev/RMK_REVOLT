# Cumulative Validation Ledger

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/VALIDATION_LEDGER.md`  
**Current Phase**: Phase 6.1.1 — Final Evidence Consistency, Numerical Reconciliation & Freeze Audit  
**Policy**: Cumulative Validation & No-Redundant-Retest Policy  
**Status**: AUDITED, RECONCILED & SCIENTIFICALLY FROZEN — FINAL EVIDENCE FREEZE  

---

## 1. Frozen Phase Baselines

| Phase | Milestone | Baseline Test Count | Pass Rate | Status |
|---|---|:---:|:---:|:---:|
| **Phase 0** | Repository Audit & Ground Truth Isolation | 67 | 100% | FROZEN |
| **Phase 1** | Canonical Contracts & Epistemic Separation | 81 | 100% | FROZEN |
| **Phase 2** | Measurement Validity & False Pulse Protection | 107 | 100% | FROZEN |
| **Phase 3** | Qualification Data Model & Explainable Console | 121 | 100% | FROZEN |
| **Phase 4 Initial** | Canonical Feature Engine & 8-Gate Admission | 143 | 100% | SUPERSEDED BY REMEDIATION |
| **Phase 4 Frozen Baseline** | Scope-Aware, Leakage-Isolated Feature Engine | 161 | 100% | FROZEN |
| **Phase 5 Validation Initial** | Initial LOBO Validation & Feature Ablation Engine | 171 | 100% | SUPERSEDED BY SCIENTIFIC REMEDIATION |
| **Phase 5.1 Frozen Baseline** | Evidence-Freeze Correction & Multidimensional Baseline Freeze | 184 | 100% | FROZEN |
| **Phase 6 Exploratory Baseline** | Chemistry Stratification, Domain Validity Layer & Epistemic Gating | 200 | 100% | FROZEN — EXPLORATORY ONLY |
| **Phase 6.1 Audit Baseline** | Scientific Claim, Threshold & Uncertainty Calibration Audit | 207 | 100% | AUDITED, RETRACTED & SCIENTIFICALLY FROZEN |
| **Phase 6.1.1 Evidence Freeze** | Final Evidence Consistency & Numerical Reconciliation Freeze | 210 | 100% | AUDITED, RECONCILED & SCIENTIFICALLY FROZEN |
| **Phase 6.1.2 Micro-Audit** | **Final Attribution & Reproducibility Micro-Audit** | **211** | **100%** | **AUDITED, VERIFIED & SCIENTIFICALLY FROZEN** |
| **Real Hardware Integration** | **Levels 0-4 Hardware/Software Integration, T1-T12 Suite & Fail-Safe Control** | **228** | **100%** | **INTEGRATION COMPLETE WITH LIMITATIONS** |
| **Live Dashboard Data Integration** | **Complete Live Telemetry, TEST-DASH-01 to TEST-DASH-20 Suite & Evidence Segregation** | **248** | **100%** | **INTEGRATION COMPLETE WITH LIMITATIONS** |

---

## 2. Master Cumulative Validation Ledger

| Evaluation | Phase | Type | Status | Evidence | Affected Modules | Last Validated | Rerun Required? | Reason | Supersedes | Notes |
|---|:---:|:---:|:---:|---|---|:---:|:---:|---|:---:|---|
| **Phase 0 Baseline & Isolation** | Phase 0 | HISTORICAL | PASS | `test_ground_truth_isolation.py` (6 tests) | `secondshift/interfaces/` | Phase 0 | No | Reused evidence; baseline isolation unchanged | None | Verifies no runtime inference code accesses ground-truth SOH/chemistry |
| **Epistemic & Action Separation** | Phase 1 | HISTORICAL | PASS | `test_epistemic_schema.py` (14 tests) | `epistemic_schema.py` | Phase 1 | Regression Only | Reused evidence; contract unchanged | None | Enforces EpistemicState, OperationalDecision, InformationAction separation |
| **Adversarial Safety Scenarios** | Phase 1 | HISTORICAL | PASS | `test_adversarial_scenarios.py` (9 tests) | Decision Engine, Triage | Phase 1 | Regression Only | Reused evidence; decision rules untouched | None | Tests noise, overconfidence, chemistry attacks |
| **Hardware Pipeline & HIL** | Phase 1 | HISTORICAL | PASS | `test_hardware_integration*.py` (21 tests) | `hil_runner.py`, `actuation_policy.py` | Phase 1 | Regression Only | Reused evidence; hardware layer untouched | None | HILRunner, Serial/Mock/Replay, supervisor trip |
| **Layer 1 Sensor & Layer 2 Admissibility** | Phase 2 | HISTORICAL | PASS | `test_data_quality.py` (26 tests) | `data_quality_schema.py`, `telemetry_validator.py` | Phase 2 | Regression Only | Reused evidence; admissibility pipeline preserved | None | Layer 1 sensor check vs Layer 2 current flow check |
| **Correction A: Invalid Pulse Delta V -> None** | Phase 3 | HISTORICAL | PASS | `test_data_quality.py::test_invalid_pulse_delta_v_is_none` | `measurement_primitives.py`, `telemetry_validator.py` | Phase 3 | Regression Only | Preserves Unknown != Zero invariant | Legacy Delta V = 0.0 | Verified invalid diagnostic pulse produces delta_v = None, r0 = None |
| **Canonical Qualification Data Model** | Phase 3 | HISTORICAL | PASS | `test_qualification_data_model.py` (7 tests) | `qualification_schema.py` | Phase 3 | Continuous | Canonical schema for battery qualification lifecycle | None | Validates BatteryRecord, TestProtocol, TestSegment, Session lifecycle |
| **Temporal Provenance & Admissibility** | Phase 3 | HISTORICAL | PASS | `test_qualification_data_model.py` | `qualification_schema.py` | Phase 3 | Continuous | Observation window end <= t_decision enforcement | None | Detects future leakage and sets FUTURE_INFORMATION |
| **Explainable Dashboard & Scenarios** | Phase 3 | HISTORICAL | PASS | `test_dashboard_status.py` (16 tests) | `status_adapter.py`, `dashboard.py` | Phase 3 | Continuous | Status adapter JSON serialization & UI sections | None | Missing values remain None; invalid telemetry blocks healthy classification |
| **Canonical Feature Engine Suite** | Phase 4 | HISTORICAL | PASS | `test_feature_engine.py` (22 tests) | `secondshift/software/features/` | Phase 4 | Continuous | End-to-end extraction across 7 feature families | Phase 4 Initial | Recomputed with availability and scope awareness |
| **8-Gate Feature Admission Framework** | Phase 4 | HISTORICAL | PASS | `test_feature_engine.py::test_8_gate_audit_report` | `admission.py` | Phase 4 | Continuous | Audits Gates 1 through 8 for candidate features | Phase 4 Initial | Enhanced with scope-aware bounds, GT isolation, R0 context |
| **Scope Scaling & Determinism** | Phase 4 | HISTORICAL | PASS | `test_feature_engine.py` | `feature_metadata.py`, `admission.py` | Phase 4 | Continuous | 2s pack voltage scaling & bitwise extraction determinism | None | Verified across repeated extractions and pack geometries |
| **Registry Single Source of Truth** | Phase 4 | HISTORICAL | PASS | `test_feature_engine.py` | `feature_registry.py` | Phase 4 | Continuous | 29 active + 1 deferred = 30 total cataloged | None | Resolves 28 vs 29 ambiguity; guarantees single count truth |
| **Battery-Disjoint LOBO Validation** | Phase 5 | HISTORICAL | PASS | `test_feature_validation.py` | `validation_models.py`, `ablation.py` | Phase 5 | Continuous | Evaluates out-of-distribution generalization across cells | None | Confirms generalization gap (LOBO - Random = +0.0044) |
| **Real vs. Synthetic Cohort Separation** | Phase 5 | HISTORICAL | PASS | `test_feature_validation_remediation.py` | `validation_models.py`, `ablation.py` | Phase 5 | Continuous | Separates Real (N=12) from Synthetic (N=100) datasets | None | Physical MAE = 0.1646 vs Synthetic MAE = 0.0949 |
| **Random Split vs LOBO Gap Definition** | Phase 5.1 | NEW | PASS | `test_feature_validation_remediation.py` | `validation_models.py` | Phase 5.1 | Continuous | Generalization gap defined: LOBO_MAE - RANDOM_SPLIT_MAE > 0 | "LOBO outperforms random" | Random split produces artificially optimistic error (0.0915 vs 0.0959) |
| **A2 Baseline Definition Clarification** | Phase 5.1 | NEW | PASS | `test_feature_validation_remediation.py` | `validation_models.py` | Phase 5.1 | Continuous | A2 vs A0 is -0.0390 MAE; A2 vs A1 is -0.0256 MAE on physical cohort | Unspecified baseline | Explicitly defines reference baselines |
| **Suite vs Feature Evidence Separation** | Phase 5.1 | NEW | PASS | `test_feature_validation_remediation.py` | `validation_models.py` | Phase 5.1 | Continuous | A2 suite selection does NOT imply constituent features are independently useful | Constituent overclaim | LOFO separates individual incremental values |
| **Phase 5.1 Feature Status Taxonomy** | Phase 5.1 | NEW | PASS | `test_feature_validation_remediation.py` | `validation_models.py` | Phase 5.1 | Continuous | 1 Prov Supported + 1 Modest + 1 Contextual + 1 Insufficient + 5 Cond + 1 Def + 20 Rej = 30 | Phase 5 Provisional set | Establishes multidimensional non-collapsed evidence |
| **Evidence Freeze Machine Consistency** | Phase 5.1 | NEW | PASS | `test_feature_validation_remediation.py` | `phase5_evidence_freeze.json` | Phase 5.1 | Continuous | Verified 30 features, Level 2 physical evidence, effect sizes, superseded claims | Phase 5 initial freeze | Source of truth machine-readable artifact |
| **Chemistry Provenance & Data Origin Audit** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `domain_models.py` | Phase 6 | Continuous | Audited 112 specimens; verified 168 observed, 1800 simulated, 224 unknown fields | None | Enforces VERIFIED, DOCUMENTED, INFERRED, SIMULATED, UNKNOWN taxonomy |
| **Chemistry Confounding & Separability Test** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_domain_adaptation.py` | Phase 6 | Continuous | Proved V_MEAN is a chemistry proxy (d=3.82) with negative transfer | Phase 5 naive voltage | Identifies Delta V Total as primary anchor feature (r=-0.88 LFP, r=-0.91 NMC) |
| **R0 vs Delta V Ohmic Collinearity Audit** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_domain_adaptation.py` | Phase 6 | Continuous | Proved r=1.0000 under fixed 10A current; r=0.7009 under variable current sweep | Legacy separate feature claim | R0 acts as current-normalizer on production benches |
| **Within vs Cross-Chemistry LOBO/LOCO** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_domain_adaptation.py` | Phase 6 | Continuous | Within-LFP MAE=0.1801; Cross LFP->NMC MAE=0.0742; Cross NMC->LFP MAE=0.1832 | None | Classified strictly as EXPLORATORY DOMAIN TRANSFER; physical cross-chem not yet validated |
| **Domain Shift Detection & Epistemic Inflation** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `domain_models.py` | Phase 6 | Continuous | Evaluated DomainValidityLayer; verified 2.5x-2.9x epistemic sigma inflation on OOD | Mahalanobis OOD gate | SPECIMEN_12 assigned DISTRIBUTION_SHIFTED and triggers DEFER |
| **Model Ablation Suite (A0 through A6)** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_domain_adaptation.py` | Phase 6 | Continuous | Evaluated 7 models across 12 LOBO folds; Model A6 achieves 0.1507 MAE with 0% false acceptance | Naive lowest MAE selection | Model A3 (normalization) failed catastrophically (2.42 worst error) |
| **Phase 6 Evidence Freeze & Machine Sync** | Phase 6 | NEW | PASS | `test_phase6_domain_adaptation.py` | `results/phase6_domain_evidence.json` | Phase 6 | Continuous | Serialized all 8 experiments, worst-case metrics, and final feature table | Phase 5.1 freeze | Source of truth machine-readable artifact for Phase 6 |
| **Uncertainty Calibration Audit** | Phase 6.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_1_audit.py` | Phase 6.1 | Continuous | Proved responsiveness != calibration; r(|e|, sigma)=-0.0036; calibration UNVALIDATED | Overconfidence eliminated | Confirms epistemic inflation is heuristic penalty; intervals dilate >1.0 SOH |
| **Chemistry Confidence Threshold Audit** | Phase 6.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_1_audit.py` | Phase 6.1 | Continuous | Swept tau in [0.50, 0.99]; 0.90 classified as PROVISIONAL ENGINEERING THRESHOLD | Optimal threshold claim | Optimization underpowered due to discrete binary cohort confidences |
| **R0 Status Downgrade to Contextual** | Phase 6.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `domain_models.py` | Phase 6.1 | Continuous | R0 downgraded from SUPPORTED to CONTEXTUAL / PROVISIONAL (LOFO delta=0.0) | Supported with norm | Variance reduction does not establish incremental prognostic value |
| **Model A1 vs A6 Tradeoff Formalization** | Phase 6.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `run_phase6_1_audit.py` | Phase 6.1 | Continuous | Formalized A6 as risk-constrained/conservative; sacrifices 0.0137 MAE for 0% false OOD acceptance | "A6 is best/more accurate" | Directly comparable on same 12 physical LOBO folds |
| **Contact Resistance & Hardware Scoping** | Phase 6.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `docs/PHASE6_1_SCIENTIFIC_AUDIT.md` | Phase 6.1 | Continuous | Scoped delta_v_ohmic to aggregate response; scoped LM393 trip to tested LFP bench limits | General cross-chem hardware safety | Eliminates unproven physical mechanisms from terminal measurements |
| **Mixed-Cohort LOFO Attribution Decoupling** | Phase 6.1.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `results/phase6_1_1_evidence_freeze.json` | Phase 6.1.1 | Continuous | d=0.67 and p=0.0382 decoupled from NMC and attributed strictly to Physical Mixed-Cohort LOFO Ablation (N=12: 8 LFP, 3 NMC, 1 UNKNOWN) | NMC inferential claim | NMC N=3 is exploratory/descriptive only (r=-0.9984); zero independent hypothesis tests |
| **Uncertainty Interval Audit** | Phase 6.1.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `results/phase6_1_1_evidence_freeze.json` | Phase 6.1.1 | Continuous | 3.92*sigma full-width verified; raw unclipped intervals dilate to 1.99-2.28 SOH units | Calibrated interval | Dilated widths >1.0 confirm uncalibrated heuristic distance penalty |
| **Phase 6.1.1 Canonical Machine Freeze** | Phase 6.1.1 | NEW | PASS | `test_phase6_domain_adaptation.py` | `results/phase6_1_1_evidence_freeze.json` | Phase 6.1.1 | Continuous | Serialized canonical evidence freeze across all reconciled metrics, counts, and verdicts | Phase 6.1 audit json | Final machine-readable source of truth before freezing |
| **NMC Correlation Reproducibility Verification** | Phase 6.1.2 | NEW | PASS | `test_phase6_domain_adaptation.py` | `results/phase6_1_1_evidence_freeze.json` | Phase 6.1.2 | Continuous | Deterministic Pearson r=-0.9984 from persisted canonical observations; cross-process hash salt variation documented | Stochastic drift | run1 == run2 bitwise identical on persisted canonical inputs; descriptive only under N=3 |
| **Level 0 Observation & Stream Jitter** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_level_0_observation_telemetry_stream` | `serial_hardware.py`, ESP32 firmware | Current | Continuous | Verified 5-packet stream, zero dropped packets, 1.0s timestamp spacing, plausible physical bounds | None | Passive observation without actuation |
| **Telemetry Validation Suite (T1-T12)** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_t1` through `test_t12` | `telemetry_validator.py`, `telemetry_schema.py` | Current | Continuous | Evaluated idle, load OFF/ON, cycling, disconnects, malformed JSON, staleness, gaps, range faults, and reset recovery | None | Protocol and sensor validation across 12 controlled failure modes |
| **Level 2 Feature Gating (1Hz Scoping)** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_level_2_real_feature_extraction_and_temporal_resolution` | `feature_engine.py`, `pulse.py` | Current | Continuous | Verified V_MEAN and DELTA_V_TOTAL; gated DELTA_V_OHMIC and R0_OHMIC as TEMPORALLY_UNAVAILABLE under 1Hz acquisition | Silent extrapolation | Enforces None != 0 and prevents invalid high-rate claims from 1Hz telemetry |
| **Level 3 Shadow Decision Mode** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_level_3_shadow_decision_mode_zero_actuation` | `hil_runner.py`, `event_logger.py` | Current | Continuous | Evaluated full NEXUS pipeline on physical telemetry; produces OPERATE/HOLD shadow decisions with zero load actuation | None | Complete shadow qualification without actuator intervention |
| **Level 4 Controlled Actuation & Cutoff Authority** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_level_4_controlled_actuation_and_stop_priority` | `actuation_policy.py`, `command_schema.py` | Current | Continuous | Validated CommandFrame translation, ASCII mapping (ON/OFF/STOP), STOP priority, and hardware safety cutoff authority | None | Hardware retains final safety authority; software cannot override trips |
| **Physical Trace Replay Determinism** | Integration | NEW | PASS | `test_real_hardware_integration.py::test_physical_trace_replay_determinism` | `replay_hardware.py`, `esp32_prototype_run_001.ndjson` | Current | Continuous | Verified bitwise deterministic replay of 20 physical frames across independent instances | Non-deterministic bug | Captured physical trace serves as permanent regression artifact |

---

## 3. Superseded Claims & Retractions Ledger

| Previous Claim / Report Statement | Superceding Status | Scientific Reason for Correction / Retraction |
|---|:---:|---|
| *"Battery-disjoint LOBO outperforms random row splitting"* | **SUPERSEDED / WORDING CORRECTED** | Random row splitting produced lower apparent error (0.0915 vs 0.0959), which reflects artificial optimism due to identity leakage. LOBO is conservative and appropriate, not numerically lower in error. Generalization gap is defined as $\text{LOBO\_MAE} - \text{RANDOM\_SPLIT\_MAE} = +0.0044$ MAE. |
| *"A2 improves MAE by 0.0390"* (unspecified baseline) | **SUPERSEDED / CLARIFIED** | Clarified baseline references: A2 improves physical MAE by $0.0390$ relative to minimal baseline A0 (`V_MEAN`), and by $0.0256$ relative to electrical baseline A1. |
| *"DELTA_V_OHMIC directly resolves SEI degradation"* | **RETRACTED** | Terminal electrical pulse measurements aggregate ohmic, contact, wiring, and charge-transfer responses. Without three-electrode EIS or destructive teardown, direct SEI identification is scientifically unproven. |
| *"R0_OHMIC is a universal battery-health scalar"* | **RETRACTED** | $R_0$ exhibits $>25\%$ variation across SOC regimes and varies with temperature, current amplitude, and cabling. It is a protocol- and operating-condition-dependent electrical observation. |
| *"DELTA_V_OHMIC and R0_OHMIC possess Level 3 Cross-Battery Evidence"* | **SUPERSEDED / DOWNGRADED** | The real physical cohort consists of only $N=12$ cells (8 LFP, 3 NMC, 1 UNKNOWN). This is classified strictly as Level 2 (`LEVEL_2_SMALL_PHYSICAL_COHORT`). Level 3+ claims are retracted. |
| *"RELAXATION_DELTA_V is an admitted SOH prognostic feature"* | **SUPERSEDED / DOWNGRADED** | Physical LOFO ablation demonstrates zero incremental contribution to bulk SOH ($\Delta\text{MAE} = 0.00000$) in rapid 10s screening. Reclassified as `INSUFFICIENT_INCREMENTAL_EVIDENCE`. |
| *"Temperature does not predict SOH"* | **SUPERSEDED / CLARIFIED** | Corrected to: "The tested rapid-screening thermal features did not demonstrate incremental SOH predictive value under the evaluated protocol." Temperature remains mandatory for safety, anomaly detection, and context gating. |
| *"All four pulse features are independently validated"* | **SUPERSEDED / SEPARATED** | Suite A2 selection in nested CV reflects aggregate representation, not individual constituent independence. LOFO proves only `DELTA_V_TOTAL` has statistically and engineering significant independent value on physical cells ($d = 0.67$, $p = 0.0382$). |
| *"Unstratified cell voltage can be pooled across chemistries"* | **SUPERSEDED / RETRACTED** | $V_{\text{mean}}$ displays a $+0.477\,\text{V}$ plateau shift between LFP and NMC ($d = 3.82$). Pooling raw voltages produces negative transfer ($\Delta\text{MAE} = -0.00192$). Classified as `DOMAIN_DEPENDENT`. |
| *"Cross-chemistry generalization is proven by synthetic cohort"* | **SUPERSEDED / DOWNGRADED** | Synthetic transfer is strictly Level 1 evidence. Physical cross-chemistry validation requires Level 4 evidence and remains unproven due to physical NMC $N=3$ underpowering. |
| *"Continuous chemistry-conditioned normalization (Model A3) is mathematically unsound"* | **SUPERSEDED / SCOPED** | Continuous normalization is mathematically valid. The failure arose from an empirical sample variance estimator collapsing on $N=2$ training NMC cells ($\hat{\sigma} \to 0$). Scoped strictly to implementation and sample size instability. |
| *"Overconfidence eliminated under domain shift / Uncertainty is calibrated"* | **SUPERSEDED / SCOPED** | Sigma inflation demonstrates uncertainty responsiveness, but empirical calibration against prediction error is unvalidated ($r = -0.0036$). Classified as `UNCERTAINTY CALIBRATION: UNVALIDATED`. |
| *"P(M|y) < 0.90 is an empirically validated confidence threshold"* | **SUPERSEDED / CLASSIFIED PROVISIONAL** | 0.90 is an engineering heuristic from `ChemistryDisambiguationEngine`. Threshold optimization is statistically underpowered on $N=12$. Classified as `PROVISIONAL ENGINEERING THRESHOLD`. |
| *"R0 is supported with context normalization"* | **SUPERSEDED / DOWNGRADED** | Contextual variance reduction (76%) does not equal incremental prognostic value. Collinear with $\Delta V_{\text{ohmic}}$ under fixed current ($r=1.0000$). Downgraded to `CONTEXTUAL / PROVISIONAL`. |
| *"DELTA_V_OHMIC can distinguish contact resistance"* | **RETRACTED / SCOPED** | Terminal pulse measurements aggregate bulk electrolyte, separator tortuosity, tabs, and contact resistance. Cannot isolate contact resistance without independent instrumentation. |
| *"Autonomous comparator proves cross-chemistry hardware safety"* | **RETRACTED / SCOPED** | Comparator tripping demonstrates only that fixed LFP thresholds prevented NMC operation on that specific bench. Does not prove general cross-chemistry safety. |
| *"Model A6 is the most accurate cross-domain model"* | **SUPERSEDED / CORRECTED** | Model A1 has lower average MAE ($0.1370$ vs $0.1507$). Model A6 is risk-constrained and domain-aware, trading 0.0137 MAE to eliminate unsupported false acceptance ($8.33\% \to 0.00\%$) via DEFER. |
| *"DELTA_V_TOTAL is validated across LFP and NMC"* | **SUPERSEDED / SCOPED** | Physical NMC cohort contains only $N=3$ cells. Monotonic association observed, but cross-chemistry generalization remains unproven (Level 2 exploratory only). |
| *"Observed domain differences reflect pure chemistry effects"* | **SUPERSEDED / CONFOUNDED** | Physical LFP cells are 4S cylindrical modules; physical NMC cells are single pouch cells. Chemistry is completely confounded with packaging form factor. |
| *"NMC DELTA_V_TOTAL correlation is r = -0.912"* | **SUPERSEDED_BY_PHASE6_1_CORRECTION** | The canonical serialized machine-readable artifact value is $r = -0.9984$ ($p=0.0357$). The draft value $r = -0.9120$ is superseded. Under $N=3$, both values are descriptive and volatile. |
| *"Cohen's d = 0.67 and p = 0.0382 establish NMC significance"* | **SUPERSEDED / DECOUPLED** | Cohen's $d = 0.67$ and $p = 0.0382$ belong strictly to the Physical Mixed-Cohort LOFO Ablation (N=12: 8 LFP, 3 NMC, 1 UNKNOWN) in EXP-503. They must never be attached specifically to the $N=3$ NMC sample or claimed as cross-chemistry inferential significance. |

---

## 4. Retest & Preservation Guidelines

1. **Reused Historical Evidence**: Phase 0, 1, 2, 3, 4, 5, 5.1, 6, 6.1, 6.1.1, and 6.1.2 baseline evidence is retained without modification and verified via continuous regression test runs.
2. **Current Passing Test Suite**: Full regression run confirms **249 total tests passing** with zero failures (211 frozen scientific baseline + 17 serial hardware tests + 21 Wi-Fi hardware integration tests covering Levels 0-4, W0-W8, feature gating, shadow decision mode, controlled actuation, and replay determinism).
3. **Historical Evaluations Intentionally Not Rerun**:
   - Historical False Alarm Rate (FAR) testbench campaigns from Phase 2.
   - Physical load bench hardware runs (`run_physical_benchmark_suite.py`).
   - Dwell-time comparison benchmarks between Phase 1 and Phase 2.
   - Full Phase 6 training suite.
4. **Frozen Evidence Baselines**:
   - Phase 5.1 evidence freeze: [`results/phase5_evidence_freeze.json`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/results/phase5_evidence_freeze.json).
   - Phase 6 domain evidence freeze: [`results/phase6_domain_evidence.json`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/results/phase6_domain_evidence.json) and [`secondshift/data/processed/phase6_domain_evidence.json`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/data/processed/phase6_domain_evidence.json).
   - Phase 6.1 audit payload: [`results/phase6_1_audit.json`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/results/phase6_1_audit.json).
   - Phase 6.1.1 evidence freeze: [`results/phase6_1_1_evidence_freeze.json`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/results/phase6_1_1_evidence_freeze.json).
   - Master evidence freeze document: [`docs/PHASE6_1_1_FINAL_EVIDENCE_FREEZE.md`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/docs/PHASE6_1_1_FINAL_EVIDENCE_FREEZE.md).

---

## 5. Real Wi-Fi Hardware Integration Ledger (Phases W0 – W8)

| Phase | Description | Architecture Component | Verification Artifact | Status |
|---|---|---|---|:---:|
| **W0** | Repository & Architecture Audit | Layer 1 Hardware Interface & NDJSON Protocol | `test_w0_schema_compliance` | **PASS** |
| **W1** | Wi-Fi Connection & Credential Hygiene | Untracked `secrets.h`, `.env`, `.gitignore` | `test_w1_credentials_scrubbed_from_snapshots`, `test_w1_gitignore_contains_secrets` | **PASS** |
| **W2** | Telemetry Ingestion & Sequence Monotonicity | `TelemetryIngestEngine` (HTTP POST / NDJSON) | `test_w2_valid_packet_ingest`, `test_w2_sequence_increment` | **PASS** |
| **W3** | Backend Validation & Rejection Engine | Structural, NaN/Inf, bounds, gaps, duplicate checks | `test_w3_reject_unauthorized_device` through `test_w3_preserve_missingness_none_not_zero` | **PASS** |
| **W4** | Frontend Live Reflection & Heartbeat FSM | SSE `/api/telemetry/stream` & 1s poll | `test_w4_heartbeat_transitions`, `test_w4_status_adapter_snapshot_format` | **PASS** |
| **W5** | Physical Sensor Feasibility | INA219 (V/I) & DS18B20 (T) CRC / disconnect checks | `test_w5_sensor_validity_flag` | **PASS** |
| **W6** | Actuation Safety & Command Lifecycle | Autonomous ESP32 Interlock & Preempting `STOP` | `test_w6_command_lifecycle_queue`, `test_w6_reject_arbitrary_unsafe_commands` | **PASS** |
| **W7** | NEXUS Shadow Mode Integration | Real Telemetry $\to$ Feature Engine $\to$ Epistemic State | `test_w7_shadow_mode_pipeline` | **PASS** |
| **W8** | Replay Determinism & HIL Runner | `WifiHardware` & NDJSON Replay Artifact | `test_w8_wifi_hardware_interface`, `esp32_wifi_prototype_run_001.ndjson` | **PASS** |

---

## 6. Live Hardware Dashboard Integration Ledger (TEST-DASH-01 – TEST-DASH-20)

| Test ID | Requirement | Architecture Component | Verification Suite | Status |
|---|---|---|---|:---:|
| **TEST-DASH-01** | Live Voltage Appears | Real INA219 Telemetry Stream | `test_dash_01_live_voltage_appears` | **PASS** |
| **TEST-DASH-02** | Live Current Appears | Quiescent Current Preservation (0.000A) | `test_dash_02_live_current_appears` | **PASS** |
| **TEST-DASH-03** | Live Power Appears | Real Power Ingestion & Calculation | `test_dash_03_live_power_appears` | **PASS** |
| **TEST-DASH-04** | Live Temperature Appears | Real DS18B20 1-Wire Stream | `test_dash_04_live_temperature_appears` | **PASS** |
| **TEST-DASH-05** | Live Hardware State Appears | Dynamic Hardware State Reflection | `test_dash_05_live_hardware_state_appears` | **PASS** |
| **TEST-DASH-06** | Live Fault Appears | Fault Latching & SENSOR_INVALID Trip | `test_dash_06_live_fault_appears` | **PASS** |
| **TEST-DASH-07** | Wi-Fi Status Appears | Wi-Fi Connectivity & Real RSSI (dBm) | `test_dash_07_wifi_status_appears` | **PASS** |
| **TEST-DASH-08** | Sequence Appears | Monotonic Packet Sequence Counter | `test_dash_08_sequence_appears` | **PASS** |
| **TEST-DASH-09** | Packet Loss Appears | Gap Detection & Packet Loss Count | `test_dash_09_packet_loss_appears` | **PASS** |
| **TEST-DASH-10** | Fault Recovery Updates Frontend | Deterministic Recovery FSM & Trip Clear | `test_dash_10_fault_recovery_updates_frontend` | **PASS** |
| **TEST-DASH-11** | Historical Data Labelled HISTORICAL | Class C Segregation (Phase 5/6.1.1) | `test_dash_11_historical_data_is_labelled_historical` | **PASS** |
| **TEST-DASH-12** | Historical Never Replaces Live | Real Telemetry Preservation Priority | `test_dash_12_historical_data_never_replaces_live_data` | **PASS** |
| **TEST-DASH-13** | Missing SOH Displays Unavailable | Explicit Unperformed Qualification State | `test_dash_13_missing_soh_displays_unavailable_state` | **PASS** |
| **TEST-DASH-14** | Missing R0 Displays Unavailable | Explicit Unperformed Resistance State | `test_dash_14_missing_r0_displays_unavailable_state` | **PASS** |
| **TEST-DASH-15** | Missing Risk Trace Displays Unavailable | Explicit Unperformed Risk State | `test_dash_15_missing_risk_trace_displays_unavailable_state` | **PASS** |
| **TEST-DASH-16** | No Fake Graph Points Generated | Zero Interpolation & Exact Point Count | `test_dash_16_no_fake_graph_points_are_generated` | **PASS** |
| **TEST-DASH-17** | Decision Trace Appears on Events | Actual Recorded Event Rendering | `test_dash_17_decision_trace_appears_when_real_decision_events_exist` | **PASS** |
| **TEST-DASH-18** | Decision Trace Unavailable Without Run | Structured Empty Audit Box Rendering | `test_dash_18_decision_trace_remains_unavailable_when_no_qualification_run` | **PASS** |
| **TEST-DASH-19** | API Status & Telemetry Consistency | Status Adapter & Live Engine Sync | `test_dash_19_api_status_and_live_telemetry_remain_consistent` | **PASS** |
| **TEST-DASH-20** | No Stale FAULT After Recovery | Dynamic State Deserialization & Clearing | `test_dash_20_frontend_does_not_show_stale_fault_after_real_recovery` | **PASS** |

---

**Current Master Validation Status**: **`INTEGRATION_COMPLETE_WITH_LIMITATIONS`**  
*Explanation*: Complete real hardware Wi-Fi telemetry integration, live dynamic charting without fabrication, robust fault-recovery propagation, explicit evidence-backed segregation, and comprehensive test suite pass. Active monitoring stream confirmed; active diagnostic pulse qualification testing remains pending next physical excitation phase.



