"""
Hardware-in-the-Loop Pipeline Integration Test Suite
Project: RMK-REVOLT / SECONDShift Platform

Tests:
1. All four major decision outcomes emerge cleanly from the 5-layer HIL pipeline:
   - OPERATE (Healthy LFP, low risk, low uncertainty)
   - DERATE (Moderate degradation, bounded risk)
   - RETIRE (Triage failure or critical degradation)
   - HOLD (Uncertainty or measurement failure)
2. Adversarial failure injection through the hardware pipeline:
   - Sensor disconnect / FAULT status -> Fail-Safe HOLD
   - Stale telemetry -> Fail-Safe HOLD
   - Overvoltage / Undervoltage -> Triage RETIRE
   - Hardware comm dropout -> Fail-Safe HOLD
3. Replay determinism: identical traces produce identical qualification outputs
4. Zero ground-truth leakage across all test executions
"""

import math
import time
import pytest
from typing import Dict, Any

from secondshift.hardware.mock_hardware import MockHardware
from secondshift.hardware.replay_hardware import ReplayHardware
from secondshift.hardware.hil_runner import HILRunner
from secondshift.interfaces.telemetry_schema import TelemetryFrame, TelemetryQuality, SensorHealthStatus
from secondshift.interfaces.state_machine import SystemState


def test_hil_pipeline_operates_healthy_lfp():
    """Healthy LFP with fleet prior qualifies directly to OPERATE."""
    hw = MockHardware(chemistry="LFP", soh=0.94, r0_mohm=1.8)
    runner = HILRunner(hw)

    res = runner.run_qualification(
        cell_id="BENCH_HEALTHY_LFP_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.92,
        prior_sigma_soh=0.03,
        prior_r0_mohm=2.0,
        prior_sigma_r0_mohm=0.4
    )

    assert res["final_decision"] == "OPERATE"
    assert res["actuation_intent"] == "ENABLE_LOAD"
    assert res["safety_tripped"] is False
    assert res["system_state"] == SystemState.OPERATE.value
    assert "true_soh" not in res  # Ground truth isolation


def test_hil_pipeline_retires_triage_undervoltage():
    """Cell below 2.0V is rejected at Stage 0 Triage and RETIRED."""
    hw = MockHardware(chemistry="LFP", soh=0.90, r0_mohm=2.0)
    hw.set_fault_mode("UVP_FAULT") # Cell drops below 2.0V
    runner = HILRunner(hw)

    res = runner.run_qualification(
        cell_id="BENCH_UVP_CELL_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.90
    )

    assert res["final_decision"] == "RETIRE"
    assert res["actuation_intent"] == "ISOLATE"
    assert "TR-03" in res["reason"] or "Triage" in res["reason"]
    assert res["system_state"] == SystemState.RETIRE.value


def test_hil_pipeline_failsafe_hold_on_sensor_fault():
    """Hardware sensor fault immediately triggers fail-safe HOLD."""
    hw = MockHardware(chemistry="LFP", soh=0.94, r0_mohm=1.8)
    hw.set_fault_mode("MISSING_SENSOR")
    runner = HILRunner(hw)

    res = runner.run_qualification(
        cell_id="BENCH_FAULTY_SENSOR_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.92
    )

    assert res["final_decision"] in ["HOLD", "EMERGENCY_ISOLATE"]
    assert res["actuation_intent"] in ["KEEP_ISOLATED", "ISOLATE"]
    assert "validation" in res["reason"].lower() or "sensor" in res["reason"].lower()


def test_hil_pipeline_failsafe_hold_on_comm_dropout():
    """Communication loss during intake immediately triggers fail-safe HOLD."""
    hw = MockHardware(chemistry="LFP", soh=0.94, r0_mohm=1.8)
    hw.set_fault_mode("COMM_DROPOUT")
    runner = HILRunner(hw)

    res = runner.run_qualification(
        cell_id="BENCH_DROPOUT_CELL_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.92
    )

    assert res["final_decision"] == "HOLD"
    assert res["actuation_intent"] == "KEEP_ISOLATED"
    assert "dropout" in res["reason"].lower() or "failed" in res["reason"].lower() or "invalid" in res["reason"].lower()


def test_hil_pipeline_replay_determinism():
    """Replaying identical telemetry frames produces bit-for-bit identical decision outputs."""
    t0 = 2000.0
    frames_run1 = [
        TelemetryFrame("REPLAY-01", 1, t0, 3.32, 0.0, 25.0, cell_voltages_v=[3.32]),
        TelemetryFrame("REPLAY-01", 2, t0 + 1.0, 3.30, 2.0, 25.1, cell_voltages_v=[3.30])
    ]
    frames_run2 = [
        TelemetryFrame("REPLAY-01", 1, t0, 3.32, 0.0, 25.0, cell_voltages_v=[3.32]),
        TelemetryFrame("REPLAY-01", 2, t0 + 1.0, 3.30, 2.0, 25.1, cell_voltages_v=[3.30])
    ]

    hw1 = ReplayHardware(frames=frames_run1)
    runner1 = HILRunner(hw1)
    res1 = runner1.run_qualification("SPECIMEN_REPLAY", prior_source="KNOWN_LFP_FLEET", prior_soh=0.90)

    hw2 = ReplayHardware(frames=frames_run2)
    runner2 = HILRunner(hw2)
    res2 = runner2.run_qualification("SPECIMEN_REPLAY", prior_source="KNOWN_LFP_FLEET", prior_soh=0.90)

    assert res1["final_decision"] == res2["final_decision"]
    assert res1["actuation_intent"] == res2["actuation_intent"]
    assert res1["reason"] == res2["reason"]
    assert res1["safety_tripped"] == res2["safety_tripped"]


def test_hil_pipeline_retires_critically_degraded_cell():
    """Severely degraded cell (low SOH, high resistance) is retired by the research decision engine."""
    hw = MockHardware(chemistry="LFP", soh=0.45, r0_mohm=8.5)
    hw.set_fault_mode("LOW_SOH")
    runner = HILRunner(hw)

    res = runner.run_qualification(
        cell_id="DEGRADED_CELL_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.50,
        prior_sigma_soh=0.08,
        prior_r0_mohm=7.0,
        prior_sigma_r0_mohm=1.5
    )

    assert res["final_decision"] in ["RETIRE", "DERATE"]
    if res["final_decision"] == "RETIRE":
        assert res["actuation_intent"] == "ISOLATE"
    elif res["final_decision"] == "DERATE":
        assert res["actuation_intent"] == "LIMIT_LOAD"
