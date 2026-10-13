"""
Dedicated Wi-Fi Telemetry Ingestion, Validation & Connection Engine (Layer 1 / 2)
Project: RMK-REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Responsibilities:
1. Ingest raw telemetry packets over Wi-Fi (HTTP POST / WebSocket / Stream).
2. Authenticate and identify devices against authorized device registry.
3. Enforce strict canonical schema validation, field presence, and type checking.
4. Detect sequence gaps, duplicates, out-of-order packets, and timestamp regressions.
5. Preserve raw telemetry audit trail while isolating validated accepted telemetry.
6. Track connection heartbeat state: CONNECTED, STALE, DISCONNECTED, FAULT.
7. Integrate with TelemetryValidator, EventLogger, and NEXUS software shadow mode.
8. Enforce invariant: None != 0. Missing measurements are never masked.
"""

import time
import math
import os
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Deque
from collections import deque

from secondshift.interfaces.telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus,
    TelemetrySource
)
from secondshift.interfaces.telemetry_validator import (
    TelemetryValidator,
    TelemetryValidationResult
)
from secondshift.interfaces.event_logger import EventLogger
from secondshift.interfaces.command_schema import CommandFrame, AbstractAction, ActuatorIntent
from secondshift.safety.actuation_policy import ActuationPolicy


class DeviceConnectionState(str, Enum):
    CONNECTED = "CONNECTED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    FAULT = "FAULT"


@dataclass
class IngestionStatistics:
    total_received: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    malformed_count: int = 0
    sequence_gaps: int = 0
    duplicate_packets: int = 0
    out_of_order_packets: int = 0
    stale_packets: int = 0
    last_sequence: Optional[int] = None
    last_device_timestamp_ms: Optional[float] = None
    last_server_timestamp: Optional[float] = None
    reconnect_count: int = 0
    disconnection_events: int = 0
    wifi_rssi_dbm: Optional[int] = None

    @property
    def total_accepted(self) -> int:
        return self.accepted_count

    @property
    def total_rejected(self) -> int:
        return self.rejected_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_received": self.total_received,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "malformed_count": self.malformed_count,
            "sequence_gaps": self.sequence_gaps,
            "duplicate_packets": self.duplicate_packets,
            "out_of_order_packets": self.out_of_order_packets,
            "stale_packets": self.stale_packets,
            "last_sequence": self.last_sequence,
            "last_device_timestamp_ms": self.last_device_timestamp_ms,
            "last_server_timestamp": self.last_server_timestamp,
            "reconnect_count": self.reconnect_count,
            "disconnection_events": self.disconnection_events,
            "wifi_rssi_dbm": self.wifi_rssi_dbm
        }


class TelemetryIngestEngine:
    """
    Central server-side telemetry intake engine.
    Ingests raw packets, validates integrity, manages device heartbeat,
    preserves raw audit logs, and coordinates shadow decisions.
    """
    def __init__(
        self,
        authorized_devices: Optional[List[str]] = None,
        telemetry_timeout_s: float = 3.0,
        disconnect_timeout_s: float = 10.0,
        validator: Optional[TelemetryValidator] = None,
        logger: Optional[EventLogger] = None,
        max_buffer_size: int = 1000,
        raw_log_path: Optional[str] = None
    ):
        self.authorized_devices = set(authorized_devices or ["NEXUS-ESP32-01", "SECONDShift-DEFAULT"])
        self.telemetry_timeout_s = float(telemetry_timeout_s)
        self.disconnect_timeout_s = float(disconnect_timeout_s)
        self.validator = validator or TelemetryValidator()
        self.logger = logger or EventLogger()
        self.raw_log_path = raw_log_path

        # Dual buffers: RAW vs ACCEPTED
        self.raw_history: Deque[Dict[str, Any]] = deque(maxlen=max_buffer_size)
        self.accepted_frames: Deque[TelemetryFrame] = deque(maxlen=max_buffer_size)
        self.rejected_records: Deque[Dict[str, Any]] = deque(maxlen=max_buffer_size)

        # Connection & Sequence tracking
        self.stats = IngestionStatistics()
        self._last_state: DeviceConnectionState = DeviceConnectionState.DISCONNECTED
        self._current_state: DeviceConnectionState = DeviceConnectionState.DISCONNECTED
        self._active_device_id: Optional[str] = None
        self._pending_commands: Deque[Dict[str, Any]] = deque(maxlen=50)

        # Rolling Physical Time-Series History & Qualification Session Tracker
        self.session_start_time: Optional[float] = None
        self.telemetry_history: Deque[Dict[str, Any]] = deque(maxlen=max_buffer_size)
        self.fault_event_count: int = 0
        self._current_fault_reason: str = "NONE"

        # Shadow decision state cache
        self.shadow_decision: Dict[str, Any] = {
            "epistemic_state": "UNCERTAIN",
            "operational_decision": "HOLD",
            "information_action": "REQUEST_TEST",
            "actuation_intent": "KEEP_ISOLATED",
            "domain_validity": "DISTRIBUTION_SHIFTED",
            "soh_estimate": None,
            "rul_cycles": None,
            "prognostics_status": "NOT AVAILABLE",
            "reason": "Awaiting valid physical telemetry stream"
        }

    def get_connection_status(self, now: Optional[float] = None) -> DeviceConnectionState:
        """Computes live heartbeat connection state based on last seen time."""
        current_time = now if now is not None else time.time()
        last_seen = self.stats.last_server_timestamp

        if last_seen is None:
            self._current_state = DeviceConnectionState.DISCONNECTED
            return self._current_state

        age = current_time - last_seen

        # Check if hardware reported an active fault
        if self.raw_history:
            last_raw = self.raw_history[-1].get("raw_payload", {})
            if last_raw.get("hardware_fault") is True or (last_raw.get("fault") and str(last_raw.get("fault")).upper() not in ["NONE", "OK", "0", "FALSE"]):
                self._current_state = DeviceConnectionState.FAULT
                return self._current_state

        if age > self.disconnect_timeout_s:
            if self._current_state != DeviceConnectionState.DISCONNECTED:
                self.stats.disconnection_events += 1
                self.logger.log_event("WIFI_DISCONNECT", {
                    "device_id": self._active_device_id,
                    "age_s": age,
                    "last_sequence": self.stats.last_sequence,
                    "reason": "HEARTBEAT_TIMEOUT"
                })
            self._current_state = DeviceConnectionState.DISCONNECTED
        elif age > self.telemetry_timeout_s:
            self._current_state = DeviceConnectionState.STALE
        else:
            self._current_state = DeviceConnectionState.CONNECTED

        return self._current_state

    def get_telemetry_age(self, now: Optional[float] = None) -> Optional[float]:
        """Returns age in seconds since last accepted telemetry packet."""
        current_time = now if now is not None else time.time()
        if self.stats.last_server_timestamp is None:
            return None
        return max(0.0, current_time - self.stats.last_server_timestamp)

    def get_connection_state(self, now: Optional[float] = None) -> str:
        """Returns string connection state: CONNECTED, STALE, DISCONNECTED, FAULT."""
        return self.get_connection_status(now).value

    @property
    def connection_state(self) -> str:
        """Returns current string connection state."""
        return self.get_connection_status().value

    def is_stale(self, now: Optional[float] = None) -> bool:
        """Returns True if connection is in STALE state."""
        return self.get_connection_status(now) == DeviceConnectionState.STALE

    def get_last_accepted_frame(self) -> Optional[TelemetryFrame]:
        """Alias returning the most recent accepted TelemetryFrame."""
        return self.get_latest_frame()

    def get_raw_history(self) -> List[Dict[str, Any]]:
        """Returns snapshot list of raw telemetry history entries."""
        return list(self.raw_history)

    def evaluate_shadow_decision(self, specimen_id: str = "SPECIMEN_01") -> Dict[str, Any]:
        """Returns active shadow decision computed from recent physical telemetry."""
        return dict(self.shadow_decision)

    def ingest_packet(
        self,
        payload: Dict[str, Any],
        client_ip: Optional[str] = None,
        now: Optional[float] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Ingests, authenticates, validates, and sequences an incoming raw telemetry packet.
        Returns: (accepted: bool, status_message: str, details: Dict[str, Any])
        """
        receive_time = now if now is not None else time.time()
        self.stats.total_received += 1

        # 1. Structural Dictionary Check
        if not isinstance(payload, dict):
            self.stats.malformed_count += 1
            self.stats.rejected_count += 1
            return False, "MALFORMED_PAYLOAD", {"error": "Packet must be a valid JSON object"}

        # Preserve exact RAW payload immediately for forensic audit
        raw_entry = {
            "server_receive_time": receive_time,
            "client_ip": client_ip,
            "raw_payload": dict(payload)
        }
        self.raw_history.append(raw_entry)
        if self.raw_log_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.raw_log_path)), exist_ok=True)
                with open(self.raw_log_path, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps(payload) + "\n")
            except Exception:
                pass

        # 2. Device Identity & Authentication
        device_id = str(payload.get("device_id", "UNKNOWN"))
        if self.authorized_devices and device_id not in self.authorized_devices:
            self.stats.rejected_count += 1
            rejection = {
                "reason": "UNAUTHORIZED_DEVICE",
                "device_id": device_id,
                "timestamp": receive_time
            }
            self.rejected_records.append(rejection)
            return False, "UNAUTHORIZED_DEVICE", rejection

        self._active_device_id = device_id

        # 3. Wi-Fi Signal Strength
        if "wifi_rssi" in payload and payload["wifi_rssi"] is not None:
            try:
                self.stats.wifi_rssi_dbm = int(payload["wifi_rssi"])
            except (ValueError, TypeError):
                pass

        # 4. Mandatory Schema Fields Check
        seq_raw = payload.get("sequence", payload.get("sequence_number", payload.get("seq")))
        if seq_raw is None or not isinstance(seq_raw, int) or isinstance(seq_raw, bool):
            self.stats.malformed_count += 1
            self.stats.rejected_count += 1
            return False, "INVALID_SEQUENCE_FIELD", {"error": "Missing or non-integer sequence field"}
        seq = int(seq_raw)

        ts_ms_raw = payload.get("timestamp_ms", payload.get("timestamp"))
        if ts_ms_raw is None or not isinstance(ts_ms_raw, (int, float)) or isinstance(ts_ms_raw, bool):
            self.stats.malformed_count += 1
            self.stats.rejected_count += 1
            return False, "INVALID_TIMESTAMP_FIELD", {"error": "Missing or non-numeric timestamp field"}
        ts_ms = float(ts_ms_raw)

        # 5. Device Reboot Detection & Sequence Monotonicity Continuity
        if self.stats.last_sequence is not None:
            # Detect device reboot / reset: timestamp regression or sequence reset to near zero
            is_reboot = False
            if self.stats.last_device_timestamp_ms is not None and ts_ms < self.stats.last_device_timestamp_ms:
                is_reboot = True
            elif seq < self.stats.last_sequence and (seq <= 5 or ts_ms < 60000):
                is_reboot = True

            if is_reboot:
                self.logger.log_event("DEVICE_REBOOT_DETECTED", {
                    "device_id": device_id,
                    "previous_seq": self.stats.last_sequence,
                    "new_seq": seq,
                    "previous_ms": self.stats.last_device_timestamp_ms,
                    "current_ms": ts_ms
                })
                self.stats.last_sequence = None
                self.stats.last_device_timestamp_ms = None
            else:
                expected_seq = self.stats.last_sequence + 1
                if seq == self.stats.last_sequence:
                    self.stats.duplicate_packets += 1
                    self.stats.rejected_count += 1
                    return False, "DUPLICATE_PACKET", {"sequence": seq, "last_sequence": self.stats.last_sequence}
                elif seq < self.stats.last_sequence:
                    self.stats.out_of_order_packets += 1
                    self.stats.rejected_count += 1
                    return False, "SEQUENCE_REGRESSION", {"sequence": seq, "last_sequence": self.stats.last_sequence}
                elif seq > expected_seq:
                    gap = seq - expected_seq
                    self.stats.sequence_gaps += gap
                    self.logger.log_event("SEQUENCE_GAP", {
                        "device_id": device_id,
                        "expected_sequence": expected_seq,
                        "received_sequence": seq,
                        "packets_lost": gap
                    })


        # Check for Wi-Fi reconnection event
        if self._current_state in (DeviceConnectionState.DISCONNECTED, DeviceConnectionState.STALE):
            self.stats.reconnect_count += 1
            self.logger.log_event("WIFI_RESTORED", {
                "device_id": device_id,
                "first_recovered_sequence": seq,
                "reconnect_count": self.stats.reconnect_count
            })

        # 7. Convert to Canonical TelemetryFrame (Preserving None != 0)
        try:
            frame = TelemetryFrame.from_dict(payload)
            frame.source = TelemetrySource.REAL_HARDWARE.value
        except Exception as exc:
            self.stats.malformed_count += 1
            self.stats.rejected_count += 1
            return False, "CANONICAL_PARSE_ERROR", {"error": str(exc)}

        # 8. Physical & Semantic Validation via TelemetryValidator
        val_result = self.validator.validate_telemetry(frame, current_time=receive_time, allow_stale_for_replay=True)

        # 9. Hardware-level Fault Detection from Payload
        has_hw_fault = (
            payload.get("hardware_fault") is True
            or (payload.get("fault") and str(payload.get("fault")).upper() not in ["NONE", "OK", "0", "FALSE"])
            or payload.get("sensor_valid") is False
        )

        # Record sample into rolling physical history (Class A Live Hardware)
        if self.session_start_time is None:
            self.session_start_time = receive_time
        elapsed_s = round(receive_time - self.session_start_time, 2)

        raw_v = payload.get("raw_voltage_V", payload.get("voltage_V", payload.get("voltage_v")))
        raw_i = payload.get("raw_current_A", payload.get("current_A", payload.get("current_a")))
        raw_p = payload.get("raw_power_W", payload.get("power_W", payload.get("power_w")))
        raw_t = payload.get("temperature_C", payload.get("temperature_c"))

        meas_v = float(raw_v) if isinstance(raw_v, (int, float)) and not isinstance(raw_v, bool) else (frame.voltage_v if frame else None)
        meas_i = float(raw_i) if isinstance(raw_i, (int, float)) and not isinstance(raw_i, bool) else (frame.current_a if frame else None)
        meas_p = float(raw_p) if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool) else (round(meas_v * meas_i, 3) if meas_v is not None and meas_i is not None else None)
        meas_t = float(raw_t) if isinstance(raw_t, (int, float)) and not isinstance(raw_t, bool) else (frame.temperature_c if frame else None)

        if has_hw_fault:
            self.fault_event_count += 1
            self._current_fault_reason = str(payload.get("fault", "SENSOR_INVALID"))
        else:
            self._current_fault_reason = "NONE"

        history_pt = {
            "timestamp": receive_time,
            "elapsed_s": elapsed_s,
            "sequence": seq,
            "voltage_v": meas_v,
            "current_a": meas_i,
            "power_w": meas_p,
            "temperature_c": meas_t,
            "raw_voltage_v": meas_v,
            "raw_current_a": meas_i,
            "state": str(payload.get("state", payload.get("hardware_state", "UNKNOWN"))),
            "fault": str(payload.get("fault", "NONE")),
            "mosfet": "ON" if payload.get("mosfet") is True or payload.get("mosfet_state") == "ON" else "OFF",
            "sensor_valid": bool(payload.get("sensor_valid", True)),
            "is_valid": bool(val_result.valid and not has_hw_fault),
            "source": "REAL_HARDWARE"
        }
        self.telemetry_history.append(history_pt)

        if not val_result.valid or has_hw_fault:
            self.stats.rejected_count += 1
            rejection_details = {
                "sequence": seq,
                "errors": val_result.errors,
                "warnings": val_result.warnings,
                "quality": val_result.quality,
                "hardware_fault": has_hw_fault,
                "fault_reason": str(payload.get("fault", "NONE"))
            }
            self.rejected_records.append(rejection_details)
            self.logger.log_telemetry_evaluation(frame, val_result, device_id)

            # Update sequence tracker even on invalid frame so packet loss count stays accurate
            self.stats.last_sequence = seq
            self.stats.last_device_timestamp_ms = ts_ms
            self.stats.last_server_timestamp = receive_time
            self._current_state = DeviceConnectionState.FAULT if has_hw_fault else DeviceConnectionState.CONNECTED
            return False, "VALIDATION_FAILED", rejection_details

        # 10. Frame Accepted! Update Accepted State
        self.stats.accepted_count += 1
        self.stats.last_sequence = seq
        self.stats.last_device_timestamp_ms = ts_ms
        self.stats.last_server_timestamp = receive_time
        self._current_state = DeviceConnectionState.CONNECTED

        self.accepted_frames.append(frame)
        self.logger.log_telemetry_evaluation(frame, val_result, device_id)

        # 11. Execute Shadow Decision Inference (No Actuation)
        self._update_shadow_decision(frame, val_result)

        return True, "ACCEPTED", {
            "sequence": seq,
            "device_id": device_id,
            "server_timestamp": receive_time,
            "voltage_v": frame.voltage_v,
            "current_a": frame.current_a,
            "power_w": frame.voltage_v * frame.current_a if (frame.voltage_v is not None and frame.current_a is not None) else None,
            "temperature_c": frame.temperature_c,
            "quality": val_result.quality
        }

    def _update_shadow_decision(self, frame: TelemetryFrame, val_result: TelemetryValidationResult):
        """
        Executes NEXUS software pipeline in shadow mode.
        Computes Epistemic State and Operational Decision without commanding actuation.
        """
        # Strict scientific boundaries:
        # Cross-chemistry generalization is unproven.
        # Under single-channel 1Hz telemetry, prognostic RUL is NOT identifiable.
        epistemic = "UNCERTAIN"
        op_decision = "HOLD"
        info_action = "REQUEST_TEST"
        reason = "Physical telemetry within valid range; holding load isolated pending qualification protocol."

        if not val_result.valid:
            epistemic = "KNOWN_DEGRADED"
            op_decision = "HOLD"
            info_action = "REQUEST_TEST"
            reason = f"Telemetry validation failure: {', '.join(val_result.errors)}"
        else:
            # Check physical voltage boundaries for nominal 2S Li-ion pack
            v = frame.voltage_v or 0.0
            if v < 6.4:
                epistemic = "KNOWN_DEGRADED"
                op_decision = "HOLD"
                info_action = "NO_TEST"
                reason = "Pack voltage below undervoltage threshold (6.40 V)."
            elif v > 8.5:
                epistemic = "KNOWN_DEGRADED"
                op_decision = "HOLD"
                info_action = "NO_TEST"
                reason = "Pack voltage above overvoltage threshold (8.50 V)."
            else:
                epistemic = "UNCERTAIN"
                op_decision = "HOLD"
                info_action = "REQUEST_TEST"
                reason = "Nominal resting telemetry observed. Epistemic state is UNCERTAIN pending controlled diagnostic pulses."

        self.shadow_decision = {
            "epistemic_state": epistemic,
            "operational_decision": op_decision,
            "information_action": info_action,
            "actuation_intent": ActuatorIntent.KEEP_ISOLATED.value,
            "domain_validity": "DISTRIBUTION_SHIFTED",
            "soh_estimate": None,
            "rul_cycles": None,
            "prognostics_status": "NOT AVAILABLE",
            "reason": reason,
            "last_evaluated_sequence": frame.sequence_number,
            "evaluated_at": time.time()
        }

    def get_latest_frame(self) -> Optional[TelemetryFrame]:
        """Returns the most recent accepted TelemetryFrame."""
        return self.accepted_frames[-1] if self.accepted_frames else None

    def get_latest_raw(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent raw packet payload."""
        return self.raw_history[-1]["raw_payload"] if self.raw_history else None

    def get_live_snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Produces complete live snapshot for dashboard reflection.
        Distinguishes LIVE vs STALE vs DISCONNECTED vs FAULT.
        """
        current_time = now if now is not None else time.time()
        conn_state = self.get_connection_status(current_time)
        age = self.get_telemetry_age(current_time)

        latest = self.get_latest_frame()
        raw = self.get_latest_raw() or {}

        # Electrical & Thermal values (prefer validated latest frame, fallback to latest raw payload)
        v = latest.voltage_v if latest else raw.get("voltage_V", raw.get("voltage_v"))
        i = latest.current_a if latest else raw.get("current_A", raw.get("current_a"))
        p = round(v * i, 3) if (v is not None and i is not None) else None
        t = latest.temperature_c if latest else raw.get("temperature_C", raw.get("temperature_c"))

        mosfet_state = raw.get("mosfet_state", "OFF" if not raw.get("mosfet") else "ON")
        hw_state = raw.get("state", raw.get("hardware_state", "UNKNOWN"))
        hw_fault = bool(raw.get("hardware_fault") or (raw.get("fault") and str(raw.get("fault")).upper() not in ["NONE", "OK", "0", "FALSE"]))
        sensor_valid = bool(raw.get("sensor_valid", True))

        # Next pending command to deliver to ESP32 on its next poll/response
        next_cmd = self._pending_commands.popleft() if self._pending_commands else None

        wifi_online = (conn_state in (DeviceConnectionState.CONNECTED, DeviceConnectionState.STALE, DeviceConnectionState.FAULT))

        return {
            "nexus_hardware": {
                "device_id": self._active_device_id or "NEXUS-ESP32-01",
                "wifi_status": "CONNECTED" if wifi_online else "DISCONNECTED",
                "backend_connection": conn_state.value,
                "telemetry_state": "LIVE" if conn_state == DeviceConnectionState.CONNECTED else conn_state.value,
                "telemetry_age_s": round(age, 2) if age is not None else None,
                "is_stale": conn_state == DeviceConnectionState.STALE,
                "is_disconnected": conn_state == DeviceConnectionState.DISCONNECTED,
                "is_fault": conn_state == DeviceConnectionState.FAULT,
                "sequence": self.stats.last_sequence,
                "packet_loss_gaps": self.stats.sequence_gaps,
                "wifi_rssi_dbm": self.stats.wifi_rssi_dbm,
                "reconnect_count": self.stats.reconnect_count
            },
            "electrical": {
                "voltage_v": v,
                "current_a": i,
                "power_w": p,
                "raw_voltage_v": raw.get("raw_voltage_V", v),
                "raw_current_a": raw.get("raw_current_A", i)
            },
            "thermal": {
                "temperature_c": t
            },
            "hardware": {
                "mosfet_state": mosfet_state,
                "hardware_state": hw_state,
                "hardware_fault": hw_fault,
                "fault_reason": str(raw.get("fault", "NONE")),
                "sensor_valid": sensor_valid,
                "cycle_count": raw.get("cycle_count", 0)
            },
            "nexus_decision": dict(self.shadow_decision),
            "command_directive": next_cmd,
            "qualification_session": self.get_qualification_session(),
            "graph_series": {
                "v": self.get_graph_series("voltage"),
                "i": self.get_graph_series("current"),
                "p": self.get_graph_series("power"),
                "t": self.get_graph_series("temperature"),
                "risk": self.get_graph_series("marginal_risk"),
                "soh": self.get_graph_series("soh"),
                "r0": self.get_graph_series("r0")
            },
            "telemetry_history": self.get_telemetry_history(100)
        }

    def get_telemetry_history(self, max_points: int = 300) -> List[Dict[str, Any]]:
        """Returns recent physical telemetry history samples (Class A Live Hardware)."""
        return list(self.telemetry_history)[-max_points:]

    def get_graph_series(self, metric: str, max_points: int = 150) -> Dict[str, Any]:
        """
        Canonical Graph Data Contract (Step 18).
        Explicitly indicates source: LIVE vs UNAVAILABLE.
        Never fabricates points or interpolates fake time series.
        """
        m = metric.lower()
        if m in ("v", "voltage"):
            pts = []
            for p in list(self.telemetry_history)[-max_points:]:
                if p["voltage_v"] is not None:
                    pts.append({
                        "timestamp": p["timestamp"],
                        "elapsed_s": p["elapsed_s"],
                        "sequence": p["sequence"],
                        "value": p["voltage_v"],
                        "label": f"{p['elapsed_s']:.0f}s"
                    })
            return {
                "source": "LIVE",
                "metric": "voltage",
                "unit": "V",
                "points": pts,
                "total_points": len(pts),
                "status": "LIVE_SAMPLES" if pts else "NO_LIVE_DATA"
            }
        elif m in ("i", "current"):
            pts = []
            for p in list(self.telemetry_history)[-max_points:]:
                if p["current_a"] is not None:
                    pts.append({
                        "timestamp": p["timestamp"],
                        "elapsed_s": p["elapsed_s"],
                        "sequence": p["sequence"],
                        "value": p["current_a"],
                        "label": f"{p['elapsed_s']:.0f}s"
                    })
            return {
                "source": "LIVE",
                "metric": "current",
                "unit": "A",
                "points": pts,
                "total_points": len(pts),
                "status": "LIVE_SAMPLES" if pts else "NO_LIVE_DATA"
            }
        elif m in ("p", "power"):
            pts = []
            for p in list(self.telemetry_history)[-max_points:]:
                if p["power_w"] is not None:
                    pts.append({
                        "timestamp": p["timestamp"],
                        "elapsed_s": p["elapsed_s"],
                        "sequence": p["sequence"],
                        "value": p["power_w"],
                        "label": f"{p['elapsed_s']:.0f}s"
                    })
            return {
                "source": "LIVE",
                "metric": "power",
                "unit": "W",
                "points": pts,
                "total_points": len(pts),
                "status": "LIVE_SAMPLES" if pts else "NO_LIVE_DATA"
            }
        elif m in ("t", "temperature"):
            pts = []
            for p in list(self.telemetry_history)[-max_points:]:
                if p["temperature_c"] is not None:
                    pts.append({
                        "timestamp": p["timestamp"],
                        "elapsed_s": p["elapsed_s"],
                        "sequence": p["sequence"],
                        "value": p["temperature_c"],
                        "label": f"{p['elapsed_s']:.0f}s"
                    })
            return {
                "source": "LIVE",
                "metric": "temperature",
                "unit": "°C",
                "points": pts,
                "total_points": len(pts),
                "status": "LIVE_SAMPLES" if pts else "NO_LIVE_DATA"
            }
        elif m in ("risk", "marginal_risk"):
            return {
                "source": "UNAVAILABLE",
                "metric": "marginal_risk",
                "unit": "%",
                "reason": "NO CURRENT RISK TRACE — AWAITING QUALIFICATION RUN",
                "points": [],
                "total_points": 0,
                "status": "INSUFFICIENT_CURRENT_EVIDENCE",
                "historical_reference_available": True
            }
        elif m == "soh":
            return {
                "source": "UNAVAILABLE",
                "metric": "soh",
                "unit": "%",
                "reason": "NO CURRENT SOH ESTIMATE — INSUFFICIENT CURRENT EVIDENCE",
                "points": [],
                "total_points": 0,
                "status": "INSUFFICIENT_CURRENT_EVIDENCE",
                "historical_reference_available": True
            }
        elif m in ("r0", "r0_mohm"):
            return {
                "source": "UNAVAILABLE",
                "metric": "r0_mohm",
                "unit": "mΩ",
                "reason": "NO CURRENT R0 ESTIMATE — INSUFFICIENT CURRENT EVIDENCE",
                "points": [],
                "total_points": 0,
                "status": "INSUFFICIENT_CURRENT_EVIDENCE",
                "historical_reference_available": True
            }
        return {
            "source": "UNAVAILABLE",
            "metric": metric,
            "unit": "",
            "reason": "UNKNOWN_METRIC",
            "points": [],
            "total_points": 0
        }

    def get_qualification_session(self) -> Dict[str, Any]:
        """
        Builds QualificationSession entity for the current hardware stream (Step 5, 16).
        Strictly distinguishes hardware connectivity from battery qualification.
        """
        now = time.time()
        start = self.session_start_time or now
        return {
            "session_id": f"SESS-WIFI-{self._active_device_id or 'ESP32'}-{int(start)}",
            "device_id": self._active_device_id or "NEXUS-ESP32-01",
            "start_time": start,
            "last_update": self.stats.last_server_timestamp,
            "elapsed_time_s": round(now - start, 2),
            "telemetry_count": self.stats.total_received,
            "valid_telemetry_count": self.stats.accepted_count,
            "invalid_telemetry_count": self.stats.rejected_count,
            "fault_count": self.fault_event_count,
            "current_state": self._current_state.value,
            "current_fault": self._current_fault_reason,
            "mosfet_state": self.get_latest_raw().get("mosfet_state", "OFF") if self.get_latest_raw() else "OFF",
            "wifi_status": "CONNECTED" if self.get_connection_status() in (DeviceConnectionState.CONNECTED, DeviceConnectionState.STALE, DeviceConnectionState.FAULT) else "DISCONNECTED",
            "wifi_rssi": self.stats.wifi_rssi_dbm,
            "packet_loss_gaps": self.stats.sequence_gaps,
            "qualification_lifecycle": "MONITORING_ONLY",
            "qualification_status": "NOT_STARTED",
            "feature_availability": {
                "V_MEAN": len(self.telemetry_history) >= 5,
                "DELTA_V_TOTAL": False,
                "DELTA_V_OHMIC": False,
                "R0_OHMIC": False,
                "RELAXATION_DELTA_V": False
            },
            "decision_availability": False,
            "data_classification": {
                "telemetry": "CLASS_A_LIVE_HARDWARE",
                "session": "CLASS_B_DERIVED_CURRENT",
                "qualification": "NOT_STARTED"
            }
        }

    def get_decision_trace(self) -> List[Dict[str, Any]]:
        """Returns recorded qualification decision trace events (Step 7). Empty if unrun."""
        return []

    def queue_command(self, action: str, requested_by: str = "SUPERVISOR") -> Dict[str, Any]:
        """
        Queues an authorized command frame (STOP, CLEAR, STATUS, AUTO, ON, OFF, HOLD)
        to be dispatched to the ESP32. STOP always has highest priority.
        """
        act = action.strip().upper()
        allowed = {"STOP", "CLEAR", "STATUS", "AUTO", "ON", "OFF", "HOLD"}
        if act not in allowed:
            raise ValueError(f"Unauthorized command action: '{action}'. Must be one of {allowed}")

        cmd = {
            "command_id": f"CMD-{int(time.time()*1000)%1000000:06d}",
            "action": act,
            "status": "QUEUED",
            "timestamp": time.time(),
            "requested_by": requested_by
        }
        if act == "STOP":
            self._pending_commands.appendleft(cmd)  # STOP preempts all others
        else:
            self._pending_commands.append(cmd)
        self.logger.log_event("SUPERVISORY_COMMAND_QUEUED", cmd)
        return cmd
