# ARTIFACT B: System Architecture Specification
**Project:** RMK-REVOLT — EV Battery Circularity Challenge  
**Core Subsystems:** TRIAGE + SECONDShift + Decision Engine + H.E.R.M.E.S.

---

## 1. Closed-Loop Architectural Flow

The RMK-REVOLT system operates as a closed-loop epistemic-physical control system:

```
[ RETIRED EV BATTERY PACK ]
             │
             ▼
   ┌───────────────────┐
   │      TRIAGE       │ ──(Safety Failure: Voc < 2.0V, Bulge, Leakage)──► [ HARD REJECT / RECYCLE ]
   │ Deterministic Gate│
   └───────────────────┘
             │ (PASSED)
             ▼
   ┌───────────────────┐
   │    SECONDShift    │ ◄─────────────────────────────────────────────┐
   │ Diagnostic Engine │                                               │
   └───────────────────┘                                               │
             │ (Belief b_i + VOI)                                      │
             ▼                                                         │ (Belief Update)
   ┌───────────────────┐                                               │
   │  DECISION ENGINE  │                                               │
   │ Utility Optimizer │                                               │
   └───────────────────┘                                               │
       │           │                                                   │
  (Action:TEST) (Action: OPERATE / DERATE / BYPASS)                    │
       │           │                                                   │
       ▼           ▼                                                   │
 [Physical Test] ┌───────────────────┐                                 │
       │         │    H.E.R.M.E.S.   │                                 │
       │         │ Topology Machine  │                                 │
       │         └───────────────────┘                                 │
       │                   │                                           │
       │                   ▼                                           │
       │           [ SECOND-LIFE APP ] (Solar / Telecom BESS)          │
       │                   │                                           │
       └───────────────────┴──► [ DYNAMIC VOLTAGE / CURRENT RESPONSE ] ─┘
```

---

## 2. Subsystem Definitions

### 2.1 TRIAGE (Initial Deterministic Safety Gate)
TRIAGE is strictly **deterministic**. It forbids black-box AI classifiers to prevent safety hallucinations.

- **Inputs:**
  1. Open circuit voltage ($V_{oc}$)
  2. Ambient and cell surface temperature ($T_{cell}$)
  3. Visual / physical indicators (bulging, venting seal rupture, terminal corrosion)
  4. Self-discharge relaxation rate ($\frac{dV}{dt}$) over a 15-second rest window
  5. BMS log records (if uncorrupted history exists)

- **Deterministic Logic:**
  - **REJECT Gate 1 (Copper Dissolution):** If $V_{oc} < 2.00$ V $\implies$ REJECT immediately.
  - **REJECT Gate 2 (Overcharge Hazard):** If $V_{oc} > 3.75$ V $\implies$ REJECT immediately.
  - **REJECT Gate 3 (Mechanical Integrity):** If pouch/canister bulging or venting $\implies$ REJECT immediately.
  - **REJECT Gate 4 (Internal Exothermic):** If $T_{cell} - T_{ambient} > 4.0^\circ\text{C}$ at rest $\implies$ REJECT immediately.
  - **REJECT Gate 5 (Internal Micro-Short):** If self-discharge $\frac{dV}{dt} > 15$ mV/hour $\implies$ REJECT immediately.
  - **HOLD Gate (Ambiguity):** If $2.00 \le V_{oc} < 2.50$ V or terminal damage $\implies$ HOLD for manual bench examination.
  - **ACCEPT:** Cleared for SECONDShift adaptive characterization.

---

### 2.2 SECONDShift (Decision-Efficient Diagnosis)
SECONDShift does not execute rigid sequential testing. It computes:
$$\text{"What is the minimum additional measurement required to make the next safe decision?"}$$

- **Available Diagnostic Actions:**
  1. `pulse_power_test`: 20-second 1.0C pulse $\implies$ measures immediate ohmic jump $\Delta V / I$ to isolate $R_0$, and subsequent polarization to isolate $R_1$. (Cost: ₹17.0, Time: 20s).
  2. `short_coulometric_cycle`: 600-second 0.5C partial discharge $\implies$ observes ampere-hour throughput and voltage inflection to collapse capacity uncertainty $\sigma_{\text{SOH}}$ from 0.12 to 0.02. (Cost: ₹78.0, Time: 600s).
  3. `thermal_recovery_step`: 180-second 0.8C load with rest $\implies$ measures $\frac{dT}{dt}$ and convective heat dissipation $h_{eff}$ to identify localized high-resistance joints. (Cost: ₹35.0, Time: 180s).

---

### 2.3 DECISION ENGINE (Mathematical Formulation)
The Decision Engine maps the belief state $b_i = (\mu_{\text{SOH}}, \sigma_{\text{SOH}}, \mu_{R_0}, \sigma_{R_0})$ into an action $a \in \{\text{TEST}, \text{OPERATE}, \text{DERATE}, \text{BYPASS}, \text{ISOLATE}, \text{RETIRE}\}$.

$$\max_{a} \mathcal{U}(a \mid b_i, \mathcal{A})$$

- **Expected Operational Utility:**
  $$\mathcal{U}(\text{OPERATE}) = P_{\text{compliant}} \cdot V_{\text{revenue}} - (1 - P_{\text{compliant}}) \cdot C_{\text{safety\_penalty}} - C_{\text{deg}}$$
  where:
  $$P_{\text{compliant}} = \Phi\left(\frac{\mu_{\text{SOH}} - \text{SOH}_{min}}{\sigma_{\text{SOH}}}\right) \cdot \Phi\left(\frac{R_{0,max} - \mu_{R_0}}{\sigma_{R_0}}\right)$$

- **DERATED Mode Formulation:**
  By restricting maximum module current to $0.5 \times I_{string}$:
  - Joule heating $I^2 R$ drops by $75\%$.
  - Thermal runaway probability drops by $>85\%$.
  - $\mathcal{U}(\text{DERATE}) = P_{\text{comp, derate}} \cdot (0.75 \cdot V_{\text{rev}}) - (1 - P_{\text{comp, derate}}) \cdot (0.15 \cdot C_{\text{penalty}}) - C_{\text{deg, derate}}$.

- **Value of Information (VOI) for Test $k$:**
  $$\text{VOI}(k) = \mathbb{E}_{y_k}\left[\max_{a \in \mathcal{A}_{op}} \mathcal{U}(a \mid b_i \oplus y_k)\right] - \max_{a \in \mathcal{A}_{op}} \mathcal{U}(a \mid b_i) - \text{Cost}(k)$$
  If $\max_k \text{VOI}(k) > 0$ and $\sigma_{\text{SOH}} > \sigma_{target} \implies$ **Schedule Test $k^*$**.  
  Else $\implies$ **Transition directly to best operational action $a^*$**.

---

### 2.4 H.E.R.M.E.S. (Uncertainty-Aware Module Participation Control)
H.E.R.M.E.S. is the physical actuator layer implementing dynamic topological bypass and current derating.

```
       [ MODULE + ] ───┐
                       │
             ┌─────────┴─────────┐
             │                   │
         [ S_series ]        [ S_bypass ]
             │                   │
             ▼                   ▼
       [ MODULE - ] ───┬─────────────────── [ STRING BUS ]
                       │
```

- **Topological States:**
  1. `ACTIVE` ($S_{series} = \text{ON}, S_{bypass} = \text{OFF}$): Carries 100% of string current ($I_{mod} = I_{string}$).
  2. `DERATED` (PWM current duty-cycling or interleaved current-sharing): Carries average 50% load ($I_{mod} = 0.5 \times I_{string}$).
  3. `BYPASS` ($S_{series} = \text{OFF}, S_{bypass} = \text{ON}$): Shunts string current around the module ($I_{mod} = 0$). Module rests or cools down.
  4. `ISOLATED` ($S_{series} = \text{OFF}, S_{bypass} = \text{OFF}$): Completely disconnected from pack circuitry upon hard safety trip.
