"""
Measurement & Data Quality Validation Configuration (Layer 2 / 3)
Project: RMK-REVOLT / SECONDShift Platform

Provides versioned, externalized configuration thresholds for:
- Diagnostic pulse validation (|I| >= I_MIN, duration, transient limits)
- Sensor range boundaries (Voltage, Current, Temperature)
- Temporal integrity limits (Staleness window, Clock skew / future tolerance)
- Sequence continuity checks

Invariants:
- Zero arbitrary hardcoded thresholds inside validation routines.
- Versioned configuration tag embedded into every validation record for traceability.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
import os
import json

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class MeasurementValidationConfig:
    """
    Versioned configuration parameters for telemetry and scientific measurement admissibility.
    """
    config_version: str = "2.0.0"

    # Diagnostic Pulse Admissibility Thresholds
    # Prototype bench parameter; subject to cell-capacity/C-rate and sensor-resolution validation.
    # Note: Not a universal scientific threshold for all cell formats/capacities; maintain configurability.
    i_min_pulse_a: float = 1.0                # Prototype bench excitation current threshold (A)
    min_pulse_duration_s: float = 0.05        # Minimum valid transient duration (s)
    min_pulse_samples: int = 2                # Minimum samples required in transient window
    max_pulse_noise_sigma_a: float = 0.5      # Maximum allowable current fluctuation/noise (A)

    # Physical Sensor Range Limits
    v_min_module_v: float = 1.0              # Minimum physically plausible module voltage (V)
    v_max_module_v: float = 60.0             # Maximum physically plausible module voltage (V)
    v_min_cell_v: float = 1.0                # Minimum cell voltage (V)
    v_max_cell_v: float = 4.5                # Maximum cell voltage (V)
    i_min_a: float = -50.0                   # Minimum string current (A, charging)
    i_max_a: float = 50.0                    # Maximum string current (A, discharging)
    temp_min_c: float = -20.0                # Minimum surface temperature (°C)
    temp_max_c: float = 85.0                 # Maximum surface temperature (°C)

    # Temporal Integrity Limits
    max_stale_age_s: float = 2.0             # Telemetry staleness timeout window (s)
    future_skew_tolerance_s: float = 5.0     # Maximum clock skew / future drift (s)

    # Metadata & Provenance
    description: str = "RMK-REVOLT Phase 2 Canonical Measurement Admissibility Configuration"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementValidationConfig":
        """Reconstructs configuration from dictionary, ignoring unknown keys."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def from_yaml_file(cls, path: str) -> "MeasurementValidationConfig":
        """Loads configuration from YAML or JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            if yaml:
                data = yaml.safe_load(f) or {}
            else:
                data = json.load(f)
        
        # If wrapped under 'validation' key (as in hardware.yaml), unwrap
        if "validation" in data:
            val_section = data["validation"]
            mapped = {}
            if "voltage_min_v" in val_section:
                mapped["v_min_cell_v"] = float(val_section["voltage_min_v"])
            if "voltage_max_v" in val_section:
                mapped["v_max_cell_v"] = float(val_section["voltage_max_v"])
            if "current_discharge_max_a" in val_section:
                mapped["i_max_a"] = float(val_section["current_discharge_max_a"])
            if "temp_min_c" in val_section:
                mapped["temp_min_c"] = float(val_section["temp_min_c"])
            if "temp_max_c" in val_section:
                mapped["temp_max_c"] = float(val_section["temp_max_c"])
            if "stale_timeout_sec" in val_section:
                mapped["max_stale_age_s"] = float(val_section["stale_timeout_sec"])
            if "i_min_pulse_a" in val_section:
                mapped["i_min_pulse_a"] = float(val_section["i_min_pulse_a"])
            return cls.from_dict({**val_section, **mapped})
            
        return cls.from_dict(data)
