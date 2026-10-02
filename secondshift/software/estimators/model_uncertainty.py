"""
Model Uncertainty & Bayesian Model Averaging (BMA) Evaluator
Project: RMK-REVOLT / SECONDShift Platform
Distinguishes STATE UNCERTAINTY (epistemic/aleatoric variance in SOH, R0)
from MODEL UNCERTAINTY (epistemic ambiguity over physical chemistry M in {LFP, NMC, UNKNOWN}).

Marginalizes operational failure risk across model hypotheses:
P(Failure | y) = SUM_M [ P(Failure | y, M) * P(M | y) ]
"""

from typing import Dict, Any, Tuple
from scipy.stats import norm
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator

class ModelUncertaintyEvaluator:
    def __init__(
        self,
        min_soh_threshold: float = 0.70,
        derate_soh_threshold: float = 0.65,
        max_r0_mohm: float = 3.5,
        pack_target_chemistry: str = "LFP"
    ):
        self.min_soh = min_soh_threshold
        self.derate_soh = derate_soh_threshold
        self.max_r0 = max_r0_mohm / 1000.0
        self.pack_target_chem = pack_target_chemistry

    def evaluate_model_conditional_risk(
        self,
        estimator: BayesianStateEstimator,
        chemistry_model: str,
        action: str
    ) -> float:
        """
        Calculates P(Failure | y, M) under the defined operating envelope.
        """
        # If model is incompatible with pack envelope:
        if chemistry_model != self.pack_target_chem:
            # Under an LFP operating envelope (2.0V - 3.65V), operating NMC or UNKNOWN
            # cells causes severe copper dissolution below 3.0V or catastrophic overcharge.
            # Incompatible models have failure risk = 1.0 for load-bearing actions.
            if action in ["OPERATE", "DERATE"]:
                return 1.000
            else: # HOLD, RETIRE, BYPASS
                return 0.000

        # Compatible LFP model: evaluate Gaussian risk against action threshold
        threshold_soh = self.min_soh if action == "OPERATE" else self.derate_soh
        max_r0_lim = self.max_r0 if action == "OPERATE" else (self.max_r0 * 1.35)

        z_soh = (estimator.mu_soh - threshold_soh) / max(estimator.sigma_soh, 1e-4)
        z_r0 = (max_r0_lim - estimator.mu_r0) / max(estimator.sigma_r0, 1e-5)

        p_safe_soh = float(norm.cdf(z_soh))
        p_safe_r0 = float(norm.cdf(z_r0))

        p_compliant = p_safe_soh * p_safe_r0
        return float(1.0 - p_compliant)

    def compute_marginal_failure_risk(
        self,
        estimator: BayesianStateEstimator,
        chemistry_posterior: Dict[str, float],
        action: str
    ) -> Dict[str, Any]:
        """
        Computes the model-averaged failure risk:
        P(Failure | y) = SUM_M [ P(Failure | y, M) * P(M | y) ]
        """
        p_fail_lfp = self.evaluate_model_conditional_risk(estimator, "LFP", action)
        p_fail_nmc = self.evaluate_model_conditional_risk(estimator, "NMC", action)
        p_fail_unk = self.evaluate_model_conditional_risk(estimator, "UNKNOWN", action)

        p_lfp = chemistry_posterior.get("LFP", 0.0)
        p_nmc = chemistry_posterior.get("NMC", 0.0)
        p_unk = chemistry_posterior.get("UNKNOWN", 0.0)

        # Marginal failure risk
        p_fail_marginal = (p_fail_lfp * p_lfp) + (p_fail_nmc * p_nmc) + (p_fail_unk * p_unk)

        return {
            "action": action,
            "p_fail_marginal": float(p_fail_marginal),
            "p_fail_conditional": {
                "LFP": float(p_fail_lfp),
                "NMC": float(p_fail_nmc),
                "UNKNOWN": float(p_fail_unk)
            },
            "chemistry_weights": {
                "LFP": float(p_lfp),
                "NMC": float(p_nmc),
                "UNKNOWN": float(p_unk)
            },
            "envelope_statement": (
                f"Under the defined {self.pack_target_chem} operating envelope, "
                f"marginal failure risk is {p_fail_marginal * 100.0:.3f}%."
            )
        }
