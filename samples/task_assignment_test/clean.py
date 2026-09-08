"""Teardown and cleanup utility for the Task Assignment Test environment.

Terminates background Coordinator and Trainer processes recorded in .test_pids.txt,
frees network ports, and deletes temporary databases, artifacts, and log files.
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
COORDINATOR_PORT = 5050
COORDINATOR_GRPC_PORT = 5051

PID_FILE = SAMPLE_DIR / ".test_pids.txt"
DB_DIR = SAMPLE_DIR / "db"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
CLIENT_WORK_DIR = SAMPLE_DIR / "client_work"
COORD_LOG_FILE = SAMPLE_DIR / "coordinator.log"
TRAINER_LOG_FILE = SAMPLE_DIR / "trainer.log"


def kill_process_tree(pid: int) -> None:
    """Kill process and all descendant processes."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def free_port_if_in_use(port: int) -> None:
    """Check if port is currently in use and terminate the listening process."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess",
                ],
                capture_output=True,
                text=True,
            )
            pids = [line.strip() for line in res.stdout.strip().splitlines() if line.strip().isdigit()]
            for pid in pids:
                print(f"[Clean] Port {port} occupied by PID {pid}. Terminating process...")
                kill_process_tree(int(pid))
        except Exception:
            pass


def clean_environment(keep_artifacts: bool = False) -> None:
    """Tear down spawned processes and temporary test directories."""
    print("================================================================================")
    print("=== [Clean] Cleaning Task Assignment Test Environment ===")
    print("================================================================================")

    # 1. Terminate recorded background processes
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pids = [int(line.strip()) for line in f if line.strip().isdigit()]
            for pid in pids:
                print(f"[Clean] Terminating background process PID {pid}...")
                kill_process_tree(pid)
            PID_FILE.unlink()
            print("[Clean] [OK] Removed .test_pids.txt")
        except Exception as e:
            print(f"[Clean] [WARN] Error during PID cleanup: {e}")

    # 2. Free ports if occupied
    free_port_if_in_use(COORDINATOR_PORT)
    free_port_if_in_use(COORDINATOR_GRPC_PORT)

    # 3. Clean temporary directories
    dirs_to_clean = [DB_DIR, CLIENT_WORK_DIR]
    if not keep_artifacts:
        dirs_to_clean.append(ARTIFACTS_DIR)

    for target_dir in dirs_to_clean:
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir)
                print(f"[Clean] [OK] Removed directory: {target_dir.name}/")
            except Exception as e:
                print(f"[Clean] [WARN] Could not remove {target_dir}: {e}")

    # 4. Clean log files
    for log_file in [COORD_LOG_FILE, TRAINER_LOG_FILE]:
        if log_file.exists():
            try:
                log_file.unlink()
                print(f"[Clean] [OK] Removed log file: {log_file.name}")
            except Exception as e:
                print(f"[Clean] [WARN] Could not remove {log_file}: {e}")

    print("================================================================================")
    print("=== [Clean] Teardown complete. All test processes and files cleaned. ===")
    print("================================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up Task Assignment test environment.")
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep generated PyTorch model and dataset artifacts under artifacts/.",
    )
    args = parser.parse_args()
    clean_environment(keep_artifacts=args.keep_artifacts)


if __name__ == "__main__":
    main()
