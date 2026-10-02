"""
RMK-REVOLT SECONDShift: Decision-Efficient Diagnostic Test Engine
Evaluates test informativeness and Value of Information (VOI) to schedule
the minimum test sequence required for safe, confident decision-making.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from scipy.stats import norm
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief

class SecondShiftDiagnosticEngine:
    """
    Computes diagnostic informativeness and executes adaptive testing.
    Test Suite:
    1. pulse_power_test: 10s 1C discharge pulse -> measures R0 and initial R1
    2. short_coulometric_cycle: 15-minute 0.5C step -> observes capacity inflection
    3. thermal_recovery_step: 5-minute thermal load -> verifies cooling & internal dissipation
    """
    def __init__(
        self,
        electricity_cost_kwh: float = 8.0,
        labor_rate_hr: float = 250.0,
        **kwargs
    ):
        self.electricity_cost_kwh = float(kwargs.get("electricity_cost_inr_per_kwh", electricity_cost_kwh))
        self.labor_rate_hr = float(kwargs.get("labor_rate_inr_per_hour", labor_rate_hr))

        
        # Test physical specifications and costs
        self.test_specs = {
            "pulse_power_test": {
                "name": "Controlled 1C Current Pulse",
                "duration_s": 20.0,
                "current_c_rate": 1.0,
                "energy_cost_wh": 1.5,
                "sensor_noise_sigma_r0": 0.00025,
                "degradation_cost_inr": 2.0,
                "equipment_labor_cost_inr": 15.0
            },
            "short_coulometric_cycle": {
                "name": "Short Coulometric Charge/Discharge Step",
                "duration_s": 600.0,  # 10 minutes
                "current_c_rate": 0.5,
                "energy_cost_wh": 25.0,
                "meas_noise_sigma_soh": 0.025,
                "degradation_cost_inr": 18.0,
                "equipment_labor_cost_inr": 60.0
            },
            "thermal_recovery_step": {
                "name": "Thermal Impedance Recovery Step",
                "duration_s": 180.0,
                "current_c_rate": 0.8,
                "energy_cost_wh": 8.0,
                "sensor_noise_sigma_r0": 0.0004,
                "degradation_cost_inr": 5.0,
                "equipment_labor_cost_inr": 30.0
            }
        }

    def get_test_cost_inr(self, test_name: str) -> float:
        spec = self.test_specs[test_name]
        time_cost = (spec["duration_s"] / 3600.0) * self.labor_rate_hr
        energy_cost = (spec["energy_cost_wh"] / 1000.0) * self.electricity_cost_kwh
        total_cost = time_cost + energy_cost + spec["degradation_cost_inr"] + spec["equipment_labor_cost_inr"]
        return float(total_cost)

    def execute_test(
        self,
        test_name: str,
        module: BatteryModule,
        belief: ModuleBelief
    ) -> Dict[str, Any]:
        """
        Execute the specified physical test on the simulated module
        and update the belief state accordingly.
        """
        spec = self.test_specs[test_name]
        duration_s = spec["duration_s"]
        current_a = spec["current_c_rate"] * module.nominal_capacity_ah
        
        # Physics execution (exact analytical discrete step)
        v_start = module.v_terminal
        # Step 1: Immediate ohmic jump (1s)
        module.step_analytical(current_a, 1.0)
        meas_1 = module.measure(current_a)
        v_immediate = meas_1["v_meas"]
        
        # Remaining pulse duration
        remaining_s = max(0.0, duration_s - 1.0)
        if remaining_s > 0:
            module.step_analytical(current_a, remaining_s)
            
        meas = module.measure(current_a)
        
        # Test cost tracking
        test_cost = self.get_test_cost_inr(test_name)
        belief.total_diagnostic_time_s += duration_s
        belief.total_diagnostic_energy_wh += spec["energy_cost_wh"]
        belief.total_test_cost_inr += test_cost
        belief.applied_tests.append(test_name)
        
        # Parameter estimation & Bayesian belief update
        if test_name == "pulse_power_test":
            # Estimate R0 = Immediate Delta V / Delta I (Ohmic jump)
            delta_v_ohmic = abs(v_start - v_immediate)
            delta_i = max(abs(meas_1["i_meas"]), 1.0)
            measured_r0 = delta_v_ohmic / delta_i
            belief.update_from_pulse_test(measured_r0, spec["sensor_noise_sigma_r0"])
            
        elif test_name == "short_coulometric_cycle":
            # Estimate SOH from partial cycling observation
            measured_soh = module.soh + module.rng.normal(0.0, spec["meas_noise_sigma_soh"])
            belief.update_from_coulometric_test(measured_soh, spec["meas_noise_sigma_soh"])
            
        elif test_name == "thermal_recovery_step":
            # Observe thermal rate dT/dt
            measured_r0 = (abs(v_start - meas["v_meas"])) / max(abs(meas["i_meas"]), 1.0)
            belief.temp_c = meas["t_meas"]
            belief.update_from_pulse_test(measured_r0, spec["sensor_noise_sigma_r0"])

        # Rest module for recovery
        module.rest(duration_s=30.0, dt_s=1.0)
        
        return {
            "test_name": test_name,
            "duration_s": duration_s,
            "cost_inr": round(test_cost, 2),
            "updated_mu_soh": round(belief.mu_soh, 4),
            "updated_sigma_soh": round(belief.sigma_soh, 4),
            "updated_mu_r0_mohm": round(belief.mu_r0 * 1000.0, 3),
            "updated_sigma_r0_mohm": round(belief.sigma_r0 * 1000.0, 3)
        }
