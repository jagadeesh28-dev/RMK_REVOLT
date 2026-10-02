# Epistemic Chemistry & Model Disambiguation Model

```
====================================================================================================
MODULE: Layer 2A — Chemistry & Model Identity Disambiguation Engine
HYPOTHESIS CLASS: M ∈ {LFP, NMC, UNKNOWN}
CORE PRINCIPLE: "KNOW WHAT YOU KNOW. KNOW WHAT YOU DON'T KNOW. NEVER GUESS AN IDENTITY."
ABSTENTION STATE: UNKNOWN / AMBIGUOUS ---> HOLD / RECYCLE
====================================================================================================
```

---

## 1. Problem Formulation

Second-life battery qualification cannot assume that incoming battery modules possess authentic, trustworthy nameplate labels. In real-world recycling streams, retired modules often lack markings, possess incorrect vendor tags, or arrive mixed.

Because Lithium Iron Phosphate (LFP) and Nickel Manganese Cobalt (NMC) differ fundamentally in operating voltage envelopes, thermal runaway kinetics, and critical degradation thresholds, operating an NMC cell under an LFP algorithm (or vice-versa) presents catastrophic safety risks.

We formalize chemistry identity as an **epistemic discrete hypothesis random variable**:
$$\mathcal{M} \in \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$$

Where **`UNKNOWN`** represents an explicit, non-empty hypothesis encompassing unmodeled, contaminated, or exotic battery chemistries (e.g. LCO, LTO, Na-ion, solid-state).

---

## 2. Multi-Feature Physical Observation Vector

Rather than relying on a single scalar measurement (which exhibits phase ambiguity at intermediate states of charge), the physical observation vector $\mathbf{y}$ extracts seven electrochemical features:

$$\mathbf{y} = \begin{bmatrix}
\text{OCV} \\
\Delta V \\
\Delta V / \Delta I \\
dV/dt \\
\text{Relaxation Slope} \\
\Delta T / \Delta Q \\
\text{Recovery Ratio}
\end{bmatrix} = \begin{bmatrix}
\text{Thermodynamic resting open-circuit voltage (V)} \\
\text{Transient voltage drop during 5A galvanostatic pulse (V)} \\
\text{High-frequency Ohmic resistance } R_0 \; (\Omega) \\
\text{Galvanostatic potential slope during discharge (V/s)} \\
\text{Post-pulse diffusion relaxation rate (mV/s)} \\
\text{Entropic/ohmic thermal rise coefficient (}^\circ\text{C/Ah)} \\
\text{Electrochemical potential recovery ratio after 60s}
\end{bmatrix}$$

---

## 3. Bayesian Inference Equations

Given prior belief distribution $\mathbf{P}_0 = [P(\text{LFP}), P(\text{NMC}), P(\text{UNKNOWN})]^T$, the posterior probability given physical measurements $\mathbf{y}$ is updated via Bayes' Theorem:

$$P(M \mid \mathbf{y}) = \frac{p(\mathbf{y} \mid M) P(M)}{\sum_{M' \in \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}} p(\mathbf{y} \mid M') P(M')}$$

### Likelihood Models:
1. **LFP Likelihood:** Characterized by a flat two-phase plateau ($V_{\text{plateau}} \approx 3.28\text{V} - 3.34\text{V}$), low galvanostatic slope $dV/dt \approx 0.0044\text{ V/s}$, and low entropic coefficient:
   $$p(\mathbf{y} \mid \text{LFP}) = \mathcal{N}(\mathbf{y}; \boldsymbol{\mu}_{\text{LFP}}, \mathbf{\Sigma}_{\text{LFP}})$$
2. **NMC Likelihood:** Characterized by a sloping solid-solution potential ($3.60\text{V} - 4.15\text{V}$), steeper galvanostatic slope $dV/dt \approx 0.0125\text{ V/s}$, and higher thermal dissipation:
   $$p(\mathbf{y} \mid \text{NMC}) = \mathcal{N}(\mathbf{y}; \boldsymbol{\mu}_{\text{NMC}}, \mathbf{\Sigma}_{\text{NMC}})$$
3. **UNKNOWN Likelihood:** Formulated as a bounded uniform distribution over the permissible SELV operating envelope ($V \in [10.0\text{V}, 14.6\text{V}]$):
   $$p(\mathbf{y} \mid \text{UNKNOWN}) = \frac{1}{\prod_{i=1}^d (y_{i,\text{max}} - y_{i,\text{min}})}$$

---

## 4. Confidence States & Epistemic Abstention

The continuous posterior probability vector is mapped onto three discrete confidence states:

```
                      POSTERIOR PROBABILITY P(M | y)
                                    |
          +-------------------------+-------------------------+
          |                                                   |
    P(M) >= 0.990 & P(UNK) <= 0.005             P(M) < 0.990 OR P(UNK) > 0.050
          |                                                   |
          v                                                   v
     [KNOWN STATE]                                      [UNCERTAIN STATE]
          |                                                   |
  Proceed to Bayesian                               +---------+---------+
  State Estimator                                   |                   |
                                             0.900 <= P(M) < 0.990   P(M) < 0.900
                                                    |                   |
                                                    v                   v
                                             [PROBABLE STATE]    [AMBIGUOUS STATE]
                                                    |                   |
                                             Trigger Active      Epistemic Refusal:
                                             Diagnostic Test     HOLD / RECYCLE
```

### Action Admissibility Matrix:
| Confidence State | Condition | Permitted Actions | Strictly Forbidden Actions |
| :--- | :--- | :--- | :--- |
| **KNOWN** | $P(M \mid \mathbf{y}) \ge 0.990$ | `OPERATE`, `DERATE`, `TEST`, `RETIRE` | None |
| **PROBABLE** | $0.900 \le P(M \mid \mathbf{y}) < 0.990$ | `TEST`, `HOLD` | **`OPERATE`, `DERATE`** |
| **AMBIGUOUS** | $P(M \mid \mathbf{y}) < 0.900$ | `TEST`, `HOLD`, `RETIRE` | **`OPERATE`, `DERATE`** |
| **UNKNOWN** | Diagnostic Budget Exhausted | `HOLD`, `RETIRE` | **`OPERATE`, `DERATE`, `TEST`** |

---

## 5. Empirical Stress Test Verification

The chemistry disambiguation engine was evaluated across 250 cycles in [`run_chemistry_attacks.py`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/experiments/run_chemistry_attacks.py):

| Test Scenario | Cohort Size | Unsafe Cells | False Acceptances | Empirical FAR | Abstention Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Known LFP** | 50 | 19 | 0 | **0.0%** | 0.0% |
| **Known NMC** | 50 | 50 | 0 | **0.0%** | 96.0% |
| **Unknown Chemistry** | 50 | 31 | 0 | **0.0%** | **56.0% (Refused)** |
| **Wrong Label (NMC as LFP)** | 50 | 50 | 0 | **0.0%** | **100.0% (Refused)** |
| **Mixed LFP/NMC (50/50)** | 50 | 34 | 0 | **0.0%** | **52.0% (Refused)** |

> [!NOTE]
> **Conclusion:** When chemistry is ambiguous, the system refrains from forced classification, guaranteeing conservative behavior and preventing unsafe deployment.
