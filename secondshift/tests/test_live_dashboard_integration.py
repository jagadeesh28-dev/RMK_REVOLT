"""
Live Hardware -> Backend -> NEXUS -> Frontend Dashboard Data Integration Tests.
Project: RMK REVOLT / SECONDShift Platform
Reference: MASTER PROMPT TEST-DASH-01 through TEST-DASH-20.

Non-Negotiable Data Policy Verification:
- Class A: Live Hardware Data (voltage, current, power, temperature, MOSFET, hardware state, fault, sequence)
- Class B: Derived Current Data (data quality, SOH, R0, marginal risk, decision trace)
- Class C: Historical / Frozen Evidence (Phase 5/6.1.1 baseline, strictly labeled)
"""

import time
import pytest
from typing import Dict, Any

from secondshift.hardware.telemetry_ingest import TelemetryIngestEngine, DeviceConnectionState
from secondshift.software.ui import status_adapter


@pytest.fixture
def ingest_engine() -> TelemetryIngestEngine:
    """Creates a clean TelemetryIngestEngine instance."""
    return TelemetryIngestEngine(
        authorized_devices={"NEXUS-ESP32-01"},
        telemetry_timeout_s=2.0,
        disconnect_timeout_s=5.0,
    )


def make_packet(seq: int, v: float, i: float, t: float, state: str = "IDLE",
                fault: str = "NONE", sensor_valid: bool = True, mosfet: bool = False,
                rssi: int = -45) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "device_id": "NEXUS-ESP32-01",
        "sequence": seq,
        "timestamp_ms": int(time.time() * 1000) + seq * 100,
        "raw_voltage_V": v,
        "voltage_V": v,
        "raw_current_A": i,
        "current_A": i,
        "raw_power_W": round(v * i, 3),
        "power_W": round(v * i, 3),
        "temperature_C": t,
        "mosfet": mosfet,
        "mosfet_state": "ON" if mosfet else "OFF",
        "state": state,
        "hardware_state": state,
        "fault": fault,
        "hardware_fault": (fault != "NONE" or state == "FAULT" or not sensor_valid),
        "sensor_valid": sensor_valid,
        "wifi_rssi": rssi
    }


# ===========================================================================
# TEST-DASH-01: Live Voltage Appears
# ===========================================================================
def test_dash_01_live_voltage_appears(ingest_engine):
    pkt = make_packet(seq=1, v=6.964, i=0.0, t=32.5)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["telemetry"]["voltage_v"] == pytest.approx(6.964, rel=1e-3)
    assert snap["data_classification"]["voltage"] == "CLASS_A_LIVE_HARDWARE"
    v_series = snap["graph_series"]["v"]
    assert v_series["source"] == "LIVE"
    assert v_series["metric"] == "voltage"
    assert len(v_series["points"]) == 1
    assert v_series["points"][0]["value"] == pytest.approx(6.964, rel=1e-3)


# ===========================================================================
# TEST-DASH-02: Live Current Appears (Zero is Real Measurement)
# ===========================================================================
def test_dash_02_live_current_appears(ingest_engine):
    pkt = make_packet(seq=1, v=6.964, i=0.000, t=32.5)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    # Zero is a real measurement and must be preserved, never replaced by historical values
    assert snap["telemetry"]["current_a"] == 0.000
    assert snap["data_classification"]["current"] == "CLASS_A_LIVE_HARDWARE"
    i_series = snap["graph_series"]["i"]
    assert i_series["source"] == "LIVE"
    assert i_series["points"][0]["value"] == 0.000


# ===========================================================================
# TEST-DASH-03: Live Power Appears
# ===========================================================================
def test_dash_03_live_power_appears(ingest_engine):
    pkt = make_packet(seq=1, v=7.200, i=1.500, t=31.0)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["telemetry"]["power_w"] == pytest.approx(10.800, rel=1e-3)
    p_series = snap["graph_series"]["p"]
    assert p_series["source"] == "LIVE"
    assert p_series["points"][0]["value"] == pytest.approx(10.800, rel=1e-3)


# ===========================================================================
# TEST-DASH-04: Live Temperature Appears
# ===========================================================================
def test_dash_04_live_temperature_appears(ingest_engine):
    pkt = make_packet(seq=1, v=6.964, i=0.0, t=32.56)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["telemetry"]["temperature_c"] == pytest.approx(32.56, rel=1e-3)
    t_series = snap["graph_series"]["t"]
    assert t_series["source"] == "LIVE"
    assert t_series["points"][0]["value"] == pytest.approx(32.56, rel=1e-3)


# ===========================================================================
# TEST-DASH-05: Live Hardware State Appears
# ===========================================================================
def test_dash_05_live_hardware_state_appears(ingest_engine):
    pkt_fault = make_packet(seq=1, v=6.964, i=0.0, t=32.5, state="FAULT", fault="SENSOR_INVALID", sensor_valid=False)
    ingest_engine.ingest_packet(pkt_fault)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["hardware_state"] == "FAULT"
    assert snap["nexus_hardware"]["hardware_fault"] is True


# ===========================================================================
# TEST-DASH-06: Live Fault Appears
# ===========================================================================
def test_dash_06_live_fault_appears(ingest_engine):
    pkt = make_packet(seq=1, v=6.964, i=0.0, t=32.5, state="FAULT", fault="SENSOR_INVALID", sensor_valid=False)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["fault_reason"] == "SENSOR_INVALID"
    assert snap["nexus_hardware"]["hardware_fault"] is True
    assert snap["safety_barrier"]["safety_tripped"] is True
    assert snap["safety_barrier"]["trip_reason"] == "SENSOR_INVALID"


# ===========================================================================
# TEST-DASH-07: Wi-Fi Status Appears
# ===========================================================================
def test_dash_07_wifi_status_appears(ingest_engine):
    pkt = make_packet(seq=1, v=6.964, i=0.0, t=32.5, rssi=-42)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["wifi_status"] == "CONNECTED"
    assert snap["nexus_hardware"]["backend_status"] == "CONNECTED"
    assert snap["nexus_hardware"]["wifi_rssi"] == -42


# ===========================================================================
# TEST-DASH-08: Sequence Appears
# ===========================================================================
def test_dash_08_sequence_appears(ingest_engine):
    pkt = make_packet(seq=388, v=6.964, i=0.0, t=32.5)
    ingest_engine.ingest_packet(pkt)

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["sequence"] == 388
    assert snap["telemetry"]["sequence_number"] == 388


# ===========================================================================
# TEST-DASH-09: Packet Loss Gaps Appear
# ===========================================================================
def test_dash_09_packet_loss_appears(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=10, v=6.964, i=0.0, t=32.5))
    ingest_engine.ingest_packet(make_packet(seq=15, v=6.964, i=0.0, t=32.5))

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["packet_gaps"] == 4


# ===========================================================================
# TEST-DASH-10: Fault Recovery Updates Frontend
# ===========================================================================
def test_dash_10_fault_recovery_updates_frontend(ingest_engine):
    # Step 1: Fault occurs
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5, state="FAULT", fault="SENSOR_INVALID", sensor_valid=False))
    snap1 = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap1["nexus_hardware"]["hardware_state"] == "FAULT"
    assert snap1["nexus_hardware"]["hardware_fault"] is True
    assert snap1["safety_barrier"]["safety_tripped"] is True

    # Step 2: Fault recovers
    ingest_engine.ingest_packet(make_packet(seq=2, v=6.964, i=0.0, t=32.5, state="IDLE", fault="NONE", sensor_valid=True))
    snap2 = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap2["nexus_hardware"]["hardware_state"] == "IDLE"
    assert snap2["nexus_hardware"]["hardware_fault"] is False
    assert snap2["nexus_hardware"]["fault_reason"] == "NONE"
    assert snap2["safety_barrier"]["safety_tripped"] is False


# ===========================================================================
# TEST-DASH-11: Historical Data is Labelled HISTORICAL
# ===========================================================================
def test_dash_11_historical_data_is_labelled_historical(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    hb = snap["historical_baseline"]
    assert hb is not None
    assert "HISTORICAL" in hb["status"]
    assert "Phase 5" in hb["source"]
    assert snap["data_classification"]["validation_baseline"] == "CLASS_C_HISTORICAL_EVIDENCE"


# ===========================================================================
# TEST-DASH-12: Historical Data Never Replaces Live Data
# ===========================================================================
def test_dash_12_historical_data_never_replaces_live_data(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    # Live voltage must remain 6.964 V, never overwritten by historical nominal 3.2V
    assert snap["telemetry"]["voltage_v"] == pytest.approx(6.964, rel=1e-3)
    assert snap["graph_series"]["v"]["points"][0]["value"] == pytest.approx(6.964, rel=1e-3)


# ===========================================================================
# TEST-DASH-13: Missing SOH Displays Unavailable State
# ===========================================================================
def test_dash_13_missing_soh_displays_unavailable_state(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    assert snap["bayesian"]["soh_estimate"] is None
    assert snap["bayesian"]["soh_uncertainty"] is None
    soh_series = snap["graph_series"]["soh"]
    assert soh_series["source"] == "UNAVAILABLE"
    assert "INSUFFICIENT" in soh_series["reason"] or "NO CURRENT" in soh_series["reason"]


# ===========================================================================
# TEST-DASH-14: Missing R0 Displays Unavailable State
# ===========================================================================
def test_dash_14_missing_r0_displays_unavailable_state(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    assert snap["bayesian"]["r0_mohm"] is None
    r0_series = snap["graph_series"]["r0"]
    assert r0_series["source"] == "UNAVAILABLE"
    assert "INSUFFICIENT" in r0_series["reason"] or "NO CURRENT" in r0_series["reason"]


# ===========================================================================
# TEST-DASH-15: Missing Risk Trace Displays Unavailable State
# ===========================================================================
def test_dash_15_missing_risk_trace_displays_unavailable_state(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    risk_series = snap["graph_series"]["risk"]
    assert risk_series["source"] == "UNAVAILABLE"
    assert len(risk_series["points"]) == 0
    assert "NO CURRENT RISK TRACE" in risk_series["reason"]


# ===========================================================================
# TEST-DASH-16: No Fake Graph Points are Generated
# ===========================================================================
def test_dash_16_no_fake_graph_points_are_generated(ingest_engine):
    # Ingest exactly 3 real packets
    for s in [1, 2, 3]:
        ingest_engine.ingest_packet(make_packet(seq=s, v=6.90 + s * 0.01, i=0.0, t=30.0))

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    v_series = snap["graph_series"]["v"]
    # Total points must exactly equal 3 — zero synthetic interpolation points
    assert len(v_series["points"]) == 3
    assert v_series["total_points"] == 3


# ===========================================================================
# TEST-DASH-17: Decision Trace Appears When Real Decision Events Exist
# ===========================================================================
def test_dash_17_decision_trace_appears_when_real_decision_events_exist():
    mock_events = [
        {
            "event_type": "QUALIFICATION_DECISION",
            "data": {
                "stage": "STAGE 0 TRIAGE",
                "decision": "TEST",
                "reason": "Initial screening test required",
                "marginal_risk": 0.045,
                "state_estimate": {"mu_soh": 0.88, "sigma_soh": 0.08, "mu_r0_mohm": 42.1}
            }
        },
        {
            "event_type": "QUALIFICATION_DECISION",
            "data": {
                "stage": "LOOP ITERATION 0",
                "decision": "OPERATE",
                "reason": "Battery meets secondary life criteria",
                "marginal_risk": 0.005,
                "state_estimate": {"mu_soh": 0.91, "sigma_soh": 0.02, "mu_r0_mohm": 39.5}
            }
        }
    ]
    res = {
        "final_decision": "OPERATE",
        "operational_decision": "OPERATE",
        "safety_tripped": False
    }
    snap = status_adapter.build_status_snapshot(res, mock_events)
    assert len(snap["decision_trace"]) == 2
    assert snap["decision_trace"][0]["stage"] == "STAGE 0 TRIAGE"
    assert snap["decision_trace"][0]["marginal_risk"] == 0.045
    assert snap["decision_trace"][1]["decision"] == "OPERATE"


# ===========================================================================
# TEST-DASH-18: Decision Trace Remains Unavailable When No Qualification Run Exists
# ===========================================================================
def test_dash_18_decision_trace_remains_unavailable_when_no_qualification_run(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5))
    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    assert len(snap["decision_trace"]) == 0
    assert snap["decision_trace_status"] == "NO_QUALIFICATION_DECISION_RECORDED"
    assert snap["session"]["qualification_lifecycle"] == "MONITORING_ONLY"
    assert snap["session"]["qualification_status"] == "NOT_STARTED"


# ===========================================================================
# TEST-DASH-19: API Status and Live Telemetry Remain Consistent
# ===========================================================================
def test_dash_19_api_status_and_live_telemetry_remain_consistent(ingest_engine):
    ingest_engine.ingest_packet(make_packet(seq=142, v=6.850, i=0.500, t=33.1, state="IDLE"))

    live_snap = ingest_engine.get_live_snapshot()
    dash_snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)

    assert live_snap["nexus_hardware"]["sequence"] == dash_snap["nexus_hardware"]["sequence"] == 142
    assert live_snap["electrical"]["voltage_v"] == dash_snap["telemetry"]["voltage_v"] == pytest.approx(6.850, rel=1e-3)
    assert live_snap["hardware"]["hardware_state"] == dash_snap["nexus_hardware"]["hardware_state"] == "IDLE"
    assert live_snap["hardware"]["hardware_fault"] == dash_snap["nexus_hardware"]["hardware_fault"] is False


# ===========================================================================
# TEST-DASH-20: Frontend Does Not Show Stale FAULT After Real Recovery
# ===========================================================================
def test_dash_20_frontend_does_not_show_stale_fault_after_real_recovery(ingest_engine):
    # Sequence of events: IDLE -> FAULT -> RECOVERY (IDLE)
    ingest_engine.ingest_packet(make_packet(seq=1, v=6.964, i=0.0, t=32.5, state="IDLE", fault="NONE"))
    assert ingest_engine.get_connection_status() == DeviceConnectionState.CONNECTED

    ingest_engine.ingest_packet(make_packet(seq=2, v=6.964, i=0.0, t=32.5, state="FAULT", fault="SENSOR_INVALID", sensor_valid=False))
    assert ingest_engine.get_connection_status() == DeviceConnectionState.FAULT

    ingest_engine.ingest_packet(make_packet(seq=3, v=6.964, i=0.0, t=32.5, state="IDLE", fault="NONE", sensor_valid=True))
    assert ingest_engine.get_connection_status() == DeviceConnectionState.CONNECTED

    snap = status_adapter.build_live_telemetry_snapshot(ingest_engine)
    assert snap["nexus_hardware"]["hardware_state"] == "IDLE"
    assert snap["nexus_hardware"]["hardware_fault"] is False
    assert snap["nexus_hardware"]["fault_reason"] == "NONE"
    assert snap["safety_barrier"]["safety_tripped"] is False
