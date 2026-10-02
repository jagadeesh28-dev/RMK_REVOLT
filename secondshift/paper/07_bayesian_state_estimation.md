# Section 6: Bayesian State Estimation Under Joint Uncertainty

## 6.1 State Formulation & Priors

The battery degradation state vector $\mathbf{x} = [\text{SOH}, R_0]^T$ is tracked using conjugate Gaussian belief states conditional on model identity $M$:

$$p(\text{SOH}) = \mathcal{N}(\mu_{\text{SOH}}, \sigma_{\text{SOH}}^2)$$
$$p(R_0) = \mathcal{N}(\mu_{R_0}, \sigma_{R_0}^2)$$

For uncharacterized intakes, priors are initialized conservatively:
- $\mu_{\text{SOH}, 0} = 0.75$, $\sigma_{\text{SOH}, 0} = 0.15$
- $\mu_{R_0, 0} = 2.50\text{ m}\Omega$, $\sigma_{R_0, 0} = 1.20\text{ m}\Omega$

If authenticated OEM fleet telemetry logs are available, informative priors are assigned (e.g., $\sigma_{\text{SOH}, 0} = 0.03$).

## 6.2 Closed-Form Conjugate Recursive Updates

When an active test executes, sequential observations update the posterior mean and variance in closed form without expensive Markov Chain Monte Carlo (MCMC) sampling.

### 6.2.1 Ohmic Jump Internal Resistance Update
Applying a current step pulse of amplitude $I_{\text{pulse}}$ yields an instantaneous terminal voltage drop $\Delta V_{\text{jump}}$ measured by the 16-bit differential ADC. The observed resistance is $z_R = \frac{\Delta V_{\text{jump}}}{I_{\text{pulse}}}$, with sensor noise variance $\sigma_{\text{sens}}^2$:

$$\sigma_{R_0, k+1}^2 = \left(\frac{1}{\sigma_{R_0, k}^2} + \frac{1}{\sigma_{\text{sens}}^2}\right)^{-1}$$
$$\mu_{R_0, k+1} = \sigma_{R_0, k+1}^2 \left(\frac{\mu_{R_0, k}}{\sigma_{R_0, k}^2} + \frac{z_R}{\sigma_{\text{sens}}^2}\right)$$

### 6.2.2 Coulometric SOH Observation Update
Executing a partial discharge step with precise current integration $\Delta Q = \int I(t) dt$ and corresponding state-of-charge change $\Delta \text{SOC}$ yields a coulometric capacity observation $z_S = \frac{\Delta Q}{Q_{\text{nom}} \cdot \Delta \text{SOC}}$ with observation variance $\sigma_{\text{obs}}^2$:

$$\sigma_{\text{SOH}, k+1}^2 = \left(\frac{1}{\sigma_{\text{SOH}, k}^2} + \frac{1}{\sigma_{\text{obs}}^2}\right)^{-1}$$
$$\mu_{\text{SOH}, k+1} = \sigma_{\text{SOH}, k+1}^2 \left(\frac{\mu_{\text{SOH}, k}}{\sigma_{\text{SOH}, k}^2} + \frac{z_S}{\sigma_{\text{obs}}^2}\right)$$

## 6.3 Model-Marginalized Failure Risk Integration

To enforce the Hard Safety Barrier, the overall probability of catastrophic failure $P(\text{Failure} \mid \mathbf{Y}_k, d)$ must marginalize over both continuous parameter uncertainty and discrete model identity:

$$P(\text{Failure} \mid \mathbf{Y}_k, d) = \sum_{M \in \mathcal{M}} P(\text{Failure} \mid \mathbf{Y}_k, M, d) \cdot P(M \mid \mathbf{Y}_k)$$

For operational deployment ($d = \text{OPERATE}$), failure occurs if either true capacity retention falls below $\text{SOH}_{\text{crit}} = 0.70$ or internal resistance exceeds critical thermal limits $R_{0,\text{crit}} = 3.50\text{ m}\Omega$:

$$P(\text{Failure} \mid M) = 1 - \left[\Phi\left(\frac{\mu_{\text{SOH}} - \text{SOH}_{\text{crit}}}{\sigma_{\text{SOH}}}\right) \cdot \Phi\left(\frac{R_{0,\text{crit}} - \mu_{R_0}}{\sigma_{R_0}}\right)\right]$$

where $\Phi(\cdot)$ is the standard normal cumulative distribution function (CDF).

### The Hard Safety Barrier Filter
$$\mathcal{D}_{\text{admissible}} = \left\{d \in \mathcal{D}_{\text{term}} \mid P(\text{Failure} \mid \mathbf{Y}_k, d) \le \epsilon_{\text{safe}}\right\}$$

where $\epsilon_{\text{safe}} = 0.010$ ($1.0\%$). If $\text{OPERATE} \notin \mathcal{D}_{\text{admissible}}$, direct operational qualification is strictly prohibited.
