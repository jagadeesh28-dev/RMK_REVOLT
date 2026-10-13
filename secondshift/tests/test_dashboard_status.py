"""Tests for the status adapter and dashboard endpoints (no hardware required)."""
import http.server
import json
import os
import threading
import urllib.request

import pytest

from secondshift.software.ui import dashboard as dash
from secondshift.software.ui import status_adapter as sa

RESULT = {
    "cell_id": "CELL_X", "final_decision": "OPERATE", "actuation_intent": "OPERATE_FULL",
    "reason": "ok", "command_id": "cmd-1", "safety_tripped": False, "system_state": "OPERATE",
    "tests_executed_count": 1, "elapsed_time_s": 0.5, "final_soh_estimate": 0.9,
    "final_soh_uncertainty": 0.03, "final_r0_mohm": 2.0, "final_chemistry": "LFP",
    "final_chem_confidence": "KNOWN",
    "ground_truth": {"true_soh": 0.5},  # must never be copied
}
EVENTS = [
    {"event_type": "TELEMETRY_EVALUATION", "data": {
        "voltage_v": 13.1, "current_a": 0.0, "temperature_c": 25.0, "sequence_number": 3,
        "frame_timestamp": 1.5, "is_valid": True, "quality": "GOOD", "errors": [], "warnings": ["w"]}},
    {"event_type": "QUALIFICATION_DECISION", "data": {
        "cell_id": "CELL_X", "stage": "LOOP_ITERATION_0", "decision": "OPERATE", "reason": "r",
        "state_estimate": {"mu_soh": 0.9, "sigma_soh": 0.03, "mu_r0_mohm": 2.0, "true_soh": 0.1},
        "marginal_risk": 0.002}},
    {"event_type": "ACTUATION_COMMAND", "data": {"acknowledged": True}},
]
FORBIDDEN = ("ground_truth", "true_", "characterized_timestamp", "acknowledged")


def test_snapshot_maps_result_and_events():
    s = sa.build_status_snapshot(RESULT, EVENTS, "mock", now=0)
    assert (s["source"], s["mode"], s["cell_id"]) == ("secondshift_cli", "mock", "CELL_X")
    assert s["decision"]["actuation_intent"] == "OPERATE_FULL" and s["decision"]["safety_tripped"] is False
    assert s["bayesian"] == {"soh_estimate": 0.9, "soh_uncertainty": 0.03, "r0_mohm": 2.0}
    assert s["chemistry"]["final_chemistry"] == "LFP"
    assert s["telemetry"]["voltage_v"] == 13.1 and s["telemetry"]["is_valid"] is True
    assert s["telemetry"]["warnings"] == ["w"]
    assert s["decision_trace"][0]["marginal_risk"] == 0.002 and s["decision_trace"][0]["soh_estimate"] == 0.9


@pytest.mark.parametrize("result,events", [({}, None), (None, []), ({"cell_id": "A"}, [{"bad": 1}, {"event_type": "X", "data": 5}])])
def test_missing_fields_do_not_crash(result, events):
    s = sa.build_status_snapshot(result, events, None)
    assert s["mode"] is None and s["bayesian"]["soh_estimate"] is None
    assert s["telemetry"]["voltage_v"] is None and s["decision_trace"] == []


def test_no_ground_truth_in_snapshot():
    dumped = json.dumps(sa.build_status_snapshot(RESULT, EVENTS, "mock")).lower()
    assert not any(f in dumped for f in FORBIDDEN)


def test_adapter_never_references_benchmark_file():
    src = open(sa.__file__, encoding="utf-8").read()
    assert "physical_benchmark_results" not in src


def test_atomic_write_and_read(tmp_path):
    p = str(tmp_path / "last_run_status.json")
    sa.record_last_run(RESULT, EVENTS, "replay", p)
    assert os.listdir(tmp_path) == ["last_run_status.json"]  # no temp leftovers
    got = sa.read_status_snapshot(p)
    assert got["available"] is True and got["mode"] == "replay"


def test_read_missing_or_corrupt(tmp_path):
    assert sa.read_status_snapshot(str(tmp_path / "nope.json"))["available"] is False
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert sa.read_status_snapshot(str(bad))["status"] == "SNAPSHOT_UNREADABLE"


def test_read_strips_forbidden_keys_from_tampered_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"cell_id": "A", "ground_truth": {"true_soh": 1}, "x": {"true_r0": 1}}))
    dumped = json.dumps(sa.read_status_snapshot(str(p)))
    assert "ground_truth" not in dumped and "true_" not in dumped


def test_benchmarks_strip_ground_truth():
    raw = {"E01": {"objective": "o", "decision": "OPERATE", "passed": True, "observations": "obs",
                   "ground_truth": {"true_soh": 0.94, "characterized_timestamp": 1},
                   "measurements": {"soh": 0.9, "true_r0_mohm": 1.9}},
           "E13": {"ground_truth": "N/A", "decision": "SAFE_SHUTDOWN"}}
    out = dash.sanitize_benchmarks(raw)
    dumped = json.dumps(out)
    assert out["count"] == 2 and out["scenarios"][0]["measurements"] == {"soh": 0.9}
    assert not any(f in dumped for f in ("ground_truth", "true_", "characterized_timestamp"))
    assert "not live physical hardware validation" in out["notice"]


@pytest.fixture
def port(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "STATUS_PATH", str(tmp_path / "last_run_status.json"))
    monkeypatch.setattr(dash, "BENCHMARK_PATH", str(tmp_path / "bench.json"))
    monkeypatch.setattr(dash, "GLOBAL_INGEST_ENGINE", None)
    httpd = None
    for p in [18080, 18081, 18082, 18083, 18084, 0]:
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", p), dash.DashboardHandler)
            break
        except (PermissionError, OSError):
            continue
    if httpd is None:
        pytest.skip("No open loopback port available for test")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def test_api_status_absent_and_present(port, tmp_path):
    code, body = _get(port, "/api/status")
    assert code == 200 and json.loads(body)["available"] is False
    sa.record_last_run(RESULT, EVENTS, "mock", str(tmp_path / "last_run_status.json"))
    j = json.loads(_get(port, "/api/status")[1])
    assert j["available"] is True and j["cell_id"] == "CELL_X"
    assert "benchmark" not in json.dumps(j).lower()
    assert not any(f in body.lower() + json.dumps(j).lower() for f in ("ground_truth", "true_"))


def test_api_benchmarks_endpoint(port, tmp_path):
    (tmp_path / "bench.json").write_text(json.dumps({"E01": {"decision": "OPERATE", "ground_truth": {"true_soh": 1}}}))
    body = _get(port, "/api/benchmarks")[1]
    assert json.loads(body)["count"] == 1 and "ground_truth" not in body and "true_" not in body


def test_html_has_no_hardcoded_fake_state_and_is_clean():
    html = dash.HTML_TEMPLATE
    assert html.isascii() and "\u00e2\u20ac" not in html
    for fake in ("13.24", "99.8", "CELL_1_HEALTHY", "ARMED", "LM393", "TPS3823", "CLOSED (12V)", "11.8", "92.0%", "1.97"):
        assert fake not in html
    assert "Historical Recorded Qualification Results" in html


def test_phase3_status_snapshot_canonical_sections():
    """Verify that Phase 3 canonical sections (Battery, Session, DataQuality, Epistemic, OperationalDecision, InfoAction, Prognostics) are populated."""
    result = {
        "cell_id": "SPECIMEN_01",
        "battery_id": "BAT_NMC_01",
        "declared_chemistry": "NMC",
        "final_decision": "HOLD",
        "operational_decision": "HOLD",
        "information_action": "REQUEST_TEST",
        "recommended_test": "QUICK_PULSE_R0",
        "epistemic_state": "INSUFFICIENT_DATA",
        "reason_codes": ["INSUFFICIENT_DATA_FOR_RUL", "ADDITIONAL_INFORMATION_VALUE"],
        "reason": "Diagnostic pulse needed to disambiguate internal resistance",
        "actuation_intent": "SAFE_STANDBY",
        "safety_tripped": False,
        "final_soh_estimate": 0.88,
        "final_soh_uncertainty": 0.04,
        "final_r0_mohm": None,  # Not yet evaluated
        "pulse_valid": False,
        "current_flow_valid": False,
        "session_id": "SESS_QUAL_001",
        "protocol_id": "QUAL_RAPID_V2",
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.65, "current_a": 0.0, "temperature_c": 24.5, "sequence_number": 10,
            "is_valid": True, "quality": "GOOD", "errors": [], "warnings": []
        }},
        {"event_type": "PULSE_VALIDATION", "data": {
            "pulse_valid": False, "current_flow_valid": False,
            "admissibility_reasons": ["CURRENT_FLOW_BELOW_MINIMUM"],
            "delta_v_total": None, "delta_v_ohmic": None
        }}
    ]
    s = sa.build_status_snapshot(result, events, mode="mock", now=100.0)

    # Section A: Battery Identity
    assert s["battery"]["battery_id"] == "BAT_NMC_01"
    assert s["battery"]["declared_chemistry"] == "NMC"
    assert s["battery"]["software_version"] == "SECONDShift-v2.0"

    # Section B: Live Telemetry with Power
    assert s["telemetry"]["voltage_v"] == 3.65
    assert s["telemetry"]["current_a"] == 0.0
    assert s["telemetry"]["power_w"] == 0.0  # 3.65 * 0.0 = 0.0 W

    # Section C: Data Quality
    assert s["data_quality"]["sensor_valid"] is True
    assert s["data_quality"]["pulse_valid"] is False
    assert s["data_quality"]["current_flow_valid"] is False
    assert "CURRENT_FLOW_BELOW_MINIMUM" in s["data_quality"]["reasons"]
    assert s["data_quality"]["delta_v_total"] is None

    # Section D: Test Progress
    assert s["session"]["session_id"] == "SESS_QUAL_001"
    assert s["session"]["protocol_id"] == "QUAL_RAPID_V2"

    # Section E: Chemistry Declared vs Inferred
    assert s["chemistry"]["declared_chemistry"] == "NMC"
    assert s["chemistry"]["inferred_chemistry"] is None  # Not yet inferred
    assert s["chemistry"]["confidence_state"] == "NOT_YET_ESTIMATED"

    # Section F: State Estimation
    assert s["bayesian"]["soh_estimate"] == 0.88
    assert s["bayesian"]["r0_mohm"] is None  # Never converted to 0.0!

    # Section G: Prognostics Placeholder
    assert s["prognostics"]["rul_cycles"] is None
    assert s["prognostics"]["rul_status"] == "NOT YET IMPLEMENTED"

    # Section H, I, J: Epistemic State, Operational Decision, Information Action
    assert s["epistemic"]["epistemic_state"] == "INSUFFICIENT_DATA"
    assert s["operational_decision"]["decision"] == "HOLD"
    assert s["information_action"]["action"] == "REQUEST_TEST"

    # Section K: Safety Barrier
    assert s["safety_barrier"]["status"] == "CLEAR"
    assert s["safety_barrier"]["safety_tripped"] is False

    # Decision Explanation
    assert len(s["explanation"]["summary"]) > 0
    assert "CURRENT_FLOW_BELOW_MINIMUM" in s["explanation"]["reasons"] or "INSUFFICIENT_DATA_FOR_RUL" in s["explanation"]["reasons"]


def test_adversarial_dashboard_state_section_22():
    """
    Adversarial Dashboard State (Phase 3 Section 22):
    sensor_valid = TRUE
    pulse_valid = FALSE
    current_flow_valid = FALSE
    R0 = None
    chemistry update = rejected

    Dashboard MUST NOT show:
    - R0 = 0
    - Pulse successful
    - Healthy
    Must show:
    PULSE: INVALID
    R0: NOT AVAILABLE
    REASON: CURRENT_FLOW_BELOW_MINIMUM
    """
    res = {
        "cell_id": "CELL_ADVERSARIAL_01",
        "final_decision": "HOLD",
        "operational_decision": "HOLD",
        "information_action": "REQUEST_TEST",
        "final_r0_mohm": None,  # Crucial: None, NOT 0.0
        "reason": "CURRENT_FLOW_BELOW_MINIMUM",
        "data_quality": {
            "sensor_valid": True,
            "telemetry_valid": True,
            "pulse_valid": False,
            "current_flow_valid": False,
            "quality_state": "INVALID",
            "reason_codes": ["CURRENT_FLOW_BELOW_MINIMUM"],
            "delta_v_total": None
        }
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.32, "current_a": 0.0, "temperature_c": 23.0,
            "is_valid": True, "quality": "GOOD"
        }}
    ]

    snapshot = sa.build_status_snapshot(res, events, mode="mock")

    # Verify snapshot properties
    assert snapshot["data_quality"]["sensor_valid"] is True
    assert snapshot["data_quality"]["pulse_valid"] is False
    assert snapshot["data_quality"]["current_flow_valid"] is False
    assert "CURRENT_FLOW_BELOW_MINIMUM" in snapshot["data_quality"]["reasons"]
    assert snapshot["bayesian"]["r0_mohm"] is None
    assert snapshot["operational_decision"]["decision"] == "HOLD"
    assert snapshot["operational_decision"]["decision"] != "OPERATE"

    # Verify missing values never become 0
    assert snapshot["bayesian"]["r0_mohm"] is not 0.0
    assert snapshot["bayesian"]["r0_mohm"] is not 0
    assert snapshot["data_quality"]["delta_v_total"] is None
    assert snapshot["data_quality"]["delta_v_total"] is not 0.0


def test_missing_values_never_default_to_zero():
    """Missing or invalid quantities must remain None and never default to zero or healthy."""
    empty_snapshot = sa.build_status_snapshot({}, [], None)
    assert empty_snapshot["bayesian"]["soh_estimate"] is None
    assert empty_snapshot["bayesian"]["soh_uncertainty"] is None
    assert empty_snapshot["bayesian"]["r0_mohm"] is None
    assert empty_snapshot["prognostics"]["rul_cycles"] is None
    assert empty_snapshot["telemetry"]["voltage_v"] is None
    assert empty_snapshot["telemetry"]["current_a"] is None
    assert empty_snapshot["telemetry"]["power_w"] is None
    assert empty_snapshot["data_quality"]["delta_v_total"] is None
    assert empty_snapshot["battery"]["nominal_voltage"] is None
    assert empty_snapshot["battery"]["nominal_capacity_ah"] is None
    assert empty_snapshot["session"]["session_id"] is None
    assert empty_snapshot["session"]["protocol_id"] is None
    assert empty_snapshot["session"]["current_segment"] is None
    assert empty_snapshot["session"]["segment_status"] is None
    assert empty_snapshot["session"]["overall_data_status"] is None
    assert empty_snapshot["session"]["next_expected_action"] is None
    assert empty_snapshot["chemistry"]["posterior"] is None

    # Invalid pulse or missing evidence must never default to SUPPORTED_HEALTHY
    invalid_pulse_res = {
        "final_decision": "OPERATE",
        "pulse_valid": False,
        "final_soh_estimate": 0.90
    }
    snap_inv = sa.build_status_snapshot(invalid_pulse_res, [], None)
    assert snap_inv["epistemic"]["epistemic_state"] != "SUPPORTED_HEALTHY"


def test_deterministic_status_adapter_output():
    """Same inputs must produce byte-for-byte identical snapshots."""
    s1 = sa.build_status_snapshot(RESULT, EVENTS, mode="replay", now=42.0)
    s2 = sa.build_status_snapshot(RESULT, EVENTS, mode="replay", now=42.0)
    assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)


def test_deterministic_demo_scenarios_a_through_f():
    """Verify all 6 demo scenarios produce valid snapshots with honest state representations."""
    from secondshift.software.ui import demo_scenarios as ds

    sa_a = ds.create_scenario_a_healthy_pulse()
    assert sa_a["operational_decision"]["decision"] == "OPERATE"
    assert sa_a["data_quality"]["pulse_valid"] is True
    assert sa_a["prognostics"]["rul_status"] == "NOT YET IMPLEMENTED"

    sa_b = ds.create_scenario_b_zero_current_false_pulse()
    assert sa_b["operational_decision"]["decision"] == "HOLD"
    assert sa_b["data_quality"]["pulse_valid"] is False
    assert sa_b["data_quality"]["current_flow_valid"] is False
    assert "CURRENT_FLOW_BELOW_MINIMUM" in sa_b["data_quality"]["reasons"]
    assert sa_b["bayesian"]["r0_mohm"] is None

    sa_c = ds.create_scenario_c_sensor_fault()
    assert sa_c["data_quality"]["sensor_valid"] is False
    assert sa_c["telemetry"]["is_valid"] is False
    assert sa_c["operational_decision"]["decision"] == "HOLD"

    sa_d = ds.create_scenario_d_contactor_trip()
    assert sa_d["safety_barrier"]["status"] == "TRIPPED"
    assert sa_d["safety_barrier"]["safety_tripped"] is True
    assert sa_d["operational_decision"]["decision"] == "HOLD"

    sa_e = ds.create_scenario_e_insufficient_data()
    assert sa_e["epistemic"]["epistemic_state"] == "INSUFFICIENT_DATA"
    assert sa_e["information_action"]["action"] == "REQUEST_TEST"
    assert sa_e["chemistry"]["inferred_chemistry"] is None

    sa_f = ds.create_scenario_f_distribution_shift()
    assert sa_f["epistemic"]["epistemic_state"] == "DISTRIBUTION_SHIFTED"
    assert sa_f["operational_decision"]["decision"] == "HOLD"
    assert sa_f["prognostics"]["rul_cycles"] is None
