"""
RMK-REVOLT H.E.R.M.E.S. State Machine
Uncertainty-Aware Module Participation Control.
Manages topological participation (ACTIVE, DERATED, BYPASS, ISOLATED)
based on diagnostic confidence, thermal safety, and operational feedback.
"""

from typing import Dict, Any, Tuple
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief

class HermesController:
    """
    Module Participation Controller.
    States:
    - ACTIVE: Full current string participation (1.0x load)
    - DERATED: Safe reduced current participation (0.5x load via PWM / current sharing)
    - BYPASS: Zero module current; string current shunted through bypass switch
    - ISOLATED: Disconnected completely from string due to critical safety trip
    """
    VALID_STATES = {"ACTIVE", "DERATED", "BYPASS", "ISOLATED"}

    def __init__(self, module_id: str):
        self.module_id = module_id
        self.current_state = "BYPASS"  # Default safe startup state
        self.state_history = [("INIT", "BYPASS", 0.0)]
        self.current_share_factor = 0.0

    def command_transition(
        self,
        target_state: str,
        reason: str,
        timestamp_s: float = 0.0
    ) -> bool:
        """
        Execute state transition. Hard safety checks cannot be bypassed.
        """
        if target_state not in self.VALID_STATES:
            raise ValueError(f"Invalid HERMES state: {target_state}")

        # Once isolated due to hard safety, cannot automatically transition out
        if self.current_state == "ISOLATED" and target_state != "ISOLATED":
            return False

        old_state = self.current_state
        self.current_state = target_state
        
        if target_state == "ACTIVE":
            self.current_share_factor = 1.0
        elif target_state == "DERATED":
            self.current_share_factor = 0.5
        elif target_state in {"BYPASS", "ISOLATED"}:
            self.current_share_factor = 0.0

        self.state_history.append((old_state, target_state, timestamp_s, reason))
        return True

    def step_operational_feedback(
        self,
        module: BatteryModule,
        belief: ModuleBelief,
        string_current_a: float,
        dt_s: float
    ) -> Dict[str, Any]:
        """
        Simulate operational physics under current participation state
        and perform in-situ feedback observation (Experiment 5).
        """
        module_current = string_current_a * self.current_share_factor
        v_term, i_eff, temp = module.step(module_current, dt_s)
        meas = module.measure(module_current)

        # In-situ observation: if current is flowing, estimate dynamic impedance
        observed_r0 = None
        if abs(module_current) > 2.0:
            # Dynamic delta V / I against estimated OCV
            ocv_approx = belief.mu_soc * 0.128 + 3.24
            observed_r0 = max(0.0005, abs(ocv_approx - meas["v_meas"]) / abs(meas["i_meas"]))
            belief.update_from_operational_observation(observed_r0, dt_s, module_current)

        # Hard safety monitor in controller
        if meas["t_meas"] >= 58.0 or meas["v_meas"] <= 2.20 or meas["v_meas"] >= 3.70:
            self.command_transition("ISOLATED", "Hard safety limit violation during operation", module.total_test_time_s)

        return {
            "module_id": self.module_id,
            "state": self.current_state,
            "current_a": module_current,
            "v_terminal": v_term,
            "temp_c": temp,
            "observed_r0_mohm": (observed_r0 * 1000.0) if observed_r0 else None,
            "updated_sigma_soh": belief.sigma_soh
        }
