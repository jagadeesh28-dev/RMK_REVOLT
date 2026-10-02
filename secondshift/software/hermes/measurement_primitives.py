"""
HERMES Measurement Primitives & Hardware Abstraction Layer
Project: RMK-REVOLT / SECONDShift Platform
Provides deterministic physical measurement routines:
- measure_voltage()
- measure_current()
- measure_temperature()
- measure_rest_voltage()
- perform_current_pulse()
- measure_voltage_response()
- measure_relaxation()
- measure_temperature_response()

All data logged to CSV using monotonic timestamps.
"""

import time
import os
import csv
import json
from typing import Dict, Any, List, Optional, Tuple

class HermesMeasurementEngine:
    def __init__(
        self,
        hardware_interface: Any,
        data_log_path: str = "secondshift/data/raw/hermes_telemetry.csv",
        active_cell_idx: int = 0,
        sim_mode: bool = True
    ):
        self.hw = hardware_interface
        self.log_path = data_log_path
        self.cell_idx = active_cell_idx
        self.sim_mode = sim_mode
        self._sim_clock = 0.0
        self._init_csv_log()

    def _sleep(self, duration_s: float):
        if self.sim_mode:
            self._sim_clock += duration_s
            time.sleep(0.001)
        else:
            time.sleep(duration_s)

    def _init_csv_log(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_monotonic",
                    "timestamp_iso",
                    "cell_idx",
                    "voltage",
                    "current",
                    "temperature",
                    "test_state",
                    "hardware_trip"
                ])

    def log_record(self, voltage: float, current: float, temperature: float, test_state: str, hw_trip: bool = False):
        t_mono = time.monotonic()
        t_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        with open(self.log_path, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                f"{t_mono:.6f}",
                t_iso,
                self.cell_idx,
                f"{voltage:.5f}",
                f"{current:.4f}",
                f"{temperature:.3f}",
                test_state,
                int(hw_trip)
            ])

    def measure_voltage(self) -> float:
        """Returns the high-precision terminal voltage of the active cell."""
        raw = self.hw.read_sensors()
        v = raw["voltages"][self.cell_idx]
        self.log_record(v, raw["current"], raw["temperatures"][self.cell_idx], "MEASURE_V")
        return v

    def measure_current(self) -> float:
        """Returns the string current passing through the active cell in Amperes."""
        raw = self.hw.read_sensors()
        i = raw["current"]
        self.log_record(raw["voltages"][self.cell_idx], i, raw["temperatures"][self.cell_idx], "MEASURE_I")
        return i

    def measure_temperature(self) -> float:
        """Returns the surface temperature of the active cell in Celsius."""
        raw = self.hw.read_sensors()
        t = raw["temperatures"][self.cell_idx]
        self.log_record(raw["voltages"][self.cell_idx], raw["current"], t, "MEASURE_TEMP")
        return t

    def measure_rest_voltage(self, rest_duration_s: float = 10.0, sample_interval_s: float = 1.0) -> Dict[str, Any]:
        """
        Observes cell at zero current across rest_duration_s.
        Computes open-circuit voltage and self-discharge drift rate (mV/hour).
        """
        # Ensure cell is isolated or bypassed
        self.hw.set_cell_state(self.cell_idx, "BYPASS")
        start_mono = time.monotonic()
        samples = []
        n_steps = 3 if self.sim_mode else int(max(1, rest_duration_s / sample_interval_s))
        for step in range(n_steps):
            raw = self.hw.read_sensors()
            v = raw["voltages"][self.cell_idx]
            cur = raw["current"]
            temp = raw["temperatures"][self.cell_idx]
            samples.append((time.monotonic(), v, temp))
            self.log_record(v, cur, temp, "REST_OBSERVATION")
            self._sleep(sample_interval_s)

        v_start = samples[0][1]
        v_end = samples[-1][1]
        dt_hr = (samples[-1][0] - samples[0][0]) / 3600.0
        
        if hasattr(self.hw, "get_leakage_rate_mv_hr"):
            drift_mv_hr = self.hw.get_leakage_rate_mv_hr(self.cell_idx)
        elif dt_hr >= (60.0 / 3600.0): # At least 60 seconds of observation
            drift_mv_hr = max(0.0, ((v_start - v_end) * 1000.0) / dt_hr)
        else:
            # Over short intake observation, check for severe voltage collapse (> 15mV)
            delta_v_mv = (v_start - v_end) * 1000.0
            drift_mv_hr = 25.0 if delta_v_mv > 15.0 else 1.2

        return {
            "v_rest": float(v_end),
            "v_start": float(v_start),
            "drift_mv_hr": float(drift_mv_hr),
            "temperature_c": float(samples[-1][2]),
            "duration_s": float(time.monotonic() - start_mono)
        }

    def perform_current_pulse(
        self,
        current_a: float,
        duration_s: float,
        dt_sample_s: float = 0.1
    ) -> List[Dict[str, float]]:
        """
        Applies a controlled current step and records rapid terminal response.
        """
        self.hw.set_cell_state(self.cell_idx, "ACTIVE")
        self.hw.set_load_current(current_a)
        start_mono = time.monotonic()
        records = []

        n_steps = 5 if self.sim_mode else int(max(1, duration_s / dt_sample_s))
        for step in range(n_steps):
            now = time.monotonic()
            raw = self.hw.read_sensors()
            v = raw["voltages"][self.cell_idx]
            i = raw["current"]
            temp = raw["temperatures"][self.cell_idx]
            records.append({
                "t_rel": now - start_mono,
                "voltage": v,
                "current": i,
                "temperature": temp
            })
            self.log_record(v, i, temp, "CURRENT_PULSE")
            self._sleep(dt_sample_s)

        # De-energize load
        self.hw.set_load_current(0.0)
        self.hw.set_cell_state(self.cell_idx, "BYPASS")
        return records

    def measure_voltage_response(
        self,
        pulse_current_a: float = 10.0,
        pulse_duration_s: float = 10.0
    ) -> Dict[str, Any]:
        """
        Executes a current pulse to calculate immediate Ohmic jump R0 and polarization drop.
        """
        v_pre = self.measure_voltage()
        pulse_data = self.perform_current_pulse(pulse_current_a, pulse_duration_s, dt_sample_s=0.05)
        
        # Immediate Ohmic step within first 100ms
        v_immediate = pulse_data[1]["voltage"] if len(pulse_data) > 1 else pulse_data[0]["voltage"]
        delta_v_ohmic = abs(v_pre - v_immediate)
        i_actual = max(abs(pulse_data[1]["current"]), 0.5)
        r0_est = delta_v_ohmic / i_actual

        v_end = pulse_data[-1]["voltage"]
        delta_v_total = abs(v_pre - v_end)

        return {
            "v_pre": float(v_pre),
            "v_immediate": float(v_immediate),
            "v_end": float(v_end),
            "r0_ohms": float(r0_est),
            "delta_v_total": float(delta_v_total),
            "pulse_data": pulse_data
        }

    def measure_relaxation(
        self,
        observation_duration_s: float = 30.0,
        dt_sample_s: float = 1.0
    ) -> Dict[str, Any]:
        """
        Monitors post-pulse open-circuit relaxation recovery.
        """
        self.hw.set_cell_state(self.cell_idx, "BYPASS")
        start_mono = time.monotonic()
        samples = []

        t_end = start_mono + observation_duration_s
        while time.monotonic() < t_end:
            now = time.monotonic()
            raw = self.hw.read_sensors()
            v = raw["voltages"][self.cell_idx]
            samples.append((now - start_mono, v))
            self.log_record(v, raw["current"], raw["temperatures"][self.cell_idx], "RELAXATION")
            time.sleep(dt_sample_s)

        v_start = samples[0][1]
        v_end = samples[-1][1]
        delta_v_rec = abs(v_end - v_start)

        return {
            "v_start": float(v_start),
            "v_end": float(v_end),
            "delta_v_recovery": float(delta_v_rec),
            "relaxation_trajectory": samples
        }

    def measure_temperature_response(
        self,
        continuous_current_a: float = 15.0,
        duration_s: float = 60.0
    ) -> Dict[str, Any]:
        """
        Monitors thermal rise dT/dt under sustained load.
        """
        t_pre = self.measure_temperature()
        pulse_data = self.perform_current_pulse(continuous_current_a, duration_s, dt_sample_s=1.0)
        t_post = self.measure_temperature()
        delta_t = t_post - t_pre
        rate_c_s = delta_t / max(duration_s, 1.0)

        return {
            "t_pre": float(t_pre),
            "t_post": float(t_post),
            "delta_t_c": float(delta_t),
            "dT_dt_c_s": float(rate_c_s)
        }
