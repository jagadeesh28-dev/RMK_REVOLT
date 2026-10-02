"""
Abstract Hardware Adapter Interface (Layer 1)
Project: RMK-REVOLT / SECONDShift Platform

Defines the contract for hardware interaction.
Implementations:
- MockHardware: Physics emulation for testing
- SerialHardware: Serial communication with embedded ESP32
- ReplayHardware: Deterministic playback from telemetry files
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from .telemetry_schema import TelemetryFrame


class HardwareInterface(ABC):
    """
    Abstract interface for physical or emulated battery testbed hardware.
    Encapsulates bidirectional communication without exposing low-level GPIO.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection with the hardware endpoint."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Safely terminates connection with the hardware endpoint."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if the transport link is active and healthy."""
        pass

    @abstractmethod
    def read_telemetry(self, timeout_s: float = 1.0) -> Optional[TelemetryFrame]:
        """
        Reads the latest telemetry frame from the hardware.
        Returns a strongly-typed TelemetryFrame or None if timed out.
        """
        pass

    @abstractmethod
    def send_command(self, command: Dict[str, Any]) -> bool:
        """
        Transmits an abstract command to the hardware.
        Returns True if acknowledged by the hardware, False otherwise.
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns metadata about the adapter state, link health, and counters."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
