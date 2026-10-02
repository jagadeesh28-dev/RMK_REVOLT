"""
HERMES Hardware Interface & Physical Emulation Driver
Project: RMK-REVOLT / SECONDShift Platform
Provides seamless switching between live ESP32 Serial and physics-based hardware emulation.
"""

import time
import json
from typing import Dict, Any, Optional, List
import numpy as np

class MockHermesHardware:
    """
    High-fidelity physical hardware emulator matching bench specifications.
    Simulates cell electrochemical dynamics, contact resistance, thermal rise,
    and the independent LM393 comparator / KSD9700 thermal trip chain.
    """
    def __init__(
        self,
        cell_chemistries: Optional[List[str]] = None,
        cell_soh: Optional[List[float]] = None,
        cell_r0_mohm: Optional[List[float]] = None,
        ambient_temp_c: float = 25.0,
        enable_watchdog: bool = False
    ):
        self.chemistries = cell_chemistries or ["LFP", "LFP", "LFP", "LFP"]
        self.n_cells = len(self.chemistries)
        self.soh = np.array(cell_soh if cell_soh is not None else [0.94, 0.73, 0.67, 0.48][:self.n_cells], dtype=float)
        r0_defaults = [1.9, 3.2, 4.4, 18.5][:self.n_cells]
        self.r0 = np.array(cell_r0_mohm if cell_r0_mohm is not None else r0_defaults, dtype=float) / 1000.0
        self.soc = np.full(self.n_cells, 0.55, dtype=float)
        self.temps = np.full(self.n_cells, ambient_temp_c, dtype=float)
        self.ambient_temp = ambient_temp_c

        self.cell_states = ["BYPASS"] * self.n_cells
        self.load_current_a = 0.0
        self.relay_enabled = True
        self.hardware_tripped = False
        self.trip_reason = None
        self.watchdog_healthy = True
        self.enable_watchdog = enable_watchdog
        self.last_wdt_time = time.monotonic()
        # Underlying self-discharge leakage (mV/hr)
        self.leakage_rates = [22.0 if s < 0.50 else 1.2 for s in self.soh]

    def get_leakage_rate_mv_hr(self, idx: int) -> float:
        if idx < len(self.leakage_rates):
            return float(self.leakage_rates[idx])
        return 1.2

    def feed_watchdog(self):
        self.last_wdt_time = time.monotonic()
        self.watchdog_healthy = True

    def set_load_current(self, current_a: float):
        if self.hardware_tripped or not self.relay_enabled:
            self.load_current_a = 0.0
            return
        self.load_current_a = current_a

    def set_cell_state(self, cell_idx: int, state: str):
        if self.hardware_tripped:
            self.cell_states[cell_idx] = "ISOLATED"
            return
        self.cell_states[cell_idx] = state

    def inject_fault(self, fault_type: str, cell_idx: int = 0, value: float = 0.0):
        if fault_type == "UVP":
            self.soc[cell_idx] = -0.1
        elif fault_type == "OVP":
            self.soc[cell_idx] = 1.15
        elif fault_type == "OTP":
            self.temps[cell_idx] = 63.5

    def _get_ocv(self, idx: int) -> float:
        chem = self.chemistries[idx]
        s = self.soc[idx]
        if s < 0.0:
            return 1.850 # Over-discharged / UVP fault condition
        elif s > 1.05:
            return 3.750 # Over-charged / OVP fault condition
        s = np.clip(s, 0.0, 1.0)
        if chem == "LFP":
            if s < 0.05:
                return 2.50 + 11.0 * s
            elif s < 0.15:
                return 3.05 + 1.9 * (s - 0.05)
            elif s < 0.85:
                return 3.24 + 0.12857 * (s - 0.15)
            elif s < 0.95:
                return 3.33 + 0.9 * (s - 0.85)
            else:
                return 3.42 + 4.6 * (s - 0.95)
        else: # NMC
            if s < 0.10:
                return 3.00 + 4.5 * s
            elif s < 0.80:
                return 3.45 + 0.6714 * (s - 0.10)
            else:
                return 3.92 + 1.40 * (s - 0.80)

    def read_sensors(self) -> Dict[str, Any]:
        now = time.monotonic()
        # 1. Check Watchdog timeout (> 200ms) if watchdog enabled
        if self.enable_watchdog and (now - self.last_wdt_time) > 0.250 and not self.hardware_tripped:
            self.hardware_tripped = True
            self.trip_reason = "TPS3823_WATCHDOG_TIMEOUT"
            self.relay_enabled = False

        voltages = []
        for i in range(self.n_cells):
            ocv = self._get_ocv(i)
            # Current flowing through this cell
            eff_current = 0.0
            if self.relay_enabled and not self.hardware_tripped:
                if self.cell_states[i] == "ACTIVE":
                    eff_current = self.load_current_a
                elif self.cell_states[i] == "DERATED":
                    eff_current = self.load_current_a * 0.50

            # V_terminal = OCV - I * R0 + noise
            noise = np.random.normal(0, 0.001) # 1mV ADC noise
            v_term = ocv - (eff_current * self.r0[i]) + noise
            voltages.append(float(v_term))

            # Update thermal model: C_th * dT = I^2 * R0 * dt - h * (T - Tamb)
            q_dot = (eff_current ** 2) * self.r0[i]
            c_th = 1200.0 if self.chemistries[i] == "LFP" else 850.0
            self.temps[i] += (q_dot / c_th) - 0.02 * (self.temps[i] - self.ambient_temp)

            # 2. Check Independent Analog Comparator (LM393) Trip Conditions
            if v_term < 2.00:
                self.hardware_tripped = True
                self.trip_reason = f"LM393_UVP_TRIP_CELL_{i}_V={v_term:.3f}"
                self.relay_enabled = False
            elif v_term > 3.70:
                self.hardware_tripped = True
                self.trip_reason = f"LM393_OVP_TRIP_CELL_{i}_V={v_term:.3f}"
                self.relay_enabled = False

            # 3. Check Independent Bimetallic Thermal Snap (KSD9700 > 60C)
            if self.temps[i] >= 60.0:
                self.hardware_tripped = True
                self.trip_reason = f"KSD9700_OTP_SNAP_TRIP_CELL_{i}_T={self.temps[i]:.1f}C"
                self.relay_enabled = False

        return {
            "voltages": voltages,
            "current": float(self.load_current_a if self.relay_enabled and not self.hardware_tripped else 0.0),
            "temperatures": [float(t) for t in self.temps],
            "relay_enabled": self.relay_enabled,
            "hardware_tripped": self.hardware_tripped,
            "trip_reason": self.trip_reason
        }

    def reset_hardware_trip(self):
        # Reset allowed only if physical voltage and temperature are in safe envelope
        if all(2.10 <= v <= 3.65 for v in self.read_sensors()["voltages"]) and all(t < 45.0 for t in self.temps):
            self.hardware_tripped = False
            self.trip_reason = None
            self.relay_enabled = True
            self.last_wdt_time = time.monotonic()
            return True
        return False
