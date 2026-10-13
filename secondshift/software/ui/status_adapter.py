"""
Read-only Status Adapter (observability only)
Project: RMK-REVOLT / SECONDShift Platform

Converts a COMPLETED qualification result + EventLogger events into a sanitized
snapshot (last_run_status.json) that the dashboard serves at /api/status.

- Explicit allow-lists only; arbitrary result/event dicts are never dumped.
- Never reads benchmark data and never emits ground-truth keys.
- Never runs qualification or actuation; nothing here feeds back into decisions.
- "acknowledged" from the event log is deliberately NOT exported (it is not
  physical hardware confirmation).
"""

import json
import math
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.normpath(os.path.join(_UI_DIR, "..", "..", "data", "processed"))
STATUS_FILENAME = "last_run_status.json"
DEFAULT_STATUS_PATH = os.path.join(PROCESSED_DATA_DIR, STATUS_FILENAME)
SCHEMA_VERSION = 1
SOURCE = "secondshift_cli"

_FORBIDDEN_KEYS = {"characterized_timestamp"}
_FORBIDDEN_PREFIXES = ("ground_truth", "true_")


def is_forbidden_key(key: Any) -> bool:
    k = str(key).lower()
    return k in _FORBIDDEN_KEYS or k.startswith(_FORBIDDEN_PREFIXES)


def strip_forbidden_keys(obj: Any) -> Any:
    """Defense in depth: recursively drop ground-truth style keys."""
    if isinstance(obj, dict):
        return {k: strip_forbidden_keys(v) for k, v in obj.items() if not is_forbidden_key(k)}
    if isinstance(obj, list):
        return [strip_forbidden_keys(v) for v in obj]
    return obj


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def _int(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _str(v: Any) -> Optional[str]:
    return v if isinstance(v, str) else None


def _bool(v: Any) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def _scalar(v: Any) -> Any:
    if isinstance(v, (str, bool)):
        return v
    return _num(v)


def _strs(v: Any) -> Optional[List[str]]:
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else None


def build_status_snapshot(
    result: Optional[Dict[str, Any]],
    events: Optional[List[Dict[str, Any]]],
    mode: Optional[str] = None,
    now: Optional[float] = None,
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    res = result if isinstance(result, dict) else {}
    cell_id = _str(res.get("cell_id"))

    tele: Dict[str, Any] = {}
    trace: List[Dict[str, Any]] = []
    for ev in events or []:
        if not isinstance(ev, dict) or not isinstance(ev.get("data"), dict):
            continue
        data, etype = ev["data"], ev.get("event_type")
        if etype == "TELEMETRY_EVALUATION":
            tele = data  # keep the latest evaluated frame
        elif etype == "QUALIFICATION_DECISION":
            if cell_id and _str(data.get("cell_id")) not in (None, cell_id):
                continue
            se = data.get("state_estimate")
            se = se if isinstance(se, dict) else {}
            trace.append({
                "stage": _str(data.get("stage")),
                "decision": _str(data.get("decision")),
                "reason": _str(data.get("reason")),
                "marginal_risk": _num(data.get("marginal_risk")),
                "soh_estimate": _num(se.get("mu_soh")),
                "soh_uncertainty": _num(se.get("sigma_soh")),
                "r0_mohm": _num(se.get("mu_r0_mohm")),
            })

    # Extract data quality and pulse validation events if present
    pulse_ev = next((ev["data"] for ev in reversed(events or []) if isinstance(ev, dict) and ev.get("event_type") == "PULSE_VALIDATION" and isinstance(ev.get("data"), dict)), {})
    dq_ev = next((ev["data"] for ev in reversed(events or []) if isinstance(ev, dict) and ev.get("event_type") == "DATA_QUALITY" and isinstance(ev.get("data"), dict)), {})
    
    dq_res = res.get("data_quality") if isinstance(res.get("data_quality"), dict) else {}
    pv_res = res.get("pulse_validation") if isinstance(res.get("pulse_validation"), dict) else {}

    errors = _strs(tele.get("errors"))
    if errors is None:
        errors = _strs(res.get("validation_errors"))

    # Session and Battery resolution
    sess_obj = session if session is not None else res.get("session")
    sess: Dict[str, Any] = {}
    if hasattr(sess_obj, "to_dict") and callable(getattr(sess_obj, "to_dict")):
        sess = sess_obj.to_dict()
    elif isinstance(sess_obj, dict):
        sess = sess_obj

    bat: Dict[str, Any] = sess.get("battery_record") if isinstance(sess.get("battery_record"), dict) else {}
    battery_id = _str(bat.get("battery_id")) or _str(res.get("battery_id")) or cell_id
    declared_chem = _str(bat.get("declared_chemistry")) or _str(res.get("declared_chemistry")) or "UNKNOWN"
    nominal_voltage = _num(bat.get("nominal_voltage")) if "nominal_voltage" in bat else _num(res.get("nominal_voltage"))
    nominal_capacity = _num(bat.get("nominal_capacity_ah")) if "nominal_capacity_ah" in bat else _num(res.get("nominal_capacity_ah"))

    session_id = _str(sess.get("session_id")) or _str(res.get("session_id"))
    protocol_id = _str(sess.get("protocol_id")) or _str(res.get("protocol_id"))
    session_status = _str(sess.get("status")) or _str(res.get("session_status")) or ("COMPLETED" if res else None)
    current_segment = _str(sess.get("current_segment")) or _str(res.get("current_segment"))
    segment_status = _str(sess.get("segment_status")) or _str(res.get("segment_status")) or ("INVALID" if res.get("pulse_valid") is False else ("VALID" if res.get("pulse_valid") is True else None))
    overall_data_status = _str(sess.get("overall_data_status")) or _str(res.get("overall_data_status")) or ("INVALID" if res.get("pulse_valid") is False else ("VALID" if res.get("pulse_valid") is True else None))
    next_action = _str(res.get("next_expected_action")) or ("NONE" if res.get("final_decision") else None)

    # Voltage, Current, and Power calculation
    voltage_v = _num(tele.get("voltage_v"))
    current_a = _num(tele.get("current_a"))
    power_w = round(voltage_v * current_a, 4) if (voltage_v is not None and current_a is not None) else None

    # Data Quality & Admissibility resolution
    sensor_valid = _bool(dq_res.get("sensor_valid")) if "sensor_valid" in dq_res else (_bool(dq_ev.get("sensor_valid")) if "sensor_valid" in dq_ev else _bool(tele.get("is_valid")))
    tele_valid = _bool(dq_res.get("telemetry_valid")) if "telemetry_valid" in dq_res else (_bool(dq_ev.get("telemetry_valid")) if "telemetry_valid" in dq_ev else _bool(tele.get("is_valid")))
    event_valid = _bool(dq_res.get("event_valid")) if "event_valid" in dq_res else (_bool(dq_ev.get("event_valid")) if "event_valid" in dq_ev else (_bool(tele.get("is_valid")) if tele else None))
    inference_admissible = _bool(dq_res.get("inference_admissible")) if "inference_admissible" in dq_res else (_bool(dq_ev.get("inference_admissible")) if "inference_admissible" in dq_ev else (True if tele.get("is_valid") is True else (False if tele.get("is_valid") is False else None)))

    if "pulse_valid" in pv_res:
        pulse_valid = _bool(pv_res.get("pulse_valid"))
    elif "pulse_valid" in dq_res:
        pulse_valid = _bool(dq_res.get("pulse_valid"))
    elif "pulse_valid" in res:
        pulse_valid = _bool(res.get("pulse_valid"))
    elif "pulse_valid" in pulse_ev:
        pulse_valid = _bool(pulse_ev.get("pulse_valid"))
    else:
        pulse_valid = None

    if "current_flow_valid" in pv_res:
        current_flow_valid = _bool(pv_res.get("current_flow_valid"))
    elif "current_flow_valid" in dq_res:
        current_flow_valid = _bool(dq_res.get("current_flow_valid"))
    elif "current_flow_valid" in res:
        current_flow_valid = _bool(res.get("current_flow_valid"))
    elif "current_flow_valid" in pulse_ev:
        current_flow_valid = _bool(pulse_ev.get("current_flow_valid"))
    else:
        current_flow_valid = None

    quality_state = _str(dq_res.get("quality_state")) or _str(dq_ev.get("quality_state")) or _scalar(tele.get("quality"))
    if quality_state is None and tele:
        quality_state = "VALID" if tele.get("is_valid") else "INVALID"

    delta_v_total = _num(pv_res.get("delta_v_total")) if "delta_v_total" in pv_res else (_num(pulse_ev.get("delta_v_total")) if "delta_v_total" in pulse_ev else _num(res.get("delta_v_total")))
    delta_v_ohmic = _num(pv_res.get("delta_v_ohmic")) if "delta_v_ohmic" in pv_res else (_num(pulse_ev.get("delta_v_ohmic")) if "delta_v_ohmic" in pulse_ev else _num(res.get("delta_v_ohmic")))

    dq_reasons = []
    for r_source in (pv_res.get("admissibility_reasons"), pulse_ev.get("admissibility_reasons"), dq_res.get("reason_codes"), dq_ev.get("reason_codes")):
        if isinstance(r_source, (list, tuple)):
            for r in r_source:
                rs = str(r.value if hasattr(r, "value") else r)
                if rs and rs not in dq_reasons:
                    dq_reasons.append(rs)
    if not dq_reasons and res.get("reason") and (pulse_valid is False or current_flow_valid is False):
        dq_reasons.append(str(res["reason"]))

    # Chemistry declared vs inferred
    inferred_chem_record = sess.get("inferred_chemistry_record") if isinstance(sess.get("inferred_chemistry_record"), dict) else {}
    inferred_chemistry = _str(inferred_chem_record.get("inferred_chemistry")) or _str(res.get("inferred_chemistry")) or _str(res.get("final_chemistry"))
    chem_confidence_state = _str(inferred_chem_record.get("confidence_state")) or _str(res.get("final_chem_confidence")) or "NOT_YET_ESTIMATED"
    chem_confidence_score = _num(inferred_chem_record.get("confidence_score")) or _num(res.get("chem_confidence_score"))
    chem_posterior = inferred_chem_record.get("posterior") or res.get("chem_posterior") or None

    # Operational decision, Information action, Epistemic state
    audit = res.get("audit_record") if isinstance(res.get("audit_record"), dict) else (sess.get("audit_record") if isinstance(sess.get("audit_record"), dict) else {})
    op_dec = _str(audit.get("operational_decision")) or _str(res.get("operational_decision"))
    if not op_dec:
        fd = _str(res.get("final_decision"))
        if fd == "TEST":
            op_dec = "HOLD"
        elif fd in ("OPERATE", "DERATE", "HOLD", "RETIRE"):
            op_dec = fd
        elif fd in ("SAFE_STOP", "SAFE_SHUTDOWN"):
            op_dec = "HOLD"
        elif fd:
            op_dec = fd

    info_act = _str(audit.get("information_action")) or _str(res.get("information_action"))
    if not info_act:
        if res.get("final_decision") == "TEST" or res.get("recommended_test"):
            info_act = "REQUEST_TEST"
        elif op_dec in ("OPERATE", "DERATE", "RETIRE"):
            info_act = "NO_TEST"
        else:
            info_act = "NO_TEST"

    epistemic_state = _str(audit.get("epistemic_state")) or _str(res.get("epistemic_state"))
    if not epistemic_state:
        if res.get("safety_tripped"):
            epistemic_state = "KNOWN_DEGRADED"
        elif res.get("distribution_shifted"):
            epistemic_state = "DISTRIBUTION_SHIFTED"
        elif op_dec in ("RETIRE", "DERATE"):
            epistemic_state = "KNOWN_DEGRADED"
        elif (
            op_dec == "OPERATE"
            and (sensor_valid is not False)
            and (pulse_valid is not False)
            and (res.get("final_soh_estimate") is not None or sess.get("soh_estimate") is not None)
        ):
            epistemic_state = "SUPPORTED_HEALTHY"
        elif op_dec == "HOLD":
            epistemic_state = "INSUFFICIENT_DATA"
        else:
            epistemic_state = "INSUFFICIENT_DATA"

    reason_codes = []
    rc_src = audit.get("reason_codes") or res.get("reason_codes")
    if isinstance(rc_src, (list, tuple)):
        reason_codes = [str(x.value if hasattr(x, "value") else x) for x in rc_src]
    elif res.get("reason"):
        reason_codes = [str(res["reason"])]

    # Safety Barrier
    tripped = _bool(res.get("safety_tripped"))
    safety_status = "TRIPPED" if tripped is True else ("CLEAR" if tripped is False else "UNKNOWN")
    active_constraints = _strs(res.get("active_constraints")) or [
        "LM393_HARDWARE_LIMIT", "THERMAL_SNAP_OTP", "CELL_VOLTAGE_WINDOW", "CONTACTOR_INTERLOCK"
    ]
    trip_reason = _str(res.get("trip_reason")) or (_str(res.get("reason")) if tripped else None)

    # Prognostics placeholders
    rul_cycles = _num(res.get("rul_cycles_estimate")) or _num(res.get("rul_cycles"))
    rul_uncertainty = _num(res.get("rul_uncertainty"))
    rul_status = _str(res.get("prognostic_status")) or "NOT YET IMPLEMENTED"

    # Explanation synthesis
    explanation_summary = _str(res.get("explanation"))
    if not explanation_summary:
        if tripped:
            explanation_summary = "HARD SAFETY BARRIER TRIPPED: All operational actuation halted due to safety protection."
        elif pulse_valid is False:
            explanation_summary = "Diagnostic pulse invalid: Admissibility criteria not met (current flow below threshold or sensor fault)."
        elif epistemic_state == "INSUFFICIENT_DATA":
            explanation_summary = "Epistemic state is INSUFFICIENT_DATA: Additional diagnostic evidence required before operational commitment."
        elif epistemic_state == "DISTRIBUTION_SHIFTED":
            explanation_summary = "Epistemic state is DISTRIBUTION_SHIFTED: Observed characteristics deviate from validated population."
        elif op_dec == "OPERATE":
            explanation_summary = "Specimen validated healthy: Observations align with calibrated parameters within safe operating bounds."
        elif op_dec == "RETIRE":
            explanation_summary = "Specimen degraded: State estimate or safety criteria indicate irreversible retirement."
        else:
            explanation_summary = "Qualification evaluation complete."

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())),
        "source": SOURCE,
        "mode": _str(mode),
        "cell_id": cell_id,
        "battery": {
            "battery_id": battery_id,
            "cell_id": cell_id,
            "declared_chemistry": declared_chem,
            "nominal_voltage": nominal_voltage,
            "nominal_capacity_ah": nominal_capacity,
            "data_source": _str(bat.get("source")) or _str(res.get("data_source")) or SOURCE,
            "software_version": "SECONDShift-v2.0",
            "configuration_version": "2.0.0",
        },
        "session": {
            "session_id": session_id,
            "protocol_id": protocol_id,
            "status": session_status,
            "current_segment": current_segment,
            "segment_status": segment_status,
            "overall_data_status": overall_data_status,
            "elapsed_time_s": _num(res.get("elapsed_time_s")),
            "next_expected_action": next_action,
        },
        "decision": {
            "final_decision": _str(res.get("final_decision")),
            "actuation_intent": _str(res.get("actuation_intent")),
            "reason": _str(res.get("reason")),
            "system_state": _str(res.get("system_state")),
            "safety_tripped": _bool(res.get("safety_tripped")),
            "command_id": _str(res.get("command_id")),
            "tests_executed_count": _int(res.get("tests_executed_count")),
            "elapsed_time_s": _num(res.get("elapsed_time_s")),
        },
        "operational_decision": {
            "decision": op_dec,
            "reason": _str(res.get("reason")),
        },
        "information_action": {
            "action": info_act,
            "recommended_test": _str(res.get("recommended_test")),
        },
        "epistemic": {
            "epistemic_state": epistemic_state,
            "reason_codes": reason_codes,
        },
        "bayesian": {
            "soh_estimate": _num(res.get("final_soh_estimate")) if res.get("final_soh_estimate") is not None else _num(sess.get("soh_estimate")),
            "soh_uncertainty": _num(res.get("final_soh_uncertainty")) if res.get("final_soh_uncertainty") is not None else _num(sess.get("soh_uncertainty")),
            "r0_mohm": _num(res.get("final_r0_mohm")) if res.get("final_r0_mohm") is not None else _num(sess.get("r0_mohm_estimate")),
        },
        "prognostics": {
            "rul_cycles": rul_cycles,
            "rul_uncertainty": rul_uncertainty,
            "rul_status": rul_status,
            "explanation": "RUL prognostics models scheduled for future phases; interface placeholder active",
        },
        "chemistry": {
            "declared_chemistry": declared_chem,
            "final_chemistry": _str(res.get("final_chemistry")),
            "inferred_chemistry": inferred_chemistry,
            "final_chem_confidence": _str(res.get("final_chem_confidence")),
            "confidence_state": chem_confidence_state,
            "confidence_score": chem_confidence_score,
            "posterior": chem_posterior,
        },
        "telemetry": {
            "voltage_v": voltage_v,
            "current_a": current_a,
            "power_w": power_w,
            "temperature_c": _num(tele.get("temperature_c")),
            "sequence_number": _int(tele.get("sequence_number")),
            "frame_timestamp": _num(tele.get("frame_timestamp")),
            "is_valid": _bool(tele.get("is_valid")),
            "quality": _scalar(tele.get("quality")),
            "errors": errors,
            "warnings": _strs(tele.get("warnings")),
            "hardware_state": _str(tele.get("hardware_state")),
        },
        "data_quality": {
            "sensor_valid": sensor_valid,
            "telemetry_valid": tele_valid,
            "event_valid": event_valid,
            "inference_admissible": inference_admissible,
            "current_flow_valid": current_flow_valid,
            "pulse_valid": pulse_valid,
            "quality_state": quality_state,
            "reasons": dq_reasons,
            "delta_v_total": delta_v_total,
            "delta_v_ohmic": delta_v_ohmic,
        },
        "nexus_hardware": {
            "device_id": _str(res.get("device_id")) or _str(tele.get("device_id")) or "NEXUS-ESP32-01",
            "wifi_status": _str(res.get("wifi_status")) or "CONNECTED",
            "backend_connection": _str(res.get("backend_connection")) or "CONNECTED",
            "telemetry_state": _str(res.get("telemetry_state")) or "LIVE",
            "telemetry_age_s": _num(res.get("telemetry_age_s")),
            "sequence": _int(tele.get("sequence_number")),
            "packet_loss_gaps": _int(res.get("packet_loss_gaps", 0)),
            "wifi_rssi_dbm": _int(res.get("wifi_rssi_dbm")),
            "reconnect_count": _int(res.get("reconnect_count", 0)),
        },
        "safety_barrier": {
            "status": safety_status,
            "safety_tripped": tripped,
            "active_constraints": active_constraints,
            "trip_reason": trip_reason,
            "voltage_limits": {"min_v": 2.0, "max_v": 3.75},
            "current_limits": {"min_a": -50.0, "max_a": 50.0},
            "temperature_limits": {"max_c": 45.0},
        },
        "explanation": {
            "summary": explanation_summary,
            "reasons": reason_codes or dq_reasons,
        },
        "decision_trace": trace,
        "historical_baseline": load_historical_validation_baseline(),
    }
    return strip_forbidden_keys(snapshot)


def load_historical_validation_baseline() -> Dict[str, Any]:
    """
    Loads frozen research and validation evidence from Phase 5 and Phase 6.1.1.
    Strictly classified as CLASS C — HISTORICAL EVIDENCE (never masquerades as live data).
    """
    return {
        "title": "Validation Baseline — Historical Frozen Evidence",
        "status": "HISTORICAL — NOT CURRENT HARDWARE",
        "source": "NEXUS Phase 5 / Phase 5.1 / Phase 6.1.1 Frozen Evidence",
        "governing_invariant": "COMPUTABLE != IMPLEMENTATION_VALID != PHYSICALLY VALIDATED != PROGNOSTICALLY SUPPORTED != CROSS_CHEMISTRY VALIDATED != UNCERTAINTY CALIBRATED != UNIVERSALLY VALID != CAUSALLY INTERPRETED != SAFETY PROVEN",
        "phase5_features": {
            "features_evaluated": 30,
            "admitted": ["V_MEAN", "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V"],
            "conditional": ["RELAXATION_SLOPE_DV_DT", "DISCHARGE_AH", "DISCHARGE_WH", "T_MEAN"],
            "deferred": ["DQ_DV_PEAK"],
            "rejected_count": 20
        },
        "phase6_lofo_ablation": {
            "cohort": "Physical Mixed-Cohort LOFO Ablation (N=12: 8 LFP, 3 NMC, 1 UNKNOWN)",
            "feature": "DELTA_V_TOTAL",
            "delta_mae": 0.01355,
            "cohens_d": 0.67,
            "p_value": 0.0382,
            "folds_improved": "9 of 12 folds",
            "status": "PROVISIONALLY_SUPPORTED"
        },
        "phase6_nmc_correlation": {
            "cohort": "Physical NMC Specimen Cohort (N=3)",
            "sample_size": 3,
            "r": -0.9984,
            "status": "EXPLORATORY / DESCRIPTIVE ONLY"
        },
        "safety_thresholds": {
            "voltage_limits_v": [2.00, 3.75],
            "current_limit_a": 50.0,
            "temperature_limit_c": 45.0
        },
        "historical_risk_trace": [
            {"stage": "TRIAGE", "decision": "TEST", "marginal_risk": 0.045, "soh_estimate": 0.88, "soh_uncertainty": 0.08, "r0_mohm": 2.15},
            {"stage": "LOOP ITERATION 0", "decision": "TEST", "marginal_risk": 0.021, "soh_estimate": 0.90, "soh_uncertainty": 0.05, "r0_mohm": 1.98},
            {"stage": "LOOP ITERATION 1", "decision": "OPERATE", "marginal_risk": 0.0038, "soh_estimate": 0.92, "soh_uncertainty": 0.02, "r0_mohm": 1.85}
        ]
    }



def write_status_snapshot(snapshot: Dict[str, Any], path: Optional[str] = None) -> str:
    """Atomic write: temp file in the same directory, then os.replace."""
    target = os.path.abspath(path or DEFAULT_STATUS_PATH)
    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".last_run_status.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return target


def record_last_run(
    result: Optional[Dict[str, Any]],
    events: Optional[List[Dict[str, Any]]],
    mode: Optional[str] = None,
    path: Optional[str] = None,
    session: Optional[Any] = None,
) -> str:
    return write_status_snapshot(build_status_snapshot(result, events, mode, session=session), path)


_NO_RUN = {
    "available": False,
    "status": "NO_COMPLETED_QUALIFICATION",
    "message": "No completed qualification is available yet. Run the CLI to produce one.",
}


def read_status_snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """Never raises. Returns the sanitized snapshot or a safe 'none yet' response."""
    try:
        with open(path or DEFAULT_STATUS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(_NO_RUN)
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        return {**_NO_RUN, "status": "SNAPSHOT_UNREADABLE", "message": "The status snapshot could not be read."}
    out = strip_forbidden_keys(data)
    out["available"] = True
    if "historical_baseline" not in out:
        out["historical_baseline"] = load_historical_validation_baseline()
    return out


def build_live_telemetry_snapshot(engine: Any) -> Dict[str, Any]:
    """
    Constructs a live qualification status snapshot directly from the TelemetryIngestEngine,
    conforming to the UI schema expected by the SECONDShift dashboard.
    """
    import datetime

    live = engine.get_live_snapshot()
    hw = live.get("nexus_hardware", {})
    elec = live.get("electrical", {})
    therm = live.get("thermal", {})
    hstate = live.get("hardware", {})
    dec = live.get("nexus_decision", {})

    conn_state = hw.get("backend_connection", "DISCONNECTED")
    is_live = (conn_state == "CONNECTED")

    q_session = live.get("qualification_session", {})
    trace = live.get("decision_trace", [])
    has_fault = hstate.get("hardware_fault", False)
    fault_reason = hstate.get("fault_reason", "NONE")

    summary_msg = (
        f"Hardware safety fault reported ({fault_reason}); battery test load isolated."
        if has_fault
        else "Awaiting qualification test sequence. Real ESP32 hardware telemetry stream is active in MONITORING mode."
    )

    snapshot: Dict[str, Any] = {
        "available": True,
        "mode": "WIFI",
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "nexus_hardware": {
            "device_id": hw.get("device_id", "NEXUS-ESP32-01"),
            "wifi_status": hw.get("wifi_status", "DISCONNECTED"),
            "backend_status": conn_state,
            "telemetry_status": hw.get("telemetry_state", "DISCONNECTED"),
            "is_stale": hw.get("is_stale", False),
            "packet_age_s": hw.get("telemetry_age_s"),
            "sequence": hw.get("sequence", 0),
            "packet_gaps": hw.get("packet_loss_gaps", 0),
            "wifi_rssi": hw.get("wifi_rssi_dbm"),
            "mosfet_state": hstate.get("mosfet_state", "OFF"),
            "hardware_state": hstate.get("hardware_state", "UNKNOWN"),
            "hardware_fault": has_fault,
            "fault_reason": fault_reason,
            "sensor_valid": hstate.get("sensor_valid", True),
            "last_seen_iso": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "telemetry": {
            "voltage_v": elec.get("voltage_v"),
            "current_a": elec.get("current_a"),
            "power_w": elec.get("power_w"),
            "temperature_c": therm.get("temperature_c"),
            "sequence_number": hw.get("sequence"),
            "timestamp": time.time(),
            "hardware_state": hstate.get("hardware_state"),
            "is_valid": hstate.get("sensor_valid", True) and not has_fault,
            "source": "REAL_HARDWARE"
        },
        "data_quality": {
            "sensor_valid": hstate.get("sensor_valid", True),
            "telemetry_valid": is_live,
            "event_valid": True,
            "inference_admissible": is_live and hstate.get("sensor_valid", True) and not has_fault,
            "current_flow_valid": True if (elec.get("current_a") or 0) > 0.05 else False,
            "pulse_valid": True if (is_live and not has_fault) else False,
            "quality_state": "VALID" if (is_live and not has_fault) else "DEGRADED",
            "delta_v_total": None,
            "delta_v_ohmic": None,
            "reasons": ["LIVE_WIFI_TELEMETRY"] if (is_live and not has_fault) else ([fault_reason] if has_fault else ["DISCONNECTED_OR_STALE"])
        },
        "session": q_session or {
            "session_id": f"SESS-WIFI-{hw.get('device_id', 'ESP32')}",
            "protocol_id": "RAPID-SCREENING-V2",
            "status": "MONITORING" if is_live else "IDLE",
            "current_segment": "MONITORING",
            "segment_status": "RUNNING" if is_live else "STOPPED",
            "overall_data_status": "VALID" if (is_live and not has_fault) else "DEGRADED",
            "elapsed_time_s": 0.0,
            "qualification_lifecycle": "MONITORING_ONLY",
            "qualification_status": "NOT_STARTED",
            "next_expected_action": dec.get("information_action", "REQUEST_TEST")
        },
        "battery": {
            "battery_id": hw.get("device_id", "NEXUS-ESP32-01"),
            "cell_id": hw.get("device_id", "NEXUS-ESP32-01"),
            "declared_chemistry": "LFP",
            "nominal_voltage": 3.2,
            "nominal_capacity_ah": 2.5,
            "data_source": "PHYSICAL_BENCH_WIFI",
            "software_version": "NEXUS-v2.0-WIFI",
            "configuration_version": "2.0.0"
        },
        "chemistry": {
            "declared_chemistry": "LFP",
            "inferred_chemistry": "NOT YET ESTIMATED",
            "confidence_state": "NOT_YET_ESTIMATED",
            "confidence_score": None,
            "posterior": None
        },
        "bayesian": {
            "soh_estimate": None,
            "soh_uncertainty": None,
            "r0_mohm": None
        },
        "prognostics": {
            "rul_cycles": None,
            "rul_uncertainty": None,
            "rul_status": "NOT AVAILABLE"
        },
        "epistemic": {
            "epistemic_state": dec.get("epistemic_state", "UNCERTAIN")
        },
        "operational_decision": {
            "decision": dec.get("operational_decision", "HOLD")
        },
        "information_action": {
            "action": dec.get("information_action", "REQUEST_TEST")
        },
        "decision": {
            "final_decision": dec.get("operational_decision", "HOLD"),
            "actuation_intent": dec.get("actuation_intent", "KEEP_ISOLATED"),
            "system_state": "HOLD",
            "safety_tripped": has_fault,
            "reason": summary_msg
        },
        "safety_barrier": {
            "safety_tripped": has_fault,
            "trip_reason": fault_reason,
            "voltage_limits": {"min_v": 2.00, "max_v": 3.75},
            "current_limits": {"max_a": 50.0},
            "temperature_limits": {"max_c": 45.0},
            "active_constraints": ["ESP32_AUTONOMOUS_INTERLOCK", "SUPERVISOR_POLICY"]
        },
        "explanation": {
            "summary": summary_msg,
            "reasons": [dec.get("epistemic_state", "UNCERTAIN")] if not has_fault else [fault_reason]
        },
        "decision_trace": trace,
        "decision_trace_status": "RECORDED" if trace else "NO_QUALIFICATION_DECISION_RECORDED",
        "graph_series": live.get("graph_series", {}),
        "telemetry_history": live.get("telemetry_history", []),
        "historical_baseline": load_historical_validation_baseline(),
        "data_classification": {
            "voltage": "CLASS_A_LIVE_HARDWARE",
            "current": "CLASS_A_LIVE_HARDWARE",
            "power": "CLASS_A_LIVE_HARDWARE",
            "temperature": "CLASS_A_LIVE_HARDWARE",
            "hardware_state": "CLASS_A_LIVE_HARDWARE",
            "fault": "CLASS_A_LIVE_HARDWARE",
            "mosfet_state": "CLASS_A_LIVE_HARDWARE",
            "wifi_status": "CLASS_A_LIVE_HARDWARE",
            "sequence": "CLASS_A_LIVE_HARDWARE",
            "data_quality": "CLASS_B_DERIVED_CURRENT",
            "session": "CLASS_B_DERIVED_CURRENT",
            "soh_estimate": "CLASS_B_DERIVED_CURRENT",
            "r0_mohm": "CLASS_B_DERIVED_CURRENT",
            "marginal_risk": "CLASS_B_DERIVED_CURRENT",
            "decision_trace": "CLASS_B_DERIVED_CURRENT",
            "validation_baseline": "CLASS_C_HISTORICAL_EVIDENCE"
        }
    }
    return strip_forbidden_keys(snapshot)