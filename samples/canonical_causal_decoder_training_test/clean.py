"""
Standalone cleanup and process termination utility for Canonical Causal Decoder Training Test.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

SAMPLE_DIR = Path(__file__).resolve().parent
WORK_DIR = SAMPLE_DIR / "work"
PIDS_FILE = SAMPLE_DIR / ".test_pids.json"

TEST_PORTS = [4001, 8090, 8080, 8081, 50051, 50052, 50053, 9001, 9002, 9003]


def kill_tracked_processes() -> None:
    """Kill processes tracked in .test_pids.json."""
    if not PIDS_FILE.exists():
        return

    print(f"[Clean] Found tracked PIDs file at {PIDS_FILE}...")
    try:
        with open(PIDS_FILE, "r", encoding="utf-8") as f:
            pids = json.load(f)

        print(f"[Clean] Terminating {len(pids)} tracked background processes...")
        for pid in pids:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
                else:
                    os.kill(pid, 9)
            except Exception:
                pass
    except Exception as exc:
        print(f"[Clean] Warning reading {PIDS_FILE}: {exc}")
    finally:
        PIDS_FILE.unlink(missing_ok=True)


def kill_processes_on_ports(ports: list[int]) -> None:
    """Terminate any remaining processes listening on the test ports."""
    print(f"[Clean] Checking test ports: {ports}...")
    if sys.platform == "win32":
        try:
            ports_str = ",".join(map(str, ports))
            ps_cmd = (
                f"Get-NetTCPConnection -LocalPort {ports_str} -ErrorAction SilentlyContinue "
                f"| Select-Object -ExpandProperty OwningProcess -Unique"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=False,
            )
            killed_pids = []
            for line in res.stdout.splitlines():
                pid_str = line.strip()
                if pid_str.isdigit() and int(pid_str) not in (0, 4):
                    subprocess.run(["taskkill", "/F", "/T", "/PID", pid_str], capture_output=True, check=False)
                    killed_pids.append(pid_str)
            if killed_pids:
                print(f"[Clean] Terminated processes on ports with PIDs: {killed_pids}")
        except Exception as exc:
            print(f"[Clean] Warning during port cleanup: {exc}")

        # Also kill any orphan p2pd.exe or relay.exe
        for proc_name in ["p2pd.exe", "relay.exe"]:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True, check=False)
    else:
        for port in ports:
            try:
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, check=False)
            except Exception:
                pass

    time.sleep(1.0)


def purge_work_dir() -> None:
    """Purge temporary runtime artifacts in work directory."""
    if WORK_DIR.exists():
        print(f"[Clean] Removing working directory: {WORK_DIR}...")
        try:
            shutil.rmtree(WORK_DIR, ignore_errors=True)
            print("[Clean] Working directory successfully removed.")
        except Exception as exc:
            print(f"[Clean] Warning removing {WORK_DIR}: {exc}")


def main() -> int:
    print("================================================================================")
    print("    Canonical Causal Decoder Training Test: Teardown & Clean                    ")
    print("================================================================================")
    kill_tracked_processes()
    kill_processes_on_ports(TEST_PORTS)
    purge_work_dir()
    print("[Clean] Teardown and cleanup completed successfully.")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
