"""
Value of Information (VOI) & EVSI Numerical Quadrature Engine
Project: RMK-REVOLT / SECONDShift Platform
Evaluates:
EVSI(t) = E_y [ max_a' U(a' | y) ] - max_a U(a)
VOI(t)  = EVSI(t) - C_test(t)
using 5-point Gauss-Hermite numerical integration over predictive measurement distributions.
"""

import numpy as np
from typing import Dict, Any, Callable, List

class ValueOfInformationEngine:
    def __init__(
        self,
        labor_rate_inr_per_hr: float = 250.0,
        electricity_rate_inr_per_kwh: float = 8.0
    ):
        self.labor_rate_sec = labor_rate_inr_per_hr / 3600.0
        self.elec_rate_wh = electricity_rate_inr_per_kwh / 1000.0

        # Standard 5-point Gauss-Hermite nodes and weights
        self.gh_nodes = np.array([
            -2.02018287,
            -0.95857246,
             0.0,
             0.95857246,
             2.02018287
        ])
        self.gh_weights = np.array([
            0.01995324,
            0.39361930,
            0.94530872,
            0.39361930,
            0.01995324
        ]) / np.sqrt(np.pi)

        # Available physical diagnostic test catalog
        self.test_catalog = {
            "QUICK_PULSE_R0": {
                "name": "QUICK_PULSE_R0",
                "duration_s": 15.0,
                "energy_wh": 0.15,
                "sigma_obs": 0.00035, # Ohmic jump noise
                "parameter": "R0"
            },
            "CHEM_DISAMBIG_PULSE": {
                "name": "CHEM_DISAMBIG_PULSE",
                "duration_s": 45.0,
                "energy_wh": 0.35,
                "sigma_obs": 0.005,
                "parameter": "CHEMISTRY"
            },
            "SHORT_COULOMETRIC_CYCLE": {
                "name": "SHORT_COULOMETRIC_CYCLE",
                "duration_s": 180.0,
                "energy_wh": 1.80,
                "sigma_obs": 0.025, # SOH observation noise
                "parameter": "SOH"
            }
        }

    def compute_test_cost(self, test_name: str) -> float:
        spec = self.test_catalog[test_name]
        c_labor = spec["duration_s"] * self.labor_rate_sec
        c_elec = spec["energy_wh"] * self.elec_rate_wh
        c_deg = 0.50 # Nominal cycling degradation cost in INR
        return float(c_labor + c_elec + c_deg)

    def calculate_evsi(
        self,
        test_name: str,
        current_prior_mu: float,
        current_prior_sigma: float,
        utility_evaluator_fn: Callable[[float, float], float],
        baseline_max_utility: float
    ) -> float:
        """
        Computes Expected Value of Sample Information using Gauss-Hermite integration.
        """
        spec = self.test_catalog[test_name]
        sigma_m = spec["sigma_obs"]

        # Marginal variance of observation y: sigma_y^2 = sigma_prior^2 + sigma_m^2
        sigma_y = np.sqrt(current_prior_sigma ** 2 + sigma_m ** 2)

        # Posterior variance is deterministic given test noise:
        post_variance = 1.0 / (1.0 / (current_prior_sigma ** 2) + 1.0 / (sigma_m ** 2))
        post_sigma = np.sqrt(post_variance)

        expected_posterior_utility = 0.0

        for z_node, weight in zip(self.gh_nodes, self.gh_weights):
            y_sample = current_prior_mu + np.sqrt(2.0) * sigma_y * z_node
            # Posterior mean given y_sample:
            post_mu = post_variance * (current_prior_mu / (current_prior_sigma ** 2) + y_sample / (sigma_m ** 2))
            
            # Evaluate optimal admissible action under posterior (post_mu, post_sigma)
            best_post_u = utility_evaluator_fn(post_mu, post_sigma)
            expected_posterior_utility += weight * best_post_u

        evsi = max(0.0, float(expected_posterior_utility - baseline_max_utility))
        return evsi
