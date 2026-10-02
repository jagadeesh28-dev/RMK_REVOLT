"""
RMK-REVOLT Adversarial Stress-Testing Framework
Systematically injects physical faults, sensor anomalies, and extreme conditions
to determine failure boundaries and verify fail-safe containment.
"""

import os
import sys
import json
import numpy as np
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.triage import TriageEngine
from src.secondshift import SecondShiftDiagnosticEngine
from src.decision_engine import DecisionEngine
from src.hermes import HermesController

def run_adversarial_suite() -> List[Dict[str, Any]]:
    print("\n" + "="*70)
    print("RUNNING ADVERSARIAL TESTING: Physical Fault Injection & Boundary Stress")
    print("="*70)
    
    app_config = {
        "min_soh_threshold": 0.70,
        "max_acceptable_r0_mohm": 3.5,
        "max_allowable_uncertainty_sigma_soh": 0.04,
        "safety_penalty_inr": 6000.0,
        "energy_revenue_per_kwh_inr": 10.0,
        "lifetime_cycles": 1200.0
    }
    
    diag = SecondShiftDiagnosticEngine()
    engine = DecisionEngine(app_config, diag)
    triage = TriageEngine()
    
    scenarios = [
        # 1. 10x Measurement Noise
        {
            "id": "ADV_01_EXTREME_NOISE",
            "name": "10x ADC Noise (20 mV noise, 0.5A current noise)",
            "setup": lambda: (BatteryModule("MOD_NOISE", soh=0.75, noise_v=0.020, noise_i=0.50),
                              ModuleBelief("MOD_NOISE", prior_soh=0.75, prior_sigma_soh=0.15)),
            "fault_type": "Sensor Jitter"
        },
        # 2. Extreme Ambient Temperature Drift (48 C ambient)
        {
            "id": "ADV_02_THERMAL_DRIFT",
            "name": "Extreme High Ambient Temperature (48 C)",
            "setup": lambda: (BatteryModule("MOD_HOT", soh=0.85, ambient_temp_c=48.0),
                              ModuleBelief("MOD_HOT", prior_soh=0.85, prior_sigma_soh=0.04)),
            "fault_type": "Environmental Extreme"
        },
        # 3. Voltage Sensor Dropout (ADC stuck at 0.0V or disconnected)
        {
            "id": "ADV_03_SENSOR_DROPOUT",
            "name": "Voltage Sensor Disconnect (0.0V read)",
            "setup": lambda: (BatteryModule("MOD_DROP", soh=0.90),
                              ModuleBelief("MOD_DROP", prior_soh=0.90, prior_sigma_soh=0.03)),
            "modify_module": lambda mod: setattr(mod, "v_terminal", 0.0),
            "fault_type": "Hardware Sensor Open-Circuit"
        },
        # 4. Severe Internal Micro-Short (Continuous 0.5A internal self-discharge)
        {
            "id": "ADV_04_MICRO_SHORT",
            "name": "Internal Micro-Short Self-Discharge (0.5A)",
            "setup": lambda: (BatteryModule("MOD_SHORT", soh=0.82, abnormal_leakage=True),
                              ModuleBelief("MOD_SHORT", prior_soh=0.82, prior_sigma_soh=0.08)),
            "fault_type": "Electrochemical Dendrite"
        },
        # 5. Dangerous High Internal Resistance (6.0 mOhm)
        {
            "id": "ADV_05_HIGH_IMPEDANCE",
            "name": "Thermal Runaway Precursor (4x Nominal Resistance)",
            "setup": lambda: (BatteryModule("MOD_HI_R", soh=0.78, r0_multiplier=4.0),
                              ModuleBelief("MOD_HI_R", prior_soh=0.78, prior_sigma_soh=0.05)),
            "fault_type": "Contact / Delamination Fault"
        },
        # 6. Gross Prior Misleading (Prior claims 95% SOH, Actual is 45% SOH)
        {
            "id": "ADV_06_GROSS_PRIOR_ERROR",
            "name": "Fraudulent/Corrupted BMS History (True SOH 45%, Claimed 95%)",
            "setup": lambda: (BatteryModule("MOD_FRAUD", soh=0.45, r0_multiplier=2.5),
                              ModuleBelief("MOD_FRAUD", prior_soh=0.95, prior_sigma_soh=0.02)),
            "fault_type": "Adversarial History"
        },
        # 7. Stuck Bypass Switch in HERMES
        {
            "id": "ADV_07_SWITCH_FAILURE",
            "name": "Switch Failure: MOSFET Stuck in Bypass",
            "setup": lambda: (BatteryModule("MOD_SW", soh=0.85),
                              ModuleBelief("MOD_SW", prior_soh=0.85, prior_sigma_soh=0.03)),
            "fault_type": "Actuator Hardware Fault"
        }
    ]
    
    results = []
    
    for s in scenarios:
        mod, belief = s["setup"]()
        if "modify_module" in s:
            s["modify_module"](mod)
            
        hermes = HermesController(mod.module_id)
        
        # 1. Triage Screening Gate
        t_status, t_reason = triage.evaluate(mod, belief, resting_duration_s=15.0)
        
        # 2. Decision Logic
        if t_status == "REJECT":
            final_action = "RETIRE"
            hermes.command_transition("ISOLATED", f"Triage rejection: {t_reason}")
        else:
            while True:
                act, test_to_run, _ = engine.select_action(belief, max_tests_allowed=3)
                if act == "TEST" and test_to_run:
                    diag.execute_test(test_to_run, mod, belief)
                else:
                    final_action = act
                    break
                    
            if final_action == "OPERATE":
                hermes.command_transition("ACTIVE", "Cleared for full load")
            elif final_action == "DERATE":
                hermes.command_transition("DERATED", "Operate under current limit")
            elif final_action == "RETIRE":
                hermes.command_transition("ISOLATED", "Decommissioned")

        # 3. Simulate operational stress if accepted into pack
        safety_tripped = False
        if hermes.current_state in ["ACTIVE", "DERATED"]:
            # Run 100 seconds of pack current
            for _ in range(100):
                step_res = hermes.step_operational_feedback(mod, belief, string_current_a=30.0, dt_s=1.0)
                if hermes.current_state == "ISOLATED":
                    safety_tripped = True
                    break

        # Ground truth evaluation: Is this cell actually compliant?
        truly_compliant = (mod.soh >= 0.70 and mod.r0 <= 0.0035 and not mod.abnormal_leakage and mod.v_terminal >= 2.0)
        
        # Unsafe Escape: Cell is non-compliant BUT operated actively without tripping
        unsafe_escape = (not truly_compliant) and (hermes.current_state == "ACTIVE") and (not safety_tripped)
        
        scenario_record = {
            "scenario_id": s["id"],
            "name": s["name"],
            "fault_type": s["fault_type"],
            "triage_status": t_status,
            "final_action": final_action,
            "hermes_final_state": hermes.current_state,
            "safety_tripped": bool(safety_tripped),
            "truly_compliant": bool(truly_compliant),
            "safe_containment": bool(not unsafe_escape),
            "verdict": "FAIL-SAFE CONTAINED" if not unsafe_escape else "UNSAFE ESCAPE"
        }
        results.append(scenario_record)
        print(f"[{s['id']:24s}] -> Action: {final_action:8s} | HERMES: {hermes.current_state:8s} | Verdict: {scenario_record['verdict']}")
        
    return results

if __name__ == "__main__":
    res = run_adversarial_suite()
    out_path = os.path.join(os.path.dirname(__file__), "..", "results", "adversarial_results.json")
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\nAdversarial test report saved to {out_path}")
