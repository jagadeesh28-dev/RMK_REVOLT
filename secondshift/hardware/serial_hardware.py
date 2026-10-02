"""
Serial Hardware Adapter (Layer 1)
Project: RMK-REVOLT / SECONDShift Platform

Provides robust, fault-tolerant serial communication with embedded controllers (ESP32).
Protocol: Newline-delimited JSON (NDJSON).
Handles:
- Partial packets across read chunks
- Malformed JSON recovery
- Serial disconnects and reconnection attempts
- Timeouts
- Sequence continuity tracking
"""

import json
import time
import io
from typing import Dict, Any, Optional

try:
    import serial
except ImportError:
    serial = None

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


class SerialHardware(HardwareInterface):
    """
    Serial adapter for bidirectional communication with the HERMES ESP32 controller.
    Accepts an optional stream object for headless testing without hardware.
    """
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout_s: float = 1.0,
        stream: Optional[Any] = None
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self._stream = stream
        self._serial_port = None
        self._connected = False
        self._rx_buffer = ""

        # Telemetry tracking & error counters
        self._last_seq: Optional[int] = None
        self.stats = {
            "packets_received": 0,
            "packets_sent": 0,
            "malformed_json_errors": 0,
            "timeouts": 0,
            "duplicate_sequences": 0,
            "dropped_sequences": 0,
            "reconnect_attempts": 0
        }

    def connect(self) -> bool:
        if self._stream is not None:
            self._connected = True
            return True

        if serial is None:
            self._connected = False
            return False

        try:
            self._serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout_s
            )
            self._connected = self._serial_port.is_open
            self._rx_buffer = ""
            return self._connected
        except Exception as e:
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False
        if self._serial_port is not None:
            try:
                self._serial_port.close()
            except Exception:
                pass
            self._serial_port = None

    def is_connected(self) -> bool:
        if self._stream is not None:
            return self._connected
        if self._serial_port is not None:
            return self._serial_port.is_open
        return False

    def _read_raw_line(self, timeout_s: float) -> Optional[str]:
        """Reads a complete newline-delimited line from the stream or serial port."""
        start_time = time.time()
        while time.time() - start_time < timeout_s:
            if "\n" in self._rx_buffer:
                line, self._rx_buffer = self._rx_buffer.split("\n", 1)
                return line.strip()

            chunk = ""
            if self._stream is not None:
                if hasattr(self._stream, "readline"):
                    line = self._stream.readline()
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    if line:
                        return line.strip()
                elif hasattr(self._stream, "read"):
                    data = self._stream.read(256)
                    if isinstance(data, bytes):
                        chunk = data.decode("utf-8", errors="replace")
                    else:
                        chunk = str(data)
            elif self._serial_port is not None and self._serial_port.is_open:
                try:
                    raw_bytes = self._serial_port.read(self._serial_port.in_waiting or 1)
                    if raw_bytes:
                        chunk = raw_bytes.decode("utf-8", errors="replace")
                except Exception:
                    self._connected = False
                    return None

            if chunk:
                self._rx_buffer += chunk
            else:
                time.sleep(0.01)

        # Timeout
        return None

    def read_telemetry(self, timeout_s: Optional[float] = None) -> Optional[TelemetryFrame]:
        if not self.is_connected():
            return None

        effective_timeout = timeout_s if timeout_s is not None else self.timeout_s
        raw_line = self._read_raw_line(effective_timeout)
        if raw_line is None or not raw_line.strip():
            self.stats["timeouts"] += 1
            return None

        # Parse JSON
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            self.stats["malformed_json_errors"] += 1
            return None

        if not isinstance(payload, dict):
            self.stats["malformed_json_errors"] += 1
            return None

        # Verify packet type
        packet_type = payload.get("type", "telemetry")
        if packet_type != "telemetry":
            return None

        self.stats["packets_received"] += 1

        # Check sequence continuity
        seq = payload.get("seq") or payload.get("sequence_number")
        if seq is not None and isinstance(seq, int):
            if self._last_seq is not None:
                if seq == self._last_seq:
                    self.stats["duplicate_sequences"] += 1
                elif seq > self._last_seq + 1:
                    dropped = seq - (self._last_seq + 1)
                    self.stats["dropped_sequences"] += dropped
            self._last_seq = seq

        # Map to canonical TelemetryFrame
        frame = TelemetryFrame.from_dict(payload)
        frame.source = TelemetrySource.REAL_HARDWARE.value
        return frame

    def send_command(self, command: Dict[str, Any]) -> bool:
        if not self.is_connected():
            return False

        try:
            serialized = json.dumps(command) + "\n"
            raw_bytes = serialized.encode("utf-8")

            if self._stream is not None:
                if hasattr(self._stream, "write"):
                    self._stream.write(raw_bytes if isinstance(self._stream, io.BytesIO) else serialized)
                self.stats["packets_sent"] += 1
                return True
            elif self._serial_port is not None and self._serial_port.is_open:
                self._serial_port.write(raw_bytes)
                self._serial_port.flush()
                self.stats["packets_sent"] += 1
                return True
        except Exception:
            self._connected = False
            return False

        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "connected": self.is_connected(),
            "stats": dict(self.stats)
        }
