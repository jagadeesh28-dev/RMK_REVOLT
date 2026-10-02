"""
RMK-REVOLT Evaluation Metrics Suite
Implements rigorous mathematical definitions for FAR, FRR, UIR,
Usable Energy Retained, Information Gain, and Decision Efficiency (DE).
"""

import numpy as np
from typing import List, Dict, Any

class MetricEvaluator:
    """
    Computes rigorous statistical metrics across a test population of battery modules.
    Evaluates safety compliance, diagnostic burden, and economic opportunity loss.
    """
    def __init__(self, soh_threshold: float = 0.70, r0_max_mohm: float = 3.5):
        self.soh_threshold = soh_threshold
        self.r0_max = r0_max_mohm / 1000.0

    def evaluate_cohort(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Input record format:
        {
            "module_id": str,
            "true_soh": float,
            "true_r0": float,
            "true_leakage": bool,
            "decision": str,  # OPERATE, DERATE, BYPASS, ISOLATE, RETIRE
            "diag_time_s": float,
            "diag_energy_wh": float,
            "diag_cost_inr": float,
            "num_tests": int,
            "final_mu_soh": float,
            "final_sigma_soh": float
        }
        """
        n_total = len(records)
        if n_total == 0:
            return {}

        n_healthy = 0
        n_degraded = 0
        
        false_accept_count = 0      # Degraded module assigned to full OPERATE
        false_reject_count = 0      # Healthy module assigned to RETIRE
        unnecessary_isolation = 0   # Healthy module assigned to ISOLATE or premature RETIRE
        derated_healthy_count = 0   # Healthy module derated
        
        total_diag_time_s = 0.0
        total_diag_energy_wh = 0.0
        total_diag_cost_inr = 0.0
        total_tests_run = 0
        usable_energy_retained_kwh = 0.0
        potential_healthy_energy_kwh = 0.0
        
        calibration_errors = []

        for r in records:
            # Ground Truth Definition:
            is_healthy = (
                r["true_soh"] >= self.soh_threshold and
                r["true_r0"] <= self.r0_max and
                not r.get("true_leakage", False)
            )
            
            module_true_kwh = (r["true_soh"] * 50.0 * 3.2) / 1000.0
            
            if is_healthy:
                n_healthy += 1
                potential_healthy_energy_kwh += module_true_kwh
            else:
                n_degraded += 1

            dec = r["decision"]
            
            # Classification outcome evaluation
            if not is_healthy and dec == "OPERATE":
                false_accept_count += 1
            elif is_healthy and dec == "RETIRE":
                false_reject_count += 1
                unnecessary_isolation += 1
            elif is_healthy and dec == "ISOLATE":
                unnecessary_isolation += 1
            elif is_healthy and dec == "DERATE":
                derated_healthy_count += 1
                # Derated module recovers ~80% equivalent energy
                usable_energy_retained_kwh += module_true_kwh * 0.80

            if dec == "OPERATE":
                usable_energy_retained_kwh += module_true_kwh

            # Diagnostic burden accumulation
            total_diag_time_s += r["diag_time_s"]
            total_diag_energy_wh += r["diag_energy_wh"]
            total_diag_cost_inr += r["diag_cost_inr"]
            total_tests_run += r["num_tests"]
            
            # Uncertainty calibration: (mu - true)^2 / sigma^2
            z_err = (r["final_mu_soh"] - r["true_soh"]) / max(r["final_sigma_soh"], 1e-4)
            calibration_errors.append(float(z_err))

        far = (false_accept_count / max(n_degraded, 1)) * 100.0
        frr = (false_reject_count / max(n_healthy, 1)) * 100.0
        uir = (unnecessary_isolation / max(n_healthy, 1)) * 100.0
        
        energy_retention_ratio = (usable_energy_retained_kwh / max(potential_healthy_energy_kwh, 1e-6)) * 100.0
        
        # Decision Efficiency (DE):
        # Useful Safe Decisions / Total Diagnostic Burden
        # Hard safety penalty: if FAR > 2.0%, DE drops drastically to prevent unsafe shortcuts
        safety_multiplier = 1.0 if far <= 2.0 else max(0.01, 1.0 - (far - 2.0) * 0.2)
        mean_diag_time_min = (total_diag_time_s / n_total) / 60.0
        mean_cost_inr = total_diag_cost_inr / n_total
        
        decision_efficiency = (
            (usable_energy_retained_kwh * 10.0 * safety_multiplier) /
            max(mean_cost_inr * (mean_diag_time_min + 1.0), 1.0)
        )

        return {
            "n_total": n_total,
            "n_healthy": n_healthy,
            "n_degraded": n_degraded,
            "far_percent": round(far, 2),
            "frr_percent": round(frr, 2),
            "uir_percent": round(uir, 2),
            "derated_healthy_percent": round((derated_healthy_count / max(n_healthy, 1)) * 100.0, 2),
            "mean_diag_time_s": round(total_diag_time_s / n_total, 1),
            "mean_diag_energy_wh": round(total_diag_energy_wh / n_total, 2),
            "mean_diag_cost_inr": round(mean_cost_inr, 2),
            "mean_tests_per_module": round(total_tests_run / n_total, 2),
            "usable_energy_retained_kwh": round(usable_energy_retained_kwh, 2),
            "energy_retention_ratio_percent": round(energy_retention_ratio, 2),
            "decision_efficiency": round(decision_efficiency, 4),
            "mean_z_calibration": round(float(np.mean(calibration_errors)), 3),
            "z_calibration_std": round(float(np.std(calibration_errors)), 3)
        }
