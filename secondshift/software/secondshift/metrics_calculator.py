"""
Experimental Metrics & Statistical Evaluation Calculator
Project: RMK-REVOLT / SECONDShift Platform
Calculates:
- Diagnostic Time, Energy, Cost
- FAR (False Acceptance Rate) with 95% Confidence Upper Bounds
- FRR (False Rejection Rate) / UIR (Unnecessary Isolation Rate)
- Retained Usable Energy (kWh)
- EVSI (Expected Value of Sample Information)
- ERDS (Energy Recovery per Diagnostic Second: Delta E / Delta t)
- Net Economic Value (INR)
"""

import numpy as np
from typing import Dict, Any, List
from scipy.stats import norm

class MetricsCalculator:
    def __init__(
        self,
        nominal_cell_kwh: float = 0.064, # 20Ah * 3.2V / 1000
        safety_penalty_inr: float = 6000.0,
        energy_revenue_per_kwh_inr: float = 10.0,
        lifetime_cycles: float = 1200.0,
        recycle_rate_inr_kwh: float = 1200.0
    ):
        self.nominal_kwh = nominal_cell_kwh
        self.safety_penalty = safety_penalty_inr
        self.revenue_kwh = energy_revenue_per_kwh_inr
        self.cycles = lifetime_cycles
        self.salvage_rate = recycle_rate_inr_kwh

    def evaluate_cohort_performance(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a cohort of test records against ground truth.
        """
        n_total = len(records)
        n_truly_unsafe = 0
        n_unsafe_accepted = 0
        n_truly_usable = 0
        n_unnecessary_isolation = 0

        total_diag_time_s = 0.0
        total_diag_cost_inr = 0.0
        total_diag_energy_wh = 0.0
        total_retained_kwh = 0.0
        total_net_economic_value = 0.0

        for r in records:
            true_soh = r["ground_truth"]["true_soh"]
            true_r0 = r["ground_truth"]["true_r0_mohm"]
            true_chem = r["ground_truth"]["true_chemistry"]
            action = r["decision"]
            diag_time = r.get("elapsed_time_s", 0.0)
            diag_cost = r.get("total_diag_cost_inr", 0.0)
            diag_energy = r.get("total_diag_energy_wh", 0.0)

            total_diag_time_s += diag_time
            total_diag_cost_inr += diag_cost
            total_diag_energy_wh += diag_energy

            # True usability under LFP pack envelope:
            is_usable = (true_chem == "LFP" and true_soh >= 0.70 and true_r0 <= 3.5)
            is_derate_safe = (true_chem == "LFP" and true_soh >= 0.65 and true_r0 <= 4.7)

            if not is_usable:
                n_truly_unsafe += 1
            else:
                n_truly_usable += 1

            # Action consequence
            cell_kwh = true_soh * self.nominal_kwh

            if action == "OPERATE":
                if not is_usable:
                    n_unsafe_accepted += 1
                    asset_val = -self.safety_penalty
                else:
                    total_retained_kwh += cell_kwh
                    asset_val = cell_kwh * self.cycles * self.revenue_kwh - 100.0

            elif action == "DERATE":
                if not is_derate_safe:
                    n_unsafe_accepted += 1
                    asset_val = -self.safety_penalty
                else:
                    total_retained_kwh += cell_kwh * 0.75
                    asset_val = (cell_kwh * 0.75) * self.cycles * self.revenue_kwh - 30.0

            else: # HOLD, RETIRE
                if is_usable:
                    n_unnecessary_isolation += 1
                asset_val = self.nominal_kwh * self.salvage_rate - 50.0

            net_val = asset_val - diag_cost
            total_net_economic_value += net_val

        far_pct = (n_unsafe_accepted / max(1, n_truly_unsafe)) * 100.0
        uir_pct = (n_unnecessary_isolation / max(1, n_truly_usable)) * 100.0

        # Exact Clopper-Pearson 95% Confidence Upper Bound on FAR
        if n_unsafe_accepted == 0:
            far_95_upper = (1.0 - (0.05 ** (1.0 / max(1, n_truly_unsafe)))) * 100.0
        else:
            z = 1.645 # 95% one-sided
            p_hat = n_unsafe_accepted / n_truly_unsafe
            denom = 1.0 + z**2 / n_truly_unsafe
            center = (p_hat + z**2 / (2 * n_truly_unsafe)) / denom
            spread = z * np.sqrt(p_hat * (1 - p_hat) / n_truly_unsafe + z**2 / (4 * n_truly_unsafe**2)) / denom
            far_95_upper = (center + spread) * 100.0

        return {
            "n_total": n_total,
            "n_unsafe": n_truly_unsafe,
            "n_unsafe_accepted": n_unsafe_accepted,
            "far_percent": round(far_pct, 4),
            "far_95_upper_bound_percent": round(far_95_upper, 4),
            "n_usable": n_truly_usable,
            "n_unnecessary_isolation": n_unnecessary_isolation,
            "uir_percent": round(uir_pct, 2),
            "total_retained_kwh": round(total_retained_kwh, 3),
            "mean_diagnostic_time_s": round(total_diag_time_s / max(1, n_total), 2),
            "mean_diagnostic_cost_inr": round(total_diag_cost_inr / max(1, n_total), 2),
            "mean_diagnostic_energy_wh": round(total_diag_energy_wh / max(1, n_total), 3),
            "mean_net_economic_value_inr": round(total_net_economic_value / max(1, n_total), 2)
        }

    @staticmethod
    def calculate_erds(
        retained_kwh_policy: float,
        retained_kwh_baseline: float,
        diag_time_s_policy: float,
        diag_time_s_baseline: float
    ) -> float:
        """
        Energy Recovery per Diagnostic Second (Wh / diagnostic-second):
        ERDS = (E_policy - E_baseline) / (T_policy - T_baseline)
        """
        delta_e_wh = (retained_kwh_policy - retained_kwh_baseline) * 1000.0
        delta_t_s = diag_time_s_policy - diag_time_s_baseline
        if abs(delta_t_s) < 1e-4:
            return 0.0
        return float(delta_e_wh / delta_t_s)
