"""
RMK-REVOLT Battery Physics Simulation Model
Thevenin 1-RC Equivalent Circuit Model + Lumped Thermal Model for LFP Cells
"""

import numpy as np
from typing import Dict, Tuple, Optional

def lfp_ocv(soc: float) -> float:
    """
    Empirical OCV(SOC) curve for Lithium Iron Phosphate (LiFePO4 / LFP) cells.
    Reflects the characteristic wide flat plateau (~3.28V to 3.32V) and sharp steep knees.
    """
    soc = np.clip(soc, 0.0, 1.0)
    # Piecewise continuous representation tuned to empirical LFP cell data
    if soc < 0.05:
        # Steep discharge cutoff knee: 2.50V at soc=0.0 -> 3.05V at soc=0.05
        return 2.50 + 11.0 * soc
    elif soc < 0.15:
        # Transition into plateau: 3.05V -> 3.24V
        return 3.05 + 1.9 * (soc - 0.05)
    elif soc < 0.85:
        # Extremely flat central plateau: 3.24V -> 3.33V (90 mV rise over 70% SOC)
        return 3.24 + 0.12857 * (soc - 0.15)
    elif soc < 0.95:
        # Transition out of plateau: 3.33V -> 3.42V
        return 3.33 + 0.9 * (soc - 0.85)
    else:
        # Steep charge saturation knee: 3.42V -> 3.65V at soc=1.0
        return 3.42 + 4.6 * (soc - 0.95)

def lfp_docv_dsoc(soc: float) -> float:
    """Derivative d(OCV)/d(SOC) - key for Kalman filtering and observable sensitivity."""
    soc = np.clip(soc, 0.001, 0.999)
    delta = 0.001
    return (lfp_ocv(soc + delta) - lfp_ocv(soc - delta)) / (2.0 * delta)


def nmc_ocv(soc: float) -> float:
    """
    Empirical OCV(SOC) curve for Nickel Manganese Cobalt (NMC 622/811) cells.
    Characteristic continuously sloping OCV from 3.00V (0% SOC) to 4.20V (100% SOC).
    """
    soc = np.clip(soc, 0.0, 1.0)
    if soc < 0.10:
        return 3.00 + 4.5 * soc
    elif soc < 0.80:
        # Sloping active plateau: 3.45V -> 3.92V
        return 3.45 + 0.6714 * (soc - 0.10)
    else:
        # High-voltage charging knee: 3.92V -> 4.20V
        return 3.92 + 1.40 * (soc - 0.80)


def nmc_docv_dsoc(soc: float) -> float:
    """Derivative d(OCV)/d(SOC) for NMC cells."""
    soc = np.clip(soc, 0.001, 0.999)
    delta = 0.001
    return (nmc_ocv(soc + delta) - nmc_ocv(soc - delta)) / (2.0 * delta)



class BatteryModule:
    """
    Defensible Physical Module Model.
    Includes:
    - True capacity Q_actual (Ah)
    - True Ohmic resistance R0 (Ohms)
    - True diffusion polarization R1, C1 (tau = R1*C1)
    - Thermal lumped model: C_th * dT/dt = I^2*(R0+R1) - h*(T - T_amb)
    - Sensor noise generators for voltage, current, and temperature
    """
    def __init__(
        self,
        module_id: str,
        nominal_capacity_ah: float = 50.0,
        soh: float = 1.0,
        r0_multiplier: float = 1.0,
        initial_soc: float = 0.60,
        ambient_temp_c: float = 25.0,
        fresh_r0: float = 0.0015,
        fresh_r1: float = 0.0010,
        c1: float = 2000.0,
        c_th: float = 1200.0,
        h_cooling: float = 0.8,
        noise_v: float = 0.002,
        noise_i: float = 0.05,
        noise_t: float = 0.25,
        abnormal_leakage: bool = False,
        rng: Optional[np.random.RandomState] = None,
        chemistry: str = "LFP",
        degradation_knee: bool = False,
        sensor_bias_v: float = 0.0,
        sensor_gain_i: float = 1.0,
        heavy_tailed_noise: bool = False,
        contact_spike_r0: float = 0.0
    ):
        self.module_id = module_id
        self.nominal_capacity_ah = nominal_capacity_ah
        self.soh = float(np.clip(soh, 0.1, 1.2))
        self.actual_capacity_ah = self.nominal_capacity_ah * self.soh
        self.chemistry = chemistry.upper()
        self.degradation_knee = degradation_knee
        self.sensor_bias_v = sensor_bias_v
        self.sensor_gain_i = sensor_gain_i
        self.heavy_tailed_noise = heavy_tailed_noise
        self.contact_spike_r0 = contact_spike_r0
        
        # Ground truth impedance parameters
        if self.degradation_knee:
            # Nonlinear degradation knee (accelerates below 75% SOH)
            loss = max(0.0, 1.0 - self.soh)
            degradation_factor = 1.0 + 1.2 * loss + 6.0 * (loss ** 4)
        else:
            degradation_factor = 1.0 + 1.8 * (1.0 - self.soh)
            
        self.r0 = fresh_r0 * degradation_factor * r0_multiplier + contact_spike_r0
        self.r1 = fresh_r1 * degradation_factor
        self.c1 = c1
        self.tau = self.r1 * self.c1
        
        # Thermal parameters
        self.c_th = c_th
        self.h_cooling = h_cooling
        self.ambient_temp_c = ambient_temp_c
        self.temperature_c = ambient_temp_c
        self.t_max_limit = 50.0 if self.chemistry == "NMC" else 55.0
        
        # States
        self.soc = float(np.clip(initial_soc, 0.0, 1.0))
        self.v_rc = 0.0  # Polarization voltage across RC pair
        self.v_terminal = self.get_ocv(self.soc)
        
        # Sensor noise settings
        self.noise_v = noise_v
        self.noise_i = noise_i
        self.noise_t = noise_t
        self.rng = rng if rng is not None else np.random.RandomState(42)
        
        # Fault injection flags
        self.abnormal_leakage = abnormal_leakage  # High self-discharge / internal micro-short
        self.leakage_current_a = 0.35 if abnormal_leakage else 0.0001
        
        # Operational history tracking
        self.cumulative_energy_wh = 0.0
        self.total_test_time_s = 0.0
        self.cycle_count = 0.0

    def get_ocv(self, soc: float) -> float:
        """Evaluate open circuit voltage based on cell chemistry."""
        if self.chemistry == "NMC":
            return nmc_ocv(soc)
        return lfp_ocv(soc)

    def step(self, current_a: float, dt_s: float) -> Tuple[float, float, float]:
        """
        Advance physics by dt_s with applied load current_a.
        Current convention: I > 0 discharge, I < 0 charge.
        Returns true (v_terminal, current, temperature).
        """
        effective_current = current_a + self.leakage_current_a
        
        # 1. SOC Update (Coulomb Counting)
        delta_soc = -(effective_current * dt_s) / (3600.0 * self.actual_capacity_ah)
        self.soc = float(np.clip(self.soc + delta_soc, 0.0, 1.0))
        
        # 2. RC Polarization Voltage Update (exact analytical discrete solution)
        alpha = np.exp(-dt_s / self.tau)
        self.v_rc = self.v_rc * alpha + effective_current * self.r1 * (1.0 - alpha)
        
        # 3. Terminal Voltage calculation
        ocv = self.get_ocv(self.soc)
        self.v_terminal = ocv - effective_current * self.r0 - self.v_rc
        
        # 4. Thermal dynamics: P_loss = I^2 * R0 + V_rc^2 / R1
        p_joule = (effective_current ** 2) * self.r0 + (self.v_rc ** 2) / max(self.r1, 1e-6)
        p_dissipated = self.h_cooling * (self.temperature_c - self.ambient_temp_c)
        dt_temp = (p_joule - p_dissipated) / self.c_th * dt_s
        self.temperature_c += dt_temp
        
        # Energy accounting
        self.cumulative_energy_wh += abs(self.v_terminal * effective_current * dt_s) / 3600.0
        self.total_test_time_s += dt_s
        
        return self.v_terminal, effective_current, self.temperature_c

    def step_analytical(self, current_a: float, duration_s: float) -> Tuple[float, float, float]:
        """
        Exact closed-form analytical integration of 1-RC Thevenin + thermal ODE
        under piecewise-constant current. Zero truncation error, O(1) evaluation.
        """
        effective_current = current_a + self.leakage_current_a
        
        # 1. Exact SOC integration
        delta_soc = -(effective_current * duration_s) / (3600.0 * self.actual_capacity_ah)
        self.soc = float(np.clip(self.soc + delta_soc, 0.0, 1.0))
        
        # 2. Exact RC polarization solution
        alpha_rc = np.exp(-duration_s / self.tau)
        self.v_rc = self.v_rc * alpha_rc + effective_current * self.r1 * (1.0 - alpha_rc)
        
        # 3. Terminal voltage calculation
        ocv = self.get_ocv(self.soc)
        self.v_terminal = ocv - effective_current * self.r0 - self.v_rc
        
        # 4. Exact lumped thermal ODE solution: dT/dt + (h/C)T = (P_loss + h*T_amb)/C
        p_loss = (effective_current ** 2) * self.r0 + (self.v_rc ** 2) / max(self.r1, 1e-6)
        alpha_th = np.exp(-(self.h_cooling / self.c_th) * duration_s)
        t_steady = self.ambient_temp_c + p_loss / max(self.h_cooling, 1e-6)
        self.temperature_c = t_steady + (self.temperature_c - t_steady) * alpha_th
        
        self.cumulative_energy_wh += abs(self.v_terminal * effective_current * duration_s) / 3600.0
        self.total_test_time_s += duration_s
        return self.v_terminal, effective_current, self.temperature_c

    def measure(self, current_a: float) -> Dict[str, float]:
        """
        Generate physically noisy sensor measurements.
        Simulates ADC quantization, thermal jitter, bias, and optional heavy-tailed noise.
        """
        if self.heavy_tailed_noise:
            # Student-t noise with df=3 has infinite 4th moment (heavy tails)
            # Scaled so that variance matches standard Gaussian
            scale = np.sqrt(3.0 / (3.0 - 2.0))  # sqrt(3)
            noise_v = (self.rng.standard_t(df=3) / scale) * self.noise_v
            noise_i = (self.rng.standard_t(df=3) / scale) * self.noise_i
            noise_t = (self.rng.standard_t(df=3) / scale) * self.noise_t
        else:
            noise_v = self.rng.normal(0.0, self.noise_v)
            noise_i = self.rng.normal(0.0, self.noise_i)
            noise_t = self.rng.normal(0.0, self.noise_t)
            
        v_meas = self.v_terminal + self.sensor_bias_v + noise_v
        i_meas = current_a * self.sensor_gain_i + noise_i
        t_meas = self.temperature_c + noise_t
        return {
            "v_meas": float(v_meas),
            "i_meas": float(i_meas),
            "t_meas": float(t_meas),
            "timestamp_s": float(self.total_test_time_s)
        }

    def rest(self, duration_s: float, dt_s: float = 1.0) -> None:
        """Let module rest with zero external current using exact analytical solution."""
        self.step_analytical(0.0, duration_s)
