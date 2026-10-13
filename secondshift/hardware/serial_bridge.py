"""
Serial-to-HTTP Telemetry Bridge
Project: RMK REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Reads NDJSON telemetry packets from the ESP32 over USB Serial and forwards them
directly into the local dashboard ingestion endpoint: http://127.0.0.1:8088/api/telemetry.

Usage:
    python secondshift/hardware/serial_bridge.py [COM_PORT] [BAUDRATE]
    Example: python secondshift/hardware/serial_bridge.py COM11 115200
"""

import sys
import time
import json
import urllib.request
import urllib.error

try:
    import serial
except ImportError:
    print("[ERROR] pyserial is not installed. Run: pip install pyserial")
    sys.exit(1)


DEFAULT_PORT = "COM11"
DEFAULT_BAUD = 115200
DASHBOARD_URL = "http://127.0.0.1:8088/api/telemetry"


def run_bridge(port_name: str = DEFAULT_PORT, baudrate: int = DEFAULT_BAUD):
    print("=" * 65)
    print("       NEXUS SERIAL -> DASHBOARD TELEMETRY BRIDGE")
    print(f"       Port: {port_name} @ {baudrate} baud")
    print(f"       Forwarding to: {DASHBOARD_URL}")
    print("=" * 65)
    print("\n[NOTE] Ensure Arduino IDE Serial Monitor is CLOSED so this bridge can access the port.\n")

    try:
        ser = serial.Serial(port_name, baudrate, timeout=1.0)
    except Exception as exc:
        print(f"[ERROR] Could not open {port_name}: {exc}")
        print("[HINT] If port is busy, close the Serial Monitor in Arduino IDE and retry.")
        return

    print(f"[READY] Listening on {port_name}... Press Ctrl+C to stop.\n")
    forwarded_count = 0

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue

            # Check if line is valid JSON telemetry
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    req_data = line.encode("utf-8")
                    req = urllib.request.Request(
                        DASHBOARD_URL,
                        data=req_data,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        res_body = json.loads(resp.read().decode("utf-8"))
                        forwarded_count += 1
                        seq = payload.get("sequence", "?")
                        v = payload.get("voltage_V", "?")
                        state = payload.get("state", "?")
                        print(f"[FORWARD #{forwarded_count}] Seq: {seq} | State: {state} | V: {v}V -> Dashboard: {res_body.get('status')}")
                except Exception as post_err:
                    print(f"[POST_ERROR] Forwarding packet failed: {post_err}")
            else:
                # Regular debug/log line from ESP32
                print(f"[ESP32_LOG] {line}")

        except KeyboardInterrupt:
            print("\n[STOPPING] Bridge stopped by operator.")
            break
        except Exception as exc:
            print(f"[RX_ERROR] {exc}")
            time.sleep(0.5)

    ser.close()


if __name__ == "__main__":
    com = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD
    run_bridge(com, baud)
