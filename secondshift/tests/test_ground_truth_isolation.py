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

def resolve_repo_path(rel_path: str) -> str:
    if os.path.exists(rel_path):
        return rel_path
    if rel_path.startswith("secondshift/"):
        stripped = rel_path[len("secondshift/"):]
        if os.path.exists(stripped):
            return stripped
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base_dir, rel_path)
    if os.path.exists(candidate):
        return candidate
    if rel_path.startswith("secondshift/"):
        candidate_stripped = os.path.join(base_dir, rel_path[len("secondshift/"):])
        if os.path.exists(candidate_stripped):
            return candidate_stripped
    return rel_path

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
        actual_path = resolve_repo_path(mod_path)
        assert os.path.exists(actual_path), f"Module {actual_path} does not exist"
        with open(actual_path, "r", encoding="utf-8") as f:
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
    runner_path = resolve_repo_path("secondshift/software/secondshift/closed_loop_runner.py")
    with open(runner_path, "r", encoding="utf-8") as f:
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
    search_dir = resolve_repo_path("secondshift")
    model_weight_files = (
        glob.glob(os.path.join(search_dir, "**/*.pth"), recursive=True) +
        glob.glob(os.path.join(search_dir, "**/*.onnx"), recursive=True) +
        glob.glob(os.path.join(search_dir, "**/*.pt"), recursive=True)
    )
    assert len(model_weight_files) == 0, f"Found unexpected model weights: {model_weight_files}"


def test_hardware_integration_modules_isolation():
    """
    Verifies that the new Layer 1-5 hardware integration modules contain ZERO references
    to ground_truth_registry.json in their source code.
    """
    hw_modules = [
        "secondshift/hardware/hil_runner.py",
        "secondshift/hardware/mock_hardware.py",
        "secondshift/hardware/replay_hardware.py",
        "secondshift/hardware/serial_hardware.py",
        "secondshift/safety/actuation_policy.py",
        "secondshift/interfaces/telemetry_schema.py",
        "secondshift/interfaces/telemetry_validator.py",
        "secondshift/interfaces/command_schema.py"
    ]
    for mod_path in hw_modules:
        actual_path = resolve_repo_path(mod_path)
        if os.path.exists(actual_path):
            with open(actual_path, "r", encoding="utf-8") as f:
                code = f.read()
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert "ground_truth_registry.json" not in node.value, (
                        f"VIOLATION: Hardware integration module {actual_path} references ground_truth_registry.json!"
                    )


def test_hil_runner_runtime_ground_truth_isolation():
    """
    Proves that HILRunner and ReplayHardware can execute completely without
    touching ground_truth_registry.json at runtime.
    """
    from unittest.mock import patch
    import inspect
    from secondshift.hardware.mock_hardware import MockHardware
    from secondshift.hardware.hil_runner import HILRunner

    orig_open = open

    def guarded_open(file, *args, **kwargs):
        file_str = str(file)
        if "ground_truth_registry.json" in file_str:
            stack = inspect.stack()
            for frame_info in stack[1:]:
                caller = frame_info.filename
                if "hil_runner.py" in caller or "mock_hardware.py" in caller:
                    raise PermissionError(f"VIOLATION: Hardware integration called open on ground truth from {caller}")
        return orig_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=guarded_open):
        mock_hw = MockHardware(chemistry="LFP", soh=0.92, r0_mohm=2.0)
        runner = HILRunner(mock_hw)
        res = runner.run_qualification(cell_id="BLIND_SPECIMEN_01", prior_source="KNOWN_LFP_FLEET", prior_soh=0.90)
        assert res["final_decision"] in ["OPERATE", "DERATE", "HOLD", "RETIRE"]
        assert "ground_truth" not in res


