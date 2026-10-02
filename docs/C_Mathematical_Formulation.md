# ARTIFACT C: Formal State Model, Action Space & VOI Formulation
**Project:** RMK-REVOLT — EV Battery Circularity Challenge  
**Focus:** Mathematical Rigor, Observable State Minimality, Decision Theory

---

## 1. Minimal State Representation $x_i(t)$

For each battery module $i$, the state vector is defined as:
$$x_i(t) = \left[ \text{SOC}_i,\ \mu_{\text{SOH},i},\ \sigma_{\text{SOH},i},\ \mu_{R_0,i},\ \sigma_{R_0,i},\ T_i,\ \left(\frac{dT}{dt}\right)_i,\ d_i \right]^T$$

To prevent academic feature inflation, every variable is subjected to 6 hostile engineering criteria:

### Variable 1: State of Charge ($\text{SOC}_i$)
1. **Why needed?** Determines immediate usable energy, dictates open-circuit voltage via $OCV(SOC)$, and prevents overdischarge/overcharge cutoffs.
2. **Can we measure it?** No, it cannot be measured directly with any physical sensor.
3. **Can we estimate it?** Yes, via Coulomb counting combined with Extended Kalman Filtering (EKF) during voltage knee transitions.
4. **Sensor/test:** Voltage ADC (ADS1115) + Current shunt (INA226).
5. **Uncertainty:** In flat LFP plateau (20%–80%), $\sigma_{SOC} \approx \pm 10\%$; near knees (<15% or >85%), $\sigma_{SOC} \le \pm 2\%$.
6. **Removing it damages decision?** **CRITICAL DAMAGE.** Without SOC, the system would drive cells into copper-dissolution overdischarge ($<2.0V$) or thermal-runaway overcharge ($>3.65V$).

---

### Variable 2: Expected Health ($\mu_{\text{SOH},i}$) & Capacity
1. **Why needed?** Measures irreversible loss of active lithium inventory and cathode material; sets nameplate energy rating for second-life application.
2. **Can we measure it?** Not instantaneously. Only by full discharge cycling.
3. **Can we estimate it?** Yes, via short partial coulometric steps and high-frequency resistance correlation.
4. **Sensor/test:** `short_coulometric_cycle` or current pulse.
5. **Uncertainty:** Tracked dynamically as $\sigma_{\text{SOH},i} \in [0.015, 0.18]$.
6. **Removing it damages decision?** **FATAL DAMAGE.** The core circularity decision is whether the module meets application minimum health (e.g. 70%).

---

### Variable 3: SOH Uncertainty ($\sigma_{\text{SOH},i}$)
1. **Why needed?** Distinguishes a genuinely degraded cell from an uncharacterized cell with noisy history; governs the Value of Information (VOI).
2. **Can we measure it?** No, it is an epistemic Bayesian quantity.
3. **Can we estimate it?** Yes, updated via Bayesian conjugate variance reduction: $\frac{1}{\sigma_{post}^2} = \frac{1}{\sigma_{prior}^2} + \frac{1}{\sigma_{meas}^2}$.
4. **Sensor/test:** Bayesian estimator tracking test execution history.
5. **Uncertainty:** Meta-uncertainty calibrated against ground truth residuals ($z$-score calibration).
6. **Removing it damages decision?** **FOUNDATIONAL CONTRIBUTION.** Removing $\sigma_{\text{SOH}}$ collapses the architecture into Baseline B (uncertainty-blind scalar threshold), which was proven in Experiment E3 to cause a 100% Unnecessary Isolation Rate.

---

### Variable 4: Internal Ohmic Resistance ($\mu_{R_0,i}$) & Uncertainty ($\sigma_{R_0,i}$)
1. **Why needed?** Dictates $I^2 R$ Joule heat dissipation, determines maximum continuous C-rate, and serves as an early indicator of contact delamination or internal degradation.
2. **Can we measure it?** Yes, via immediate voltage jump $\Delta V / \Delta I$ upon 1C pulse onset ($t \le 1.0$s).
3. **Can we estimate it?** Yes, through recursive least squares or Kalman filtering on dynamic load current.
4. **Sensor/test:** `pulse_power_test` (20s 1C discharge) or H.E.R.M.E.S. in-situ load feedback.
5. **Uncertainty:** $\sigma_{R_0} \approx \pm 0.15\text{ m}\Omega$ with a 16-bit differential ADC.
6. **Removing it damages decision?** **FATAL TO SAFETY.** A cell may have 80% SOH capacity but a 5 m$\Omega$ resistance defect; removing $R_0$ causes thermal runaway at 1C.

---

### Variable 5: Cell Temperature ($T_i$) and Thermal Gradient Rate ($\frac{dT_i}{dt}$)
1. **Why needed?** Real-time physical safety gate; confirms thermal dissipation $P = I^2 R - h(T - T_{amb})$.
2. **Can we measure it?** Yes, directly with physical sensors.
3. **Can we estimate it?** Measured directly; gradient estimated via $\frac{T(t) - T(t-\Delta t)}{\Delta t}$.
4. **Sensor/test:** Calibrated NTC thermistors (10k 1% B3950) or digital DS18B20 1-Wire sensors.
5. **Uncertainty:** $\sigma_T \approx \pm 0.25^\circ\text{C}$.
6. **Removing it damages decision?** **ILLEGAL & UNSAFE.** Required by IEC 62619 / UL 1973 second-life safety standards.

---

### Variable 6: Self-Discharge / Leakage Rate ($d_i$)
1. **Why needed?** Primary physical precursor for internal micro-dendrites and separator perforation.
2. **Can we measure it?** Yes, by tracking resting open-circuit relaxation ($\frac{dV}{dt}$) over 15 to 60 seconds in the flat LFP plateau.
3. **Can we estimate it?** Yes, linear regression on resting voltage trajectory.
4. **Sensor/test:** TRIAGE Gate 5 resting measurement.
5. **Uncertainty:** $\pm 1.5$ mV/hour.
6. **Removing it damages decision?** **CATASTROPHIC ESCAPE RISK.** Experiment E4 proved that without leakage tracking, internal micro-shorts escape into active packs.

---

## 2. Action Space & Decision Matrix

$$A = \{\text{TEST},\ \text{OPERATE},\ \text{DERATE},\ \text{BYPASS},\ \text{ISOLATE},\ \text{RETIRE}\}$$

| Action | Preconditions | Expected Benefit | Financial / Physical Cost | Safety Risk | Information Gained | Effect on Future Decisions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TEST** | Passed Triage; $\text{VOI} > 0$; test budget remaining. | Resolves epistemic variance $\sigma$; enables safe classification. | ₹17–₹78 testing cost; 20–600s test time; minor wear. | Zero (laboratory bench with hardware OVP/OTP). | **HIGH** ($\Delta \sigma \approx -0.06$ to $-0.10$). | Updates belief $b_i$; enables transition to OPERATE or DERATE. |
| **OPERATE** | $P_{\text{compliant}} \ge 98\%$; $\sigma_{\text{SOH}} \le 0.04$; $R_0 \le R_{max}$. | Full lifetime energy revenue (₹1,600 / module @ ₹10/kWh). | 1.0C normal cyclic degradation (~₹100). | Low if compliant; catastrophic (₹6,000 penalty) if false acceptance. | Low (passive current monitoring). | Generates revenue; periodically re-verified by BMS. |
| **DERATE** | Intermediate health or moderate $\sigma$; safe for low C-rate. | Recovers 75% energy revenue (₹1,200); extends cell life by $2\times$. | Lower power throughput; minor balancing duty. | **VERY LOW** ($I^2 R$ heat generation cut by $75\%$). | **MODERATE** (in-situ dynamic load response shrinks $\sigma$). | May upgrade to ACTIVE if in-situ observation confirms low $R_0$. |
| **BYPASS** | Module resting, cooling, or temporarily balancing. | Prevents weak/hot module from throttling the series string. | Slight string capacity reduction (~₹50 opportunity loss). | Zero. | Zero. | Re-activates when cooled or balanced. |
| **ISOLATE** | Hardware safety trip (OVP, UVP, OTP, OCP) or sensor fault. | Eliminates catastrophic pack-level fire or propagation risk. | Permanent string capacity loss (-₹100). | Zero (fail-safe disconnect). | Error diagnostic code. | Requires physical technician inspection. |
| **RETIRE** | Genuinely degraded ($SOH < SOH_{min}$) or unrecoverable defect. | Recovers material recycling scrap value (₹142 / module). | Forfeits operational reuse revenue. | Zero. | End-of-life status. | Shipped to hydrometallurgical recycling facility. |

---

## 3. Value of Information (VOI) Formulation

A full infinite-horizon Partially Observable Markov Decision Process (POMDP) is computationally intractable on an embedded microcontroller ($O(|S|^{|A|})$ curse of dimensionality).

We formulate a **closed-form Gaussian quadrature VOI approximation**:

$$\text{VOI}(k) = \int_{-\infty}^{\infty} \left[ \max_{a \in \mathcal{A}_{op}} \mathcal{U}\left(a \mid b_i \oplus y\right) \right] p(y \mid b_i) \, dy - \max_{a \in \mathcal{A}_{op}} \mathcal{U}(a \mid b_i) - \text{Cost}(k)$$

Using 7-point Gauss-Hermite quadrature:
$$\text{VOI}(k) \approx \sum_{j=1}^{7} w_j \max_{a \in \mathcal{A}_{op}} \mathcal{U}\left(a \mid \mu + \xi_j \sigma_{total}\right) - \max_{a \in \mathcal{A}_{op}} \mathcal{U}(a \mid b_i) - \text{Cost}(k)$$

Where:
- $\sigma_{total} = \sqrt{\sigma_{prior}^2 + \sigma_{sensor}^2}$
- $w_j, \xi_j$ are standard normalized quadrature weights and nodes.
- $\text{Cost}(k) = \text{TimeCost}(k) + \text{EnergyCost}(k) + \text{EquipmentCost}(k) + \text{DegradationCost}(k)$.

### Stopping Rule:
$$\text{If } \max_{k} \text{VOI}(k) \le 0 \quad \text{or} \quad \sigma_{\text{SOH}} \le \sigma_{\text{allowable}} \implies \text{STOP TESTING, ACT IMMEDIATELY.}$$
