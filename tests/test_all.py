"""
RMK-REVOLT Comprehensive Unit Tests
Validates battery model, triage rules, Bayesian belief updates,
VOI calculations, HERMES state transitions, and safety constraints.
"""

import pytest
import numpy as np
from models.battery_model import BatteryModule, lfp_ocv, lfp_docv_dsoc
from models.belief_state import ModuleBelief
from src.triage import TriageEngine
from src.secondshift import SecondShiftDiagnosticEngine
from src.decision_engine import DecisionEngine
from src.hermes import HermesController
from metrics.evaluator import MetricEvaluator

def test_lfp_ocv_characteristics():
    """Verify LFP flat plateau and steep knees."""
    v_0 = lfp_ocv(0.0)
    v_50 = lfp_ocv(0.5)
    v_100 = lfp_ocv(1.0)
    
    assert v_0 >= 2.45 and v_0 <= 2.55, "0% SOC OCV out of range"
    assert v_50 >= 3.25 and v_50 <= 3.32, "Plateau OCV out of expected flat range"
    assert v_100 >= 3.60 and v_100 <= 3.70, "100% SOC OCV out of range"
    assert lfp_docv_dsoc(0.50) < lfp_docv_dsoc(0.98), "Flat plateau must have lower derivative than upper knee"

def test_battery_module_step_and_thermal():
    """Verify discharge step causes voltage drop and Joule heating."""
    module = BatteryModule(
        module_id="TEST_MOD_01",
        nominal_capacity_ah=50.0,
        soh=0.90,
        initial_soc=0.80,
        ambient_temp_c=25.0
    )
    v_init = module.v_terminal
    t_init = module.temperature_c
    
    # Discharge at 1C (50A) for 10 seconds
    for _ in range(100):
        module.step(50.0, 0.1)
        
    assert module.v_terminal < v_init, "Discharge under load must reduce terminal voltage"
    assert module.temperature_c > t_init, "I^2*R Joule heating must increase module temperature"
    assert module.soc < 0.80, "Discharge must reduce SOC"

def test_triage_deterministic_safety_gates():
    """Verify hard deterministic safety cutoffs in Triage."""
    triage = TriageEngine()
    
    # 1. Normal safe module
    mod_good = BatteryModule("MOD_GOOD", initial_soc=0.60)
    b_good = ModuleBelief("MOD_GOOD")
    status, _ = triage.evaluate(mod_good, b_good, resting_duration_s=5.0)
    assert status == "ACCEPT", "Good module must pass triage"
    
    # 2. Overdischarged copper-dissolution cell (Voc < 2.0V)
    mod_dead = BatteryModule("MOD_DEAD", initial_soc=0.0)
    mod_dead.v_terminal = 1.85
    b_dead = ModuleBelief("MOD_DEAD")
    status_dead, _ = triage.evaluate(mod_dead, b_dead, resting_duration_s=5.0)
    assert status_dead == "REJECT", "Cell with Voc < 2.0V must be rejected"
    
    # 3. Pouch bulging
    status_bulge, _ = triage.evaluate(mod_good, b_good, visual_bulge=True)
    assert status_bulge == "REJECT", "Physical bulging must trigger hard rejection"

def test_bayesian_belief_update():
    """Verify conjugate Gaussian update reduces uncertainty variance."""
    belief = ModuleBelief("MOD_BAYES", prior_soh=0.75, prior_sigma_soh=0.15)
    init_sigma = belief.sigma_soh
    
    # Apply coulometric test measurement of 0.82 with 0.025 std error
    belief.update_from_coulometric_test(0.82, measurement_sigma_soh=0.025)
    
    assert belief.sigma_soh < init_sigma, "Bayesian update must shrink uncertainty"
    assert 0.78 < belief.mu_soh < 0.83, "Posterior mean must shift towards observation"

def test_decision_engine_voi():
    """Verify VOI calculation and decision selection."""
    diag = SecondShiftDiagnosticEngine()
    app_config = {
        "min_soh_threshold": 0.70,
        "max_acceptable_r0_mohm": 3.5,
        "max_allowable_uncertainty_sigma_soh": 0.05,
        "safety_penalty_inr": 100000.0,
        "energy_revenue_per_kwh_inr": 10.0,
        "runtime_hours": 2000.0
    }
    engine = DecisionEngine(app_config, diag)
    
    # High-uncertainty module near cutoff should trigger TEST
    uncertain_belief = ModuleBelief("MOD_UNCERTAIN", prior_soh=0.72, prior_sigma_soh=0.18)
    uncertain_belief.triage_status = "ACCEPT"
    
    action, test_name, debug = engine.select_action(uncertain_belief)
    assert action == "TEST", "High-uncertainty module near threshold should prioritize diagnostic testing"
    assert test_name in ["pulse_power_test", "short_coulometric_cycle"]

def test_hermes_state_transitions():
    """Verify HERMES state machine transitions and participation control."""
    hermes = HermesController("MOD_HERMES")
    assert hermes.current_state == "BYPASS"
    assert hermes.current_share_factor == 0.0
    
    hermes.command_transition("ACTIVE", "Cleared for full operation")
    assert hermes.current_state == "ACTIVE"
    assert hermes.current_share_factor == 1.0
    
    hermes.command_transition("DERATED", "High temperature warning")
    assert hermes.current_state == "DERATED"
    assert hermes.current_share_factor == 0.5
    
    # Once isolated, cannot transition back to active
    hermes.command_transition("ISOLATED", "Hardware OVP trip")
    allowed = hermes.command_transition("ACTIVE", "Attempted restart")
    assert not allowed, "Cannot transition out of ISOLATED without clearance"
    assert hermes.current_state == "ISOLATED"

def test_metric_evaluator():
    """Verify calculation of FAR, FRR, and Decision Efficiency."""
    evaluator = MetricEvaluator(soh_threshold=0.70, r0_max_mohm=3.5)
    records = [
        # Truly healthy, operated correctly
        {"module_id": "1", "true_soh": 0.85, "true_r0": 0.002, "true_leakage": False, "decision": "OPERATE",
         "diag_time_s": 60, "diag_energy_wh": 2, "diag_cost_inr": 20, "num_tests": 1, "final_mu_soh": 0.84, "final_sigma_soh": 0.03},
        # Truly degraded, retired correctly
        {"module_id": "2", "true_soh": 0.55, "true_r0": 0.005, "true_leakage": False, "decision": "RETIRE",
         "diag_time_s": 60, "diag_energy_wh": 2, "diag_cost_inr": 20, "num_tests": 1, "final_mu_soh": 0.56, "final_sigma_soh": 0.03},
        # Truly healthy, unnecessarily retired (False rejection)
        {"module_id": "3", "true_soh": 0.74, "true_r0": 0.0025, "true_leakage": False, "decision": "RETIRE",
         "diag_time_s": 20, "diag_energy_wh": 1, "diag_cost_inr": 10, "num_tests": 1, "final_mu_soh": 0.68, "final_sigma_soh": 0.08},
    ]
    summary = evaluator.evaluate_cohort(records)
    assert summary["far_percent"] == 0.0, "No degraded module was accepted"
    assert summary["frr_percent"] == 50.0, "1 out of 2 healthy modules falsely rejected"
    assert summary["decision_efficiency"] > 0.0, "Decision efficiency should be positive"
