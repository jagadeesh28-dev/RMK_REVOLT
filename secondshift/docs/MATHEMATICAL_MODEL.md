# MATHEMATICAL FORMULATION & EQUATION SPECIFICATION
**Project:** RMK-REVOLT / SECONDShift Platform  
**Document ID:** `MATH-SECONDSHIFT-01`  
**Classification:** Analytical Core & Algorithmic Derivations  

---

## 1. Thermodynamic & Equivalent Circuit Physics

### 1.1 Terminal Voltage Equation (1-RC Thevenin Model)
$$V_{\text{term}}(t) = V_{\text{oc}}(\text{SOC}(t)) - I(t) \cdot R_0 - V_1(t)$$

| Symbol | Definition | Units | Physical Assumptions | Source / Reference | Implementation Location |
| :--- | :--- | :--- | :--- | :--- | :--- |
| $V_{\text{term}}(t)$ | Terminal voltage across cell | Volts ($\text{V}$) | Lumped parameter equivalent circuit | Plett, *Battery Management Systems*, Vol. 2 | `secondshift/software/hermes/hermes_driver.py#L90-L105` |
| $V_{\text{oc}}(\text{SOC})$ | Open-circuit equilibrium potential | Volts ($\text{V}$) | Evaluated after diffusion relaxation | Empirical LFP/NMC titration data | `secondshift/software/hermes/hermes_driver.py#L55-L80` |
| $I(t)$ | Cell current (positive on discharge) | Amperes ($\text{A}$) | Uniform current density across plates | Standard battery sign convention | `secondshift/software/hermes/measurement_primitives.py#L80` |
| $R_0$ | High-frequency Ohmic resistance | Ohms ($\Omega$) | Constant over short sub-second step | EIS High-frequency intercept ($1\text{ kHz}$) | `secondshift/software/hermes/measurement_primitives.py#L180-L195` |
| $V_1(t)$ | Polarization overpotential voltage | Volts ($\text{V}$) | Single dominant diffusion RC pair | Linear diffusion approximation | `secondshift/software/hermes/hermes_driver.py` |

### 1.2 Diffusion Polarization Dynamic ODE
$$\frac{dV_1(t)}{dt} = -\frac{V_1(t)}{R_1 \cdot C_1} + \frac{I(t)}{C_1}$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $R_1$ | Charge-transfer & diffusion resistance | Ohms ($\Omega$) | Symmetric charge/discharge kinetics | `secondshift/models/battery_model.py` |
| $C_1$ | Double-layer & diffusion capacitance | Farads ($\text{F}$) | Constant over operating SOC range | `secondshift/models/battery_model.py` |
| $\tau_1 = R_1 C_1$ | Diffusion polarization time constant | Seconds ($\text{s}$) | $\tau_1 \approx 20\text{s} - 40\text{s}$ for 20Ah LFP | `secondshift/models/battery_model.py` |

### 1.3 Lumped Thermal Heat Transfer ODE
$$C_{\text{th}} \frac{dT(t)}{dt} = I^2(t) \cdot \left( R_0 + R_1 \right) - h_{\text{cooling}} \cdot \left( T(t) - T_{\text{ambient}} \right)$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $C_{\text{th}}$ | Lumped cell heat capacity | Joules / Kelvin ($\text{J/K}$) | Uniform internal temperature distribution | `secondshift/software/hermes/hermes_driver.py#L107-L110` |
| $h_{\text{cooling}}$ | Effective convective heat dissipation | Watts / Kelvin ($\text{W/K}$) | Linear Newton cooling law; bench airflow | `secondshift/software/hermes/hermes_driver.py#L110` |
| $T(t)$ | Cell surface temperature | Celsius ($^\circ\text{C}$) | Thermally bonded DS18B20 measurement | `secondshift/software/hermes/measurement_primitives.py#L90` |
| $T_{\text{ambient}}$ | Ambient room temperature | Celsius ($^\circ\text{C}$) | Measured baseline ambient ($25.0^\circ\text{C}$) | `secondshift/software/hermes/hermes_driver.py#L23` |

---

## 2. Bayesian State Estimation & Information Update

### 2.1 Conjugate Gaussian Information Precision
$$\frac{1}{\sigma_{\text{post}}^2} = \frac{1}{\sigma_{\text{prior}}^2} + \frac{1}{\sigma_m^2}$$

$$\mu_{\text{post}} = \sigma_{\text{post}}^2 \left( \frac{\mu_{\text{prior}}}{\sigma_{\text{prior}}^2} + \frac{y_m}{\sigma_m^2} \right) = \mu_{\text{prior}} + K \cdot \left( y_m - \mu_{\text{prior}} \right)$$

$$K = \frac{\sigma_{\text{prior}}^2}{\sigma_{\text{prior}}^2 + \sigma_m^2}$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $\mu_{\text{prior}}, \mu_{\text{post}}$ | Prior and posterior expected parameter mean | Dimensionless (SOH) / $\Omega$ ($R_0$) | Gaussian prior and observation likelihood | `secondshift/software/estimators/bayesian_state_estimator.py#L40-L65` |
| $\sigma_{\text{prior}}, \sigma_{\text{post}}$ | Prior and posterior standard deviation | Dimensionless / $\Omega$ | Linear measurement model with additive noise | `secondshift/software/estimators/bayesian_state_estimator.py#L45-L60` |
| $y_m$ | Scalar diagnostic observation | Dimensionless / $\Omega$ | Independent zero-mean Gaussian error $\mathcal{N}(0, \sigma_m^2)$ | `secondshift/software/estimators/bayesian_state_estimator.py#L48` |
| $\sigma_m$ | Sensor / observational noise standard deviation | Volts ($\text{V}$) / $\Omega$ / Dimensionless | $\sigma_{m, R0} = 0.35\text{ m}\Omega$, $\sigma_{m, \text{SOH}} = 0.025$ | `secondshift/software/voi/evsi_calculator.py#L38-L55` |
| $K$ | Kalman / Information Gain | Dimensionless | Strictly in range $[0.0, 1.0]$ | `secondshift/software/estimators/bayesian_state_estimator.py#L50` |

---

## 3. Chemistry Model Disambiguation (Bayesian Model Averaging)

### 3.1 Posterior Chemistry Probability
$$P(M = m \mid \mathbf{y}) = \frac{p(\mathbf{y} \mid M = m) \cdot P(M = m)}{\sum_{m' \in \mathcal{M}} p(\mathbf{y} \mid M = m') \cdot P(M = m')}, \quad m \in \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $P(M = m \mid \mathbf{y})$ | Posterior probability of chemistry model $m$ | Probability $[0, 1]$ | Mutually exclusive discrete hypothesis space | `secondshift/software/chemistry/chemistry_engine.py#L70-L85` |
| $P(M = m)$ | Intake prior probability | Probability $[0, 1]$ | Configured from fleet intake manifest | `secondshift/software/chemistry/chemistry_engine.py#L25-L35` |
| $p(\mathbf{y} \mid M = m)$ | Marginal likelihood of physical features under model $m$ | Probability density | Feature distribution calibrated from cell chemistry physics | `secondshift/software/chemistry/chemistry_engine.py#L45-L65` |

### 3.2 Marginal System Failure Risk
$$P(\text{Failure} \mid \mathbf{y}) = \sum_{m \in \mathcal{M}} P(\text{Failure} \mid \mathbf{y}, M = m) \cdot P(M = m \mid \mathbf{y})$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $P(\text{Failure} \mid \mathbf{y})$ | Model-averaged operational failure probability | Probability $[0, 1]$ | Law of Total Probability over $\mathcal{M}$ | `secondshift/software/estimators/model_uncertainty.py#L50-L75` |
| $P(\text{Failure} \mid \mathbf{y}, M)$ | Model-conditional failure probability | Probability $[0, 1]$ | Incompatible chemistry in LFP pack has failure risk $\equiv 1.0$ | `secondshift/software/estimators/model_uncertainty.py#L25-L48` |

---

## 4. Hard Safety Barrier & Economic Decoupling

### 4.1 Admissible Action Set Filter
$$\mathcal{A}_{\text{safe}}(\mathbf{y}) = \left\{ a \in \{\text{OPERATE}, \text{DERATE}\} \;\middle|\; P(\text{Failure} \mid \mathbf{y}) \le \alpha \quad \text{AND} \quad \mathcal{S}_{\text{chem}} = \mathbf{KNOWN} \right\} \cup \{\text{TEST}, \text{HOLD}, \text{RETIRE}\}$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $\alpha$ | Maximum acceptable failure probability threshold | Dimensionless ($0.010 = 1.0\%$) | Regulatory gate threshold | `secondshift/software/safety/hard_safety_barrier.py#L14` |
| $\mathcal{S}_{\text{chem}}$ | Chemistry-confidence state | Discrete: `KNOWN`, `PROBABLE`, `AMBIGUOUS` | Gated by $P(M \mid \mathbf{y}) \ge 0.990$ | `secondshift/software/chemistry/chemistry_engine.py#L90-L105` |
| $\mathcal{A}_{\text{safe}}$ | Admissible action set | Set of discrete actions | Inadmissible actions receive utility $-\infty$ | `secondshift/software/safety/hard_safety_barrier.py#L25-L60` |

### 4.2 Utility Disqualification Formula
$$U_{\text{gated}}(a) = \begin{cases}
-\infty & \text{if } a \notin \mathcal{A}_{\text{safe}}(\mathbf{y}) \\
\mathbb{E}[U_{\text{econ}}(a)] & \text{if } a \in \mathcal{A}_{\text{safe}}(\mathbf{y})
\end{cases}$$

---

## 5. Value of Information (VOI) & EVSI Quadrature

### 5.1 Expected Value of Sample Information (EVSI)
$$\text{EVSI}(t) = \int_{-\infty}^{\infty} \max_{a' \in \mathcal{A}_{\text{safe}}(b'(y))} \mathbb{E}[U(a' \mid y)] \cdot p(y \mid b) \, dy - \max_{a \in \mathcal{A}_{\text{safe}}(b)} \mathbb{E}[U(a \mid b)]$$

Gauss-Hermite numerical quadrature implementation:
$$\text{EVSI}(t) \approx \sum_{j=1}^{5} \frac{w_j}{\sqrt{\pi}} \left[ \max_{a' \in \mathcal{A}_{\text{safe}}(b'(y_j))} \mathbb{E}[U(a' \mid y_j)] \right] - U_{\text{baseline}}$$

$$y_j = \mu_{\text{prior}} + \sqrt{2 \cdot (\sigma_{\text{prior}}^2 + \sigma_{m, t}^2)} \cdot z_j$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $\text{EVSI}(t)$ | Expected Value of Sample Information | Indian Rupees ($\text{INR}$) | 5-point Gauss-Hermite integration accuracy $>99.8\%$ | `secondshift/software/voi/evsi_calculator.py#L58-L85` |
| $(z_j, w_j)$ | Gauss-Hermite quadrature nodes and weights | Dimensionless | Standard Hermite polynomial roots | `secondshift/software/voi/evsi_calculator.py#L22-L35` |
| $C_{\text{test}}(t)$ | Direct cost of executing diagnostic test $t$ | Indian Rupees ($\text{INR}$) | Labor ($250\text{ INR/hr}$) + Electricity ($8\text{ INR/kWh}$) + Degradation | `secondshift/software/voi/evsi_calculator.py#L50-L56` |
| $\text{VOI}(t)$ | Net Value of Information | Indian Rupees ($\text{INR}$) | $\text{VOI}(t) = \text{EVSI}(t) - C_{\text{test}}(t)$ | `secondshift/software/voi/evsi_calculator.py` |

### 5.2 Energy Recovery per Diagnostic Second (ERDS)
$$\text{ERDS} = \frac{\Delta E_{\text{retained}}}{\Delta t_{\text{diagnostic}}} = \frac{\left( E_{\text{policy}} - E_{\text{baseline}} \right) \times 1000.0}{T_{\text{policy}} - T_{\text{baseline}}} \quad \left[ \frac{\text{Wh}}{\text{diagnostic-second}} \right]$$

| Symbol | Definition | Units | Assumptions | Implementation Location |
| :--- | :--- | :--- | :--- | :--- |
| $\text{ERDS}$ | Marginal energetic productivity of testing | $\text{Wh} / \text{s}$ (equivalent to $\text{kW}$) | Linear energy recovery efficiency | `secondshift/software/secondshift/metrics_calculator.py#L95-L108` |
| $E_{\text{policy}}$ | Usable storage capacity recovered by policy | Kilowatt-hours ($\text{kWh}$) | Integrated over 1,200 lifetime cycles | `secondshift/software/secondshift/metrics_calculator.py#L45` |
| $T_{\text{policy}}$ | Total qualification time expended | Seconds ($\text{s}$) | Monotonic hardware timestamp measurement | `secondshift/software/secondshift/metrics_calculator.py#L38` |
