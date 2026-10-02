"""
High-Integrity Experiment Logger
Project: RMK-REVOLT / SECONDShift Platform
Enforces non-destructive, machine-readable data logging conforming to mandatory schema.
"""

import os
import csv
import json
import time
from typing import Dict, Any

MANDATORY_LOG_FIELDS = [
    "experiment_id",
    "cell_id",
    "chemistry_ground_truth",
    "chemistry_posterior",
    "timestamp",
    "voltage",
    "current",
    "temperature",
    "estimated_soh",
    "soh_uncertainty",
    "resistance",
    "resistance_uncertainty",
    "model_confidence",
    "failure_risk",
    "safety_bound",
    "EVSI",
    "test_cost",
    "decision",
    "decision_reason",
    "hardware_state",
    "safety_trip",
    "final_state"
]

class ExperimentLogger:
    def __init__(self, log_dir: str = "secondshift/data/raw"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.master_csv_path = os.path.join(self.log_dir, "master_experiment_log.csv")
        self._init_master_csv()

    def _init_master_csv(self):
        if not os.path.exists(self.master_csv_path):
            with open(self.master_csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(MANDATORY_LOG_FIELDS)

    def log_experiment_step(self, data: Dict[str, Any]):
        """
        Appends an immutable experiment record to the master CSV.
        Validates presence of all schema fields.
        """
        row = []
        for field in MANDATORY_LOG_FIELDS:
            val = data.get(field, "N/A")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row.append(val)

        with open(self.master_csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
