# Section 5: Epistemic Chemistry & Model Disambiguation

## 5.1 The Danger of Chemistry Mismatch

In second-life supply chains, casing labels are frequently absent, worn away, or fraudulently mislabeled. Deploying an $\text{NMC}$ cell in an $\text{LFP}$ stationary storage battery pack creates catastrophic overcharging conditions:
- $\text{LFP}$ charge cutoff: $3.65\text{ V/cell}$ (Nominal $3.20\text{ V}$)
- $\text{NMC}$ charge cutoff: $4.20\text{ V/cell}$ (Nominal $3.70\text{ V}$)

If an $\text{NMC}$ module is mistakenly integrated into an $\text{LFP}$ system, it operates in an extreme state of deep under-discharge (below $3.0\text{ V}$), inducing accelerated copper dissolution and internal short-circuiting. Conversely, if an $\text{LFP}$ cell is charged under an $\text{NMC}$ voltage profile ($4.20\text{ V}$), it experiences massive overcharge, active material oxidation, and severe thermal runaway.

## 5.2 Multi-Hypothesis Dirichlet-Bayesian Update

To prevent chemistry-induced failures, SECONDShift treats the underlying model identity as an epistemic uncertainty distribution:

$$M \in \mathcal{M} = \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$$

Intake priors are initialized based on available documentation or uninformative defaults:

$$\mathbf{p}_0 = [P(\text{LFP}), P(\text{NMC}), P(\text{UNKNOWN})]^T = [0.45, 0.45, 0.10]^T$$

### Physics of Relaxation Disambiguation
Following an active current pulse (e.g., 10A for 15s), the open-circuit voltage relaxation dynamics $V(t)$ reflect underlying electrochemical phase behavior:
1. **LFP Phase-Boundary Pinning:** The two-phase equilibrium ($LiFePO_4 \leftrightarrow FePO_4$) pins the voltage tightly to the plateau ($3.28\text{--}3.32\text{ V}$), displaying minimal post-ohmic relaxation drift ($\Delta V_{\text{rel}} \le 4.0\text{ mV}$).
2. **NMC Solid-Solution Diffusion:** Layered transition-metal oxides exhibit continuous solid-solution lithium diffusion, resulting in steep, exponential relaxation curves ($\Delta V_{\text{rel}} \approx 26.0\text{ mV}$).

The observed polarization voltage $\Delta V_{\text{pol}} = V(t_{\text{rel}}=45\text{s}) - V(t_{\text{pulse\_end}})$ provides an observation feature $z = \Delta V_{\text{pol}}$ governed by calibrated likelihood functions:

$$p(z \mid M = \text{LFP}) = \mathcal{N}(z; \mu = 22.0\text{ mV}, \sigma = 5.0\text{ mV})$$
$$p(z \mid M = \text{NMC}) = \mathcal{N}(z; \mu = 38.0\text{ mV}, \sigma = 6.0\text{ mV})$$

The posterior model belief is updated via Bayes' rule:

$$P(M \mid z) = \frac{p(z \mid M) P(M)}{\sum_{M' \in \mathcal{M}} p(z \mid M') P(M')}$$

## 5.3 Chemistry Confidence States & The Epistemic Abstention Rule

Posterior belief is mapped into three discrete operational confidence states:
- **`KNOWN`**: $\max_M P(M \mid \mathbf{y}) \ge 0.990$ (Permitted to enter `OPERATE` or `DERATE`).
- **`PROBABLE`**: $0.900 \le \max_M P(M \mid \mathbf{y}) < 0.990$ (Requires additional diagnostic testing).
- **`AMBIGUOUS`**: $\max_M P(M \mid \mathbf{y}) < 0.900$ (Direct operation strictly forbidden).

### The Epistemic Refusal Invariant
$$\text{If } \text{Confidence} \ne \text{KNOWN} \implies \text{Action} \in \{\text{HOLD}, \text{TEST}, \text{RETIRE}\}$$

Under this invariant, the system **strictly refuses to guess**. Tagless, unknown, or ambiguous battery modules are permanently routed to `HOLD / RECYCLE`, ensuring that no cell of unconfirmed chemistry is ever connected to stationary storage.
