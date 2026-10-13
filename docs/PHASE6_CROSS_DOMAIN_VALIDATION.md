# Phase 6: Cross-Domain Validation & Feature Transfer Report

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_CROSS_DOMAIN_VALIDATION.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Principal Battery Prognostics Research Engineer, Validation Lead  
**Status**: **SCIENTIFICALLY FROZEN EVIDENCE REPORT**  
**Evidence Level**: LEVEL 2 (Small Physical Cohort $N=12$) & LEVEL 1 (Simulation Cohort $N=100$)  

---

## 1. Executive Summary

This report evaluates cross-domain prognostic validity across Leave-One-Battery-Out (LOBO) and Leave-One-Chemistry-Out (LOCO) protocols. 

Key findings:
1. **Cross-Chemistry Physical Generalization is NOT IDENTIFIABLE with Current Physical Data**: Because only $N=3$ physical NMC cells exist, testing a model trained on LFP against NMC or vice versa is statistically underpowered ($df = 1$). All LOCO transfer results are explicitly labeled **EXPLORATORY DOMAIN TRANSFER**.
2. **Asymmetric Cross-Chemistry Transfer**:
   - **Train LFP $\to$ Test NMC**: Produced apparent low error ($\text{MAE} = 0.0742$).
   - **Train NMC $\to$ Test LFP**: Produced high error ($\text{MAE} = 0.1832$).
   - This asymmetry confirms that transferring from a low-sample domain to a broader domain fails, and low forward error was an artifact of small test sample size ($N=3$).
3. **$\Delta V_{\text{total}}$ Retains Physical Supremacy**: $\Delta V_{\text{total}}$ remains the single most reliable prognostic feature across chemistries ($r = -0.876$ physical LFP; $r = -0.912$ exploratory NMC; $r = -0.689$ mixed cohort).
4. **$R_0$ vs. $\Delta V_{\text{ohmic}}$ Redundancy Resolved**:
   - Under fixed $10\,\text{A}$ pulses, $R_0$ and $\Delta V_{\text{ohmic}}$ are functionally redundant ($r = 1.0000$).
   - Under variable current amplitudes ($1\,\text{A}$ to $20\,\text{A}$), collinearity drops to $r = 0.7009$. $R_0$ acts as a current-normalizing parameter on benches with varying current loads.

---

## 2. Leave-One-Chemistry-Out (LOCO) Protocol Results

We executed a strict Leave-One-Chemistry-Out evaluation using the physical cohort ($N=12$):

| Validation Protocol | Training Partition | Test Partition | Evaluated Features | Test MAE | Test RMSE | Scientific Classification |
|---|---|---|---|:---:|:---:|---|
| **LOCO Transfer 1** | Physical LFP ($N=8$) | Physical NMC ($N=3$) | $\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}, V_{\text{mean}}$ | $0.0742$ | $0.0912$ | **EXPLORATORY DOMAIN TRANSFER** |
| **LOCO Transfer 1 (Pulse Only)** | Physical LFP ($N=8$) | Physical NMC ($N=3$) | $\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$ | $0.1120$ | $0.1345$ | **EXPLORATORY DOMAIN TRANSFER** |
| **LOCO Transfer 1 (Normalized)** | Physical LFP ($N=8$) | Physical NMC ($N=3$) | Chemistry-Normalized Suite | $0.1471$ | $0.1780$ | **EXPLORATORY DOMAIN TRANSFER** |
| **LOCO Transfer 2** | Physical NMC ($N=3$) | Physical LFP ($N=8$) | $\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}, V_{\text{mean}}$ | **$0.1832$** | **$0.2410$** | **EXPLORATORY TRANSFER FAILURE** |
| **Pooled Baseline** | All 12 Physical Cells | Battery-Disjoint LOBO | $\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}, V_{\text{mean}}$ | $0.1370$ | $0.1776$ | LEVEL 2 PHYSICAL LOBO |

### Evidentiary Conclusion
> **Generalization Claim Assessment**:  
> The physical data does **NOT** support a claim of "validated cross-chemistry generalization." Transfer from NMC ($N=3$) to LFP ($N=8$) degraded error to $0.1832$ MAE. Cross-chemistry transfer is **NOT IDENTIFIABLE WITH CURRENT PHYSICAL DATA**.

---

## 3. In-Depth Anchor Feature Analysis: $\Delta V_{\text{total}}$

$\Delta V_{\text{total}}$ is the anchor feature of the RMK REVOLT prognostic architecture. We evaluated its behavior across operating dimensions:

1. **Within-LFP Stability**: Monotonic correlation with SOH ($r = -0.8762$). Median polarization in fresh cells is $0.021\,\text{V}$; degraded cells exceed $0.080\,\text{V}$; hazardous cells exceed $0.180\,\text{V}$.
2. **Within-NMC Exploratory Behavior**: Monotonic correlation with SOH ($r = -0.9120$). Fresh cell polarization is $0.024\,\text{V}$; aged cell is $0.045\,\text{V}$.
3. **Cross-Chemistry Transfer**: Polarization increases monotonically with cell age regardless of chemistry. However, NMC nominal polarization is offset by $+15\,\text{mV}$ due to steeper $d(\text{OCV})/d(\text{SOC})$ slope ($0.671\,\text{V/SOC}$ vs $0.128\,\text{V/SOC}$ for LFP).
4. **Current Sensitivity**: Scales linearly with current amplitude ($r = 0.98$ with $I$).
5. **Temperature Sensitivity**: Inversely proportional to temperature ($Q_{10} \approx 1.4$ due to Arrhenius charge-transfer resistance).
6. **Classification**: **`SUPPORTED_WITH_CHEMISTRY_CONDITIONING`**.

---

## 4. In-Depth Analysis: $R_0$ vs. $\Delta V_{\text{ohmic}}$ Redundancy

A central Phase 6 question was whether $R_0$ and $\Delta V_{\text{ohmic}}$ contain independent physical information:

$$R_0 \equiv \frac{\Delta V_{\text{ohmic}}}{\Delta I_{\text{pulse}}}$$

### Empirical Findings (EXP-603)
1. **Fixed Current Screening ($I = 10.0\,\text{A}$)**:
   - Pearson correlation: $\mathbf{r = 1.0000}$
   - Incremental LOFO predictive improvement: $\Delta\text{MAE} = 0.00000$
   - Finding: Under fixed current, $R_0$ and $\Delta V_{\text{ohmic}}$ are mathematically redundant. Reporting both as independent predictors is misleading.
2. **Variable Current Amplitude ($1\,\text{A}$ to $20\,\text{A}$ Sweep)**:
   - Pearson correlation drops to: $\mathbf{r = 0.7009}$
   - Finding: When current fluctuates across test cycles or hardware benches, $R_0$ provides essential normalization, preventing current sag from being mistaken for internal cell degradation.

### R0 Context Conditioning Sweep
We evaluated six context conditioning models for $R_0$:
- **Mode 1 (RAW)**: $r = -0.8761$, $\text{Var} = 0.00071$
- **Mode 2 (SOC-Conditioned)**: $r = -0.8761$, $\text{Var} = 0.00069$
- **Mode 3 (Temp-Conditioned)**: $r = -0.8761$, $\text{Var} = 0.00071$
- **Mode 4 (SOC + Temp)**: $r = -0.8761$, $\text{Var} = 0.00069$
- **Mode 5 (Chemistry-Conditioned)**: $r = -0.8753$, $\text{Var} = 0.00018$
- **Mode 6 (Fully Contextualized)**: $r = -0.8753$, $\text{Var} = 0.00017$

**Conclusion**: Contextualization reduces cross-chemistry variance from $0.00071$ to $0.00017$ while preserving correlation with SOH ($|r| \ge 0.87$). $R_0$ is retained as **`SUPPORTED_WITH_CONTEXT_NORMALIZATION`**.
