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
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), dash.DashboardHandler)
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