# Phase 6: Scientific Limitations & Unresolved Risks Report

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_LIMITATIONS.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Scientific Validation Lead, Safety-Critical ML Researcher, Research-Paper Methods Reviewer  
**Status**: **SCIENTIFICALLY FROZEN LIMITATIONS DOSSIER**  
**Core Invariant**:
$$\mathbf{KNOW\ WHAT\ YOU\ KNOW.\ KNOW\ WHAT\ YOU\ DON'T\ KNOW.\ NEVER\ OPTIMIZE\ SAFETY\ AWAY.}$$

---

## 1. Executive Summary

This document formalizes the exact physical, statistical, mathematical, and architectural boundaries of Phase 6. In accordance with the RMK REVOLT scientific charter, all limitations, unvalidated domains, and unproven claims are explicitly recorded to prevent unjustified engineering optimism.

---

## 2. Sample Size & Cohort Limitations

### A. Physical Cohort Underpowering ($N = 12$)
1. **Severe Underpowering of Physical NMC ($N = 3$)**:
   - The physical cohort contains only three physical NMC specimens (`SPECIMEN_09` to `SPECIMEN_11`).
   - Evaluating Leave-One-Chemistry-Out cross-validation on $N=3$ test cells yields only $df = 1$ in training when running within-NMC folds.
   - Statistical power $(1 - \beta)$ to detect a medium effect size ($\Delta\text{MAE} = 0.02$) is under $20\%$.
   - **Mandatory Policy**: Physical NMC findings must permanently remain labeled **EXPLORATORY**. No claim of "physically validated cross-chemistry generalization" can be made from $N=3$ cells.
2. **Unmodeled Exotic Specimen ($N = 1$)**:
   - `SPECIMEN_12_UNKNOWN_EXOTIC` represents an unmodeled experimental sodium/lithium hybrid chemistry.
   - It is inadmissible for regression training and must strictly trigger **`DISTRIBUTION_SHIFTED`** / **`DEFER`**.
3. **Form Factor and Geometry Confounding**:
   - All physical LFP cells are 4S cylindrical laboratory modules.
   - All physical NMC cells are single pouch cells.
   - Consequently, **chemistry is confounded with form factor and series packaging** in the physical cohort. It is currently impossible to determine whether observed plateau variations are driven purely by intercalation thermodynamics or packaging geometry.

---

## 3. Scope & Target Boundaries

### A. RUL Cross-Domain Validation NOT PERFORMED
- **SOH Transfer $\ne$ RUL Transfer**: Demonstrating that total polarization $\Delta V_{\text{total}}$ correlates with current discharge capacity (SOH) across chemistries does **NOT** imply that future remaining useful life (RUL) trajectories transfer across chemistries.
- **Data Boundary**: Longitudinal cycle-life aging data to end-of-life (EOL) is **strictly unavailable** for the physical intake cohort.
- **Formal Status**: **RUL CROSS-DOMAIN VALIDATION NOT PERFORMED**. RUL targets are classified as `UNKNOWN`. No synthetic RUL targets were fabricated.

### B. Synthetic Data Evidence Boundary (Level 1 vs. Level 4)
- Synthetic simulation specimens ($N = 100$) were utilized exclusively for controlled sensitivity sweeps, noise injection, and algorithm stress testing.
- **Strict Prohibition**: Synthetic cross-chemistry performance is **Level 1 Evidence**. It must never be presented as proof of physical cross-chemistry generalization (which requires Level 4 evidence).

---

## 4. Modeling & Algorithmic Limitations

### A. Failure of Chemistry-Conditioned Normalization (Model A3)
- Normalizing feature scale by dividing by empirical standard deviation $\hat{\sigma}_{\text{chem}}$ completely broke down under small sample sizes ($N=3$), resulting in a worst-case error of $2.4222$ MAE.
- Continuous parametric normalization requires $N \ge 30$ independent physical specimens per chemistry to avoid division-by-near-zero instabilities.

### B. Absence of Deep Learning Architectures
- In accordance with Phase 6 Section 25, complex deep learning architectures (Transformers, LSTMs, CNNs, foundation models) were intentionally **excluded**.
- A regularized linear baseline with explicit epistemic uncertainty gating is transparent, interpretable, and reproducible. A deep neural network would mask small-sample limitations behind overparameterized training fits.

---

## 5. Architectural & Operational Boundaries

1. **Safety Boundary Isolation**:
   - Phase 6 is strictly a **Prognostic Validation & Domain Validity Layer**.
   - Phase 6 does **NOT** possess operational safety authority.
   - `HardSafetyBarrier`, hardware analog comparators (LM393), thermal snaps (KSD9700), emergency cutoff relays, and the HERMES safety supervisor remain completely unaltered and isolated from ML inference.
2. **Field Validation Absence**:
   - No prospective second-life field deployment has been conducted (Level 5 evidence is absent).
   - Real-world vibration, variable thermal cycling, and uncharacterized second-life load profiles remain unvalidated.

---

## 6. Prohibited Overclaims

The following claims are **scientifically unproven and strictly prohibited**:
- *"Cross-chemistry validated"* (False: physical NMC $N=3$ is exploratory only).
- *"Chemistry-invariant features"* (False: polarization slopes differ between LFP and NMC).
- *"Universal health scalar"* (False: $R_0$ depends heavily on SOC, temperature, and current amplitude).
- *"Production ready"* (False: requires multi-pack prospective physical validation).
- *"Certified / Safe second-life ML"* (False: ML models provide prognostic estimates, not safety certification).
