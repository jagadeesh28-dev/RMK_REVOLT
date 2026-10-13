# Phase 6.1: Scientific Claim Retractions & Scoping Ledger

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: [`docs/PHASE6_1_CLAIM_RETRACTIONS.md`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/docs/PHASE6_1_CLAIM_RETRACTIONS.md)  
**Status**: AUDITED & SYNCHRONIZED  
**Policy**: Explicit Scientific Traceability & No Hidden Overclaims  

---

## 1. Purpose & Audit Standard

The objective of Phase 6.1 is not to make RMK-REVOLT appear finished, universally valid, or production-certified. The objective is to make RMK-REVOLT **scientifically difficult to attack** by eliminating all overclaims, enforcing rigorous empirical scoping, and formally retracting or superseding statements that exceed the physical evidence.

This document compiles the complete register of claims from Phase 6 that have been retracted, superseded, or rescoped during the Phase 6.1 audit.

---

## 2. Complete Register of Retracted and Rescoped Claims

### Item 1: Uncertainty Inflation vs Calibration
- **Historical Phase 6 Text**:
  > *"Overconfident Under Domain Shift: FALSE"*  
  > *"Overconfidence successfully eliminated under domain shift."*
- **Audit Defect**: Conflated algorithm responsiveness (epistemic $\sigma$ inflating $2.54\times$ to $2.88\times$) with statistical calibration against physical prediction error. Pearson correlation across the physical cohort is $r = -0.0036$ ($p = 0.991$).
- **Phase 6.1 Corrected Baseline**:
  > *"The tested domain-shift scenarios produced increased epistemic uncertainty and DEFER behavior on unmodeled specimens. Calibration of uncertainty against independent physical prediction error remains unvalidated."*
- **Action**: **SUPERSEDED / SCOPED TO RESPONSIVENESS**.

---

### Item 2: Chemistry Confidence Threshold ($P(M|y) < 0.90$)
- **Historical Phase 6 Text**:
  > *"The 0.90 threshold validates safe cross-domain qualification gating."*
- **Audit Defect**: The threshold originated as an intuitive heuristic in `ChemistryDisambiguationEngine`. A sensitivity sweep across $[0.50, 0.99]$ showed that the physical cohort ($N=12$) contains only extreme confidence values ($0.99$ and $0.334$), rendering empirical threshold optimization completely underpowered.
- **Phase 6.1 Corrected Baseline**:
  > *"The threshold $P(M|y) < 0.90$ is designated as a PROVISIONAL ENGINEERING THRESHOLD. The threshold has not been prospectively calibrated against a sufficient physical domain-validation cohort."*
- **Action**: **SUPERSEDED / CLASSIFIED AS PROVISIONAL**.

---

### Item 3: Ohmic Resistance ($R_0$) Status & Incremental Value
- **Historical Phase 6 Text**:
  > *"Final Status: SUPPORTED_WITH_CONTEXT_NORMALIZATION"* (Phase 6 Status Table)
- **Audit Defect**: Contextualization reduced cross-chemistry variance by $76\%$, but variance reduction does not demonstrate incremental battery-disjoint prognostic value. Under fixed $10\,\text{A}$ pulses, $R_0$ is collinear with $\Delta V_{\text{ohmic}}$ ($r = 1.0000$) and provides zero independent LOFO value ($\Delta\text{MAE} = 0.00000$).
- **Phase 6.1 Corrected Baseline**:
  > *"R0_OHMIC is a protocol- and operating-condition-dependent electrical observation whose interpretation requires contextual normalization. Status: CONTEXTUAL / PROVISIONAL."*
- **Action**: **DOWNGRADED FROM SUPPORTED TO CONTEXTUAL / PROVISIONAL**.

---

### Item 4: Contact Resistance Distinction from Terminal Pulses
- **Historical Phase 6 Text**:
  > *"DELTA_V_OHMIC can distinguish contact resistance under multi-rate pulse conditions."*
- **Audit Defect**: Terminal electrical measurements aggregate bulk electrolyte resistance, separator tortuosity, tab welds, contact impedance, and testbench cabling. Direct isolation of contact resistance without independent Kelvin or micro-ohmmeter instrumentation is unproven.
- **Phase 6.1 Corrected Baseline**:
  > *"DELTA_V_OHMIC is sensitive to changes in aggregate electrical response under multi-rate pulse conditions."*
- **Action**: **WORDING RETRACTED & SCOPED TO AGGREGATE RESPONSE**.

---

### Item 5: Hardware Comparator Claim & Multi-Chemistry Safety
- **Historical Phase 6 Text**:
  > *"Autonomous LM393 analog window comparator safely protects multi-chemistry operation."*
- **Audit Defect**: The tripping of an LM393 comparator set to $3.70\,\text{V}$ (configured for 4S LFP) when an NMC cell was placed on the bench ($3.75\,\text{V}$) merely demonstrated that fixed LFP hardware thresholds prevented that specific NMC test from proceeding. It does not prove general cross-chemistry hardware safety.
- **Phase 6.1 Corrected Baseline**:
  > *"The tested LFP-configured hardware comparator prevented the tested NMC operating condition from proceeding, demonstrating that chemistry-specific hardware thresholds must be validated before cross-chemistry operation."*
- **Action**: **RE-SCOPED TO TESTED BENCH LIMITATION**.

---

### Item 6: Model A1 vs Model A6 Tradeoff Characterization
- **Historical Phase 6 Text**:
  > *"Model A6 is the preferred and best-performing cross-domain model."* (Without emphasizing accuracy sacrifice)
- **Audit Defect**: Model A6 has higher average error than Model A1 ($\text{MAE} = 0.1507$ vs $0.1370$). Calling A6 "better" without specifying the accuracy penalty obscures the engineering tradeoff.
- **Phase 6.1 Corrected Baseline**:
  > *"Model A6 is a risk-constrained, domain-aware model that trades 0.0137 average MAE (+9.98% error on known cells) in order to eliminate unsupported out-of-distribution false acceptance (8.33% -> 0.00%) by triggering DEFER."*
- **Action**: **TRADE-OFF FORMALIZED & ACCURACY PENALTY QUANTIFIED**.

---

### Item 7: Model A3 Normalization Failure Interpretation
- **Historical Phase 6 Text**:
  > *"Continuous parameter scaling on small cohorts is mathematically unsound."*
- **Audit Defect**: Continuous normalization is mathematically valid. The failure arose from an empirical sample variance estimator collapsing on $N=2$ training NMC cells ($\hat{\sigma} \to 0$).
- **Phase 6.1 Corrected Baseline**:
  > *"The tested continuous chemistry-conditioned normalization implementation was unstable under the available small-N NMC cohort, with variance estimates becoming numerically unstable."*
- **Action**: **RE-SCOPED FROM MATHEMATICAL PRINCIPLE TO IMPLEMENTATION INSTABILITY**.

---

### Item 8: $\Delta V_{\text{total}}$ Cross-Chemistry Generalization Scope
- **Historical Phase 6 Text**:
  > *"DELTA_V_TOTAL is validated across LFP and NMC."*
- **Audit Defect**: While correlation with degradation was strong in both LFP ($r = -0.843$) and NMC ($r = -0.998$), the physical NMC sample contains only $N=3$ specimens. Statistical cross-chemistry validation requires Level 4 evidence, which cannot be established on 3 cells.
- **Phase 6.1 Corrected Baseline**:
  > *"DELTA_V_TOTAL exhibited a monotonic association with the available degradation-related observations in both the LFP cohort and the small exploratory NMC cohort. Cross-chemistry generalization remains unproven."*
- **Action**: **SCOPED TO LEVEL 2 EXPLORATORY EVIDENCE**.

---

### Item 9: Physical Chemistry vs Form-Factor Confounding
- **Historical Phase 6 Text**:
  > *"Observed feature shifts reflect fundamental differences between LFP and NMC electrochemistry."*
- **Audit Defect**: In the physical cohort ($N=12$), all 8 LFP cells are 4S cylindrical modules, while all 3 NMC cells are single pouch cells. Chemistry is completely confounded with packaging geometry and electrical configuration.
- **Phase 6.1 Corrected Baseline**:
  > *"Chemistry and physical/electrical configuration are confounded in the available physical cohort, preventing clean attribution of observed domain differences to chemistry alone."*
- **Action**: **FORMALLY CLASSIFIED AS MAJOR CONFOUNDING LIMITATION**.

---

### Item 10: RUL Cross-Domain Validity
- **Historical Phase 6 Text**:
  > *"Domain adaptation architecture establishes cross-chemistry prognostic validity."* (Ambiguous scope)
- **Audit Defect**: Prognostic validity could be misinterpreted as encompassing Remaining Useful Life (RUL). Zero physical cycle aging curves were evaluated in Phase 6.
- **Phase 6.1 Corrected Baseline**:
  > *"RUL cross-domain validation was NOT PERFORMED. SOH domain transfer implies zero empirical validation for RUL domain transfer."*
- **Action**: **EXPLICITLY REAFFIRMED AS NOT PERFORMED**.

---

## 3. Summary of Prohibited Language Across Repository

The following terms and phrases are **STRICTLY PROHIBITED** when describing RMK-REVOLT cross-chemistry prognostic performance:

| Prohibited Phrase | Reason for Prohibition | Approved Replacement |
|---|---|---|
| *"Overconfidence eliminated"* | Uncertainty calibration unvalidated | *"Epistemic uncertainty increased under tested domain shifts"* |
| *"Uncertainty is calibrated"* | $r(|e|, \sigma) = -0.0036$, interval widths exceed $[0, 1]$ | *"Uncertainty calibration remains unvalidated"* |
| *"Cross-chemistry validated"* | Physical NMC $N=3$ severely underpowered | *"Exploratory cross-chemistry investigation only"* |
| *"Chemistry invariant"* | Physics and voltage plateaus differ fundamentally | *"Pulse-invariant features with domain validity gating"* |
| *"Contact resistance distinguished"* | Terminal measurements aggregate bulk, tabs, and wiring | *"Sensitive to aggregate electrical response"* |
| *"Hardware safely supports all chemistries"* | Comparator trips on unadapted NMC bench | *"Hardware thresholds must be validated per chemistry"* |
| *"Production ready"* | Prospective field testing not performed | *"Exploratory second-life research platform"* |
| *"Universal"* | Incompatible with governing scientific invariant | *"Domain-dependent within validated operational envelopes"* |
