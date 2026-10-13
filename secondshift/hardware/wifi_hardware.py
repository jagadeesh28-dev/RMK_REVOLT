"""
Wi-Fi Hardware Adapter (Layer 1)
Project: RMK-REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Implements HardwareInterface for real-time telemetry streaming and command
dispatching over local Wi-Fi network.
"""

import time
from typing import Dict, Any, Optional

from secondshift.interfaces.hardware_interface import HardwareInterface
from secondshift.interfaces.telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus,
    TelemetrySource
)
from secondshift.hardware.telemetry_ingest import (
    TelemetryIngestEngine,
    DeviceConnectionState
)


class WifiHardware(HardwareInterface):
    """
    Wi-Fi hardware adapter connecting NEXUS software to an ESP32 node via Wi-Fi.
    Can operate attached to an active TelemetryIngestEngine instance.
    """
    def __init__(
        self,
        ingest_engine: Optional[TelemetryIngestEngine] = None,
        device_id: str = "NEXUS-ESP32-01",
        timeout_s: float = 2.0
    ):
        self.engine = ingest_engine or TelemetryIngestEngine(authorized_devices=[device_id])
        self.device_id = device_id
        self.timeout_s = timeout_s
        self._connected = True
        self._last_read_seq: Optional[int] = None

    def connect(self) -> bool:
        """Checks if device is sending telemetry or establishes connection."""
        self._connected = True
        status = self.engine.get_connection_status()
        return status in (DeviceConnectionState.CONNECTED, DeviceConnectionState.STALE)

    def disconnect(self) -> None:
        """Terminates session."""
        self._connected = False

    def is_connected(self) -> bool:
        if not self._connected:
            return False
        return self.engine.get_connection_status() in (
            DeviceConnectionState.CONNECTED,
            DeviceConnectionState.STALE
        )

    def read_telemetry(self, timeout_s: Optional[float] = None) -> Optional[TelemetryFrame]:
        """
        Polls for the latest accepted telemetry frame.
        Waits up to timeout_s for a new sequence number if available.
        """
        timeout = timeout_s if timeout_s is not None else self.timeout_s
        deadline = time.time() + timeout

        while time.time() <= deadline:
            frame = self.engine.get_latest_frame()
            if frame is not None:
                if self._last_read_seq is None or frame.sequence_number != self._last_read_seq:
                    self._last_read_seq = frame.sequence_number
                    return frame
            time.sleep(0.02)

        # Timeout reached: return latest if available or synthesize dropout frame
        latest = self.engine.get_latest_frame()
        if latest is not None and self.engine.get_connection_status() != DeviceConnectionState.DISCONNECTED:
            return latest

        return TelemetryFrame(
            device_id=self.device_id,
            sequence_number=self.engine.stats.last_sequence or 0,
            timestamp=time.time(),
            voltage_v=None,
            current_a=None,
            temperature_c=None,
            communication_status=CommunicationStatus.DROPOUT.value,
            quality_flags=[TelemetryQuality.COMMUNICATION_FAULT.value],
            source=TelemetrySource.REAL_HARDWARE.value
        )

    def send_command(self, command: Any) -> bool:
        """
        Dispatches an abstract command to the ESP32 node via the ingestion engine.
        Returns True if safely queued and accepted by policy.
        """
        if isinstance(command, str):
            action = command
        elif isinstance(command, dict):
            action = command.get("action", command.get("requested_mode", "HOLD"))
        else:
            action = str(command)
        self.engine.queue_command(str(action))
        return True

    def get_hardware_state(self) -> str:
        """Returns the hardware supervisor state from the latest frame."""
        frame = self.engine.get_latest_frame()
        if frame:
            return frame.hardware_state or "RUNNING"
        return "DISCONNECTED"

    def emergency_shutdown(self) -> bool:
        """Dispatches immediate highest-priority STOP command."""
        self.engine.queue_command("STOP", requested_by="EMERGENCY_SHUTDOWN")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Returns hardware connection statistics, packet loss, and RSSI."""
        return {
            "device_id": self.device_id,
            "connected": self.is_connected(),
            "connection_state": self.engine.get_connection_status().value,
            "telemetry_age_s": self.engine.get_telemetry_age(),
            "stats": self.engine.stats.to_dict()
        }
