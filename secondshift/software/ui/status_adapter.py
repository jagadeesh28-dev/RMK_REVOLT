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

    errors = _strs(tele.get("errors"))
    if errors is None:
        errors = _strs(res.get("validation_errors"))

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())),
        "source": SOURCE,
        "mode": _str(mode),
        "cell_id": cell_id,
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
        "bayesian": {
            "soh_estimate": _num(res.get("final_soh_estimate")),
            "soh_uncertainty": _num(res.get("final_soh_uncertainty")),
            "r0_mohm": _num(res.get("final_r0_mohm")),
        },
        "chemistry": {
            "final_chemistry": _str(res.get("final_chemistry")),
            "final_chem_confidence": _str(res.get("final_chem_confidence")),
        },
        "telemetry": {
            "voltage_v": _num(tele.get("voltage_v")),
            "current_a": _num(tele.get("current_a")),
            "temperature_c": _num(tele.get("temperature_c")),
            "sequence_number": _int(tele.get("sequence_number")),
            "frame_timestamp": _num(tele.get("frame_timestamp")),
            "is_valid": _bool(tele.get("is_valid")),
            "quality": _scalar(tele.get("quality")),
            "errors": errors,
            "warnings": _strs(tele.get("warnings")),
        },
        "decision_trace": trace,
    }
    return strip_forbidden_keys(snapshot)


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
) -> str:
    return write_status_snapshot(build_status_snapshot(result, events, mode), path)


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
    return out