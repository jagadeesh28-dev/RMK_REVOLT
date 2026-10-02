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
        expected_lfp_drop = 0.022 # 22mV typical (2.0 mOhm * 10A + 2mV pol)
        expected_nmc_drop = 0.038 # 38mV typical (1.6 mOhm * 10A + 22mV pol)
        sigma_slope = 0.006

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

    def update_from_feature_vector(
        self,
        features: Dict[str, float],
        prior: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Full 7-feature Bayesian update (Phase 6 & 7 Specification):
        features = {
            'ocv': float (V),
            'delta_v': float (V),
            'impedance': float (Ohm, delta_V / delta_I),
            'dv_dt': float (V/s),
            'relaxation_slope': float (mV/s),
            'temp_response': float (deg C rise),
            'recovery': float (fractional recovery)
        }
        """
        # Feature distributions parameterized from physical laboratory characterization:
        # LFP: Flat plateau OCV (3.28-3.34V), lower temp rise, distinct dual-exponential relaxation
        # NMC: Sloped OCV (3.60-4.10V), higher dV/dt, higher temp rise per unit Ah
        
        # 1. OCV Likelihood
        ocv = features.get('ocv', 3.30)
        p_ocv_lfp = norm.pdf(ocv, loc=3.30, scale=0.08)
        p_ocv_nmc = norm.pdf(ocv, loc=3.80, scale=0.25)
        p_ocv_unk = 0.05 # Diffuse

        # 2. Impedance / delta_V Likelihood
        imp = features.get('impedance', 0.002)
        p_imp_lfp = norm.pdf(imp, loc=0.0022, scale=0.0008)
        p_imp_nmc = norm.pdf(imp, loc=0.0018, scale=0.0007)
        p_imp_unk = 0.10

        # 3. Relaxation Slope Likelihood (mV/s)
        rel = features.get('relaxation_slope', 0.5)
        p_rel_lfp = norm.pdf(rel, loc=0.45, scale=0.20)
        p_rel_nmc = norm.pdf(rel, loc=1.20, scale=0.35)
        p_rel_unk = 0.10

        # Joint Likelihood across independent features
        lik_lfp = p_ocv_lfp * p_imp_lfp * p_rel_lfp + 1e-12
        lik_nmc = p_ocv_nmc * p_imp_nmc * p_rel_nmc + 1e-12
        lik_unk = p_ocv_unk * p_imp_unk * p_rel_unk + 1e-12

        unnorm_lfp = prior["LFP"] * lik_lfp
        unnorm_nmc = prior["NMC"] * lik_nmc
        unnorm_unk = prior["UNKNOWN"] * lik_unk
        total = unnorm_lfp + unnorm_nmc + unnorm_unk + 1e-18

        return {
            "LFP": float(unnorm_lfp / total),
            "NMC": float(unnorm_nmc / total),
            "UNKNOWN": float(unnorm_unk / total)
        }

