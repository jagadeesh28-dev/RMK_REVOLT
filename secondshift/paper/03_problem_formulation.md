# Section 2: Mathematical Problem Formulation

## 2.1 State Space and Model Uncertainty

Let a retired battery module under test be characterized by an unobservable physical parameter state vector:

$$\mathbf{x} = [\text{SOH}, R_0]^T \in \mathcal{X} \subset \mathbb{R}^2$$

where $\text{SOH} \in [0.0, 1.2]$ denotes the capacity retention ratio relative to nominal capacity, and $R_0 \in \mathbb{R}_{>0}$ represents high-frequency ohmic internal resistance in milliohms ($\text{m}\Omega$).

In heterogeneous intake streams, the underlying electrochemical model identity $M$ is also uncertain, belonging to a discrete hypothesis set:

$$M \in \mathcal{M} = \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$$

Each candidate model $M$ defines a family of parameterized open-circuit voltage curves $V_{\text{oc}}(s; M)$, diffusion dynamics, and critical physical failure thresholds:

$$\theta_M = \{V_{\text{oc}}(\cdot), R_{0,\text{crit}}(M), \text{SOH}_{\text{crit}}(M), V_{\min}(M), V_{\max}(M)\}$$

## 2.2 Measurement Process & Information Dynamics

At discrete diagnostic step $k \in \{0, 1, \dots, K\}$, the system may select an active diagnostic test action $a_k$ from a discrete action library:

$$\mathcal{A}_{\text{test}} = \{\text{IDLE}, \text{REST\_OCV}, \text{QUICK\_PULSE\_R0}, \text{SHORT\_COULOMETRIC\_CYCLE}\}$$

Executing test $a_k$ incurs an operational cost $C(a_k)$ comprising equipment amortization, technician labor, and electrical energy consumption:

$$C(a) = t_{\text{dwell}}(a) \cdot (\dot{C}_{\text{amort}} + \dot{C}_{\text{labor}}) + \int_0^{t_{\text{dwell}}(a)} |I(\tau) V(\tau)| d\tau \cdot P_{\text{grid}}$$

Each test yields a noisy observation vector $\mathbf{y}_k \in \mathbb{R}^{d_k}$ governed by the likelihood function:

$$p(\mathbf{y}_k \mid \mathbf{x}, M, a_k) = \mathcal{N}\left(\mathbf{y}_k; \mathbf{h}_M(\mathbf{x}, a_k), \mathbf{\Sigma}_k\right)$$

where $\mathbf{h}_M(\cdot)$ is the physics-based observation mapping and $\mathbf{\Sigma}_k$ is the measurement covariance matrix.

## 2.3 Joint Epistemic Posterior

Given the cumulative measurement history up to step $k$, denoted $\mathbf{Y}_k = \{\mathbf{y}_1, \dots, \mathbf{y}_k\}$, the joint posterior distribution over continuous battery states and discrete model identity is decomposed via the chain rule:

$$p(\mathbf{x}, M \mid \mathbf{Y}_k) = p(\mathbf{x} \mid \mathbf{Y}_k, M) \cdot P(M \mid \mathbf{Y}_k)$$

The continuous state conditional posterior is modeled as a joint Gaussian density:

$$p(\mathbf{x} \mid \mathbf{Y}_k, M) = \mathcal{N}\left(\mathbf{x}; \boldsymbol{\mu}_{k \mid M}, \mathbf{P}_{k \mid M}\right)$$

where $\boldsymbol{\mu}_{k \mid M} = [\mu_{\text{SOH}}, \mu_{R_0}]^T$ and $\mathbf{P}_{k \mid M} = \text{diag}(\sigma_{\text{SOH}}^2, \sigma_{R_0}^2)$.

The discrete model posterior belief $P(M \mid \mathbf{Y}_k)$ is updated via Bayes' rule:

$$P(M \mid \mathbf{Y}_k) = \frac{p(\mathbf{y}_k \mid \mathbf{Y}_{k-1}, M) P(M \mid \mathbf{Y}_{k-1})}{\sum_{M' \in \mathcal{M}} p(\mathbf{y}_k \mid \mathbf{Y}_{k-1}, M') P(M' \mid \mathbf{Y}_{k-1})}$$

## 2.4 Terminal Decision Space & Risk-Constrained Objective

At any step $k$, the supervisory agent may either execute another diagnostic test $a \in \mathcal{A}_{\text{test}}$ or terminate testing and commit to an irreversible terminal assignment:

$$d \in \mathcal{D}_{\text{term}} = \{\text{OPERATE}, \text{DERATE}, \text{RETIRE}, \text{HOLD}\}$$

Let a catastrophic operational failure event $\mathcal{F}$ be defined as deploying a module that exceeds critical internal resistance or falls below minimum capacity:

$$\mathcal{F} \triangleq \left\{R_0 \ge R_{0,\text{crit}}(M)\right\} \cup \left\{\text{SOH} < \text{SOH}_{\text{crit}}(M)\right\} \cup \left\{M = \text{NMC} \text{ deployed as LFP}\right\}$$

The model-marginalized probability of failure under assignment $d$ is given by:

$$P(\mathcal{F} \mid \mathbf{Y}_k, d) = \sum_{M \in \mathcal{M}} P(\mathcal{F} \mid \mathbf{Y}_k, M, d) \cdot P(M \mid \mathbf{Y}_k)$$

### The Hard Safety Constraint
In accordance with functional safety criteria, the primary objective is to maximize terminal expected economic utility $\mathbb{E}[U(d, \mathbf{x})]$ subject to an uncompromising risk constraint:

$$\max_{d \in \mathcal{D}_{\text{term}}} \mathbb{E}\left[U(d, \mathbf{x}) \mid \mathbf{Y}_k\right] \quad \text{subject to} \quad P(\mathcal{F} \mid \mathbf{Y}_k, d) \le \epsilon_{\text{safe}}$$

where $\epsilon_{\text{safe}} = 0.010$ ($1.0\%$). If no terminal action satisfies the constraint, the system is strictly mandated to select $d = \text{HOLD}$ or $d = \text{RETIRE}$.
