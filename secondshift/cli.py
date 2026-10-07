"""
Command Line Interface (CLI) for SECONDShift Platform
Project: RMK-REVOLT / SECONDShift Platform

Supports:
- Qualification execution across mock, serial, and replay hardware modes
- Offline and streaming telemetry frame validation
- Hardware status and independent safety diagnostic queries
"""

import sys
import os
import json
import argparse
from typing import Optional, Dict, Any

try:
    import yaml
except ImportError:
    yaml = None

try:
    from secondshift.hardware.hil_runner import HILRunner
    from secondshift.hardware.mock_hardware import MockHardware
    from secondshift.hardware.serial_hardware import SerialHardware
    from secondshift.hardware.replay_hardware import ReplayHardware
    from secondshift.interfaces.telemetry_schema import TelemetryFrame
    from secondshift.interfaces.telemetry_validator import TelemetryValidator
    from secondshift.interfaces.event_logger import EventLogger
    from secondshift.software.triage.triage_gate import TriageGate
except ImportError:
    from hardware.hil_runner import HILRunner
    from hardware.mock_hardware import MockHardware
    from hardware.serial_hardware import SerialHardware
    from hardware.replay_hardware import ReplayHardware
    from interfaces.telemetry_schema import TelemetryFrame
    from interfaces.telemetry_validator import TelemetryValidator
    from interfaces.event_logger import EventLogger
    from software.triage.triage_gate import TriageGate


def load_hardware_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads hardware configuration YAML file if provided or if default exists."""
    if not config_path:
        default_yaml = os.path.join(os.path.dirname(__file__), "config", "hardware.yaml")
        if os.path.exists(default_yaml):
            config_path = default_yaml

    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            if yaml:
                return yaml.safe_load(f) or {}
            else:
                return json.load(f)
    return {}


def load_system_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads system configuration (config/default.yaml) if available."""
    if not config_path:
        candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml"))
        if os.path.exists(candidate):
            config_path = candidate
        else:
            local_cand = os.path.join("config", "default.yaml")
            if os.path.exists(local_cand):
                config_path = local_cand

    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            if yaml:
                return yaml.safe_load(f) or {}
            else:
                return json.load(f)
    return {}


def extract_app_config(system_config: Dict[str, Any], application: str = "solar_storage") -> Dict[str, Any]:
    """Extracts application profile and economic parameters for decision engine."""
    if not system_config:
        return {}
    apps = system_config.get("applications", {})
    app_cfg = dict(apps.get(application, {}))
    econs = system_config.get("economic_parameters", {})
    if "recycle_scrap_value_inr_per_kwh" in econs:
        app_cfg["recycle_rate_inr_kwh"] = float(econs["recycle_scrap_value_inr_per_kwh"])
    if "safety_limits" in system_config:
        app_cfg.setdefault("alpha_safety", 0.01)
    return app_cfg


def create_hardware_adapter(mode: str, args: argparse.Namespace, config: Dict[str, Any]):
    """Instantiates the specified Layer 1 hardware adapter."""
    transport_cfg = config.get("transport", {})

    if mode == "mock":
        chem = getattr(args, "mock_chemistry", "LFP")
        soh = getattr(args, "mock_soh", 0.92)
        r0 = getattr(args, "mock_r0", 2.0)
        hw = MockHardware(chemistry=chem, soh=soh, r0_mohm=r0)
        if getattr(args, "fault_sensor", False):
            hw.set_fault_mode("MISSING_SENSOR")
        elif getattr(args, "fault_stale", False):
            hw.set_fault_mode("STALE_TELEMETRY")
        elif getattr(args, "fault_uvp", False):
            hw.set_fault_mode("UVP_FAULT")
        elif getattr(args, "fault_ovp", False):
            hw.set_fault_mode("OVP_FAULT")
        return hw
    elif mode == "serial":
        port = args.port or transport_cfg.get("serial_port", "/dev/ttyUSB0")
        baud = args.baud or transport_cfg.get("baud_rate", 115200)
        timeout = transport_cfg.get("read_timeout_sec", 1.0)
        return SerialHardware(port=port, baudrate=baud, timeout=timeout)
    elif mode == "replay":
        replay_file = args.replay_file
        if not replay_file or not os.path.exists(replay_file):
            raise FileNotFoundError(f"Replay telemetry file '{replay_file}' not found.")
        return ReplayHardware(data_source=replay_file, realtime_replay=getattr(args, "realtime", False))
    else:
        raise ValueError(f"Unknown hardware mode: {mode}. Must be 'mock', 'serial', or 'replay'.")


def run_qualification_cmd(args: argparse.Namespace) -> int:
    """Executes closed-loop qualification via HILRunner."""
    hw_config = load_hardware_config(args.config)
    hw = create_hardware_adapter(args.mode, args, hw_config)

    # Operational configuration path: CLI -> HILRunner -> TriageGate / DecisionEngine
    sys_config_path = getattr(args, "system_config", None)
    system_cfg = load_system_config(sys_config_path)
    app_name = getattr(args, "application", "solar_storage")
    app_config = extract_app_config(system_cfg, application=app_name) if system_cfg else None

    triage = None
    if system_cfg and "safety_limits" in system_cfg:
        safety = system_cfg["safety_limits"]
        triage = TriageGate(
            v_min_reject=2.00,  # Retain electrochemical copper dissolution floor
            v_max_reject=float(safety.get("voltage_ovp", 3.75)),
            t_max_reject_c=float(safety.get("temp_otp_c", 45.0)),
            max_leakage_mv_hr=float(safety.get("max_leakage_mv_per_hr", 15.0))
        )

    runner = HILRunner(hardware=hw, app_config=app_config, triage=triage)

    print(f"[SECONDShift CLI] Starting qualification...")
    print(f"  Specimen ID:  {args.cell_id}")
    print(f"  Mode:         {args.mode.upper()}")
    print(f"  Prior Source: {args.prior_source}")
    print(f"  Prior SOH:    {args.prior_soh:.2f} (sigma={args.prior_sigma:.2f})")

    res = runner.run_qualification(
        cell_id=args.cell_id,
        prior_source=args.prior_source,
        prior_soh=args.prior_soh,
        prior_sigma_soh=args.prior_sigma,
        prior_r0_mohm=args.prior_r0,
        prior_sigma_r0_mohm=args.prior_sigma_r0
    )
    try:
        try:
            from secondshift.software.ui.status_adapter import record_last_run
        except ImportError:
            from software.ui.status_adapter import record_last_run

        record_last_run(
            res,
            runner.logger.get_events(),
            getattr(args, "mode", None)
        )

    except Exception as exc:
        print(
            f"[WARN] Dashboard status snapshot not written: {exc}",
            file=sys.stderr
        )

    print("\n[SECONDShift CLI] Qualification Complete:")
    print(f"  Final Decision:   {res['final_decision']}")
    print(f"  Actuation Intent: {res['actuation_intent']}")
    print(f"  Safety Tripped:   {res.get('safety_tripped', False)}")
    print(f"  Iterations:       {res.get('iterations', 1)}")
    print(f"  Reason:           {res.get('reason', 'N/A')}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"  Results saved:    {args.output}")

    return 0


def validate_telemetry_cmd(args: argparse.Namespace) -> int:
    """Validates telemetry frames from a file or stdin."""
    validator = TelemetryValidator()
    raw_lines = []

    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: input file {args.input} does not exist", file=sys.stderr)
            return 1
        with open(args.input, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    else:
        print("[SECONDShift CLI] Reading NDJSON telemetry frames from stdin (Ctrl+D to finish):")
        for line in sys.stdin:
            raw_lines.append(line)

    valid_count = 0
    invalid_count = 0

    for idx, line in enumerate(raw_lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            frame = TelemetryFrame.from_dict(payload)
            res = validator.validate_frame(frame)
            if res.valid:
                valid_count += 1
                if not args.quiet:
                    print(f"Frame #{idx} (seq={frame.sequence_number}): VALID [V={frame.voltage_v:.3f}V, I={frame.current_a:.3f}A, T={frame.temperature_c:.1f}°C]")
            else:
                invalid_count += 1
                print(f"Frame #{idx} (seq={frame.sequence_number}): REJECTED - Errors: {res.errors}, Quality: {res.quality}")
        except Exception as e:
            invalid_count += 1
            print(f"Frame #{idx}: PARSE ERROR - {str(e)}", file=sys.stderr)

    print(f"\n[SECONDShift CLI] Validation Summary: {valid_count} Valid, {invalid_count} Invalid, Total {valid_count + invalid_count}")
    return 0 if invalid_count == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    """Builds the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="secondshift",
        description="SECONDShift Risk-Constrained Battery Qualification CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. run command
    run_parser = subparsers.add_parser("run", help="Run qualification pipeline on a battery specimen")
    run_parser.add_argument("--mode", choices=["mock", "serial", "replay"], default="mock", help="Hardware mode (mock, serial, replay)")
    run_parser.add_argument("--cell-id", default="SPECIMEN_01", help="Specimen identifier")
    run_parser.add_argument("--prior-source", default="KNOWN_LFP_FLEET", help="Prior model origin (KNOWN_LFP_FLEET, UNKNOWN, etc.)")
    run_parser.add_argument("--prior-soh", type=float, default=0.90, help="Initial prior SOH mean [0.0 - 1.0]")
    run_parser.add_argument("--prior-sigma", type=float, default=0.04, help="Initial prior SOH uncertainty (sigma)")
    run_parser.add_argument("--prior-r0", type=float, default=2.0, help="Initial prior R0 mean (mOhm)")
    run_parser.add_argument("--prior-sigma-r0", type=float, default=0.5, help="Initial prior R0 uncertainty (mOhm)")
    run_parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port for serial mode")
    run_parser.add_argument("--baud", type=int, default=115200, help="Baud rate for serial mode")
    run_parser.add_argument("--replay-file", help="Path to telemetry trace file for replay mode")
    run_parser.add_argument("--config", help="Path to custom hardware.yaml configuration file")
    run_parser.add_argument("--system-config", help="Path to custom default.yaml system configuration file")
    run_parser.add_argument("--application", default="solar_storage", help="Target application profile from system configuration")
    run_parser.add_argument("--output", help="Path to save result JSON")

    # Mock hardware fault injection flags
    run_parser.add_argument("--mock-chemistry", default="LFP", help="Mock cell chemistry (LFP, NMC, UNKNOWN)")
    run_parser.add_argument("--mock-soh", type=float, default=0.92, help="Mock true SOH")
    run_parser.add_argument("--mock-r0", type=float, default=2.0, help="Mock true R0 (mOhm)")
    run_parser.add_argument("--fault-sensor", action="store_true", help="Simulate hardware sensor fault")
    run_parser.add_argument("--fault-stale", action="store_true", help="Simulate telemetry timestamp staleness")
    run_parser.add_argument("--fault-uvp", action="store_true", help="Simulate undervoltage condition")
    run_parser.add_argument("--fault-ovp", action="store_true", help="Simulate overvoltage condition")
    run_parser.set_defaults(func=run_qualification_cmd)

    # 2. validate-telemetry command
    val_parser = subparsers.add_parser("validate-telemetry", help="Validate telemetry frames offline or from stdin")
    val_parser.add_argument("--input", help="Path to NDJSON or JSON file containing telemetry frames")
    val_parser.add_argument("--quiet", action="store_true", help="Suppress per-frame passing messages")
    val_parser.set_defaults(func=validate_telemetry_cmd)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
