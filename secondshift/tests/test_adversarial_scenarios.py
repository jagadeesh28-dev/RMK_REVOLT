"""
Adversarial Validation & Property Invariant Test Suite (Layer 3 & 4)
Project: RMK-REVOLT / SECONDShift Platform

Tests Scenarios A through H and the mathematical Monotonic Conservatism Invariance Axiom:
  d P(Conservative Action) / d sigma >= 0
Reuses the existing simulation and HIL hardware stack without duplicating logic.
"""

import math
import time
import pytest
import numpy as np

from secondshift.hardware.mock_hardware import MockHardware
from secondshift.hardware.hil_runner import HILRunner
from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner
from secondshift.software.secondshift.decision_engine import SECONDShiftDecisionEngine
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.triage.triage_gate import TriageGate


def test_scenario_a_chemistry_mismatch():
    """
    Scenario A: Chemistry Mismatch.
    True NMC presented under diffuse/unknown prior.
    System must forbid direct OPERATE and transition to HOLD or RETIRE.
    """
    hw = MockHermesHardware(cell_chemistries=["NMC"], cell_soh=[0.85], cell_r0_mohm=[2.5])
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    res = runner.run_qualification_pipeline(
        cell_id="ADV_SCENARIO_A",
        prior_source="UNKNOWN"
    )

    assert res["final_decision"] != "OPERATE", "Adversarial NMC under diffuse prior must NEVER directly OPERATE"
    assert res["final_decision"] in ["HOLD", "RETIRE", "TEST"]


def test_scenario_b_wrong_chemistry_label():
    """
    Scenario B: Wrong Chemistry Label (Counterfeit Sticker).
    True NMC bearing fraudulent LFP fleet label.
    System must distinguish physical dynamics and forbid OPERATE.
    """
    hw = MockHermesHardware(cell_chemistries=["NMC"], cell_soh=[0.90], cell_r0_mohm=[2.0])
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    res = runner.run_qualification_pipeline(
        cell_id="ADV_SCENARIO_B",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.90,
        prior_sigma_soh=0.02,
        prior_r0_mohm=2.0,
        prior_sigma_r0_mohm=0.2
    )

    assert res["final_decision"] != "OPERATE", "Fraudulent LFP label on true NMC must NOT qualify for OPERATE"


def test_scenario_c_overconfident_prior_degraded_cell():
    """
    Scenario C: Degraded Cell under Overconfident Prior.
    True SOH=45% with an adversarial prior claiming 65% +/- 0.01.
    Testing / triage must detect physical degradation and RETIRE / HOLD.
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.45], cell_r0_mohm=[85.0])
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    res = runner.run_qualification_pipeline(
        cell_id="ADV_SCENARIO_C",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.65,
        prior_sigma_soh=0.01,
        prior_r0_mohm=3.0,
        prior_sigma_r0_mohm=0.1
    )

    assert res["final_decision"] in ["RETIRE", "HOLD"], "Severely degraded cell under biased prior must be RETIRED or HELD"
    assert res["final_decision"] != "OPERATE"


def test_scenario_d_high_prior_uncertainty():
    """
    Scenario D: High Prior Uncertainty.
    Healthy cell presented with high uncertainty (sigma=0.25).
    System must forbid direct unconstrained OPERATE without testing.
    """
    engine = SECONDShiftDecisionEngine()
    estimator = BayesianStateEstimator(
        module_id="ADV_SCENARIO_D",
        nominal_capacity_ah=50.0,
        prior_mu_soh=0.88,
        prior_sigma_soh=0.25,
        prior_mu_r0=0.002,
        prior_sigma_r0=0.0005
    )
    chem_posterior = {"LFP": 0.999, "NMC": 0.001, "UNKNOWN": 0.0}

    # Evaluate risk under high uncertainty
    risk_op = engine.model_evaluator.compute_marginal_failure_risk(estimator, chem_posterior, "OPERATE")
    # Tail risk P(SOH < 0.70) under mu=0.88, sigma=0.25 is norm.cdf((0.70 - 0.88)/0.25) ~ 23.5% >> 1%
    assert risk_op["p_fail_marginal"] > 0.01, "Diffuse prior must reflect elevated tail failure risk"
    # Hard barrier must reject direct operation
    # Hard barrier must reject direct operation
    risk_derate = engine.model_evaluator.compute_marginal_failure_risk(
        estimator, chem_posterior, "DERATE"
    )

    admissible_actions = engine.barrier.filter_admissible_actions(
        risk_evaluation_operate=risk_op,
        risk_evaluation_derate=risk_derate,
        chemistry_confidence_state="KNOWN",
        triage_status="ACCEPT"
    )

    assert "OPERATE" not in admissible_actions


def test_scenario_e_sensor_noise_amplification():
    """
    Scenario E: Sensor Noise Amplification.
    Elevated measurement noise increases posterior variance without false acceptance.
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.85], cell_r0_mohm=[2.2])
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    res = runner.run_qualification_pipeline(
        cell_id="ADV_SCENARIO_E",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.85,
        prior_sigma_soh=0.10,
        prior_r0_mohm=2.2,
        prior_sigma_r0_mohm=1.0
    )

    # Invariant: Must reach a safe, bounded decision with verified safety check
    assert res["final_decision"] in ["OPERATE", "DERATE", "HOLD", "TEST"]
    if res["final_decision"] == "OPERATE":
        decision_traces = [
            t for t in res["trace"]
            if t.get("stage") == "DECISION_EVALUATION"
        ]
        assert decision_traces
        assert decision_traces[-1]["marginal_risk_operate"] <= 0.01, \
            "Safety barrier alpha=1% must hold even with high noise"

def test_scenario_f_telemetry_dropout():
    """
    Scenario F: Sensor Telemetry Dropout.
    Communication loss or packet drop during intake immediately triggers Fail-Safe HOLD.
    """
    hw = MockHardware(chemistry="LFP", soh=0.92)
    hw.set_fault_mode("COMM_DROPOUT")
    runner = HILRunner(hw)

    res = runner.run_qualification(cell_id="ADV_SCENARIO_F")

    assert res["final_decision"] == "HOLD"
    assert res["actuation_intent"] in ["KEEP_ISOLATED", "ISOLATE"]
    assert res["system_state"] in ["FAULT", "EMERGENCY_ISOLATE"]


def test_scenario_g_elevated_temperature():
    """
    Scenario G: Temperature Disturbance.
    Hot pack at 44°C ambient must restrict full load and enforce derating or hold.
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.78], cell_r0_mohm=[3.1])
    hw.ambient_temp = 44.0
    hw.temps = np.full(hw.n_cells, 44.0)
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    res = runner.run_qualification_pipeline(
        cell_id="ADV_SCENARIO_G",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.78,
        prior_sigma_soh=0.03,
        prior_r0_mohm=3.1,
        prior_sigma_r0_mohm=0.3,
        ambient_temp_c=44.0
    )

    # Thermal anomaly must prevent unconstrained OPERATE
    assert res["final_decision"] in ["DERATE", "HOLD", "RETIRE"]


def test_scenario_h_voltage_drift_microshort():
    """
    Scenario H: Voltage Drift / Internal Micro-short.
    Resting self-discharge drift (22 mV/hr) exceeds safe threshold (15 mV/hr)
    and must be intercepted immediately by Stage 0 Triage.
    """
    triage = TriageGate(max_leakage_mv_hr=15.0)

    # Healthy drift
    status_clean, _ = triage.evaluate(v_rest=3.30, t_rest=25.0, ambient_temp_c=25.0, leakage_rate_mv_hr=1.2)
    assert status_clean == "ACCEPT"

    # Micro-short leakage drift (22 mV/hr)
    status_short, reason_short = triage.evaluate(v_rest=3.30, t_rest=25.0, ambient_temp_c=25.0, leakage_rate_mv_hr=22.0)
    assert status_short == "REJECT"
    assert "TR-08" in reason_short or "Self-discharge" in reason_short


def test_property_monotonic_conservatism_under_uncertainty():
    """
    Property-Based Invariant: Monotonic Conservatism under Uncertainty.
      d P(fail) / d sigma >= 0
    As state uncertainty sigma_soh monotonically increases, marginal failure risk
    must monotonically increase, causing the system to become more conservative.
    """
    engine = SECONDShiftDecisionEngine()
    chem_posterior = {"LFP": 1.0, "NMC": 0.0, "UNKNOWN": 0.0}

    # Deterministic sweep across uncertainty values
    sigmas = np.linspace(0.01, 0.25, 25)
    mu_soh = 0.74  # Near threshold (0.70)
    risks = []

    for s in sigmas:
        estimator = BayesianStateEstimator(
            module_id=f"PROPERTY_{s:.3f}",
    	    nominal_capacity_ah=50.0,
    	    prior_mu_soh=mu_soh,
    	    prior_sigma_soh=float(s),
    	    prior_mu_r0=0.002,
    	    prior_sigma_r0=0.0002
  	)
        risk = engine.model_evaluator.compute_marginal_failure_risk(estimator, chem_posterior, "OPERATE")
        risks.append(risk["p_fail_marginal"])

    # Verify risk is strictly monotonically non-decreasing
    diffs = np.diff(risks)
    assert np.all(diffs >= -1e-9), f"Failure risk must monotonically increase with sigma: min diff={np.min(diffs)}"

    # When uncertainty is small (sigma=0.01), risk is below alpha (1%)
    assert risks[0] < 0.01
    # When uncertainty is large (sigma=0.25), risk violates alpha (1%)
    assert risks[-1] > 0.01
