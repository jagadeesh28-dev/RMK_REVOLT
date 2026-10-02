"""
RMK-REVOLT Scenario-Based Economic Model
Transparent, sourced economic valuation of battery circularity workflows in India (INR).
Includes sensitivity analysis across labor rates, battery scrap values, and testing times.
"""

from typing import Dict, Any, List

class CircularityEconomicModel:
    """
    Sourced Economic Parameters for India (2025-2026):
    - Technician Labor: INR 250 / hour (Source: National Skill Development Corp / Indian industrial benchmark)
    - Commercial Electricity: INR 8.00 / kWh (Source: TANGEDCO / State Electricity Regulatory Commission tariff)
    - Black Mass / LFP Scrap Value: INR 1,200 / kWh (Source: Indian Battery Recycling Association / Fastmarkets LFP scrap index)
    - Repurposed BESS Pack Market Value: INR 6,500 / kWh (Source: CEEW / India Energy Storage Alliance second-life estimates)
    - New LFP Pack OEM Cost: INR 13,500 / kWh (Source: BNEF Lithium-Ion Battery Price Survey 2024-2025)
    """
    def __init__(
        self,
        labor_rate_inr_hr: float = 250.0,
        electricity_cost_inr_kwh: float = 8.0,
        scrap_value_inr_kwh: float = 1200.0,
        repurposed_value_inr_kwh: float = 6500.0,
        hardware_capex_inr: float = 18500.0,
        annual_module_throughput: int = 2000
    ):
        self.labor_rate_hr = labor_rate_inr_hr
        self.elec_cost_kwh = electricity_cost_inr_kwh
        self.scrap_value_kwh = scrap_value_inr_kwh
        self.repurposed_value_kwh = repurposed_value_kwh
        self.capex_amortized_per_module = hardware_capex_inr / annual_module_throughput

    def calculate_module_economics(
        self,
        soh: float,
        nominal_kwh: float,
        diagnostic_time_s: float,
        diagnostic_energy_wh: float,
        decision: str  # OPERATE, DERATE, RETIRE
    ) -> Dict[str, float]:
        # 1. Diagnostic cost
        labor_cost = (diagnostic_time_s / 3600.0) * self.labor_rate_hr
        energy_cost = (diagnostic_energy_wh / 1000.0) * self.elec_cost_kwh
        total_diag_cost = labor_cost + energy_cost + self.capex_amortized_per_module
        
        # 2. Revenue generation
        usable_kwh = soh * nominal_kwh
        if decision == "OPERATE":
            gross_value = usable_kwh * self.repurposed_value_kwh
        elif decision == "DERATE":
            gross_value = usable_kwh * self.repurposed_value_kwh * 0.80
        else:  # RETIRE
            gross_value = usable_kwh * self.scrap_value_kwh
            
        net_profit = gross_value - total_diag_cost
        
        return {
            "decision": decision,
            "labor_cost_inr": round(labor_cost, 2),
            "energy_cost_inr": round(energy_cost, 2),
            "total_diag_cost_inr": round(total_diag_cost, 2),
            "gross_value_inr": round(gross_value, 2),
            "net_profit_inr": round(net_profit, 2)
        }

    def run_sensitivity_analysis(self) -> List[Dict[str, Any]]:
        """Sensitivity of net profit per 100 modules to diagnostic time and labor rates."""
        nominal_kwh = (50.0 * 3.2) / 1000.0  # 0.16 kWh per module
        avg_soh = 0.78
        
        scenarios = []
        for labor in [150.0, 250.0, 350.0]:
            for diag_time_s in [100.0, 400.0, 800.0]:  # Adaptive (100s) vs Fixed (800s)
                diag_cost = (diag_time_s / 3600.0) * labor + (5.0 / 1000.0) * self.elec_cost_kwh + self.capex_amortized_per_module
                gross = avg_soh * nominal_kwh * self.repurposed_value_kwh
                net_per_mod = gross - diag_cost
                scenarios.append({
                    "labor_rate_hr": labor,
                    "diag_time_s": diag_time_s,
                    "diag_cost_per_module_inr": round(diag_cost, 2),
                    "net_profit_per_module_inr": round(net_per_mod, 2),
                    "annual_profit_2000_modules_inr": round(net_per_mod * 2000, 2)
                })
        return scenarios
