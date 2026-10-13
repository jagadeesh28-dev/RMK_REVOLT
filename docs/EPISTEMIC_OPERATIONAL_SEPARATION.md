# Epistemic Belief vs. Operational Decision Separation

**Project:** RMK REVOLT / SECONDShift Platform  
**Document ID:** `docs/EPISTEMIC_OPERATIONAL_SEPARATION.md`  
**Phase:** Phase 1 Architectural Contract  
**Status:** Canonical Reference Specification  

---

## 1. The Core Principle

A battery qualification system must strictly preserve the distinction between:

1. **WHAT THE SYSTEM BELIEVES** (The Epistemic State: an assessment of state, model, and measurement evidence under uncertainty)
2. **WHAT THE SYSTEM IS ALLOWED TO DO** (The Operational Decision: an authorized action within a bounded operating envelope)
3. **WHAT THE SYSTEM ACQUIRES NEXT** (The Information Action: whether additional diagnostic testing is justified)

These three concepts must **never be collapsed into a single variable** or overloaded into a single enum.

---

## 2. Architectural Flow Diagram

```
                 PHYSICAL EVIDENCE & TELEMETRY
                              │
                              ▼
                     EPISTEMIC STATE
             "What does the system believe?"
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
   INFORMATION ACTION                    OPERATIONAL DECISION
"Should we test further?"             "What is permitted right now?"
   NO_TEST / REQUEST_TEST                OPERATE / DERATE / HOLD / RETIRE
```

---

## 3. Epistemic States (`EpistemicState`)

Defined in [secondshift/interfaces/epistemic_schema.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/interfaces/epistemic_schema.py):

| Epistemic State | Semantic Definition | Validating Evidence | Invalidation Boundary |
| :--- | :--- | :--- | :--- |
| `SUPPORTED_HEALTHY` | Available diagnostic evidence supports the healthy interpretation within the validated operating domain. | Clear triage, high SOH posterior ($\mu \ge 0.70$), low uncertainty ($\sigma_{\text{SOH}} \le 0.04$), low $R_0$, known chemistry ($P \ge 0.99$). | Does **NOT** mean "guaranteed healthy". Overruled instantly if a physical trip occurs. |
| `UNCERTAIN` | State or model parameters have high variance or conflicting likelihoods. | Wide credible interval ($\sigma_{\text{SOH}} > 0.04$ or $\sigma_{R_0} > 0.5\text{ m}\Omega$), ambiguous chemistry ($P < 0.90$). | Does not mean degraded; implies further diagnostic testing may yield high EVSI. |
| `DISTRIBUTION_SHIFTED`| Specimen deviates statistically from qualified reference populations. | Out-of-distribution impedance curve, uncharacterized manufacturing batch, atypical form factor. | Distinct from sensor fault; telemetry is valid, but the battery dynamics are unmodeled. |
| `KNOWN_DEGRADED` | Concrete physical or electrochemical evidence of degradation is detected. | SOH below cutoff ($\mu < 0.65$), elevated resistance ($R_0 > 3.5\text{ m}\Omega$), abnormal self-discharge drift ($> 15\text{ mV/hr}$). | Permanent degradation; further diagnostic testing cannot restore eligibility. |
| `INSUFFICIENT_DATA` | History or test observations are too sparse to evaluate state or regime. | Initial intake state prior to active testing, missing telemetry cycles, truncated pulse sequence. | Default prior state before evidence acquisition. |

> [!CAUTION]
> **Prohibition of `KNOWN_GOOD`:**  
> The state `KNOWN_GOOD` is strictly prohibited in the RMK REVOLT architecture. Absence of evidence of degradation is never equivalent to proof of health. A battery may have latent internal dendrites or unobserved degradation paths that have not yet manifested at terminal rest.

---

## 4. Operational Decisions (`OperationalDecision`)

The system authorizes exactly four mutually exclusive operational actions:

1. **`OPERATE`:** Evidence permits normal intended operation under configured stationary BESS constraints.
2. **`DERATE`:** Battery may be utilized only under a restricted operating envelope (e.g., restricted C-rate $\le 0.5\text{C}$, power throttling, narrower SOC window $20\% - 80\%$).
3. **`HOLD`:** Do not authorize operation. Battery is quarantined pending additional diagnostic tests, manual engineering inspection, or thermal monitoring.
4. **`RETIRE`:** Second-life operation is permanently refused. Battery is safely discharged and routed to hydrometallurgical recycling or scrap salvage.

---

## 5. Information Action (`InformationAction`)

1. **`NO_TEST`:** No further diagnostic testing is recommended (stopping rule reached or VOI $\le 0$).
2. **`REQUEST_TEST`:** Additional diagnostic test is justified because expected value of uncertainty reduction exceeds test execution cost ($\text{VOI} > 0$).

> [!IMPORTANT]
> **Invariant:** `TEST` is an information-gathering action, **never an operational decision**. If the system is actively requesting or executing a diagnostic test, the operational decision is strictly `HOLD` or `RETIRE` during the test, never `OPERATE`.

---

## 6. Representative Case Walkthroughs

### Case A: Insufficient Intake Evidence
- **Observations:** Specimen arrives at testbed. Rest voltage is $3.31\text{V}$, casing is undamaged. Zero cycling or pulse data available.
- **Epistemic State:** `INSUFFICIENT_DATA`
- **Information Action:** `REQUEST_TEST` (VOI of initial pulse is positive)
- **Operational Decision:** `HOLD`
- **Rationale:** *"We do not know enough to certify the cell, so we request additional diagnostic testing while maintaining the cell in safe quarantine (HOLD)."*

### Case B: Supported Healthy Candidate
- **Observations:** Chemistry confirmed LFP ($P = 0.998$), SOH posterior $= 91.2\% \pm 1.8\%$, $R_0 = 1.95\text{ m}\Omega \pm 0.15\text{ m}\Omega$, all triage gates cleared, VOI of additional tests $\le 0$.
- **Epistemic State:** `SUPPORTED_HEALTHY`
- **Information Action:** `NO_TEST`
- **Operational Decision:** `OPERATE`
- **Rationale:** *"Evidence supports the healthy interpretation within the validated envelope. Additional testing is economically unjustified; normal operation is authorized."*

### Case C: Distribution Shift / Unmodeled Cell
- **Observations:** Telemetry is pristine (no sensor errors), but voltage relaxation trajectory exhibits multi-exponential dynamics incompatible with both standard LFP and standard NMC reference models.
- **Epistemic State:** `DISTRIBUTION_SHIFTED`
- **Information Action:** `NO_TEST` (standard tests cannot resolve unmodeled chemistry without reference models)
- **Operational Decision:** `HOLD`
- **Rationale:** *"Cell is statistically out-of-distribution. Normal operation is strictly refused to prevent thermal excursions under uncharacterized degradation behavior."*

### Case D: Severe Physical / Micro-Short Degradation
- **Observations:** Self-discharge drift rate $dV/dt = 22.0\text{ mV/hr} > 15.0\text{ mV/hr}$, or $R_0 = 18.5\text{ m}\Omega$.
- **Epistemic State:** `KNOWN_DEGRADED`
- **Information Action:** `NO_TEST` (diagnostic cost would be wasted on a cell that cannot qualify)
- **Operational Decision:** `RETIRE`
- **Rationale:** *"Cell exhibits irreversible electrochemical degradation violating physical triage gates. Routed directly to recycling."*

---

## 7. Mathematical & Software Invariants

The following invariants are programmatically enforced by `DecisionAuditRecord.validate_invariants()`:
1. `OperationalDecision` cannot be `TEST`.
2. `InformationAction` cannot be `OPERATE`, `DERATE`, `HOLD`, or `RETIRE`.
3. `KNOWN_GOOD` cannot exist in any enum or data structure.
4. If `sensor_valid is False` or telemetry status is `FAULT`, `OperationalDecision` cannot be `OPERATE`.
5. Missing RUL cannot be coerced to `0.0`; it must remain `None`.
6. High state uncertainty ($\sigma_{\text{SOH}} \ge 0.10$) cannot be assigned `SUPPORTED_HEALTHY`.
7. Epistemic state and operational decision must be separate instances.
8. If `information_action == REQUEST_TEST`, `OperationalDecision` cannot be `OPERATE`.
