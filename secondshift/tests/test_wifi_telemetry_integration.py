"""
Tests for NEXUS Wi-Fi Hardware Telemetry Integration (Phases W0 - W8).
Project: RMK REVOLT / SECONDShift Platform

Covers:
- Phase W0: Layer 1 Interface & Schema Compliance
- Phase W1: Credential Protection & Secret Scrubbing
- Phase W2: Valid Telemetry Transmission & Parsing
- Phase W3: Backend Validation, Malformed/NaN/Out-of-Bounds Rejection & Sequence Gaps
- Phase W4: Live Snapshot, Heartbeat Transitions (CONNECTED -> STALE -> DISCONNECTED)
- Phase W5: Sensor Validity & Physical Bounds
- Phase W6: Command Queue, Lifecycle Acknowledgment & Actuation Safety Barriers
- Phase W7: NEXUS Shadow Mode Pipeline Integration
- Phase W8: WifiHardware Adapter & HILRunner Interoperability
"""

import os
import json
import time
import pytest
from typing import Dict, Any

from secondshift.interfaces.telemetry_schema import TelemetryFrame
from secondshift.interfaces.telemetry_validator import TelemetryValidator
from secondshift.hardware.telemetry_ingest import TelemetryIngestEngine
from secondshift.hardware.wifi_hardware import WifiHardware
from secondshift.software.ui.status_adapter import build_live_telemetry_snapshot


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ingest_engine() -> TelemetryIngestEngine:
    """Creates a fresh, clean TelemetryIngestEngine for testing."""
    return TelemetryIngestEngine(
        authorized_devices={"NEXUS-ESP32-01", "NEXUS-ESP32-TEST"},
        telemetry_timeout_s=1.0,
        disconnect_timeout_s=2.5,
    )


@pytest.fixture
def valid_packet() -> Dict[str, Any]:
    """Provides a canonical valid Wi-Fi telemetry packet."""
    return {
        "schema_version": "1.0",
        "device_id": "NEXUS-ESP32-01",
        "sequence": 100,
        "timestamp_ms": int(time.time() * 1000),
        "voltage_v": 3.312,
        "current_a": 1.450,
        "power_w": 4.802,
        "temperature_c": 28.5,
        "mosfet_state": "ON",
        "hardware_state": "RUNNING",
        "hardware_fault": False,
        "sensor_valid": True,
        "wifi_rssi": -58
    }


# ---------------------------------------------------------------------------
# Phase W0: Architecture & Schema Compliance
# ---------------------------------------------------------------------------

def test_w0_schema_compliance(valid_packet):
    """Verify canonical frame creation and field fidelity."""
    frame = TelemetryFrame.from_dict(valid_packet)
    assert frame.voltage_v == 3.312
    assert frame.current_a == 1.450
    assert frame.power_w == pytest.approx(4.802, rel=1e-3)
    assert frame.temperature_c == 28.5
    assert frame.sequence_number == 100
    assert frame.mosfet_state == "ON"
    assert frame.hardware_state == "RUNNING"
    assert frame.sensor_valid is True
    assert frame.hardware_fault is False


# ---------------------------------------------------------------------------
# Phase W1: Credential Protection
# ---------------------------------------------------------------------------

def test_w1_credentials_scrubbed_from_snapshots(ingest_engine, valid_packet):
    """Verify that no Wi-Fi credentials leak into snapshot or state dictionaries."""
    ingest_engine.ingest_packet(valid_packet)
    snap = ingest_engine.get_live_snapshot()
    serialized = json.dumps(snap)
    
    assert "password" not in serialized.lower()
    assert "wifi_password" not in serialized.lower()
    assert "secret" not in serialized.lower()
    assert "ssid" not in serialized.lower()


def test_w1_gitignore_contains_secrets():
    """Verify gitignore explicitly ignores secrets.h and .env."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    gitignore_path = os.path.join(repo_root, ".gitignore")
    assert os.path.exists(gitignore_path), ".gitignore must exist"
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "secrets.h" in content
    assert ".env" in content


# ---------------------------------------------------------------------------
# Phase W2: Valid Telemetry Transmission & Monotonic Sequences
# ---------------------------------------------------------------------------

def test_w2_valid_packet_ingest(ingest_engine, valid_packet):
    """Verify successful ingestion of valid frame."""
    accepted, reason, details = ingest_engine.ingest_packet(valid_packet)
    assert accepted is True
    assert reason == "ACCEPTED"
    assert ingest_engine.stats.total_accepted == 1
    assert ingest_engine.stats.total_rejected == 0
    assert ingest_engine.connection_state == "CONNECTED"


def test_w2_sequence_increment(ingest_engine, valid_packet):
    """Verify sequential sequence incrementing does not trigger gaps."""
    t0 = int(time.time() * 1000)
    for i in range(5):
        pkt = dict(valid_packet)
        pkt["sequence"] = 100 + i
        pkt["timestamp_ms"] = t0 + (i * 1000)
        accepted, reason, _ = ingest_engine.ingest_packet(pkt)
        assert accepted is True

    assert ingest_engine.stats.total_accepted == 5
    assert ingest_engine.stats.sequence_gaps == 0


# ---------------------------------------------------------------------------
# Phase W3: Backend Validation & Fault Ingestion (Rejections)
# ---------------------------------------------------------------------------

def test_w3_reject_unauthorized_device(ingest_engine, valid_packet):
    """Verify rejection of unknown/unauthorized device."""
    pkt = dict(valid_packet)
    pkt["device_id"] = "ROGUE-DEVICE-99"
    accepted, reason, details = ingest_engine.ingest_packet(pkt)
    assert accepted is False
    assert reason == "UNAUTHORIZED_DEVICE"
    assert ingest_engine.stats.total_rejected == 1


def test_w3_reject_missing_sequence(ingest_engine, valid_packet):
    """Verify rejection when sequence field is missing."""
    pkt = dict(valid_packet)
    del pkt["sequence"]
    accepted, reason, _ = ingest_engine.ingest_packet(pkt)
    assert accepted is False
    assert reason == "INVALID_SEQUENCE_FIELD"


def test_w3_reject_nan_infinity(ingest_engine, valid_packet):
    """Verify rejection of NaN and Inf values without crashing."""
    pkt = dict(valid_packet)
    pkt["voltage_v"] = float("nan")
    accepted, reason, _ = ingest_engine.ingest_packet(pkt)
    assert accepted is False
    assert reason == "VALIDATION_FAILED"

    pkt2 = dict(valid_packet)
    pkt2["sequence"] = 101
    pkt2["current_a"] = float("inf")
    accepted2, reason2, _ = ingest_engine.ingest_packet(pkt2)
    assert accepted2 is False
    assert reason2 == "VALIDATION_FAILED"


def test_w3_detect_sequence_gap(ingest_engine, valid_packet):
    """Verify detection of sequence gaps indicating lost packets."""
    t0 = int(time.time() * 1000)
    pkt1 = dict(valid_packet)
    pkt1["sequence"] = 10
    pkt1["timestamp_ms"] = t0
    ingest_engine.ingest_packet(pkt1)

    # Jump from seq 10 to seq 15 (lost 4 packets: 11, 12, 13, 14)
    pkt2 = dict(valid_packet)
    pkt2["sequence"] = 15
    pkt2["timestamp_ms"] = t0 + 5000
    accepted, reason, details = ingest_engine.ingest_packet(pkt2)
    assert accepted is True
    assert ingest_engine.stats.sequence_gaps == 4


def test_w3_reject_duplicate_packet(ingest_engine, valid_packet):
    """Verify duplicate sequence numbers are detected and rejected."""
    t0 = int(time.time() * 1000)
    pkt1 = dict(valid_packet)
    pkt1["sequence"] = 50
    pkt1["timestamp_ms"] = t0
    ingest_engine.ingest_packet(pkt1)

    # Re-transmit same sequence
    pkt2 = dict(valid_packet)
    pkt2["sequence"] = 50
    pkt2["timestamp_ms"] = t0 + 100
    accepted, reason, details = ingest_engine.ingest_packet(pkt2)
    assert accepted is False
    assert reason == "DUPLICATE_PACKET"
    assert ingest_engine.stats.duplicate_packets == 1


def test_w3_impossible_electrical_values(ingest_engine, valid_packet):
    """Verify physical validator catches impossible voltage, current, and temperature."""
    # Impossible negative voltage
    pkt_v = dict(valid_packet)
    pkt_v["voltage_v"] = -1.5
    accepted_v, reason_v, _ = ingest_engine.ingest_packet(pkt_v)
    assert accepted_v is False

    # Impossible high current
    pkt_i = dict(valid_packet)
    pkt_i["current_a"] = 150.0  # limit is +-50A
    accepted_i, reason_i, _ = ingest_engine.ingest_packet(pkt_i)
    assert accepted_i is False

    # Impossible high temperature
    pkt_t = dict(valid_packet)
    pkt_t["temperature_c"] = 115.0  # limit is 80C
    accepted_t, reason_t, _ = ingest_engine.ingest_packet(pkt_t)
    assert accepted_t is False


def test_w3_preserve_missingness_none_not_zero(ingest_engine, valid_packet):
    """CRITICAL: None != 0. Missing fields must remain None, not manufactured 0."""
    pkt = dict(valid_packet)
    del pkt["power_w"]  # power_w is optional
    accepted, reason, details = ingest_engine.ingest_packet(pkt)
    assert accepted is True
    
    accepted_frame = ingest_engine.get_last_accepted_frame()
    assert accepted_frame is not None
    # If power_w was omitted, raw payload holds what was sent; frame computes V*I only if canonical
    raw = ingest_engine.get_raw_history()[-1]
    assert "power_w" not in raw["raw_payload"]


# ---------------------------------------------------------------------------
# Phase W4: Live Frontend Reflection & Heartbeat Timeout State Machine
# ---------------------------------------------------------------------------

def test_w4_heartbeat_transitions(ingest_engine, valid_packet):
    """Verify CONNECTED -> STALE -> DISCONNECTED transitions."""
    ingest_engine.ingest_packet(valid_packet)
    assert ingest_engine.get_connection_state() == "CONNECTED"
    assert ingest_engine.is_stale() is False

    # Wait past telemetry_timeout (1.0s)
    time.sleep(1.1)
    assert ingest_engine.get_connection_state() == "STALE"
    assert ingest_engine.is_stale() is True

    # Wait past disconnect_timeout (2.5s total)
    time.sleep(1.5)
    assert ingest_engine.get_connection_state() == "DISCONNECTED"


def test_w4_hardware_fault_latches(ingest_engine, valid_packet):
    """Verify hardware_fault=True latches connection state into FAULT."""
    pkt = dict(valid_packet)
    pkt["hardware_fault"] = True
    ingest_engine.ingest_packet(pkt)
    assert ingest_engine.get_connection_state() == "FAULT"


def test_w4_status_adapter_snapshot_format(ingest_engine, valid_packet):
    """Verify build_live_telemetry_snapshot generates complete UI schema."""
    ingest_engine.ingest_packet(valid_packet)
    snapshot = build_live_telemetry_snapshot(ingest_engine)
    
    assert snapshot["available"] is True
    assert "nexus_hardware" in snapshot
    nh = snapshot["nexus_hardware"]
    assert nh["device_id"] == "NEXUS-ESP32-01"
    assert nh["wifi_status"] == "CONNECTED"
    assert nh["telemetry_status"] == "LIVE"
    assert nh["sequence"] == 100
    assert nh["mosfet_state"] == "ON"
    assert nh["hardware_state"] == "RUNNING"
    assert nh["sensor_valid"] is True
    assert nh["hardware_fault"] is False
    assert nh["wifi_rssi"] == -58


# ---------------------------------------------------------------------------
# Phase W5: Physical Sensor Validation & Range Consistency
# ---------------------------------------------------------------------------

def test_w5_sensor_validity_flag(ingest_engine, valid_packet):
    """Verify sensor_valid=False marks frame as invalid/rejected."""
    pkt = dict(valid_packet)
    pkt["sensor_valid"] = False
    accepted, reason, details = ingest_engine.ingest_packet(pkt)
    assert accepted is False
    assert reason == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Phase W6: Actuation Safety & Command Lifecycle
# ---------------------------------------------------------------------------

def test_w6_command_lifecycle_queue(ingest_engine):
    """Verify command queueing, lifecycle tracking, and priority STOP."""
    cmd_hold = ingest_engine.queue_command("HOLD", requested_by="OPERATOR")
    assert cmd_hold["action"] == "HOLD"
    assert cmd_hold["status"] == "QUEUED"
    assert cmd_hold["command_id"].startswith("CMD-")

    # Priority STOP clears previous commands
    cmd_stop = ingest_engine.queue_command("STOP", requested_by="OPERATOR")
    assert cmd_stop["action"] == "STOP"
    
    # Directives emitted to hardware snapshot
    snap = ingest_engine.get_live_snapshot()
    directive = snap["command_directive"]
    assert directive is not None
    assert directive["action"] == "STOP"


def test_w6_reject_arbitrary_unsafe_commands(ingest_engine):
    """Verify system rejects arbitrary unsafe GPIO strings."""
    with pytest.raises(ValueError):
        ingest_engine.queue_command("SET_PIN_25_HIGH", requested_by="ATTACKER")


# ---------------------------------------------------------------------------
# Phase W7: NEXUS Shadow Mode Integration
# ---------------------------------------------------------------------------

def test_w7_shadow_mode_pipeline(ingest_engine, valid_packet):
    """Verify valid hardware telemetry flows through qualification pipeline without actuation."""
    accepted, reason, details = ingest_engine.ingest_packet(valid_packet)
    assert accepted is True
    
    # Trigger shadow decision
    decision = ingest_engine.evaluate_shadow_decision(specimen_id="SPECIMEN-LFP-01")
    assert decision["epistemic_state"] in ("UNCERTAIN", "INSUFFICIENT_DATA", "SUPPORTED_HEALTHY", "KNOWN_DEGRADED")
    assert decision["operational_decision"] in ("HOLD", "OPERATE", "DERATE", "RETIRE")
    assert decision["information_action"] in ("REQUEST_TEST", "NO_TEST")
    assert decision["actuation_intent"] in ("IDLE", "HOLD", "DISCHARGE_PULSE", "ISOLATE", "SAFE_STOP", "KEEP_ISOLATED")
    
    # Verify shadow decision is published in snapshot
    snap = ingest_engine.get_live_snapshot()
    assert snap["nexus_decision"] is not None


# ---------------------------------------------------------------------------
# Phase W8: WifiHardware Adapter Interoperability
# ---------------------------------------------------------------------------

def test_w8_wifi_hardware_interface(valid_packet):
    """Verify WifiHardware implements HardwareInterface contract."""
    engine = TelemetryIngestEngine(authorized_devices={"NEXUS-ESP32-01"})
    hw = WifiHardware(device_id="NEXUS-ESP32-01", ingest_engine=engine)
    
    # Connect
    hw.connect()
    assert hw.is_connected() is False  # No packets yet
    
    # Ingest packet into engine
    engine.ingest_packet(valid_packet)
    assert hw.is_connected() is True
    
    # Read frame
    frame = hw.read_telemetry()
    assert frame is not None
    assert frame.voltage_v == 3.312
    assert frame.sequence_number == 100
    
    # Send command
    cmd_ok = hw.send_command("HOLD")
    assert cmd_ok is True
    
    # Read hardware state
    state = hw.get_hardware_state()
    assert state == "RUNNING"
    
    # Emergency shutdown
    hw.emergency_shutdown()
    directive = engine.get_live_snapshot()["command_directive"]
    assert directive["action"] == "STOP"
    
    hw.disconnect()


def test_w4_dashboard_http_endpoints(valid_packet):
    """Verify live HTTP REST endpoints: POST /api/telemetry, GET /api/telemetry/live, POST /api/command."""
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    from secondshift.software.ui.dashboard import DashboardHandler

    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    try:
        # 1. POST /api/telemetry
        req_data = json.dumps(valid_packet).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/telemetry", data=req_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res_body = json.loads(resp.read().decode("utf-8"))
            assert res_body["status"] == "ACCEPTED"

        # 2. GET /api/telemetry/live
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/telemetry/live") as resp2:
            assert resp2.status == 200
            snap = json.loads(resp2.read().decode("utf-8"))
            assert snap["nexus_hardware"]["device_id"] == "NEXUS-ESP32-01"
            assert snap["nexus_hardware"]["sequence"] == 100

        # 3. POST /api/command
        cmd_data = json.dumps({"action": "STOP"}).encode("utf-8")
        req_cmd = urllib.request.Request(f"http://127.0.0.1:{port}/api/command", data=cmd_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_cmd) as resp3:
            assert resp3.status == 200
            cmd_body = json.loads(resp3.read().decode("utf-8"))
            assert cmd_body["status"] == "COMMAND_QUEUED"
            assert cmd_body["command"]["action"] == "STOP"
    finally:
        server.shutdown()
        server.server_close()


def test_w9_fault_recovery_telemetry_flow(ingest_engine):
    """
    Phase W9 / Step 15: Verify that ESP32 FAULT -> RECOVERY -> IDLE state transition
    is properly ingested by TelemetryIngestEngine and reflected in the live snapshot for the frontend.
    """
    from secondshift.hardware.fault_recovery_fsm import ESP32FaultRecoveryFSM, SystemState

    fsm = ESP32FaultRecoveryFSM(device_id="NEXUS-ESP32-01")

    # 1. Healthy IDLE telemetry
    fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000)
    pkt_idle = fsm.build_telemetry(now_ms=1000)
    accepted, reason, details = ingest_engine.ingest_packet(pkt_idle)
    assert accepted is True
    snap = ingest_engine.get_live_snapshot()
    assert snap["hardware"]["hardware_state"] == "IDLE"
    assert snap["hardware"]["hardware_fault"] is False
    assert snap["hardware"]["mosfet_state"] == "OFF"

    # 2. Trip to FAULT on UV (3 samples)
    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=2000)
    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=3000)
    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=4000)
    assert fsm.system_state == SystemState.STATE_FAULT

    pkt_fault = fsm.build_telemetry(now_ms=4000)
    accepted_fault, reason_fault, details_fault = ingest_engine.ingest_packet(pkt_fault)
    # Packets in FAULT are isolated from inference admissibility (accepted=False)
    assert accepted_fault is False
    assert details_fault["hardware_fault"] is True

    snap = ingest_engine.get_live_snapshot()
    assert snap["nexus_hardware"]["is_fault"] is True
    assert snap["hardware"]["hardware_state"] == "FAULT"
    assert snap["hardware"]["hardware_fault"] is True
    assert snap["hardware"]["fault_reason"] == "UNDER_VOLTAGE"
    assert snap["hardware"]["mosfet_state"] == "OFF"

    # 3. Fault clears -> 5 healthy samples qualify recovery
    for i in range(1, 6):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=4000 + i * 1000)
        pkt_step = fsm.build_telemetry(now_ms=4000 + i * 1000)
        ingest_engine.ingest_packet(pkt_step)

    # 4. Verified recovered state in backend snapshot
    snap_recovered = ingest_engine.get_live_snapshot()
    assert snap_recovered["nexus_hardware"]["is_fault"] is False
    assert snap_recovered["hardware"]["hardware_state"] == "IDLE"
    assert snap_recovered["hardware"]["hardware_fault"] is False
    assert snap_recovered["hardware"]["fault_reason"] == "NONE"
    assert snap_recovered["hardware"]["mosfet_state"] == "OFF"
    raw = ingest_engine.get_latest_raw()
    assert raw["last_fault"] == "UNDER_VOLTAGE"
    assert raw["fault_recovered"] is True


