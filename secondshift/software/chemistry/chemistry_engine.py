"""
Chemistry / Model Identity Disambiguation Engine
Project: RMK-REVOLT / SECONDShift Platform
Tracks discrete chemistry hypothesis probabilities:
P(M | y) for M in {LFP, NMC, UNKNOWN}
Extracts physical features from test pulses and classifies into:
- KNOWN (>= 0.99 confidence)
- PROBABLE (0.90 <= P < 0.99)
- AMBIGUOUS (P < 0.90 or P(UNKNOWN) > 0.05)

RULE: UNKNOWN CHEMISTRY IS NEVER FORCED INTO A LABEL.
"""

import numpy as np
from typing import Dict, Any, Tuple
from scipy.stats import norm

class ChemistryDisambiguationEngine:
    def __init__(
        self,
        known_threshold: float = 0.990,
        probable_threshold: float = 0.900,
        sensor_noise_v: float = 0.002
    ):
        self.known_thresh = known_threshold
        self.prob_thresh = probable_threshold
        self.sigma_v = sensor_noise_v

    def initialize_prior(self, prior_source: str = "UNKNOWN") -> Dict[str, float]:
        """
        Initializes prior model probability based on intake documentation.
        """
        if prior_source == "KNOWN_LFP_FLEET":
            return {"LFP": 0.990, "NMC": 0.008, "UNKNOWN": 0.002}
        elif prior_source == "KNOWN_NMC_FLEET":
            return {"LFP": 0.008, "NMC": 0.990, "UNKNOWN": 0.002}
        elif prior_source == "TAGLESS_MIXED":
            return {"LFP": 0.500, "NMC": 0.450, "UNKNOWN": 0.050}
        else: # UNKNOWN
            return {"LFP": 0.333, "NMC": 0.333, "UNKNOWN": 0.334}

    def update_from_passive_rest(
        self,
        v_oc: float,
        prior: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Bayesian update based on resting thermodynamic open-circuit voltage.
        """
        # Likelihood evaluation:
        # LFP thermodynamically relaxes below 3.42V. Only fresh 100% charged sits at 3.42-3.45V.
        # NMC spans 3.00V to 4.20V (typically 3.50V - 3.90V at mid SOC).
        if v_oc >= 3.48:
            lik_lfp = 0.001
            lik_nmc = 0.990
            lik_unk = 0.009
        elif v_oc <= 3.10:
            # Deep discharge zone for both
            lik_lfp = 0.700
            lik_nmc = 0.250
            lik_unk = 0.050
        else:
            # Active plateau zone: 3.10V to 3.45V (LFP nominal, NMC low SOC)
            lik_lfp = 0.750
            lik_nmc = 0.220
            lik_unk = 0.030

        unnorm_lfp = prior["LFP"] * lik_lfp
        unnorm_nmc = prior["NMC"] * lik_nmc
        unnorm_unk = prior["UNKNOWN"] * lik_unk
        total = unnorm_lfp + unnorm_nmc + unnorm_unk + 1e-12

        return {
            "LFP": float(unnorm_lfp / total),
            "NMC": float(unnorm_nmc / total),
            "UNKNOWN": float(unnorm_unk / total)
        }

    def update_from_pulse_slope(
        self,
        delta_v_slope: float,
        current_a: float,
        duration_s: float,
        prior: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Bayesian update based on galvanostatic voltage slope during current pulse.
        LFP: flat d(OCV)/d(SOC) = 0.128 V/SOC -> small delta_V_slope (< 22mV)
        NMC: steep d(OCV)/d(SOC) = 0.671 V/SOC -> large delta_V_slope (> 22mV)
        """
        # Threshold at 22.0 mV for 10A 30s pulse
        # Normalized by current and duration
        expected_lfp_drop = 0.013 # 13mV typical
        expected_nmc_drop = 0.035 # 35mV typical
        sigma_slope = 0.005

        lik_lfp = float(norm.pdf(delta_v_slope, loc=expected_lfp_drop, scale=sigma_slope))
        lik_nmc = float(norm.pdf(delta_v_slope, loc=expected_nmc_drop, scale=sigma_slope))
        lik_unk = 0.050 # Diffuse likelihood for unmodeled chemistries

        unnorm_lfp = prior["LFP"] * lik_lfp
        unnorm_nmc = prior["NMC"] * lik_nmc
        unnorm_unk = prior["UNKNOWN"] * lik_unk
        total = unnorm_lfp + unnorm_nmc + unnorm_unk + 1e-12

        return {
            "LFP": float(unnorm_lfp / total),
            "NMC": float(unnorm_nmc / total),
            "UNKNOWN": float(unnorm_unk / total)
        }

    def get_confidence_state(self, posterior: Dict[str, float]) -> Tuple[str, str, float]:
        """
        Maps continuous posterior to (confidence_state, best_hypothesis, confidence_score)
        States: 'KNOWN', 'PROBABLE', 'AMBIGUOUS'
        """
        p_lfp = posterior["LFP"]
        p_nmc = posterior["NMC"]
        p_unk = posterior["UNKNOWN"]

        best_chem = "LFP" if p_lfp >= p_nmc else "NMC"
        best_p = max(p_lfp, p_nmc)

        if p_unk > 0.050 or best_p < self.prob_thresh:
            return "AMBIGUOUS", "UNKNOWN", float(best_p)
        elif best_p >= self.known_thresh and p_unk <= 0.005:
            return "KNOWN", best_chem, float(best_p)
        else:
            return "PROBABLE", best_chem, float(best_p)
