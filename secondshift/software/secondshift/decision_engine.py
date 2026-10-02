"""
SECONDShift Decision Engine
Project: RMK-REVOLT / SECONDShift Platform
Risk-Constrained Adaptive Qualification Under State and Model Uncertainty.
Decides: TEST, HOLD, OPERATE, DERATE, RETIRE.
Fundamental principle: SAFETY CONSTRAINT > ECONOMIC OPTIMIZATION.
"""

from typing import Dict, Any, Tuple, Optional, List, Set
import numpy as np

from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.estimators.model_uncertainty import ModelUncertaintyEvaluator
from secondshift.software.safety.hard_safety_barrier import HardSafetyBarrier
from secondshift.software.voi.evsi_calculator import ValueOfInformationEngine

class SECONDShiftDecisionEngine:
    def __init__(
        self,
        app_config: Optional[Dict[str, Any]] = None,
        voi_engine: Optional[ValueOfInformationEngine] = None
    ):
        self.config = app_config or {
            "min_soh_threshold": 0.70,
            "derate_soh_threshold": 0.65,
            "max_acceptable_r0_mohm": 3.5,
            "max_allowable_uncertainty_sigma_soh": 0.04,
            "safety_penalty_inr": 6000.0,
            "energy_revenue_per_kwh_inr": 10.0,
            "lifetime_cycles": 1200.0,
            "recycle_rate_inr_kwh": 1200.0,
            "alpha_safety": 0.01
        }
        self.voi = voi_engine or ValueOfInformationEngine()
        self.model_evaluator = ModelUncertaintyEvaluator(
            min_soh_threshold=self.config["min_soh_threshold"],
            derate_soh_threshold=self.config["derate_soh_threshold"],
            max_r0_mohm=self.config["max_acceptable_r0_mohm"]
        )
        self.barrier = HardSafetyBarrier(alpha_safety=self.config["alpha_safety"])

    def compute_unconstrained_utilities(
        self,
        estimator: BayesianStateEstimator,
        chemistry_posterior: Dict[str, float]
    ) -> Dict[str, float]:
        nominal_kwh = (estimator.nominal_capacity_ah * 3.2) / 1000.0
        base_revenue = estimator.mu_soh * nominal_kwh * self.config["lifetime_cycles"] * self.config["energy_revenue_per_kwh_inr"]

        # Risk evaluations
        risk_op = self.model_evaluator.compute_marginal_failure_risk(estimator, chemistry_posterior, "OPERATE")
        risk_der = self.model_evaluator.compute_marginal_failure_risk(estimator, chemistry_posterior, "DERATE")

        p_fail_op = risk_op["p_fail_marginal"]
        p_fail_der = risk_der["p_fail_marginal"]

        # Utilities
        u_operate = (1.0 - p_fail_op) * base_revenue - (p_fail_op * self.config["safety_penalty_inr"]) - 100.0
        u_derate = (1.0 - p_fail_der) * (0.75 * base_revenue) - (p_fail_der * 0.15 * self.config["safety_penalty_inr"]) - 30.0
        u_retire = nominal_kwh * self.config["recycle_rate_inr_kwh"] - 50.0
        u_hold = nominal_kwh * self.config["recycle_rate_inr_kwh"] * 0.80 - 80.0

        return {
            "OPERATE": float(u_operate),
            "DERATE": float(u_derate),
            "RETIRE": float(u_retire),
            "HOLD": float(u_hold)
        }

    def evaluate_decision(
        self,
        estimator: BayesianStateEstimator,
        chemistry_posterior: Dict[str, float],
        chemistry_confidence_state: str,
        triage_status: str,
        test_history_count: int = 0,
        max_tests_allowed: int = 3
    ) -> Dict[str, Any]:
        """
        Executes the full risk-constrained, chemistry-gated decision process.
        """
        # Step 1: Marginal risk evaluation
        risk_op = self.model_evaluator.compute_marginal_failure_risk(estimator, chemistry_posterior, "OPERATE")
        risk_der = self.model_evaluator.compute_marginal_failure_risk(estimator, chemistry_posterior, "DERATE")

        # Step 2: Unconstrained economic utilities
        unconstrained_u = self.compute_unconstrained_utilities(estimator, chemistry_posterior)

        # Step 3: Filter admissible action set through Hard Safety Barrier
        admissible_actions = self.barrier.filter_admissible_actions(
            risk_op,
            risk_der,
            chemistry_confidence_state,
            triage_status
        )

        # Step 4: Constrain utilities (-1e8 for inadmissible actions)
        constrained_u = self.barrier.apply_barrier_to_utilities(unconstrained_u, admissible_actions)

        # Baseline max utility among currently admissible non-test actions
        best_static_action = max(constrained_u.items(), key=lambda x: x[1])[0]
        best_static_utility = constrained_u[best_static_action]

        # Step 5: Evaluate VOI for candidate diagnostic tests
        candidate_tests = []
        if test_history_count < max_tests_allowed and triage_status != "REJECT":
            # If chemistry is uncertain, evaluate chemistry disambiguation pulse
            if chemistry_confidence_state != "KNOWN":
                test_cost = self.voi.compute_test_cost("CHEM_DISAMBIG_PULSE")
                # Expected value of clarifying chemistry is high if it lifts restriction on OPERATE
                evsi_chem = 85.0 # Empirical EVSI for unlocking LFP operations
                voi_chem = evsi_chem - test_cost
                candidate_tests.append({
                    "test_name": "CHEM_DISAMBIG_PULSE",
                    "evsi": evsi_chem,
                    "test_cost": test_cost,
                    "voi": voi_chem,
                    "target_param": "CHEMISTRY"
                })

            # If SOH uncertainty exceeds threshold, evaluate coulometric cycle
            if estimator.sigma_soh > self.config["max_allowable_uncertainty_sigma_soh"]:
                test_cost = self.voi.compute_test_cost("SHORT_COULOMETRIC_CYCLE")
                
                # SOH utility evaluator lambda (accounting for simultaneous Ohmic characterization)
                def eval_soh_u(mu, sig):
                    est_mock = BayesianStateEstimator(
                        "mock", prior_mu_soh=mu, prior_sigma_soh=sig,
                        prior_mu_r0=estimator.mu_r0, prior_sigma_r0=min(estimator.sigma_r0, 0.00035)
                    )
                    r_op = self.model_evaluator.compute_marginal_failure_risk(est_mock, chemistry_posterior, "OPERATE")
                    r_der = self.model_evaluator.compute_marginal_failure_risk(est_mock, chemistry_posterior, "DERATE")
                    adm = self.barrier.filter_admissible_actions(r_op, r_der, chemistry_confidence_state, triage_status)
                    raw_u = self.compute_unconstrained_utilities(est_mock, chemistry_posterior)
                    filt_u = self.barrier.apply_barrier_to_utilities(raw_u, adm)
                    return max(filt_u.values())

                evsi_soh = self.voi.calculate_evsi("SHORT_COULOMETRIC_CYCLE", estimator.mu_soh, estimator.sigma_soh, eval_soh_u, best_static_utility)
                voi_soh = evsi_soh - test_cost
                candidate_tests.append({
                    "test_name": "SHORT_COULOMETRIC_CYCLE",
                    "evsi": evsi_soh,
                    "test_cost": test_cost,
                    "voi": voi_soh,
                    "target_param": "SOH"
                })

            # If R0 uncertainty exceeds 0.5 mOhm, evaluate quick pulse
            if estimator.sigma_r0 > 0.0005:
                test_cost = self.voi.compute_test_cost("QUICK_PULSE_R0")
                def eval_r0_u(mu, sig):
                    est_mock = BayesianStateEstimator(
                        "mock", prior_mu_soh=estimator.mu_soh, prior_sigma_soh=min(estimator.sigma_soh, 0.04),
                        prior_mu_r0=mu, prior_sigma_r0=sig
                    )
                    r_op = self.model_evaluator.compute_marginal_failure_risk(est_mock, chemistry_posterior, "OPERATE")
                    r_der = self.model_evaluator.compute_marginal_failure_risk(est_mock, chemistry_posterior, "DERATE")
                    adm = self.barrier.filter_admissible_actions(r_op, r_der, chemistry_confidence_state, triage_status)
                    raw_u = self.compute_unconstrained_utilities(est_mock, chemistry_posterior)
                    filt_u = self.barrier.apply_barrier_to_utilities(raw_u, adm)
                    return max(filt_u.values())

                evsi_r0 = self.voi.calculate_evsi("QUICK_PULSE_R0", estimator.mu_r0, estimator.sigma_r0, eval_r0_u, best_static_utility)
                voi_r0 = evsi_r0 - test_cost
                candidate_tests.append({
                    "test_name": "QUICK_PULSE_R0",
                    "evsi": evsi_r0,
                    "test_cost": test_cost,
                    "voi": voi_r0,
                    "target_param": "R0"
                })

        # Step 6: Final Decision Selection
        best_test = None
        if candidate_tests:
            best_test = max(candidate_tests, key=lambda x: x["voi"])

        final_action = best_static_action
        final_test_to_run = None
        decision_reason = ""

        # Gated Decision Logic
        if best_test and best_test["voi"] > 0.0:
            final_action = "TEST"
            final_test_to_run = best_test["test_name"]
            decision_reason = (
                f"VOI of {final_test_to_run} is +₹{best_test['voi']:.2f} "
                f"(EVSI=₹{best_test['evsi']:.2f} > Cost=₹{best_test['test_cost']:.2f}); "
                f"epistemic uncertainty reduction justifies diagnostic expense."
            )
        elif chemistry_confidence_state != "KNOWN" and final_action in ["OPERATE", "DERATE"]:
            # Hard Safety catch
            final_action = "HOLD"
            decision_reason = (
                f"Chemistry confidence is {chemistry_confidence_state}; "
                f"direct {best_static_action} is strictly prohibited by Hard Safety Barrier. Routing to HOLD/RECYCLE."
            )
        elif best_static_action == "OPERATE":
            decision_reason = (
                f"Known chemistry ({chemistry_posterior.get('LFP', 0.0):.1%}), "
                f"marginal failure risk {risk_op['p_fail_marginal']:.2%} <= {self.config['alpha_safety']:.1%}, "
                f"SOH={estimator.mu_soh:.2f} +/- {estimator.sigma_soh:.2f}. "
                f"Testing no longer economically justified (VOI <= 0)."
            )
        elif best_static_action == "DERATE":
            decision_reason = (
                f"Cell cleared derated safety envelope (P_fail={risk_der['p_fail_marginal']:.2%} <= 1.0%), "
                f"but failed full-rate OPERATE barrier. Assigned to 0.5C derated operation."
            )
        elif best_static_action == "HOLD":
            decision_reason = "Ambiguous condition; testing budget exhausted or not justified. Quarantined in HOLD."
        elif best_static_action == "RETIRE":
            decision_reason = (
                f"Cell violates safety barrier or cannot achieve positive operating utility. "
                f"Routed to hydro-metallurgical recycling (salvage value: ₹{best_static_utility:.1f})."
            )

        return {
            "decision": final_action,
            "recommended_test": final_test_to_run,
            "decision_reason": decision_reason,
            "admissible_actions": list(admissible_actions),
            "constrained_utilities": constrained_u,
            "marginal_risk_operate": risk_op["p_fail_marginal"],
            "marginal_risk_derate": risk_der["p_fail_marginal"],
            "candidate_tests_evaluated": candidate_tests,
            "chemistry_confidence_state": chemistry_confidence_state
        }
