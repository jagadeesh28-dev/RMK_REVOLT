"""
Bayesian State Estimator
Project: RMK-REVOLT / SECONDShift Platform
Tracks parameter belief state b(t) = N(mu, Sigma) with explicit variance shrinkage:
- SOH: mu_soh, sigma_soh
- R0:  mu_r0, sigma_r0
Logs step-by-step prior -> likelihood -> posterior update trajectories.
"""

import numpy as np
from typing import Dict, Any, List

class BayesianStateEstimator:
    def __init__(
        self,
        module_id: str,
        prior_mu_soh: float = 0.75,
        prior_sigma_soh: float = 0.15,
        prior_mu_r0: float = 0.0025,
        prior_sigma_r0: float = 0.0012,
        nominal_capacity_ah: float = 20.0
    ):
        self.module_id = module_id
        self.nominal_capacity_ah = nominal_capacity_ah

        # Latent state distributions
        self.mu_soh = float(prior_mu_soh)
        self.sigma_soh = float(prior_sigma_soh)
        self.mu_r0 = float(prior_mu_r0)
        self.sigma_r0 = float(prior_sigma_r0)

        self.update_history = []

    def log_update_step(self, parameter: str, prior_mu: float, prior_sigma: float, meas: float, meas_sigma: float, post_mu: float, post_sigma: float, test_name: str):
        record = {
            "parameter": parameter,
            "test_name": test_name,
            "prior": f"{prior_mu:.4f} +/- {prior_sigma:.4f}",
            "observation": f"{meas:.4f} +/- {meas_sigma:.4f}",
            "posterior": f"{post_mu:.4f} +/- {post_sigma:.4f}",
            "uncertainty_reduction_pct": round(((prior_sigma - post_sigma) / max(prior_sigma, 1e-6)) * 100.0, 2)
        }
        self.update_history.append(record)

    def update_r0_from_ohmic_jump(self, measured_r0: float, sensor_noise_sigma: float = 0.00035, test_name: str = "PULSE_R0"):
        """
        Conjugate Gaussian update for internal resistance:
        1 / sigma_post^2 = 1 / sigma_prior^2 + 1 / sigma_meas^2
        mu_post = sigma_post^2 * (mu_prior / sigma_prior^2 + y / sigma_meas^2)
        """
        prior_mu = self.mu_r0
        prior_sig = self.sigma_r0

        prior_prec = 1.0 / (prior_sig ** 2)
        meas_prec = 1.0 / (sensor_noise_sigma ** 2)
        post_prec = prior_prec + meas_prec

        post_sig = float(np.sqrt(1.0 / post_prec))
        post_mu = float((prior_mu * prior_prec + measured_r0 * meas_prec) / post_prec)

        self.mu_r0 = post_mu
        self.sigma_r0 = post_sig

        self.log_update_step("R0", prior_mu, prior_sig, measured_r0, sensor_noise_sigma, post_mu, post_sig, test_name)

    def update_soh_from_coulometric_observation(self, measured_soh: float, observation_noise_sigma: float = 0.025, test_name: str = "COULOMETRIC_CYCLE"):
        """
        Conjugate Gaussian update for State of Health.
        """
        prior_mu = self.mu_soh
        prior_sig = self.sigma_soh

        prior_prec = 1.0 / (prior_sig ** 2)
        meas_prec = 1.0 / (observation_noise_sigma ** 2)
        post_prec = prior_prec + meas_prec

        post_sig = float(np.sqrt(1.0 / post_prec))
        post_mu = float((prior_mu * prior_prec + measured_soh * meas_prec) / post_prec)

        self.mu_soh = post_mu
        self.sigma_soh = post_sig

        self.log_update_step("SOH", prior_mu, prior_sig, measured_soh, observation_noise_sigma, post_mu, post_sig, test_name)

    def get_belief_summary(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "mu_soh": round(self.mu_soh, 4),
            "sigma_soh": round(self.sigma_soh, 4),
            "mu_r0_mohm": round(self.mu_r0 * 1000.0, 3),
            "sigma_r0_mohm": round(self.sigma_r0 * 1000.0, 3),
            "num_updates": len(self.update_history)
        }
