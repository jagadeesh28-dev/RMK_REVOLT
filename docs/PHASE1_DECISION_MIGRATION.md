# Phase 1 Decision Migration Specification

**Project:** RMK REVOLT / SECONDShift Platform  
**Document ID:** `docs/PHASE1_DECISION_MIGRATION.md`  
**Phase:** Phase 1 Architectural Contract  
**Status:** Active Migration Plan  

---

## 1. Current Decision Semantics (As-Is)

In the current modular implementation ([secondshift/software/secondshift/decision_engine.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/software/secondshift/decision_engine.py) and [closed_loop_runner.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/software/secondshift/closed_loop_runner.py)):

1. **Overloaded `decision` Field:**
   - The method `SECONDShiftDecisionEngine.evaluate_decision()` returns a single dictionary containing:
     ```python
     {
         "decision": final_action, # Can be "TEST", "OPERATE", "DERATE", "HOLD", "RETIRE"
         "recommended_test": final_test_to_run,
         "decision_reason": decision_reason,
         "admissible_actions": list(admissible_actions),
         ...
     }
     ```
   - **Semantic Defect:** `"TEST"` is an intermediate information-gathering action, but it occupies the exact same field as operational dispositions (`"OPERATE"`, `"RETIRE"`).
2. **Missing Epistemic Belief:**
   - The decision engine outputs what the system *decided to do*, but does not formally categorize what the system *believes* about the battery (`SUPPORTED_HEALTHY`, `UNCERTAIN`, `DISTRIBUTION_SHIFTED`, `KNOWN_DEGRADED`, `INSUFFICIENT_DATA`).
3. **Hardcoded Heuristic Values:**
   - Chemistry EVSI is hardcoded to `85.0` (`evsi_chem = 85.0`) in line 112.
   - Uncertainty bounds are clamped with magic numbers (`min(estimator.sigma_soh, 0.04)`).
4. **Ad-hoc Audit Trail:**
   - Traces are recorded as simple unstructured dictionary lists without a validated schema.

---

## 2. Target Semantic Model (To-Be)

The target model strictly conforms to [secondshift/interfaces/epistemic_schema.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/interfaces/epistemic_schema.py):

```
                   UPSTREAM EVIDENCE
            (Triage + Chemistry + State + Data Quality)
                           │
                           ▼
                 EpistemicState (Enum)
        [SUPPORTED_HEALTHY | UNCERTAIN | DISTRIBUTION_SHIFTED |
              KNOWN_DEGRADED | INSUFFICIENT_DATA]
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
         ▼                                   ▼
InformationAction (Enum)           OperationalDecision (Enum)
 [NO_TEST | REQUEST_TEST]           [OPERATE | DERATE | HOLD | RETIRE]
         │                                   │
         └─────────────────┬─────────────────┘
                           │
                           ▼
                 DecisionAuditRecord
         (20-field strongly typed schema)
```

### Semantic Translation Table

| Legacy String Return | New `InformationAction` | New `OperationalDecision` | New `EpistemicState` | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `"TEST"` | `REQUEST_TEST` | `HOLD` | `UNCERTAIN` or `INSUFFICIENT_DATA` | During active diagnostic testing, the battery is held in quarantine; operational clearance is not granted until test sequence concludes. |
| `"OPERATE"` | `NO_TEST` | `OPERATE` | `SUPPORTED_HEALTHY` | Clear triage, verified chemistry ($P \ge 0.99$), low state variance ($\sigma \le 0.04$), $P(\text{Fail}) \le 0.01$. |
| `"DERATE"` | `NO_TEST` | `DERATE` | `SUPPORTED_HEALTHY` or `UNCERTAIN` | Fails full-rate barrier but clears derated envelope ($P(\text{Fail}) \le 0.01$ at $0.5\text{C}$). |
| `"HOLD"` | `NO_TEST` | `HOLD` | `UNCERTAIN` or `DISTRIBUTION_SHIFTED` | Test budget exhausted or non-actionable; quarantined for review. |
| `"RETIRE"` | `NO_TEST` | `RETIRE` | `KNOWN_DEGRADED` | Fails physical triage or violates hard probabilistic safety barrier. |

---

## 3. Module-by-Module Migration Plan

To ensure zero regressions across existing test suites, migration will proceed in controlled phases:

### Phase 1: Canonical Contracts (Current Phase — Complete)
- **Files Created:**
  - `secondshift/interfaces/epistemic_schema.py`
  - `secondshift/tests/test_epistemic_schema.py`
  - `docs/EPISTEMIC_OPERATIONAL_SEPARATION.md`
  - `docs/PHASE1_DECISION_MIGRATION.md`
- **Files Modified:**
  - `secondshift/interfaces/__init__.py`
- **Result:** Semantic contracts and invariant validators exist and are 100% tested without altering existing runner logic.

### Phase 14: Decision Engine & Closed-Loop Runner Migration (Scheduled for Phase 14)
- **Target Files:**
  - `secondshift/software/secondshift/decision_engine.py`
  - `secondshift/software/secondshift/closed_loop_runner.py`
- **Changes to be Implemented:**
  1. Add a dual-return mode to `SECONDShiftDecisionEngine.evaluate_decision()`:
     - Maintains legacy dictionary keys (`"decision": final_action`) for backward compatibility with downstream callers.
     - Adds typed fields: `"epistemic_state": epistemic_state`, `"operational_decision": operational_decision`, `"information_action": information_action`, `"audit_record": record`.
  2. Replace hardcoded EVSI chemistry constant (`85.0`) with numerical quadrature over discrete chemistry model switching probabilities.
  3. Ensure `ClosedLoopRunner.run_qualification_pipeline()` produces and returns a complete `DecisionAuditRecord`.

### Phase 16: Dashboard Adapter Migration (Scheduled for Phase 16)
- **Target Files:**
  - `secondshift/software/ui/status_adapter.py`
  - `secondshift/software/ui/dashboard.py`
- **Changes to be Implemented:**
  1. Update `StatusAdapter` to extract `epistemic_state`, `operational_decision`, and `information_action` from the `DecisionAuditRecord`.
  2. Display the 5-state epistemic badge alongside the operational action in the industrial HMI UI.

---

## 4. Behavioral Compatibility & Risk Assessment

| Risk Description | Severity | Mitigation Strategy |
| :--- | :--- | :--- |
| **Existing tests expect `res["final_decision"] == "OPERATE"`** | HIGH | When updating `ClosedLoopRunner` in Phase 14, preserve the string `final_decision` as an alias to `record.operational_decision.value` to prevent breaking existing benchmark tests. |
| **Existing loop checks `if current_decision != "TEST"`** | HIGH | In the internal runner loop, check `if information_action == InformationAction.NO_TEST` while preserving string compatibility for intermediate traces. |
| **Simulation Hardware OVP Trip Edge Case** | MEDIUM | During hostile testing, an NMC cell at $V = 3.75\text{V}$ can trip the simulated analog comparator ($3.70\text{V}$), causing current to stop flowing. `measurement_primitives.py` must check $I_{\text{actual}} > I_{\text{threshold}}$ and report hardware trip instead of computing a zero voltage drop. |
| **Ground-Truth Registry Leakage** | HIGH | All newly constructed `DecisionAuditRecord` objects must pass the AST and runtime ground-truth isolation tests in `secondshift/tests/test_ground_truth_isolation.py`. |
