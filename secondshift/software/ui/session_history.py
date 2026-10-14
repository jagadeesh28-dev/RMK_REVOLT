"""Persistent session history for the SECONDShift dashboard.

This module is deliberately independent of dashboard.py and telemetry logic.
It stores one record per intake submission and updates that record in place.
"""

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


MEASUREMENT_FIELDS = (
    "voltage_v",
    "current_a",
    "power_w",
    "temperature_c",
)


def _now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number_or_none(value: Any) -> Optional[float]:
    """Accept finite numeric values; represent unavailable measurements as None."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


class SessionHistory:
    """Thread-safe JSON session store. The caller chooses the storage path."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve()
        self._lock = threading.RLock()

    def _read_unlocked(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Cannot safely read session history at {self.path}: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise RuntimeError(
                f"Session history must contain a JSON list: {self.path}"
            )

        return [item for item in data if isinstance(item, dict)]

    def _write_unlocked(self, records: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=self.path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump(records, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, self.path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def create_session(self, intake: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new session. Every call creates a distinct session ID."""
        if not isinstance(intake, dict):
            raise ValueError("Intake must be a dictionary.")

        battery_id = str(intake.get("batteryId", "")).strip()
        cell_id = str(intake.get("cellId", "")).strip()
        chemistry = str(intake.get("chemistry", "")).strip()
        source = str(intake.get("source", "")).strip()
        voltage = _number_or_none(intake.get("voltage"))
        capacity = _number_or_none(intake.get("capacity"))

        if not all((battery_id, cell_id, chemistry, source)):
            raise ValueError("Battery ID, Cell ID, chemistry, and source are required.")
        if voltage is None or voltage <= 0:
            raise ValueError("Nominal voltage must be a positive number.")
        if capacity is None or capacity < 1:
            raise ValueError("Nominal capacity must be at least 1 mAh.")

        started = _now()
        record = {
            "session_id": str(uuid.uuid4()),
            "started_at": started,
            "updated_at": started,
            "battery": {
                "battery_id": battery_id,
                "cell_id": cell_id,
                "chemistry": chemistry,
                "nominal_voltage_v": voltage,
                "nominal_capacity_mah": capacity,
                "data_source": source,
            },
            "measurements": {
                "voltage_v": None,
                "current_a": None,
                "power_w": None,
                "temperature_c": None,
            },
            "status": "ACTIVE",
        }

        with self._lock:
            records = self._read_unlocked()
            records.append(record)
            self._write_unlocked(records)

        return record.copy()

    def update_session(
        self,
        session_id: str,
        measurements: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing session without creating another record.

        Pass status only when the application has an explicit status to report.
        Missing status does not imply completion.
        """
        if not session_id:
            raise ValueError("A session ID is required.")

        with self._lock:
            records = self._read_unlocked()
            for record in records:
                if record.get("session_id") != session_id:
                    continue

                current = record.setdefault("measurements", {})
                if isinstance(measurements, dict):
                    for field in MEASUREMENT_FIELDS:
                        if field in measurements:
                            current[field] = _number_or_none(measurements[field])

                if status is not None and str(status).strip():
                    record["status"] = str(status).strip()

                record["updated_at"] = _now()
                self._write_unlocked(records)
                return record.copy()

        raise KeyError(f"Session not found: {session_id}")

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return saved sessions, newest first."""
        with self._lock:
            records = self._read_unlocked()
            records.sort(
                key=lambda item: str(item.get("started_at", "")),
                reverse=True,
            )
            return records

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return one session by ID, or None if it does not exist."""
        with self._lock:
            for record in self._read_unlocked():
                if record.get("session_id") == session_id:
                    return record
        return None
