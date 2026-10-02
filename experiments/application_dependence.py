"""
RMK-REVOLT Application-Dependence Experiment
Evaluates whether identical battery modules receive legitimately different reuse actions
when evaluated against distinct end-use operational envelopes.
"""

import os
import sys
import json
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.belief_state import ModuleBelief
from src.secondshift import SecondShiftDiagnosticEngine
from src.decision_engine import DecisionEngine

def run_application_dependence():
    print("\n" + "="*70)
    print("RUNNING EXPERIMENT: Application-Dependent Reuse Decisions")
    print("="*70)
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    apps = config["applications"]
    diag = SecondShiftDiagnosticEngine()
    
    # 3 Benchmark Battery Modules:
    # Module 1 (SOH 0.85, R0 2.0 mOhm, sigma 0.03): High quality retired module
    # Module 2 (SOH 0.74, R0 3.0 mOhm, sigma 0.05): Intermediate retired module
    # Module 3 (SOH 0.64, R0 4.0 mOhm, sigma 0.04): Deeply aged retired module
    
    modules = [
        {"id": "MOD_HIGH_SOH", "soh": 0.85, "r0": 0.0020, "sigma_soh": 0.03, "desc": "High quality retired module"},
        {"id": "MOD_MID_SOH", "soh": 0.74, "r0": 0.0030, "sigma_soh": 0.05, "desc": "Intermediate retired module"},
        {"id": "MOD_LOW_SOH", "soh": 0.64, "r0": 0.0040, "sigma_soh": 0.04, "desc": "Deeply aged retired module"}
    ]
    
    results = {}
    
    for m in modules:
        results[m["id"]] = {"description": m["desc"], "decisions": {}}
        print(f"\n--- Module: {m['id']} (SOH={m['soh']*100:.1f}%, R0={m['r0']*1000:.1f} mOhm) ---")
        
        for app_key, app_cfg in apps.items():
            b = ModuleBelief(m["id"], prior_soh=m["soh"], prior_sigma_soh=m["sigma_soh"], prior_r0=m["r0"], prior_sigma_r0=0.0003)
            b.triage_status = "ACCEPT"
            engine = DecisionEngine(app_cfg, diag)
            
            action, test_rec, dbg = engine.select_action(b)
            results[m["id"]]["decisions"][app_key] = {
                "action": action,
                "recommended_test": test_rec,
                "op_utilities": dbg["op_utilities"],
                "best_voi": dbg["best_voi"]
            }
            print(f"  App [{app_cfg['name']:28s}]: Action -> {action:8s} (Test: {str(test_rec):10s})")

    out_file = os.path.join(os.path.dirname(__file__), "..", "results", "application_dependence_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_file}")
    return results

if __name__ == "__main__":
    run_application_dependence()
