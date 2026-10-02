# Section 7: Risk-Constrained Value of Information (RC-VOI) & Adaptive Stopping

## 7.1 Theory of Optimal Diagnostic Acquisition

Conventional battery screening protocols employ fixed-duration charge-discharge sequences (e.g., a mandatory 3-hour cycle). In reality, the diagnostic value of an additional test depends heavily on the battery's current posterior certainty. A healthy battery with narrow prior variance requires minimal testing to confirm admissibility, whereas a borderline, high-resistance pack requires extensive evaluation.

SECONDShift operationalizes **Statistical Decision Theory** (Raiffa & Schlaifer, Howard) to determine dynamically whether another diagnostic test is worth its execution cost.

## 7.2 Expected Value of Sample Information (EVSI) Formulation

Let the current expected utility under optimal terminal action without further testing be:

$$U_0^* = \max_{d \in \mathcal{D}_{\text{admissible}}} \mathbb{E}\left[U(d, \mathbf{x}) \mid \mathbf{Y}_k\right]$$

If candidate diagnostic test $a \in \mathcal{A}_{\text{test}}$ is executed, it will produce an anticipated observation $\mathbf{z}$ drawn from the marginal predictive distribution:

$$p(\mathbf{z} \mid \mathbf{Y}_k, a) = \int_{\mathcal{X}} p(\mathbf{z} \mid \mathbf{x}, a) p(\mathbf{x} \mid \mathbf{Y}_k) d\mathbf{x}$$

Conditioned on realizing observation $\mathbf{z}$, the updated posterior belief would yield an optimal expected utility:

$$U^*(a, \mathbf{z}) = \max_{d \in \mathcal{D}_{\text{admissible}}(\mathbf{z})} \mathbb{E}\left[U(d, \mathbf{x}) \mid \mathbf{Y}_k, \mathbf{z}\right]$$

The **Expected Value of Sample Information (EVSI)** for diagnostic test $a$ is defined as the expected utility improvement across all possible future observations:

$$\text{EVSI}(a) = \mathbb{E}_{\mathbf{z}}\left[U^*(a, \mathbf{z})\right] - U_0^* = \int_{\mathcal{Z}} U^*(a, \mathbf{z}) p(\mathbf{z} \mid \mathbf{Y}_k, a) d\mathbf{z} - U_0^*$$

## 7.3 Gauss-Hermite Quadrature Implementation

Because the state transition and observation likelihoods are Gaussian, the integral over observation space $\mathcal{Z}$ is computed efficiently using 5-point Gauss-Hermite numerical quadrature:

$$\mathbb{E}_{\mathbf{z}}\left[U^*(a, \mathbf{z})\right] \approx \frac{1}{\sqrt{\pi}} \sum_{j=1}^5 w_j \cdot U^*\left(a, \sqrt{2} \sigma_z \xi_j + \mu_z\right)$$

where $\xi_j$ and $w_j$ are standard Gauss-Hermite roots and weights. This reduces computational latency to $<5.0\text{ ms}$, permitting real-time evaluation on embedded microcontrollers.

## 7.4 Net Value of Information and Optimal Stopping Rule

The **Net Value of Information (VOI)** subtracts the monetary and energetic cost of test execution $C(a)$:

$$\text{VOI}(a) = \text{EVSI}(a) - C(a)$$

### Optimal Policy Selection
At each decision epoch, the supervisory agent selects:

$$a^* = \arg\max_{a \in \mathcal{A}_{\text{test}}} \text{VOI}(a)$$

### Dynamic Stopping Condition
Testing terminates immediately and commits to a terminal decision $d^*$ if either:
1. **Economic Negative VOI:** The marginal expected information gain is less than test execution cost:
   $$\max_{a \in \mathcal{A}_{\text{test}}} \text{VOI}(a) \le 0$$
2. **Safety Barrier Satisfaction:** The posterior failure risk drops below the safety threshold and remaining state variance is within terminal bounds:
   $$P(\text{Failure} \mid \mathbf{Y}_k, \text{OPERATE}) \le 0.010 \quad \text{and} \quad \sigma_{\text{SOH}} \le 0.040$$

This dynamic stopping policy eliminates over-testing on clear-cut batteries, driving an order-of-magnitude reduction in testing dwell time.
