"""
RMK-REVOLT Baseline Implementations
- Baseline A: Fixed Diagnostic Sequence (Standard industrial qualification)
- Baseline B: Health/SOH Threshold-Based (Uncertainty-blind BMS logic)
- Baseline D: Static Application-Aware (Application thresholds, non-adaptive testing)
"""

from typing import Dict, Any, Tuple
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.secondshift import SecondShiftDiagnosticEngine

class BaselineAFixedTesting:
    """
    Baseline A: Fixed Comprehensive Diagnostic Protocol.
    Standard laboratory qualification: executes a fixed rigid battery test sequence:
    1. Pulse power test (1C pulse)
    2. Short coulometric cycling step (direct capacity check)
    3. Thermal step
    Decision is based purely on the final measured values without adaptive stopping.
    """
    def __init__(self, diagnostic_engine: SecondShiftDiagnosticEngine, soh_cutoff: float = 0.70, r0_max_mohm: float = 3.5):
        self.diag = diagnostic_engine
        self.soh_cutoff = soh_cutoff
        self.r0_max = r0_max_mohm / 1000.0

    def evaluate(self, module: BatteryModule, belief: ModuleBelief) -> Tuple[str, Dict[str, Any]]:
        # Fixed execution of all diagnostic tests sequentially
        self.diag.execute_test("pulse_power_test", module, belief)
        self.diag.execute_test("short_coulometric_cycle", module, belief)
        self.diag.execute_test("thermal_recovery_step", module, belief)

        # Rigid threshold decision
        if belief.mu_soh >= self.soh_cutoff and belief.mu_r0 <= self.r0_max:
            action = "OPERATE"
        else:
            action = "RETIRE"

        return action, {
            "strategy": "Baseline A (Fixed Testing)",
            "tests_applied": list(belief.applied_tests),
            "total_diag_time_s": belief.total_diagnostic_time_s,
            "total_diag_energy_wh": belief.total_diagnostic_energy_wh,
            "final_soh_est": belief.mu_soh,
            "final_r0_mohm": belief.mu_r0 * 1000.0,
            "action": action
        }


class BaselineBSOHThreshold:
    """
    Baseline B: Conventional Threshold-Based Policy.
    Uncertainty-blind: estimates SOH with a single rapid test and applies a hard cutoff.
    Does NOT quantify uncertainty and does NOT consider Value of Information.
    """
    def __init__(self, diagnostic_engine: SecondShiftDiagnosticEngine, soh_cutoff: float = 0.75):
        self.diag = diagnostic_engine
        self.soh_cutoff = soh_cutoff

    def evaluate(self, module: BatteryModule, belief: ModuleBelief) -> Tuple[str, Dict[str, Any]]:
        # Single rapid test only
        self.diag.execute_test("pulse_power_test", module, belief)
        
        # Uncertainty-blind decision rule: if mu_soh >= cutoff -> OPERATE, else RETIRE
        if belief.mu_soh >= self.soh_cutoff:
            action = "OPERATE"
        else:
            action = "RETIRE"

        return action, {
            "strategy": "Baseline B (SOH Threshold Only)",
            "tests_applied": list(belief.applied_tests),
            "total_diag_time_s": belief.total_diagnostic_time_s,
            "total_diag_energy_wh": belief.total_diagnostic_energy_wh,
            "final_soh_est": belief.mu_soh,
            "sigma_ignored": belief.sigma_soh,
            "action": action
        }


class BaselineDStaticApplication:
    """
    Baseline D: Static Application-Aware Strategy.
    Tuned to application cutoff (e.g. 0.70 for Solar), but strictly non-adaptive.
    Always executes two predefined tests and does not support DERATE or in-situ feedback.
    """
    def __init__(self, diagnostic_engine: SecondShiftDiagnosticEngine, min_soh: float = 0.70):
        self.diag = diagnostic_engine
        self.min_soh = min_soh

    def evaluate(self, module: BatteryModule, belief: ModuleBelief) -> Tuple[str, Dict[str, Any]]:
        self.diag.execute_test("pulse_power_test", module, belief)
        self.diag.execute_test("short_coulometric_cycle", module, belief)

        if belief.mu_soh >= self.min_soh:
            action = "OPERATE"
        else:
            action = "RETIRE"

        return action, {
            "strategy": "Baseline D (Static Application)",
            "tests_applied": list(belief.applied_tests),
            "total_diag_time_s": belief.total_diagnostic_time_s,
            "total_diag_energy_wh": belief.total_diagnostic_energy_wh,
            "action": action
        }
