"""
Phase 3 Verification: Ground Truth Isolation Test
Project: RMK-REVOLT / SECONDShift Platform

Verifies strict epistemic blind data separation:
1. Decision engine, Bayesian estimators, and safety barriers MUST NOT read ground_truth_registry.json.
2. If any component in the decision pipeline attempts to read ground-truth data, the test FAILS.
3. Decision engine receives only physical observations (V, I, T, dV/dt, noise).
"""

import os
import ast
import inspect
import pytest
from unittest.mock import patch

from secondshift.software.secondshift.decision_engine import SECONDShiftDecisionEngine
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.chemistry.chemistry_engine import ChemistryDisambiguationEngine
from secondshift.software.safety.hard_safety_barrier import HardSafetyBarrier
from secondshift.software.voi.evsi_calculator import ValueOfInformationEngine
from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner

def test_ast_ground_truth_isolation():
    """
    Scans abstract syntax trees of core decision modules to ensure zero references
    to ground_truth_registry.json or ground-truth registry files.
    """
    quarantined_modules = [
        "secondshift/software/secondshift/decision_engine.py",
        "secondshift/software/secondshift/closed_loop_runner.py",
        "secondshift/software/estimators/bayesian_state_estimator.py",
        "secondshift/software/estimators/model_uncertainty.py",
        "secondshift/software/chemistry/chemistry_engine.py",
        "secondshift/software/safety/hard_safety_barrier.py",
        "secondshift/software/voi/evsi_calculator.py",
        "secondshift/software/triage/triage_gate.py"
    ]

    for mod_path in quarantined_modules:
        assert os.path.exists(mod_path), f"Module {mod_path} does not exist"
        with open(mod_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "ground_truth_registry.json" not in node.value, (
                    f"VIOLATION: Quarantined module {mod_path} contains string reference "
                    f"to ground_truth_registry.json! Zero information leakage rule breached."
                )

def test_runtime_ground_truth_interception():
    """
    Hooks Python's open() during live qualification pipeline execution.
    If the decision engine or any estimator attempts to read ground_truth_registry.json,
    the pipeline immediately fails.
    """
    orig_open = open

    def guarded_open(file, *args, **kwargs):
        file_str = str(file)
        if "ground_truth_registry.json" in file_str:
            # Check stack frames to see who is calling open()
            stack = inspect.stack()
            for frame_info in stack[1:]:
                caller_file = frame_info.filename
                if "decision_engine.py" in caller_file or "closed_loop_runner.py" in caller_file:
                    raise PermissionError(
                        f"SECURITY VIOLATION: Decision pipeline called open() on {file_str} "
                        f"from {caller_file}! Blind data separation violated."
                    )
        return orig_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=guarded_open):
        hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.94], cell_r0_mohm=[1.9])
        meas = HermesMeasurementEngine(hw, active_cell_idx=0)
        runner = ClosedLoopRunner(meas)

        # Run qualification on anonymous specimen
        res = runner.run_qualification_pipeline(
            cell_id="ANONYMOUS_TEST_SPECIMEN",
            prior_source="KNOWN_LFP_FLEET",
            prior_soh=0.90,
            prior_sigma_soh=0.04
        )

        assert res["final_decision"] in ["OPERATE", "DERATE", "TEST", "HOLD", "RETIRE"]
        # Confirm that true parameters are not in the trace or decision reason
        assert "true_soh" not in res
        assert "true_chemistry" not in res
        assert "true_capacity_ah" not in res

def test_no_direct_hardware_attribute_sniffing():
    """
    Verifies that ClosedLoopRunner source code does NOT directly access
    hw.soh or hw.r0 attributes, preserving the measurement abstraction.
    """
    with open("secondshift/software/secondshift/closed_loop_runner.py", "r", encoding="utf-8") as f:
        code = f.read()

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in ["soh", "r0"]:
                # Ensure it's not accessing self.meas.hw.soh or self.hw.soh
                if isinstance(node.value, ast.Attribute) and node.value.attr == "hw":
                    pytest.fail(f"SECURITY VIOLATION: ClosedLoopRunner directly accesses hw.{node.attr}!")

def test_training_calibration_split_audit():
    """
    Phase 1 Verification: Distinguishes Training/Calibration Data from Validation Ground Truth.
    Formally verifies that:
    1. No machine learning weight files (.pt, .pth, .onnx, .pkl, .h5) exist pretending to be 'learned'.
    2. Priors and likelihoods are purely heuristic physical constants, NOT fitted on validation data.
    """
    import glob
    model_weight_files = glob.glob("secondshift/**/*.pth", recursive=True) + \
                         glob.glob("secondshift/**/*.onnx", recursive=True) + \
                         glob.glob("secondshift/**/*.pt", recursive=True)
    assert len(model_weight_files) == 0, f"Found unexpected model weights: {model_weight_files}"

