"""
RMK-REVOLT Decision Engine
Uncertainty-Aware Utility Optimization with Value of Information (VOI)
Selects actions from A = {TEST, OPERATE, DERATE, BYPASS, ISOLATE, RETIRE}
under strict application-specific safety and economic constraints.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from scipy.stats import norm
from models.belief_state import ModuleBelief
from src.secondshift import SecondShiftDiagnosticEngine

class DecisionEngine:
    """
    Mathematical decision formulation balancing operational value,
    safety penalties, uncertainty reduction, and diagnostic expenses.
    """
    def __init__(
        self,
        application_config: Dict[str, Any],
        diagnostic_engine: SecondShiftDiagnosticEngine
    ):
        self.app = application_config
        self.diag = diagnostic_engine
        
        # Application constraints
        self.min_soh = float(self.app.get("min_soh_threshold", 0.70))
        self.max_r0 = float(self.app.get("max_acceptable_r0_mohm", 3.5)) / 1000.0
        self.max_sigma_soh = float(self.app.get("max_allowable_uncertainty_sigma_soh", 0.04))
        self.safety_penalty_inr = float(self.app.get("safety_penalty_inr", 6000.0))
        self.revenue_per_kwh = float(self.app.get("energy_revenue_per_kwh_inr", 10.0))
        self.lifetime_cycles = float(self.app.get("lifetime_cycles", 1200.0))
        self.recycle_rate_inr_kwh = 1200.0
        
        # Task 1 & 5: Hard Safety Barrier Configuration
        self.use_hard_safety_barrier = bool(self.app.get("use_hard_safety_barrier", True))
        self.alpha_safety = float(self.app.get("alpha_safety", 0.01))

    def compute_operational_utilities(
        self,
        belief: ModuleBelief,
        override_barrier: Optional[bool] = None
    ) -> Dict[str, float]:
        """
        Evaluate expected net utility for all non-diagnostic actions:
        OPERATE, DERATE, BYPASS, RETIRE, ISOLATE.
        Enforces hard probabilistic safety barrier P(fail) <= alpha.
        """
        enforce_barrier = self.use_hard_safety_barrier if override_barrier is None else override_barrier
        nominal_kwh = (belief.nominal_capacity_ah * 3.2) / 1000.0
        base_energy_revenue = belief.mu_soh * nominal_kwh * self.lifetime_cycles * self.revenue_per_kwh

        # If triage rejected, hard safety dictates immediate RETIRE / ISOLATE
        if belief.triage_status == "REJECT":
            return {
                "OPERATE": -1e8,
                "DERATE": -1e8,
                "BYPASS": -1e8,
                "ISOLATE": 0.0,
                "RETIRE": nominal_kwh * self.recycle_rate_inr_kwh - 50.0
            }

        # 1. Compliance probabilities under Gaussian belief
        z_soh = (belief.mu_soh - self.min_soh) / max(belief.sigma_soh, 1e-4)
        z_r0 = (self.max_r0 - belief.mu_r0) / max(belief.sigma_r0, 1e-5)
        
        p_safe_soh = norm.cdf(z_soh)
        p_safe_r0 = norm.cdf(z_r0)
        p_compliant_full = float(p_safe_soh * p_safe_r0)
        p_fail_full = 1.0 - p_compliant_full

        # Hard Safety Barrier check for OPERATE: P(SOH < SOH_min) <= alpha
        p_soh_fail_operate = 1.0 - p_safe_soh
        if enforce_barrier and (p_soh_fail_operate > self.alpha_safety):
            u_operate = -1e8
        else:
            u_operate = (
                p_compliant_full * base_energy_revenue
                - p_fail_full * self.safety_penalty_inr
                - 100.0  # Normal cyclic degradation cost
            )

        # 2. Compliance probabilities for DERATE (0.5C participation)
        z_soh_derate = (belief.mu_soh - (self.min_soh - 0.05)) / max(belief.sigma_soh, 1e-4)
        z_r0_derate = ((self.max_r0 * 1.35) - belief.mu_r0) / max(belief.sigma_r0, 1e-5)
        p_safe_soh_derate = float(norm.cdf(z_soh_derate))
        p_compliant_derate = float(p_safe_soh_derate * norm.cdf(z_r0_derate))
        p_fail_derate = 1.0 - p_compliant_derate

        # Hard Safety Barrier check for DERATE: P(SOH < SOH_min_derate) <= alpha
        p_soh_fail_derate = 1.0 - p_safe_soh_derate
        if enforce_barrier and (p_soh_fail_derate > self.alpha_safety):
            u_derate = -1e8
        else:
            u_derate = (
                p_compliant_derate * (0.75 * base_energy_revenue)
                - p_fail_derate * (0.15 * self.safety_penalty_inr)
                - 30.0   # Reduced degradation cost
            )

        # 3. Utility of BYPASS
        u_bypass = -50.0

        # 4. Utility of RETIRE (Salvage value)
        u_retire = nominal_kwh * self.recycle_rate_inr_kwh - 50.0

        # 5. Utility of ISOLATE
        u_isolate = -100.0

        return {
            "OPERATE": float(u_operate),
            "DERATE": float(u_derate),
            "BYPASS": float(u_bypass),
            "RETIRE": float(u_retire),
            "ISOLATE": float(u_isolate)
        }


    def compute_evsi_and_voi(
        self,
        test_name: str,
        belief: ModuleBelief,
        current_best_utility: float
    ) -> Tuple[float, float, float]:
        """
        Explicit Value of Information Formulation:
        EVSI = E_y [ max_a U(a | y) ] - max_a U(a)
        VOI = EVSI - Cost(test)
        Returns: (voi, evsi, test_cost)
        """
        spec = self.diag.test_specs[test_name]
        test_cost = self.diag.get_test_cost_inr(test_name)
        
        if test_name in belief.applied_tests:
            return -test_cost, 0.0, test_cost

        # Sample possible future observations y ~ N(mu, sigma^2 + sigma_noise^2)
        if test_name == "short_coulometric_cycle":
            meas_noise = spec["meas_noise_sigma_soh"]
            post_var = 1.0 / (1.0 / (belief.sigma_soh**2) + 1.0 / (meas_noise**2))
            post_sigma_soh = np.sqrt(post_var)
            
            # 7-point Gaussian quadrature over possible SOH outcomes
            sample_points = [-2.0, -1.33, -0.67, 0.0, 0.67, 1.33, 2.0]
            weights = norm.pdf(sample_points)
            weights = weights / np.sum(weights)
            
            expected_post_u = 0.0
            for pt, w in zip(sample_points, weights):
                s_soh = float(np.clip(belief.mu_soh + pt * belief.sigma_soh, 0.40, 1.05))
                temp_b = ModuleBelief(
                    module_id=belief.module_id,
                    prior_soh=s_soh,
                    prior_sigma_soh=post_sigma_soh,
                    prior_r0=belief.mu_r0,
                    prior_sigma_r0=belief.sigma_r0,
                    nominal_capacity_ah=belief.nominal_capacity_ah
                )
                temp_b.triage_status = belief.triage_status
                u_dict = self.compute_operational_utilities(temp_b)
                expected_post_u += w * max(u_dict.values())

        elif test_name == "pulse_power_test":
            meas_noise = spec["sensor_noise_sigma_r0"]
            post_var = 1.0 / (1.0 / (belief.sigma_r0**2) + 1.0 / (meas_noise**2))
            post_sigma_r0 = np.sqrt(post_var)
            
            sample_points = [-2.0, -1.0, 0.0, 1.0, 2.0]
            weights = norm.pdf(sample_points)
            weights = weights / np.sum(weights)
            
            expected_post_u = 0.0
            for pt, w in zip(sample_points, weights):
                s_r0 = float(max(0.0008, belief.mu_r0 + pt * belief.sigma_r0))
                # Correlation: lower resistance implies higher expected SOH
                delta_soh_inf = -(s_r0 - belief.mu_r0) * 100.0
                inferred_soh = float(np.clip(belief.mu_soh + delta_soh_inf, 0.40, 1.05))
                temp_b = ModuleBelief(
                    module_id=belief.module_id,
                    prior_soh=inferred_soh,
                    prior_sigma_soh=belief.sigma_soh * 0.85,
                    prior_r0=s_r0,
                    prior_sigma_r0=post_sigma_r0,
                    nominal_capacity_ah=belief.nominal_capacity_ah
                )
                temp_b.triage_status = belief.triage_status
                u_dict = self.compute_operational_utilities(temp_b)
                expected_post_u += w * max(u_dict.values())

        else:  # thermal_recovery_step
            expected_post_u = current_best_utility + 10.0

        evsi = max(0.0, expected_post_u - current_best_utility)
        voi = expected_post_u - current_best_utility - test_cost
        return float(voi), float(evsi), float(test_cost)

    def compute_voi(
        self,
        test_name: str,
        belief: ModuleBelief,
        current_best_utility: float
    ) -> float:
        voi, _, _ = self.compute_evsi_and_voi(test_name, belief, current_best_utility)
        return voi

    def select_action(
        self,
        belief: ModuleBelief,
        max_tests_allowed: int = 3
    ) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """
        Evaluate optimal decision:
        Returns: (primary_action, test_name_if_applicable, debug_metrics)
        """
        op_utilities = self.compute_operational_utilities(belief)
        best_op_action = max(op_utilities, key=op_utilities.get)
        best_op_utility = op_utilities[best_op_action]

        # Check if TRIAGE failed: cannot test further
        if belief.triage_status == "REJECT":
            return "RETIRE", None, {
                "reason": "Triage safety rejection",
                "op_utilities": op_utilities,
                "best_voi": 0.0,
                "best_evsi": 0.0,
                "best_cost": 0.0
            }

        # Check if testing budget exhausted
        if len(belief.applied_tests) >= max_tests_allowed:
            return best_op_action, None, {
                "reason": "Test budget exhausted",
                "op_utilities": op_utilities,
                "best_voi": 0.0,
                "best_evsi": 0.0,
                "best_cost": 0.0
            }

        # Compute VOI and EVSI for candidate diagnostic tests
        candidate_tests = [
            "pulse_power_test",
            "short_coulometric_cycle",
            "thermal_recovery_step"
        ]
        
        voi_scores = {}
        evsi_scores = {}
        cost_scores = {}
        for test in candidate_tests:
            if test not in belief.applied_tests:
                v, e, c = self.compute_evsi_and_voi(test, belief, best_op_utility)
                voi_scores[test] = v
                evsi_scores[test] = e
                cost_scores[test] = c

        if not voi_scores:
            return best_op_action, None, {
                "reason": "All diagnostic tests already completed",
                "op_utilities": op_utilities,
                "best_voi": 0.0,
                "best_evsi": 0.0,
                "best_cost": 0.0
            }

        best_test = max(voi_scores, key=voi_scores.get)
        best_voi = voi_scores[best_test]
        best_evsi = evsi_scores[best_test]
        best_cost = cost_scores[best_test]

        # Stop condition: Only test if VOI > 0 (EVSI > Cost) AND uncertainty exceeds acceptable threshold
        needs_confidence = (
            belief.sigma_soh > self.max_sigma_soh or
            belief.sigma_r0 > 0.0006
        )

        if best_voi > 0.0 and needs_confidence:
            return "TEST", best_test, {
                "reason": f"Diagnostic EVSI (+{best_evsi:.1f} INR) exceeds test cost ({best_cost:.1f} INR), net VOI = +{best_voi:.1f} INR",
                "voi_scores": voi_scores,
                "evsi_scores": evsi_scores,
                "cost_scores": cost_scores,
                "op_utilities": op_utilities,
                "best_voi": best_voi,
                "best_evsi": best_evsi,
                "best_cost": best_cost
            }
        else:
            return best_op_action, None, {
                "reason": f"VOI non-positive ({best_voi:.1f} INR) or confidence sufficient",
                "voi_scores": voi_scores,
                "evsi_scores": evsi_scores,
                "cost_scores": cost_scores,
                "op_utilities": op_utilities,
                "best_voi": best_voi,
                "best_evsi": best_evsi,
                "best_cost": best_cost
            }
