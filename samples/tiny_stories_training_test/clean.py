"""
clean.py

Standalone cleanup, process termination, and directory initialization utility
for TinyStories Multi-Round Distributed Training Test:
1. Kills all tracked background processes in .test_pids.json.
2. Clears any lingering listeners on test ports (4001, 8090, 8080, 8081, 50051..50053, 9001..9003).
3. Stops and removes Docker containers (trainswarm-relay, trainswarm-coordinator).
4. Cleans or initializes working directories under ./work/ and ./reports/.
5. Removes created test files, reports, and model/dataset artifacts (./artifacts/, ./fine-tuning-dataset/).
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SAMPLE_DIR = Path(__file__).resolve().parent
WORK_DIR = SAMPLE_DIR / "work"
REPORTS_DIR = SAMPLE_DIR / "reports"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
FINETUNING_DIR = SAMPLE_DIR / "fine-tuning-dataset"
PIDS_FILE = SAMPLE_DIR / ".test_pids.json"

TEST_PORTS = [4001, 8090, 8080, 8081, 50051, 50052, 50053, 9001, 9002, 9003]
CONTAINER_NAMES = ["trainswarm-relay", "trainswarm-coordinator"]


def kill_tracked_processes() -> None:
    """Kill processes recorded in .test_pids.json."""
    if not PIDS_FILE.exists():
        return

    print(f"[Clean] Reading tracked PIDs from {PIDS_FILE.name}...")
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
        print(f"[Clean] Warning reading {PIDS_FILE.name}: {exc}")
    finally:
        PIDS_FILE.unlink(missing_ok=True)


def kill_processes_on_ports(ports: list[int]) -> None:
    """Terminate any lingering processes bound to the test ports."""
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

        # Also terminate orphan sidecar and relay binaries
        for proc_name in ["p2pd.exe", "relay.exe"]:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True, check=False)
    else:
        for port in ports:
            try:
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, check=False)
            except Exception:
                pass

    time.sleep(1.0)


def stop_docker_containers() -> None:
    """Stops and removes Docker containers spawned by setup_docker.py."""
    for name in CONTAINER_NAMES:
        try:
            res = subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                print(f"[Clean] Removed Docker container '{name}'.")
        except FileNotFoundError:
            # Docker CLI not installed or in PATH
            break
        except Exception:
            pass


def purge_work_dir() -> None:
    """Removes temporary runtime directory work/."""
    if WORK_DIR.exists():
        print(f"[Clean] Removing working directory: {WORK_DIR.name}/...")
        try:
            shutil.rmtree(WORK_DIR, ignore_errors=True)
            print("[Clean] Working directory successfully removed.")
        except Exception as exc:
            print(f"[Clean] Warning removing {WORK_DIR.name}: {exc}")


def purge_reports_dir() -> None:
    """Removes reports directory and all generated telemetry/plots."""
    if REPORTS_DIR.exists():
        print(f"[Clean] Removing reports directory: {REPORTS_DIR.name}/...")
        try:
            shutil.rmtree(REPORTS_DIR, ignore_errors=True)
            print("[Clean] Reports directory successfully removed.")
        except Exception as exc:
            print(f"[Clean] Warning removing {REPORTS_DIR.name}: {exc}")


def purge_artifacts_dir() -> None:
    """Removes created model/dataset artifacts and directories."""
    if ARTIFACTS_DIR.exists():
        print(f"[Clean] Removing artifacts directory: {ARTIFACTS_DIR.name}/...")
        try:
            shutil.rmtree(ARTIFACTS_DIR, ignore_errors=True)
            print("[Clean] Artifacts directory successfully removed.")
        except Exception as exc:
            print(f"[Clean] Warning removing {ARTIFACTS_DIR.name}: {exc}")

    if FINETUNING_DIR.exists():
        print(f"[Clean] Removing fine-tuning dataset directory: {FINETUNING_DIR.name}/...")
        try:
            shutil.rmtree(FINETUNING_DIR, ignore_errors=True)
            print("[Clean] Fine-tuning dataset directory successfully removed.")
        except Exception as exc:
            print(f"[Clean] Warning removing {FINETUNING_DIR.name}: {exc}")


def purge_cache_and_pids() -> None:
    """Removes __pycache__ and lingering .test_pids.json."""
    if PIDS_FILE.exists():
        try:
            PIDS_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    for p in SAMPLE_DIR.rglob("__pycache__"):
        if p.is_dir():
            try:
                shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass


def init_runtime_dirs(clean_work: bool = True, clean_reports: bool = False) -> None:
    """Initializes required runtime and logging directory hierarchy."""
    if clean_work:
        purge_work_dir()
    if clean_reports:
        purge_reports_dir()

    for d in [
        WORK_DIR / "db",
        WORK_DIR / "logs",
        WORK_DIR / "client_artifacts",
        WORK_DIR / "trainer1_artifacts",
        WORK_DIR / "trainer2_artifacts",
        REPORTS_DIR / "trainers",
    ]:
        d.mkdir(parents=True, exist_ok=True)
    print(f"[Clean] Initialized directory hierarchy under '{WORK_DIR.name}/' and '{REPORTS_DIR.name}/'.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup utility for TinyStories distributed training test.")
    parser.add_argument("--keep-artifacts", action="store_true", help="Do not delete artifacts/ and fine-tuning-dataset/.")
    parser.add_argument("--keep-reports", action="store_true", help="Do not delete reports/ directory.")
    parser.add_argument("--keep-work", action="store_true", help="Do not delete work/ directory.")
    parser.add_argument("--artifacts-only", action="store_true", help="Only delete artifacts/ and created files without stopping processes.")
    args = parser.parse_args()

    print("=" * 65)
    print(" TinyStories Test: Cluster Teardown & Reset ")
    print("=" * 65)

    if not args.artifacts_only:
        kill_tracked_processes()
        stop_docker_containers()
        kill_processes_on_ports(TEST_PORTS)

    if not args.keep_work:
        purge_work_dir()
    if not args.keep_reports:
        purge_reports_dir()
    if not args.keep_artifacts:
        purge_artifacts_dir()

    purge_cache_and_pids()

    print("[+] Teardown and cleanup complete.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
