"""
Comprehensive Unit & Integration Test Suite for SECONDShift Platform
"""

import pytest
import numpy as np

from secondshift.software.triage.triage_gate import TriageGate
from secondshift.software.chemistry.chemistry_engine import ChemistryDisambiguationEngine
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.estimators.model_uncertainty import ModelUncertaintyEvaluator
from secondshift.software.safety.hard_safety_barrier import HardSafetyBarrier
from secondshift.software.secondshift.decision_engine import SECONDShiftDecisionEngine
from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.secondshift.metrics_calculator import MetricsCalculator

def test_triage_gate_mechanical_and_electrical():
    triage = TriageGate()
    # Test bulging case
    status, reason = triage.evaluate(3.29, 25.0, 25.0, visual_bulge=True)
    assert status == "REJECT"
    assert "TR-01" in reason

    # Test under-voltage
    status, reason = triage.evaluate(1.85, 25.0, 25.0)
    assert status == "REJECT"
    assert "TR-03" in reason

    # Test normal condition
    status, reason = triage.evaluate(3.29, 25.0, 25.0, leakage_rate_mv_hr=1.2)
    assert status == "ACCEPT"

def test_chemistry_disambiguation():
    chem_engine = ChemistryDisambiguationEngine()
    prior = chem_engine.initialize_prior("UNKNOWN")
    assert prior["LFP"] == pytest.approx(0.333, abs=0.01)

    # High rest voltage indicates NMC
    post = chem_engine.update_from_passive_rest(3.75, prior)
    assert post["NMC"] > 0.90
    conf_state, best_chem, _ = chem_engine.get_confidence_state(post)
    assert best_chem == "NMC"

    # LFP plateau update with flat slope
    post_lfp = chem_engine.update_from_pulse_slope(0.012, 10.0, 15.0, {"LFP": 0.5, "NMC": 0.45, "UNKNOWN": 0.05})
    assert post_lfp["LFP"] > 0.95

def test_bayesian_variance_shrinkage():
    est = BayesianStateEstimator("test_cell", prior_mu_soh=0.75, prior_sigma_soh=0.15)
    prior_sig = est.sigma_soh
    # Apply measurement
    est.update_soh_from_coulometric_observation(0.72, observation_noise_sigma=0.025)
    assert est.sigma_soh < prior_sig
    assert est.sigma_soh == pytest.approx(0.0246, abs=0.005)

def test_hard_safety_barrier_decoupling():
    barrier = HardSafetyBarrier(alpha_safety=0.01)
    # Scenario: High risk (P_fail = 20%)
    risk_op = {"p_fail_marginal": 0.20}
    risk_der = {"p_fail_marginal": 0.15}
    adm = barrier.filter_admissible_actions(risk_op, risk_der, "KNOWN", "ACCEPT")
    assert "OPERATE" not in adm
    assert "DERATE" not in adm

    # Even with huge utility, barrier assigns -1e8
    raw_u = {"OPERATE": 100000.0, "DERATE": 50000.0, "RETIRE": 26.8}
    filt_u = barrier.apply_barrier_to_utilities(raw_u, adm)
    assert filt_u["OPERATE"] == -1e8
    assert filt_u["RETIRE"] == 26.8

def test_independent_hardware_safety_trip():
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.94], cell_r0_mohm=[1.9])
    assert hw.relay_enabled == True
    assert hw.hardware_tripped == False

    # Inject UVP fault
    hw.inject_fault("UVP", cell_idx=0)
    sensors = hw.read_sensors()
    assert sensors["hardware_tripped"] == True
    assert sensors["relay_enabled"] == False
    assert "LM393_UVP_TRIP" in sensors["trip_reason"]

def test_erds_metric_calculation():
    erds = MetricsCalculator.calculate_erds(
        retained_kwh_policy=11.3,
        retained_kwh_baseline=5.9,
        diag_time_s_policy=180.0,
        diag_time_s_baseline=80.0
    )
    # (11.3 - 5.9)*1000 / (180 - 80) = 5400 / 100 = 54.0 Wh/s
    assert erds == pytest.approx(54.0, abs=0.1)
