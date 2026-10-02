"""
RMK-REVOLT Belief State and Bayesian/Gaussian Uncertainty Estimator
Tracks the multi-parameter belief distribution b_i(t) = N(mu_i, Sigma_i)
for each module, with explicit variance propagation across tests and operation.
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple

class ModuleBelief:
    """
    Belief distribution for a single battery module.
    State representation:
    - mu_soh: Expected State of Health [0.0 - 1.0]
    - sigma_soh: Standard deviation (epistemic + aleatoric uncertainty) in SOH
    - mu_r0: Expected internal Ohmic resistance (Ohms)
    - sigma_r0: Standard deviation in internal resistance
    - mu_soc: Estimated State of Charge [0.0 - 1.0]
    - sigma_soc: Uncertainty in SOC
    - temp_c: Measured current temperature (Celsius)
    - temp_rate_c_s: Measured dT/dt under recent load (C/s)
    - leakage_mv_hr: Estimated open-circuit self-discharge rate (mV/hour)
    - triage_cleared: Boolean indicating deterministic safety gate passed
    - visual_anomaly: Boolean indicating physical defect
    """
    def __init__(
        self,
        module_id: str,
        prior_soh: float = 0.75,
        prior_sigma_soh: float = 0.18,
        prior_r0: float = 0.0025,
        prior_sigma_r0: float = 0.0012,
        prior_soc: float = 0.50,
        prior_sigma_soc: float = 0.15,
        nominal_capacity_ah: float = 50.0
    ):
        self.module_id = module_id
        self.nominal_capacity_ah = nominal_capacity_ah
        
        # State estimates
        self.mu_soh = float(prior_soh)
        self.sigma_soh = float(prior_sigma_soh)
        
        self.mu_r0 = float(prior_r0)
        self.sigma_r0 = float(prior_sigma_r0)
        
        self.mu_soc = float(prior_soc)
        self.sigma_soc = float(prior_sigma_soc)
        
        # Physical observation trackers
        self.temp_c = 25.0
        self.temp_rate_c_s = 0.0
        self.leakage_mv_hr = 0.0
        self.triage_cleared = False
        self.triage_status = "PENDING"  # ACCEPTED, HOLD, REJECTED
        self.visual_anomaly = False
        
        # Test history log
        self.applied_tests = []
        self.total_diagnostic_time_s = 0.0
        self.total_diagnostic_energy_wh = 0.0
        self.total_test_cost_inr = 0.0

    @property
    def capacity_ah(self) -> float:
        """Estimated usable capacity in Ampere-hours."""
        return self.mu_soh * self.nominal_capacity_ah

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "mu_soh": round(self.mu_soh, 4),
            "sigma_soh": round(self.sigma_soh, 4),
            "mu_r0_mohm": round(self.mu_r0 * 1000.0, 3),
            "sigma_r0_mohm": round(self.sigma_r0 * 1000.0, 3),
            "mu_soc": round(self.mu_soc, 3),
            "sigma_soc": round(self.sigma_soc, 3),
            "temp_c": round(self.temp_c, 2),
            "temp_rate_c_s": round(self.temp_rate_c_s, 4),
            "leakage_mv_hr": round(self.leakage_mv_hr, 3),
            "triage_status": self.triage_status,
            "tests_applied": list(self.applied_tests),
            "diag_time_s": self.total_diagnostic_time_s,
            "diag_energy_wh": self.total_diagnostic_energy_wh,
            "diag_cost_inr": self.total_test_cost_inr
        }

    def bayesian_scalar_update(
        self,
        prior_mu: float,
        prior_sigma: float,
        measurement: float,
        meas_noise_sigma: float
    ) -> Tuple[float, float]:
        """
        Exact conjugate Gaussian update for scalar parameter:
        1 / sigma_post^2 = 1 / prior_sigma^2 + 1 / meas_noise_sigma^2
        mu_post = sigma_post^2 * (prior_mu / prior_sigma^2 + measurement / meas_noise_sigma^2)
        """
        prior_var = max(prior_sigma ** 2, 1e-12)
        meas_var = max(meas_noise_sigma ** 2, 1e-12)
        post_var = 1.0 / (1.0 / prior_var + 1.0 / meas_var)
        post_sigma = np.sqrt(post_var)
        post_mu = post_var * (prior_mu / prior_var + measurement / meas_var)
        return float(post_mu), float(post_sigma)

    def update_from_pulse_test(
        self,
        measured_r0: float,
        sensor_noise_sigma_r0: float = 0.0003
    ) -> None:
        """Update R0 estimate from current-pulse delta V / delta I."""
        self.mu_r0, self.sigma_r0 = self.bayesian_scalar_update(
            self.mu_r0, self.sigma_r0, measured_r0, sensor_noise_sigma_r0
        )
        # R0 correlates with capacity degradation in LFP:
        # High resistance implies degraded SOH. Cross-covariance update:
        fresh_r0 = 0.0015
        inferred_soh = 1.0 - max(0.0, (self.mu_r0 - fresh_r0) / (fresh_r0 * 1.8))
        inferred_soh = float(np.clip(inferred_soh, 0.4, 1.0))
        # Cross-update for SOH with moderate uncertainty
        self.mu_soh, self.sigma_soh = self.bayesian_scalar_update(
            self.mu_soh, self.sigma_soh, inferred_soh, 0.06
        )

    def update_from_coulometric_test(
        self,
        measured_soh: float,
        measurement_sigma_soh: float = 0.02
    ) -> None:
        """Update capacity SOH from partial/full cycling coulomb-counting."""
        self.mu_soh, self.sigma_soh = self.bayesian_scalar_update(
            self.mu_soh, self.sigma_soh, measured_soh, measurement_sigma_soh
        )

    def update_from_operational_observation(
        self,
        observed_r0: float,
        duration_s: float,
        current_a: float
    ) -> None:
        """
        Update belief during active/derated participation (H.E.R.M.E.S. feedback).
        Longer duration & higher current provide higher SNR.
        """
        # Noise variance scales inversely with current and sqrt(time)
        effective_noise = 0.0008 / (max(abs(current_a), 5.0) / 10.0 * np.sqrt(max(duration_s, 10.0) / 10.0))
        self.mu_r0, self.sigma_r0 = self.bayesian_scalar_update(
            self.mu_r0, self.sigma_r0, observed_r0, effective_noise
        )
        # Gradual reduction in SOH uncertainty through in-situ observation
        inferred_soh = float(np.clip(1.0 - (self.mu_r0 - 0.0015) / (0.0015 * 2.2), 0.4, 1.0))
        self.mu_soh, self.sigma_soh = self.bayesian_scalar_update(
            self.mu_soh, self.sigma_soh, inferred_soh, 0.08
        )
