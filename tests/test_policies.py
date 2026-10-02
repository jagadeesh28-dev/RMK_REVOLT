"""
Unit tests for the Four Qualification Policies (A, B, C, D) and Statistical Calculator.
"""

import pytest
import numpy as np
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.secondshift import SecondShiftDiagnosticEngine
from src.policies import (
    PolicyAFixedQualification,
    PolicyBScalarThreshold,
    PolicyCUncertaintyThreshold,
    PolicyDRCVOI
)
from metrics.stats_calculator import bootstrap_ci, cohens_d, compute_distribution_metrics

@pytest.fixture
def test_setup():
    diag = SecondShiftDiagnosticEngine()
    app = {
        "min_soh_threshold": 0.70,
        "max_acceptable_r0_mohm": 3.5,
        "max_allowable_uncertainty_sigma_soh": 0.04,
        "safety_penalty_inr": 6000.0,
        "energy_revenue_per_kwh_inr": 10.0,
        "lifetime_cycles": 1200.0
    }
    return diag, app

def test_policy_a_runs_all_tests(test_setup):
    diag, app = test_setup
    policy_a = PolicyAFixedQualification(diag, app)
    mod = BatteryModule("M_A", soh=0.85)
    belief = ModuleBelief("M_A", prior_soh=0.85)
    action, info = policy_a.evaluate(mod, belief)
    assert len(info["tests_applied"]) == 3
    assert info["diag_time_s"] == 800.0
    assert action == "OPERATE"

def test_policy_b_zero_test_time(test_setup):
    diag, app = test_setup
    policy_b = PolicyBScalarThreshold(diag, app)
    mod = BatteryModule("M_B", soh=0.85)
    belief = ModuleBelief("M_B", prior_soh=0.85)
    action, info = policy_b.evaluate(mod, belief)
    assert info["diag_time_s"] == 0.0
    assert action == "OPERATE"

def test_policy_c_adaptive_threshold(test_setup):
    diag, app = test_setup
    policy_c = PolicyCUncertaintyThreshold(diag, app, sigma_target=0.04)
    # High confidence healthy: should not test
    mod_high = BatteryModule("M_C1", soh=0.90)
    b_high = ModuleBelief("M_C1", prior_soh=0.90, prior_sigma_soh=0.02)
    act_high, info_high = policy_c.evaluate(mod_high, b_high)
    assert act_high == "OPERATE"
    assert info_high["diag_time_s"] == 0.0
    
    # Boundary uncertain: should trigger test
    mod_unc = BatteryModule("M_C2", soh=0.72)
    b_unc = ModuleBelief("M_C2", prior_soh=0.72, prior_sigma_soh=0.08)
    act_unc, info_unc = policy_c.evaluate(mod_unc, b_unc)
    assert info_unc["diag_time_s"] > 0.0

def test_policy_d_rc_voi(test_setup):
    diag, app = test_setup
    policy_d = PolicyDRCVOI(diag, app)
    mod = BatteryModule("M_D", soh=0.85)
    belief = ModuleBelief("M_D", prior_soh=0.85, prior_sigma_soh=0.02)
    belief.triage_status = "ACCEPT"
    action, info = policy_d.evaluate(mod, belief)
    assert action in ["OPERATE", "DERATE"]

def test_stats_calculator():
    d1 = np.array([10.0, 11.0, 12.0, 10.5, 11.5])
    d2 = np.array([20.0, 21.0, 22.0, 20.5, 21.5])
    metrics = compute_distribution_metrics(list(d1))
    assert metrics["mean"] == 11.0
    assert metrics["median"] == 11.0
    assert metrics["ci_95_low"] <= 11.0 <= metrics["ci_95_high"]
    d = cohens_d(d1, d2)
    assert d < -10.0  # Large negative effect size
