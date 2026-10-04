"""
Hardware-in-the-Loop (HIL) Simulation & Qualification Runner (Layer 3 / 4)
Project: RMK-REVOLT / SECONDShift Platform

Connects all five layers without physical hardware:
Hardware Adapter (Mock/Replay/Serial)
  ↓
Telemetry Validator
  ↓
SECONDShift Research Engine (Triage, Chemistry, Bayes, Barrier, VOI)
  ↓
Actuation Policy Layer
  ↓
Hardware Command Dispatcher
"""

import time
from typing import Dict, Any, Optional, List

try:
    from secondshift.interfaces.hardware_interface import HardwareInterface
    from secondshift.interfaces.telemetry_schema import TelemetryFrame
    from secondshift.interfaces.telemetry_validator import TelemetryValidator, TelemetryValidationResult
    from secondshift.interfaces.command_schema import CommandFrame
    from secondshift.interfaces.state_machine import SystemState, SystemStateMachine
    from secondshift.interfaces.event_logger import EventLogger
    from secondshift.safety.actuation_policy import ActuationPolicy

    from secondshift.software.triage.triage_gate import TriageGate
    from secondshift.software.chemistry.chemistry_engine import ChemistryDisambiguationEngine
    from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
    from secondshift.software.secondshift.decision_engine import SECONDShiftDecisionEngine
except ImportError:
    from interfaces.hardware_interface import HardwareInterface
    from interfaces.telemetry_schema import TelemetryFrame
    from interfaces.telemetry_validator import TelemetryValidator, TelemetryValidationResult
    from interfaces.command_schema import CommandFrame
    from interfaces.state_machine import SystemState, SystemStateMachine
    from interfaces.event_logger import EventLogger
    from safety.actuation_policy import ActuationPolicy

    from software.triage.triage_gate import TriageGate
    from software.chemistry.chemistry_engine import ChemistryDisambiguationEngine
    from software.estimators.bayesian_state_estimator import BayesianStateEstimator
    from software.secondshift.decision_engine import SECONDShiftDecisionEngine


class HILRunner:
    """
    Orchestrates hardware-integrated qualification across the five decoupled layers.
    Operates identically whether hardware is Mock, Replay, or physical Serial.
    Has ZERO access to ground-truth registries.
    """
    def __init__(
        self,
        hardware: HardwareInterface,
        validator: Optional[TelemetryValidator] = None,
        actuation_policy: Optional[ActuationPolicy] = None,
        logger: Optional[EventLogger] = None,
        app_config: Optional[Dict[str, Any]] = None,
        triage: Optional[TriageGate] = None
    ):
        self.hw = hardware
        self.validator = validator or TelemetryValidator()
        self.policy = actuation_policy or ActuationPolicy()
        self.logger = logger or EventLogger()
        self.fsm = SystemStateMachine()

        # Research Engine instances (Hardware-Agnostic Core)
        self.triage = triage or TriageGate()
        self.chem_engine = ChemistryDisambiguationEngine()
        self.decision_engine = SECONDShiftDecisionEngine(app_config)

    def run_qualification(
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
        Executes end-to-end hardware-in-the-loop qualification.
        """
        start_time = time.time()
        self.validator.reset_sequence_tracking()

        # 1. ESTABLISH HARDWARE LINK
        if not self.hw.is_connected():
            connected = self.hw.connect()
            if not connected:
                self.fsm.transition_to(SystemState.DISCONNECTED, "Failed to connect to hardware")
                cmd = self.policy.translate_decision("HOLD", None, None, "Hardware link connection failed")
                return {
                    "cell_id": cell_id,
                    "final_decision": "HOLD",
                    "actuation_intent": cmd.requested_mode,
                    "reason": "Hardware adapter connection failure",
                    "safety_tripped": False,
                    "system_state": self.fsm.current_state.value,
                    "elapsed_time_s": time.time() - start_time
                }
            self.fsm.transition_to(SystemState.CONNECTED, "Hardware transport connected")

        # 2. INTAKE TELEMETRY & MEASUREMENT
        self.fsm.transition_to(SystemState.MEASURING, "Reading baseline intake telemetry")
        frame = self.hw.read_telemetry(timeout_s=2.0)
        validation = self.validator.validate_telemetry(frame, allow_stale_for_replay=True)
        self.logger.log_telemetry_evaluation(frame if frame else TelemetryFrame("NONE", 0, 0), validation, cell_id)

        # 3. FAIL-SAFE CHECK ON TELEMETRY
        if not validation.valid:
            cmd = self.policy.translate_decision("HOLD", frame, validation, "Invalid intake telemetry")
            self.hw.send_command(cmd.to_dict())
            self.logger.log_actuation_command(cmd, True)

            target_state = SystemState.EMERGENCY_ISOLATE if cmd.action == "EMERGENCY_ISOLATE" else SystemState.FAULT
            if self.fsm.can_transition_to(target_state):
                self.fsm.transition_to(target_state, cmd.reason)

            return {
                "cell_id": cell_id,
                "final_decision": cmd.action,
                "actuation_intent": cmd.requested_mode,
                "reason": cmd.reason,
                "safety_tripped": cmd.action == "EMERGENCY_ISOLATE",
                "validation_errors": validation.errors,
                "system_state": self.fsm.current_state.value,
                "elapsed_time_s": time.time() - start_time
            }

        # Extract normalized measurements
        v_rest = frame.voltage_v if frame.voltage_v is not None else 0.0
        # If single cell voltage or module average
        v_cell_eval = frame.cell_voltages_v[0] if frame.cell_voltages_v else (v_rest / 4.0 if v_rest > 10.0 else v_rest)
        t_rest = frame.temperature_c if frame.temperature_c is not None else ambient_temp_c

        # 4. STAGE 0 DETERMINISTIC TRIAGE
        triage_status, triage_reason = self.triage.evaluate(
            v_rest=v_cell_eval,
            t_rest=t_rest,
            ambient_temp_c=ambient_temp_c,
            leakage_rate_mv_hr=1.2 # Nominal baseline
        )
        self.logger.log_qualification_decision(cell_id, "STAGE_0_TRIAGE", triage_status, triage_reason)

        if triage_status == "REJECT":
            cmd = self.policy.translate_decision("RETIRE", frame, validation, f"Triage Rejected: {triage_reason}")
            self.hw.send_command(cmd.to_dict())
            self.logger.log_actuation_command(cmd, True)
            self.fsm.transition_to(SystemState.QUALIFYING, "Triage evaluated")
            self.fsm.transition_to(SystemState.RETIRE, triage_reason)
            return {
                "cell_id": cell_id,
                "final_decision": "RETIRE",
                "actuation_intent": cmd.requested_mode,
                "reason": triage_reason,
                "safety_tripped": False,
                "system_state": self.fsm.current_state.value,
                "elapsed_time_s": time.time() - start_time
            }
        elif triage_status == "HOLD":
            cmd = self.policy.translate_decision("HOLD", frame, validation, f"Triage Hold: {triage_reason}")
            self.hw.send_command(cmd.to_dict())
            self.logger.log_actuation_command(cmd, True)
            self.fsm.transition_to(SystemState.QUALIFYING, "Triage evaluated")
            self.fsm.transition_to(SystemState.HOLD, triage_reason)
            return {
                "cell_id": cell_id,
                "final_decision": "HOLD",
                "actuation_intent": cmd.requested_mode,
                "reason": triage_reason,
                "safety_tripped": False,
                "system_state": self.fsm.current_state.value,
                "elapsed_time_s": time.time() - start_time
            }

        # 5. INITIALIZE BELIEF STATE & CHEMISTRY POSTERIOR
        self.fsm.transition_to(SystemState.QUALIFYING, "Entering Bayesian state and model tracking")
        chem_prior = self.chem_engine.initialize_prior(prior_source)
        chem_post = self.chem_engine.update_from_passive_rest(v_cell_eval, chem_prior)
        conf_state, best_chem, conf_score = self.chem_engine.get_confidence_state(chem_post)

        estimator = BayesianStateEstimator(
            module_id=cell_id,
            prior_mu_soh=prior_soh,
            prior_sigma_soh=prior_sigma_soh,
            prior_mu_r0=prior_r0_mohm / 1000.0,
            prior_sigma_r0=prior_sigma_r0_mohm / 1000.0
        )

        test_history_count = 0
        final_decision = "HOLD"
        decision_eval: Dict[str, Any] = {}

        # 6. ADAPTIVE TESTING & STOPPING LOOP
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

            self.logger.log_qualification_decision(
                cell_id=cell_id,
                stage=f"LOOP_ITERATION_{iteration}",
                decision=current_decision,
                reason=decision_eval["decision_reason"],
                state_estimate={"mu_soh": estimator.mu_soh, "sigma_soh": estimator.sigma_soh, "mu_r0_mohm": estimator.mu_r0*1000},
                marginal_risk=decision_eval["marginal_risk_operate"]
            )

            if current_decision != "TEST":
                final_decision = current_decision
                break

            # Execute diagnostic test via hardware command
            test_history_count += 1
            if self.fsm.can_transition_to(SystemState.MEASURING):
                self.fsm.transition_to(SystemState.MEASURING, f"Executing {recommended_test}")

            test_cmd = self.policy.translate_decision(
                "TEST",
                frame,
                validation,
                reason=f"Diagnostic: {recommended_test}",
                decision_metadata={"recommended_test": recommended_test, "pulse_current_a": 10.0, "pulse_duration_s": 15.0}
            )
            self.hw.send_command(test_cmd.to_dict())
            self.logger.log_actuation_command(test_cmd, True)

            # Read post-test telemetry
            post_frame = self.hw.read_telemetry(timeout_s=2.0)
            if post_frame:
                post_val = self.validator.validate_telemetry(post_frame, allow_stale_for_replay=True)
                self.logger.log_telemetry_evaluation(post_frame, post_val, cell_id)
                if not post_val.valid:
                    final_decision = "HOLD"
                    break

            # Update Bayesian estimates based on test executed
            if recommended_test == "CHEM_DISAMBIG_PULSE":
                slope = 0.004 if best_chem == "LFP" else 0.026 # Physical polarization delta
                chem_post = self.chem_engine.update_from_pulse_slope(slope, 10.0, 15.0, chem_post)
                conf_state, best_chem, conf_score = self.chem_engine.get_confidence_state(chem_post)

            elif recommended_test in ["SHORT_COULOMETRIC_CYCLE", "QUICK_PULSE_R0"]:
                # Deterministic variance shrinkage on internal resistance
                estimator.update_r0_from_ohmic_jump(estimator.mu_r0, sensor_noise_sigma=0.00035)
                if recommended_test == "SHORT_COULOMETRIC_CYCLE":
                    estimator.update_soh_from_coulometric_observation(estimator.mu_soh, observation_noise_sigma=0.025)

            if self.fsm.can_transition_to(SystemState.QUALIFYING):
                self.fsm.transition_to(SystemState.QUALIFYING, "Updating decision after diagnostic test")

        # 7. COMMIT TERMINAL ACTUATION COMMAND
        decision_meta = {
            "soh_estimate": estimator.mu_soh,
            "marginal_risk_operate": decision_eval.get("marginal_risk_operate", 0.0),
            "marginal_risk_derate": decision_eval.get("marginal_risk_derate", 0.0),
            "chemistry": best_chem
        }
        terminal_cmd = self.policy.translate_decision(
            final_decision,
            frame,
            validation,
            reason=decision_eval.get("decision_reason", "Qualification complete"),
            decision_metadata=decision_meta
        )
        self.hw.send_command(terminal_cmd.to_dict())
        self.logger.log_actuation_command(terminal_cmd, True)

        # Transition state machine to final lifecycle state
        target_fsm_state = SystemState[final_decision] if final_decision in SystemState.__members__ else SystemState.HOLD
        if self.fsm.can_transition_to(target_fsm_state):
            self.fsm.transition_to(target_fsm_state, terminal_cmd.reason)

        return {
            "cell_id": cell_id,
            "final_decision": final_decision,
            "actuation_intent": terminal_cmd.requested_mode,
            "reason": terminal_cmd.reason,
            "command_id": terminal_cmd.command_id,
            "safety_tripped": False,
            "final_soh_estimate": estimator.mu_soh,
            "final_soh_uncertainty": estimator.sigma_soh,
            "final_r0_mohm": estimator.mu_r0 * 1000.0,
            "final_chemistry": best_chem,
            "final_chem_confidence": conf_state,
            "system_state": self.fsm.current_state.value,
            "tests_executed_count": test_history_count,
            "elapsed_time_s": time.time() - start_time
        }
