"""Standalone cleanup and process termination utility for Full Distributed Training Test."""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

SAMPLE_DIR = Path(__file__).resolve().parent
WORK_DIR = SAMPLE_DIR / "work"

TEST_PORTS = [4001, 8090, 8080, 8081, 50051, 50052, 50053, 9001, 9002, 9003]


def kill_processes_on_ports(ports: list[int]) -> None:
    """Terminate processes listening on the test ports."""
    print(f"[Clean] Terminating processes on test ports: {ports}...")
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
                print(f"[Clean] Terminated processes with PIDs: {killed_pids}")
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
    print("       TrainSwarm: Multi-Node Teardown and Cleanup Utility                      ")
    print("================================================================================")
    kill_processes_on_ports(TEST_PORTS)
    purge_work_dir()
    print("[Clean] Teardown and cleanup completed successfully.")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
