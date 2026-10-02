"""
Replay Hardware Adapter (Layer 1)
Project: RMK-REVOLT / SECONDShift Platform

Provides deterministic playback of recorded physical or simulated battery telemetry.
Supports CSV, JSON, and JSONL formats.
Preserves:
- Timestamps
- Sequence numbers
- Sensor failures and missing values
- Deterministic event ordering
"""

import os
import csv
import json
import time
from typing import Dict, Any, List, Optional

try:
    from secondshift.interfaces.hardware_interface import HardwareInterface
    from secondshift.interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality,
        SensorHealthStatus,
        CommunicationStatus,
        TelemetrySource
    )
except ImportError:
    from interfaces.hardware_interface import HardwareInterface
    from interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality,
        SensorHealthStatus,
        CommunicationStatus,
        TelemetrySource
    )


class ReplayHardware(HardwareInterface):
    """
    Replay adapter feeding recorded telemetry frames into the validation pipeline.
    """
    def __init__(
        self,
        file_path: Optional[str] = None,
        data_source: Optional[str] = None,
        frames: Optional[List[TelemetryFrame]] = None,
        loop: bool = False,
        realtime_replay: bool = False
    ):
        self.file_path = file_path or data_source
        self.loop = loop
        self.realtime_replay = realtime_replay
        self._frames: List[TelemetryFrame] = frames if frames is not None else []
        self._cursor = 0
        self._connected = False
        self._command_history: List[Dict[str, Any]] = []

        if self.file_path:
            self.load_from_file(self.file_path)

    def load_from_file(self, path: str):
        """Loads and parses telemetry records from CSV, JSON, or JSONL."""
        self.file_path = path
        self._frames = []
        if not os.path.exists(path):
            raise FileNotFoundError(f"Replay telemetry file not found: {path}")

        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            self._load_csv(path)
        elif ext == ".jsonl":
            self._load_jsonl(path)
        elif ext == ".json":
            self._load_json(path)
        else:
            raise ValueError(f"Unsupported replay file format: {ext} (supported: .csv, .json, .jsonl)")

    def _load_csv(self, path: str):
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            seq = 0
            for row in reader:
                seq += 1
                v_str = row.get("voltage") or row.get("voltage_v")
                i_str = row.get("current") or row.get("current_a")
                t_str = row.get("temperature") or row.get("temperature_c")
                ts_str = row.get("timestamp_monotonic") or row.get("timestamp") or str(time.time())

                v = float(v_str) if v_str and v_str.strip() else None
                i = float(i_str) if i_str and i_str.strip() else 0.0
                t = float(t_str) if t_str and t_str.strip() else 25.0
                ts = float(ts_str) if ts_str and ts_str.strip() else time.time()

                cell_idx = int(row.get("cell_idx", 0))

                frame = TelemetryFrame(
                    device_id="SECONDShift-REPLAY",
                    sequence_number=seq,
                    timestamp=ts,
                    voltage_v=v,
                    current_a=i,
                    temperature_c=t,
                    cell_voltages_v=[v] if v is not None else [],
                    cell_temperatures_c=[t],
                    source=TelemetrySource.REPLAY_FILE.value,
                    quality_flags=[TelemetryQuality.VALID.value]
                )
                self._frames.append(frame)

    def _load_jsonl(self, path: str):
        seq = 0
        with open(path, mode="r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                seq += 1
                if "sequence_number" not in data and "seq" not in data:
                    data["sequence_number"] = seq
                frame = TelemetryFrame.from_dict(data)
                frame.source = TelemetrySource.REPLAY_FILE.value
                self._frames.append(frame)

    def _load_json(self, path: str):
        with open(path, mode="r", encoding="utf-8") as f:
            payload = json.load(f)

        if isinstance(payload, list):
            for seq, item in enumerate(payload, 1):
                if isinstance(item, dict):
                    if "sequence_number" not in item and "seq" not in item:
                        item["sequence_number"] = seq
                    frame = TelemetryFrame.from_dict(item)
                    frame.source = TelemetrySource.REPLAY_FILE.value
                    self._frames.append(frame)
        elif isinstance(payload, dict):
            # Check for records list
            records = payload.get("records") or payload.get("telemetry") or [payload]
            for seq, item in enumerate(records, 1):
                if isinstance(item, dict):
                    if "sequence_number" not in item and "seq" not in item:
                        item["sequence_number"] = seq
                    frame = TelemetryFrame.from_dict(item)
                    frame.source = TelemetrySource.REPLAY_FILE.value
                    self._frames.append(frame)

    def connect(self) -> bool:
        if self.file_path and not self._frames:
            self.load_from_file(self.file_path)
        self._connected = True
        self._cursor = 0
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def read_telemetry(self, timeout_s: float = 1.0) -> Optional[TelemetryFrame]:
        if not self._connected or not self._frames:
            return None

        if self._cursor < len(self._frames):
            frame = self._frames[self._cursor]
            self._cursor += 1
            return frame

        if self.loop and self._frames:
            self._cursor = 0
            frame = self._frames[self._cursor]
            self._cursor += 1
            return frame

        return None

    def send_command(self, command: Dict[str, Any]) -> bool:
        if not self._connected:
            return False
        self._command_history.append(command)
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "source_file": self.file_path,
            "connected": self._connected,
            "total_frames": len(self._frames),
            "playback_cursor": self._cursor,
            "eof": self._cursor >= len(self._frames),
            "commands_recorded": len(self._command_history)
        }
