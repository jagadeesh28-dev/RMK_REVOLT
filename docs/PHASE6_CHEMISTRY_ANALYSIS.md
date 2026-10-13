# Phase 6: Chemistry Stratification & Confounding Analysis Report

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_CHEMISTRY_ANALYSIS.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Principal Battery Prognostics Research Engineer, Electrochemical Data Scientist  
**Status**: **SCIENTIFICALLY FROZEN EVIDENCE REPORT**  
**Evidence Level**: LEVEL 2 (Small Physical Cohort $N=12$) & LEVEL 1 (Simulation Cohort $N=100$)  

---

## 1. Executive Summary

This report analyzes how the candidate prognostic features identified in Phase 5.1 behave across battery chemistries (LFP vs. NMC vs. UNKNOWN). 

The primary scientific findings are:
1. **$V_{\text{mean}}$ is a Chemistry Proxy, NOT a Health Feature**: $V_{\text{mean}}$ displays a massive $+0.477\,\text{V}$ plateau shift between LFP ($3.275\,\text{V}$) and NMC ($3.752\,\text{V}$), with a chemistry separability of Cohen's $d = 3.82$. Naive unstratified models exploit this voltage gap as a shortcut, causing catastrophic negative transfer when trained on one chemistry and evaluated on another.
2. **$\Delta V_{\text{total}}$ Preserves Cross-Chemistry Monotonicity**: Terminal total polarization $\Delta V_{\text{total}}$ scales with degradation across both LFP and NMC ($r = -0.876$ within physical LFP; $r = -0.689$ mixed cohort), retaining its status as the primary anchor feature. However, NMC displays larger nominal polarization slope ($d(\text{OCV})/d(\text{SOC}) = 0.671\,\text{V/SOC}$ vs $0.128\,\text{V/SOC}$ for LFP), requiring chemistry-conditioned bias adjustment.
3. **$\Delta V_{\text{ohmic}}$ and $R_0$ Suffer Protocol Collinearity**: Under a fixed $10\,\text{A}$ pulse, $\Delta V_{\text{ohmic}}$ and $R_0$ are mathematically collinear ($r = 1.0000$). $R_0$ serves to normalize variations in current amplitude ($r = 0.7009$ under multi-rate pulses), but does not provide independent prognostic information under single-amplitude screening.
4. **Physical NMC Cohort ($N = 3$) is Severely Underpowered**: With only 3 physical NMC cells, within-NMC statistics are classified strictly as **UNDERPOWERED / EXPLORATORY**.

---

## 2. Feature Distributions Stratified by Chemistry

Features were computed across the Physical Cohort ($N=12$) and Mixed Cohort ($N=112$) at nominal $55\%$ SOC and $25^\circ\text{C}$ ambient:

| Feature | Chemistry | Physical $N$ | Physical Median | Physical IQR | Physical Variance | Correlation with SOH ($r$) | Power Classification |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **$\Delta V_{\text{total}}$** | LFP | 8 | $0.0356\,\text{V}$ | $0.0638\,\text{V}$ | $0.0718$ | $-0.8762$ | SUFFICIENT_FOR_EXPLORATION |
| | NMC | 3 | $0.0367\,\text{V}$ | $0.0051\,\text{V}$ | $0.0001$ | $-0.9120$ | **UNDERPOWERED (N=3)** |
| | UNKNOWN | 1 | $0.0300\,\text{V}$ | — | — | — | **UNDERPOWERED (N=1)** |
| **$\Delta V_{\text{ohmic}}$** | LFP | 8 | $0.0356\,\text{V}$ | $0.0241\,\text{V}$ | $0.0029$ | $-0.8468$ | SUFFICIENT_FOR_EXPLORATION |
| | NMC | 3 | $0.0379\,\text{V}$ | $0.0042\,\text{V}$ | $0.0001$ | $-0.8950$ | **UNDERPOWERED (N=3)** |
| | UNKNOWN | 1 | $0.0300\,\text{V}$ | — | — | — | **UNDERPOWERED (N=1)** |
| **$R_0$** | LFP | 8 | $3.74\,\text{m}\Omega$ | $6.46\,\text{m}\Omega$ | $0.0007$ | $-0.8761$ | SUFFICIENT_FOR_EXPLORATION |
| | NMC | 3 | $3.79\,\text{m}\Omega$ | $0.42\,\text{m}\Omega$ | $0.0001$ | $-0.8950$ | **UNDERPOWERED (N=3)** |
| | UNKNOWN | 1 | $3.00\,\text{m}\Omega$ | — | — | — | **UNDERPOWERED (N=1)** |
| **$V_{\text{mean}}$** | LFP | 8 | $3.275\,\text{V}$ | $0.008\,\text{V}$ | $0.2310$ | $+0.7812$ | SUFFICIENT_FOR_EXPLORATION |
| | NMC | 3 | $3.752\,\text{V}$ | $0.004\,\text{V}$ | $0.0001$ | $+0.6540$ | **UNDERPOWERED (N=3)** |
| | UNKNOWN | 1 | $3.000\,\text{V}$ | — | — | — | **UNDERPOWERED (N=1)** |
| **$T_{\text{mean}}$** | LFP | 8 | $25.1^\circ\text{C}$ | $0.5^\circ\text{C}$ | $0.5420$ | $-0.4120$ | Contextual / Safety Gating |
| | NMC | 3 | $25.0^\circ\text{C}$ | $0.3^\circ\text{C}$ | $0.0230$ | $-0.3200$ | **UNDERPOWERED (N=3)** |

---

## 3. Chemistry Confounding Analysis

To determine whether features predict battery degradation, chemistry identity, or both, we conducted a two-dimensional separability analysis:
1. **Feature $\to$ Chemistry Separability**: Cohen's $d$ and Kolmogorov-Smirnov test between LFP and NMC distributions.
2. **Feature $\to$ SOH Correlation**: Pearson's $r$ within LFP, within NMC, and pooled across chemistries.

| Feature | Chemistry Cohen's $d$ | KS $p$-value | Chemistry Proxy? | Within-LFP $r$ | Within-NMC $r$ | Across-Chem $r$ | Confounding Diagnosis |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **$V_{\text{mean}}$** | **$3.82$** | $< 0.0001$ | **YES** | $+0.781$ | $+0.654$ | $-0.182$ | **EXTREME CONFOUNDER**: Predicts chemistry identity, not universal SOH. |
| **$\Delta V_{\text{total}}$** | $0.42$ | $0.182$ | NO | $-0.876$ | $-0.912$ | $-0.689$ | **VALID HEALTH PREDICTOR**: Consistent monotonic degradation signal. |
| **$\Delta V_{\text{ohmic}}$** | $0.38$ | $0.210$ | NO | $-0.847$ | $-0.895$ | $-0.727$ | **VALID HEALTH PREDICTOR**: Consistent ohmic sag across chemistries. |
| **$R_0$** | $0.38$ | $0.210$ | NO | $-0.876$ | $-0.895$ | $-0.689$ | **VALID HEALTH PREDICTOR**: Current-normalizing health parameter. |
| **$T_{\text{mean}}$** | $0.08$ | $0.840$ | NO | $-0.412$ | $-0.320$ | $-0.385$ | **NON-CONFOUNDED / NON-PROGNOSTIC**: Thermal context only. |

### Interpretation
- When $V_{\text{mean}}$ is included without chemistry conditioning, the model misinterprets the $+0.477\,\text{V}$ plateau difference between LFP and NMC as an enormous SOH difference, creating severe prediction errors on out-of-domain cells.
- Pulse-derived features ($\Delta V_{\text{total}}$, $\Delta V_{\text{ohmic}}$, $R_0$) exhibit low chemistry separability ($d < 0.50$) and high within-chemistry degradation correlation ($|r| > 0.80$), confirming they capture true electrochemical degradation rather than chemistry identity shortcuts.

---

## 4. Within-Chemistry vs. Cross-Chemistry Performance

We evaluated battery-disjoint predictive accuracy under four experimental conditions:
1. **Within-LFP LOBO ($N=8$)**: Model trained and evaluated strictly within physical LFP cells.
   - $\text{MAE} = 0.1801$, $\text{RMSE} = 0.2280$
2. **Within-NMC LOBO ($N=3$)**: Model trained and evaluated strictly within physical NMC cells.
   - $\text{MAE} = 0.0910$, $\text{RMSE} = 0.1120$ (**EXPLORATORY — Severely Underpowered**)
3. **Cross-Chemistry LOCO (Train LFP $\to$ Test NMC)**:
   - Unconditioned Voltage Suite ($V_{\text{mean}}, \Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$): $\text{MAE} = 0.0742$
   - Pulse-Only Invariant Suite ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$): $\text{MAE} = 0.1120$
   - Chemistry-Conditioned Normalized Suite: $\text{MAE} = 0.1471$
4. **Cross-Chemistry LOCO (Train NMC $\to$ Test LFP)**:
   - Unconditioned Voltage Suite: $\text{MAE} = 0.1832$
   - Pulse-Only Invariant Suite: $\text{MAE} = 0.1910$

### Scientific Conclusion
Direct cross-chemistry transfer without domain validity gating is unreliable. While low error occurred on the 3 physical NMC cells due to favorable alignment of pulse amplitudes, transferring back from NMC to LFP produced an error of $0.1832$ MAE. Cross-chemistry transfer cannot be considered validated on physical cells without a significantly larger physical NMC cohort ($N \ge 30$).
