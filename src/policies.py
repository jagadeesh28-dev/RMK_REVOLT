"""
RMK-REVOLT: The Four Qualification Policies
A. Policy A: Fixed Qualification (Industrial standard sequence)
B. Policy B: Scalar SOH Threshold (Uncertainty-blind scalar BMS)
C. Policy C: Uncertainty Threshold (Heuristic confidence-interval policy)
D. Policy D: Risk-Constrained Value-of-Information (RC-VOI)
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from scipy.stats import norm
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.secondshift import SecondShiftDiagnosticEngine
from src.decision_engine import DecisionEngine

class PolicyAFixedQualification:
    """
    Policy A: Fixed Comprehensive Qualification.
    Standard OEM protocol: executes pulse (20s) + coulometric cycle (600s) + thermal (180s).
    Total diagnostic time = 800s. Uncertainty-blind, rigid.
    """
    def __init__(self, diag: SecondShiftDiagnosticEngine, app_config: Dict[str, Any]):
        self.diag = diag
        self.soh_min = float(app_config.get("min_soh_threshold", 0.70))
        self.r0_max = float(app_config.get("max_acceptable_r0_mohm", 3.5)) / 1000.0

    def evaluate(self, module: BatteryModule, belief: ModuleBelief) -> Tuple[str, Dict[str, Any]]:
        self.diag.execute_test("pulse_power_test", module, belief)
        self.diag.execute_test("short_coulometric_cycle", module, belief)
        self.diag.execute_test("thermal_recovery_step", module, belief)

        if belief.mu_soh >= self.soh_min and belief.mu_r0 <= self.r0_max:
            action = "OPERATE"
        else:
            action = "RETIRE"

        return action, {
            "policy": "A_Fixed_Qualification",
            "action": action,
            "diag_time_s": belief.total_diagnostic_time_s,
            "diag_energy_wh": belief.total_diagnostic_energy_wh,
            "diag_cost_inr": belief.total_test_cost_inr,
            "tests_applied": list(belief.applied_tests)
        }


class PolicyBScalarThreshold:
    """
    Policy B: Scalar SOH Threshold.
    Acts strictly on scalar point-estimate SOH (assumes sigma=0). Zero diagnostic tests.
    """
    def __init__(self, diag: SecondShiftDiagnosticEngine, app_config: Dict[str, Any]):
        self.diag = diag
        self.soh_min = float(app_config.get("min_soh_threshold", 0.70))

    def evaluate(self, module: BatteryModule, belief: ModuleBelief) -> Tuple[str, Dict[str, Any]]:
        if belief.mu_soh >= self.soh_min:
            action = "OPERATE"
        else:
            action = "RETIRE"

        return action, {
            "policy": "B_Scalar_Threshold",
            "action": action,
            "diag_time_s": 0.0,
            "diag_energy_wh": 0.0,
            "diag_cost_inr": 0.0,
            "tests_applied": []
        }


class PolicyCUncertaintyThreshold:
    """
    Policy C: Heuristic Uncertainty Thresholding.
    Uses belief distribution (mu, sigma) with confidence intervals, but WITHOUT
    economic Value of Information optimization. Tests whenever sigma > sigma_target in boundary.
    """
    def __init__(
        self,
        diag: SecondShiftDiagnosticEngine,
        app_config: Dict[str, Any],
        sigma_target: float = 0.04,
        confidence_k: float = 1.645,  # 90% confidence one-sided
        allow_derating: bool = True
    ):
        self.diag = diag
        self.app = app_config
        self.soh_min = float(app_config.get("min_soh_threshold", 0.70))
        self.r0_max = float(app_config.get("max_acceptable_r0_mohm", 3.5)) / 1000.0
        self.sigma_target = sigma_target
        self.confidence_k = confidence_k
        self.allow_derating = allow_derating
        
        # Test candidate sequence
        self.test_sequence = ["pulse_power_test", "short_coulometric_cycle"]

    def evaluate(self, module: BatteryModule, belief: ModuleBelief, max_tests: int = 2) -> Tuple[str, Dict[str, Any]]:
        tests_run = 0
        while tests_run < max_tests:
            # 1. Check if definitely healthy with 90% confidence
            lower_bound_soh = belief.mu_soh - self.confidence_k * belief.sigma_soh
            upper_bound_r0 = belief.mu_r0 + self.confidence_k * belief.sigma_r0
            if lower_bound_soh >= self.soh_min and upper_bound_r0 <= self.r0_max:
                return "OPERATE", {
                    "policy": "C_Uncertainty_Threshold",
                    "action": "OPERATE",
                    "diag_time_s": belief.total_diagnostic_time_s,
                    "diag_energy_wh": belief.total_diagnostic_energy_wh,
                    "diag_cost_inr": belief.total_test_cost_inr,
                    "tests_applied": list(belief.applied_tests)
                }

            # 2. Check if definitely degraded with 90% confidence
            upper_bound_soh = belief.mu_soh + self.confidence_k * belief.sigma_soh
            if upper_bound_soh < self.soh_min:
                return "RETIRE", {
                    "policy": "C_Uncertainty_Threshold",
                    "action": "RETIRE",
                    "diag_time_s": belief.total_diagnostic_time_s,
                    "diag_energy_wh": belief.total_diagnostic_energy_wh,
                    "diag_cost_inr": belief.total_test_cost_inr,
                    "tests_applied": list(belief.applied_tests)
                }

            # 3. In boundary ambiguity: if sigma exceeds target, execute next test
            if belief.sigma_soh > self.sigma_target and tests_run < len(self.test_sequence):
                test_to_run = self.test_sequence[tests_run]
                self.diag.execute_test(test_to_run, module, belief)
                tests_run += 1
            else:
                break

        # Final disposition after testing
        if belief.mu_soh >= self.soh_min and belief.mu_r0 <= self.r0_max:
            action = "OPERATE"
        elif self.allow_derating and belief.mu_soh >= (self.soh_min - 0.05) and belief.mu_r0 <= (self.r0_max * 1.35):
            action = "DERATE"
        else:
            action = "RETIRE"

        return action, {
            "policy": "C_Uncertainty_Threshold",
            "action": action,
            "diag_time_s": belief.total_diagnostic_time_s,
            "diag_energy_wh": belief.total_diagnostic_energy_wh,
            "diag_cost_inr": belief.total_test_cost_inr,
            "tests_applied": list(belief.applied_tests)
        }


class PolicyDRCVOI:
    """
    Policy D: Risk-Constrained Value-of-Information (RC-VOI).
    Full economic decision-theoretic framework: calculates expected operational
    utility gain vs exact testing costs (labor, electricity, degradation).
    """
    def __init__(
        self,
        diag: SecondShiftDiagnosticEngine,
        app_config: Dict[str, Any],
        use_hard_safety_barrier: Optional[bool] = None,
        alpha_safety: float = 0.01
    ):
        self.diag = diag
        self.app = dict(app_config)
        if use_hard_safety_barrier is not None:
            self.app["use_hard_safety_barrier"] = use_hard_safety_barrier
        if alpha_safety is not None:
            self.app["alpha_safety"] = alpha_safety
        self.engine = DecisionEngine(self.app, diag)

    def evaluate(self, module: BatteryModule, belief: ModuleBelief, max_tests: int = 3) -> Tuple[str, Dict[str, Any]]:
        last_dbg = {}
        while True:
            act, test_to_run, dbg = self.engine.select_action(belief, max_tests_allowed=max_tests)
            last_dbg = dbg
            if act == "TEST" and test_to_run is not None:
                self.diag.execute_test(test_to_run, module, belief)
            else:
                final_action = act
                break

        return final_action, {
            "policy": "D_RC_VOI",
            "action": final_action,
            "diag_time_s": belief.total_diagnostic_time_s,
            "diag_energy_wh": belief.total_diagnostic_energy_wh,
            "diag_cost_inr": belief.total_test_cost_inr,
            "tests_applied": list(belief.applied_tests),
            "op_utilities": last_dbg.get("op_utilities", {}),
            "best_evsi": last_dbg.get("best_evsi", 0.0),
            "best_cost": last_dbg.get("best_cost", 0.0),
            "best_voi": last_dbg.get("best_voi", 0.0)
        }

