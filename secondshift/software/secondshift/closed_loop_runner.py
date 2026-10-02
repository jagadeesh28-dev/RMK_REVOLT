"""
HERMES <-> SECONDShift Closed-Loop Autonomous Pipeline
Project: RMK-REVOLT / SECONDShift Platform
Orchestrates:
OBSERVE -> TRIAGE -> CHEMISTRY -> ESTIMATE -> CHECK SAFETY -> VOI -> SELECT ACTION
-> EXECUTE TEST -> MEASURE -> UPDATE BELIEF -> TERMINATE ON STOPPING RULE.
"""

import time
import numpy as np
from typing import Dict, Any, List, Optional

from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.triage.triage_gate import TriageGate
from secondshift.software.chemistry.chemistry_engine import ChemistryDisambiguationEngine
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.secondshift.decision_engine import SECONDShiftDecisionEngine

class ClosedLoopRunner:
    def __init__(
        self,
        measurement_engine: HermesMeasurementEngine,
        app_config: Optional[Dict[str, Any]] = None
    ):
        self.meas = measurement_engine
        self.triage = TriageGate()
        self.chem_engine = ChemistryDisambiguationEngine()
        self.decision_engine = SECONDShiftDecisionEngine(app_config)

    def run_qualification_pipeline(
        self,
        cell_id: str,
        prior_source: str = "UNKNOWN",
        prior_soh: float = 0.75,
        prior_sigma_soh: float = 0.15,
        prior_r0_mohm: float = 2.5,
        prior_sigma_r0_mohm: float = 1.2,
        ambient_temp_c: float = 25.0,
        max_loop_iterations: int = 5
    ) -> Dict[str, Any]:
        """
        Executes end-to-end adaptive qualification on specimen.
        """
        trace = []
        start_mono = time.monotonic()
        total_diag_cost = 0.0
        total_diag_energy = 0.0

        # 1. INITIAL OBSERVATION & TRIAGE
        v_rest_init = self.meas.measure_voltage()
        t_init = self.meas.measure_temperature()
        rest_data = self.meas.measure_rest_voltage(rest_duration_s=2.0)
        
        triage_status, triage_reason = self.triage.evaluate(
            v_rest=rest_data["v_rest"],
            t_rest=rest_data["temperature_c"],
            ambient_temp_c=ambient_temp_c,
            leakage_rate_mv_hr=rest_data["drift_mv_hr"]
        )

        trace.append({
            "stage": "STAGE_0_TRIAGE",
            "status": triage_status,
            "reason": triage_reason,
            "v_rest": rest_data["v_rest"],
            "t_rest": rest_data["temperature_c"],
            "drift_mv_hr": rest_data["drift_mv_hr"]
        })

        if triage_status == "REJECT":
            return {
                "cell_id": cell_id,
                "final_decision": "RETIRE",
                "final_reason": f"Failed Stage 0 Deterministic Triage: {triage_reason}",
                "final_soh_estimate": prior_soh,
                "final_soh_uncertainty": prior_sigma_soh,
                "final_r0_mohm": prior_r0_mohm,
                "final_chemistry": "UNKNOWN",
                "final_chem_confidence": "AMBIGUOUS",
                "final_chem_posterior": {"LFP": 0.333, "NMC": 0.333, "UNKNOWN": 0.334},
                "elapsed_time_s": time.monotonic() - start_mono,
                "total_diag_cost_inr": total_diag_cost,
                "total_diag_energy_wh": total_diag_energy,
                "tests_executed_count": 0,
                "trace": trace
            }

        # 2. INITIALIZE BELIEF STATE & CHEMISTRY POSTERIOR
        chem_prior = self.chem_engine.initialize_prior(prior_source)
        # Update chemistry from initial resting Voc
        chem_post = self.chem_engine.update_from_passive_rest(rest_data["v_rest"], chem_prior)
        conf_state, best_chem, conf_score = self.chem_engine.get_confidence_state(chem_post)

        estimator = BayesianStateEstimator(
            module_id=cell_id,
            prior_mu_soh=prior_soh,
            prior_sigma_soh=prior_sigma_soh,
            prior_mu_r0=prior_r0_mohm / 1000.0,
            prior_sigma_r0=prior_sigma_r0_mohm / 1000.0
        )

        test_history_count = 0

        # 3. ADAPTIVE DECISION & TESTING LOOP
        for iteration in range(max_loop_iterations):
            decision_eval = self.decision_engine.evaluate_decision(
                estimator=estimator,
                chemistry_posterior=chem_post,
                chemistry_confidence_state=conf_state,
                triage_status=triage_status,
                test_history_count=test_history_count
            )

            current_decision = decision_eval["decision"]
            recommended_test = decision_eval["recommended_test"]

            trace.append({
                "iteration": iteration,
                "stage": "DECISION_EVALUATION",
                "decision": current_decision,
                "recommended_test": recommended_test,
                "decision_reason": decision_eval["decision_reason"],
                "soh_estimate": f"{estimator.mu_soh:.3f} +/- {estimator.sigma_soh:.3f}",
                "r0_mohm_estimate": f"{estimator.mu_r0*1000:.2f} +/- {estimator.sigma_r0*1000:.2f}",
                "chemistry_confidence_state": conf_state,
                "chemistry_posterior": dict(chem_post),
                "marginal_risk_operate": decision_eval["marginal_risk_operate"]
            })

            # Check termination
            if current_decision != "TEST":
                # Stopping rule reached: Decision finalized!
                break

            # Execute Recommended Test via HERMES
            test_history_count += 1
            if recommended_test == "CHEM_DISAMBIG_PULSE":
                # Apply 10A 15s pulse and observe slope
                pulse_resp = self.meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=15.0)
                slope = pulse_resp["delta_v_total"]
                chem_post = self.chem_engine.update_from_pulse_slope(slope, 10.0, 15.0, chem_post)
                conf_state, best_chem, conf_score = self.chem_engine.get_confidence_state(chem_post)
                total_diag_cost += self.decision_engine.voi.compute_test_cost("CHEM_DISAMBIG_PULSE")
                total_diag_energy += 0.35

            elif recommended_test == "SHORT_COULOMETRIC_CYCLE":
                # Apply partial discharge step and update SOH via hardware abstraction
                pulse_resp = self.meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=30.0)
                observed_soh = self.meas.measure_coulometric_soh(observation_noise_sigma=0.015)
                estimator.update_soh_from_coulometric_observation(observed_soh, observation_noise_sigma=0.025)
                estimator.update_r0_from_ohmic_jump(pulse_resp["r0_ohms"], sensor_noise_sigma=0.00035)
                total_diag_cost += self.decision_engine.voi.compute_test_cost("SHORT_COULOMETRIC_CYCLE")
                total_diag_energy += 1.80

            elif recommended_test == "QUICK_PULSE_R0":
                pulse_resp = self.meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=5.0)
                estimator.update_r0_from_ohmic_jump(pulse_resp["r0_ohms"], sensor_noise_sigma=0.00035)
                total_diag_cost += self.decision_engine.voi.compute_test_cost("QUICK_PULSE_R0")
                total_diag_energy += 0.15

        elapsed_time = time.monotonic() - start_mono

        return {
            "cell_id": cell_id,
            "final_decision": current_decision,
            "final_reason": decision_eval["decision_reason"],
            "final_soh_estimate": estimator.mu_soh,
            "final_soh_uncertainty": estimator.sigma_soh,
            "final_r0_mohm": estimator.mu_r0 * 1000.0,
            "final_chemistry": best_chem,
            "final_chem_confidence": conf_state,
            "final_chem_posterior": chem_post,
            "elapsed_time_s": elapsed_time,
            "total_diag_cost_inr": total_diag_cost,
            "total_diag_energy_wh": total_diag_energy,
            "tests_executed_count": test_history_count,
            "trace": trace
        }
