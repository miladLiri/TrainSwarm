"""Zero-mock verification runner for Trainer Connection without Docker.

Uses dotnet CLI to launch Coordinator and python CLI to launch Trainer,
waits for the Trainer startup connection workflow to complete,
and queries the Coordinator SQLite database directly to assert that the Trainer record
was inserted with Status = 1 (IDLE).
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"

COORDINATOR_PORT = 8080
HEALTH_URL = f"http://127.0.0.1:{COORDINATOR_PORT}/health"

DB_DIR = SAMPLE_DIR / "db"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
DB_FILE = DB_DIR / "coordinator.db"
PID_FILE = SAMPLE_DIR / ".test_pids.txt"
COORD_LOG_FILE = SAMPLE_DIR / "coordinator.log"
TRAINER_LOG_FILE = SAMPLE_DIR / "trainer.log"


def is_dotnet_available() -> bool:
    """Check if dotnet CLI is present in PATH."""
    return shutil.which("dotnet") is not None


def is_python_available() -> bool:
    """Check if python executable is available."""
    return shutil.which("python") is not None or shutil.which(sys.executable) is not None


def kill_process_tree(pid: int) -> None:
    """Kill process and all of its child processes."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def save_pid(pid: int) -> None:
    """Save a spawned PID for cleanup."""
    with open(PID_FILE, "a", encoding="utf-8") as f:
        f.write(f"{pid}\n")


def free_port_if_in_use(port: int) -> None:
    """Check if port is currently in use and terminate the listening process."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess"],
                capture_output=True,
                text=True,
            )
            pids = [line.strip() for line in res.stdout.strip().splitlines() if line.strip().isdigit()]
            for pid in pids:
                print(f"[Setup] Port {port} occupied by PID {pid}. Terminating process...")
                kill_process_tree(int(pid))
        except Exception:
            pass


def clean_environment() -> None:
    """Tear down spawned processes and temporary test directories."""
    print("================================================================================")
    print("=== [Clean] Cleaning Trainer Connection Test Environment ===")
    print("================================================================================")

    # 1. Kill recorded PIDs
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pids = [int(line.strip()) for line in f if line.strip().isdigit()]
            for pid in pids:
                print(f"[Clean] Terminating recorded process PID {pid}...")
                kill_process_tree(pid)
            PID_FILE.unlink()
        except Exception as e:
            print(f"[Clean] [WARN] Could not clean recorded PIDs: {e}")

    # 2. Free port 8080 if still bound
    free_port_if_in_use(COORDINATOR_PORT)

    # 3. Clean directories
    for target_dir in [DB_DIR, ARTIFACTS_DIR]:
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir)
                print(f"[Clean] Removed directory: {target_dir.name}/")
            except Exception as e:
                print(f"[Clean] [WARN] Could not remove {target_dir}: {e}")

    # 4. Clean logs
    for log_file in [COORD_LOG_FILE, TRAINER_LOG_FILE]:
        if log_file.exists():
            try:
                log_file.unlink()
                print(f"[Clean] Removed log file: {log_file.name}")
            except Exception as e:
                print(f"[Clean] [WARN] Could not remove {log_file}: {e}")

    print("[Clean] Teardown complete.")
    print("================================================================================")


def setup_and_verify(keep_alive: bool = False) -> bool:
    """Launch Coordinator and Trainer via CLI, verify database persistence."""
    if not is_dotnet_available():
        print("[Setup] [ERROR] 'dotnet' CLI was not found in PATH.", file=sys.stderr)
        return False

    if not is_python_available():
        print("[Setup] [ERROR] 'python' executable was not found.", file=sys.stderr)
        return False

    print("================================================================================")
    print("      TrainSwarm Trainer Connection: CLI Verification Runner (No Docker)       ")
    print("================================================================================")

    # Clean up previous runs
    clean_environment()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Setup] Database directory:  {DB_DIR}")
    print(f"[Setup] Artifacts directory: {ARTIFACTS_DIR}")

    # 1. Start Coordinator via dotnet CLI
    coord_proj = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "TrainSwarm.Coordinator.Api.csproj"
    if not coord_proj.exists():
        print(f"[Setup] [ERROR] Coordinator project not found at {coord_proj}", file=sys.stderr)
        return False

    coord_env = os.environ.copy()
    coord_env["COORDINATOR_DB_CONNECTION_STRING"] = f"Data Source={DB_FILE.resolve()}"
    coord_env["ASPNETCORE_URLS"] = f"http://127.0.0.1:{COORDINATOR_PORT}"

    coord_log = open(COORD_LOG_FILE, "w", encoding="utf-8")
    print(f"[Setup] Starting Coordinator on port {COORDINATOR_PORT} via dotnet CLI...")
    coord_cmd = [
        "dotnet", "run",
        "--project", str(coord_proj),
        "--urls", f"http://127.0.0.1:{COORDINATOR_PORT}",
    ]
    coord_proc = subprocess.Popen(
        coord_cmd,
        env=coord_env,
        stdout=coord_log,
        stderr=subprocess.STDOUT,
    )
    save_pid(coord_proc.pid)

    # 2. Poll Coordinator health endpoint
    print(f"[Setup] Waiting for Coordinator health endpoint at {HEALTH_URL}...", flush=True)
    healthy = False
    for attempt in range(1, 40):
        for test_url in [HEALTH_URL, f"http://127.0.0.1:{COORDINATOR_PORT}/openapi/v1.json"]:
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": "TrainerInitTest"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        print(f"[Setup] [OK] Coordinator healthy (HTTP 200 via {test_url}) on attempt {attempt}.", flush=True)
                        healthy = True
                        break
            except Exception:
                pass
        if healthy:
            break
        time.sleep(1)

    if not healthy:
        print("[Setup] [ERROR] Coordinator failed to become healthy.", file=sys.stderr)
        coord_log.flush()
        if COORD_LOG_FILE.exists():
            print("=== Coordinator Output ===", file=sys.stderr)
            print(COORD_LOG_FILE.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
        kill_process_tree(coord_proc.pid)
        coord_log.close()
        return False

    # 3. Start Trainer via python CLI
    trainer_script = SRC_DIR / "Trainer" / "main.py"
    if not trainer_script.exists():
        print(f"[Setup] [ERROR] Trainer script not found at {trainer_script}", file=sys.stderr)
        kill_process_tree(coord_proc.pid)
        coord_log.close()
        return False

    trainer_env = os.environ.copy()
    trainer_env["COORDINATOR_ADDRESS"] = f"http://127.0.0.1:{COORDINATOR_PORT}"
    trainer_env["COORDINATOR_GRPC_ADDRESS"] = f"127.0.0.1:{COORDINATOR_PORT}"
    trainer_env["TRAINER_WORKING_DIRECTORY"] = str(ARTIFACTS_DIR.resolve())
    trainer_env["PYTHONPATH"] = str(SRC_DIR / "Trainer")

    trainer_log = open(TRAINER_LOG_FILE, "w", encoding="utf-8")
    print(f"[Setup] Starting Trainer via python CLI ({sys.executable})...")
    trainer_cmd = [sys.executable, str(trainer_script)]
    trainer_proc = subprocess.Popen(
        trainer_cmd,
        env=trainer_env,
        cwd=str(SRC_DIR / "Trainer"),
        stdout=trainer_log,
        stderr=subprocess.STDOUT,
    )
    save_pid(trainer_proc.pid)

    # 4. Verify persistence in Coordinator SQLite database
    print(f"[Setup] Verifying Trainer registration in SQLite database at {DB_FILE}...")
    verified = False
    expected_node_id = "trainer-node-01"
    expected_status = 1  # TrainerStatus.IDLE

    for attempt in range(1, 30):
        if DB_FILE.exists():
            try:
                conn = sqlite3.connect(str(DB_FILE), timeout=5)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT Id, TrainerNodeId, Status FROM Trainers WHERE TrainerNodeId = ?",
                    (expected_node_id,),
                )
                row = cursor.fetchone()
                conn.close()

                if row is not None:
                    trainer_id, trainer_node_id, status = row
                    print(
                        f"[Setup] [OK] Found Trainer record on attempt {attempt}: "
                        f"Id={trainer_id}, TrainerNodeId='{trainer_node_id}', Status={status}"
                    )
                    if status == expected_status:
                        print(
                            f"[Setup] [SUCCESS] Status is {expected_status} (IDLE) as required!"
                        )
                        verified = True
                        break
                    else:
                        print(
                            f"[Setup] [WARN] Status {status} did not match expected {expected_status} (IDLE)."
                        )
            except sqlite3.OperationalError as e:
                print(f"[Setup] [DEBUG] SQLite read attempt {attempt}: {e}")
            except Exception as e:
                print(f"[Setup] [DEBUG] Database query error attempt {attempt}: {e}")

        time.sleep(1)

    # 5. Flush logs
    trainer_log.flush()
    coord_log.flush()

    if not verified:
        print("[Setup] [ERROR] Verification failed: Trainer record with status IDLE not found in DB.", file=sys.stderr)
        if TRAINER_LOG_FILE.exists():
            print("=== Trainer Output ===", file=sys.stderr)
            print(TRAINER_LOG_FILE.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
        if COORD_LOG_FILE.exists():
            print("=== Coordinator Output ===", file=sys.stderr)
            print(COORD_LOG_FILE.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)

    # 6. Teardown or Keep Alive
    if not keep_alive:
        print("[Setup] Stopping test processes...")
        kill_process_tree(trainer_proc.pid)
        kill_process_tree(coord_proc.pid)
        trainer_log.close()
        coord_log.close()
        if PID_FILE.exists():
            PID_FILE.unlink()
    else:
        print(f"[Setup] Test processes running (Coordinator PID {coord_proc.pid}, Trainer PID {trainer_proc.pid}).")
        trainer_log.close()
        coord_log.close()

    if verified:
        print("================================================================================")
        print("  [SUCCESS] ZERO-MOCK CLI VERIFICATION PASSED!                                  ")
        print("  Trainer successfully registered with Coordinator via dotnet and python CLI.   ")
        print("================================================================================")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="TrainSwarm Trainer Connection CLI Verification (No Docker)")
    parser.add_argument("--down", action="store_true", help="Stop processes and tear down test environment")
    parser.add_argument("--keep-alive", action="store_true", help="Keep Coordinator and Trainer running after verification")
    args = parser.parse_args()

    if args.down:
        clean_environment()
        return 0

    success = setup_and_verify(keep_alive=args.keep_alive)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
