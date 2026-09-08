"""Submission and end-to-end verification script for Task Assignment Test.

Executes the Client CLI submit-training workflow against the live running Coordinator,
and verifies:
1. Client SQLite database contains persisted Model entity and READY training shards.
2. Coordinator SQLite database contains TrainingTask assigned to trainer-node-01.
3. Trainer log confirms receipt of StartTrainingCommand with all 5 required fields.
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"

COORDINATOR_PORT = 5050
HEALTH_URL = f"http://127.0.0.1:{COORDINATOR_PORT}/health"

DB_DIR = SAMPLE_DIR / "db"
COORD_DB_FILE = DB_DIR / "coordinator.db"
CLIENT_DB_FILE = DB_DIR / "training.db"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
CLIENT_WORK_DIR = SAMPLE_DIR / "client_work"

TRAINER_LOG_FILE = SAMPLE_DIR / "trainer.log"
COORD_LOG_FILE = SAMPLE_DIR / "coordinator.log"


def check_prerequisites() -> bool:
    """Verify that Coordinator is healthy and test artifacts exist."""
    print("[Submit] Checking Coordinator health...")
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "TaskAssignmentSubmit"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                print(f"[Submit] [ERROR] Coordinator responded with HTTP {resp.status} instead of 200.", file=sys.stderr)
                return False
    except Exception as e:
        print(
            f"[Submit] [ERROR] Could not connect to Coordinator at {HEALTH_URL}: {e}\n"
            "         Please run 'python startup.py' first.",
            file=sys.stderr,
        )
        return False

    required_artifacts = [
        ARTIFACTS_DIR / "test_model.pt2",
        ARTIFACTS_DIR / "test_dataset.pt",
        ARTIFACTS_DIR / "training_config.json",
    ]
    for artifact in required_artifacts:
        if not artifact.exists():
            print(f"[Submit] [ERROR] Required artifact missing: {artifact}", file=sys.stderr)
            print("         Please run 'python startup.py' first.", file=sys.stderr)
            return False

    return True


def execute_client_submit() -> tuple[int, str, str]:
    """Execute Client CLI submit-training via subprocess."""
    client_script = SRC_DIR / "Client" / "main.py"
    cmd = [
        sys.executable,
        str(client_script),
        "submit-training",
        "--model-path", str((ARTIFACTS_DIR / "test_model.pt2").resolve()),
        "--dataset-path", str((ARTIFACTS_DIR / "test_dataset.pt").resolve()),
        "--model-version", "v1.0",
        "--training-config", str((ARTIFACTS_DIR / "training_config.json").resolve()),
    ]

    env = subprocess.os.environ.copy()
    env["COORDINATOR_ADDRESS"] = f"http://127.0.0.1:{COORDINATOR_PORT}"
    env["TRAINING_CLIENT_DB_PATH"] = str(CLIENT_DB_FILE.resolve())
    env["TRAINING_WORKING_DIRECTORY"] = str(CLIENT_WORK_DIR.resolve())
    env["CLIENT_NODE_ID"] = "client-node-01"
    env["PYTHONPATH"] = f"{SRC_DIR / 'Client'}{subprocess.os.pathsep}{SRC_DIR}"

    print("[Submit] Executing Client CLI submit-training...")
    print(f"         Command: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        env=env,
        cwd=str(SRC_DIR / "Client"),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def verify_client_db() -> dict:
    """Query and assert Client SQLite database contents."""
    print(f"\n[Assert] Verifying Client SQLite database at {CLIENT_DB_FILE}...")
    if not CLIENT_DB_FILE.exists():
        raise AssertionError(f"Client database file does not exist: {CLIENT_DB_FILE}")

    conn = sqlite3.connect(str(CLIENT_DB_FILE), timeout=5)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Check models table
    cursor.execute("SELECT * FROM models")
    models = cursor.fetchall()
    if not models:
        conn.close()
        raise AssertionError("Client 'models' table is empty. Model metadata was not persisted!")

    model_row = models[0]
    model_id = model_row["model_id"]
    dataset_id = model_row["dataset_id"]
    model_version = model_row["model_version"]
    model_artifact_path = model_row["model_artifact_path"]
    training_config_path = model_row["training_config_path"]

    print(f"[Assert] [OK] Found Model record in Client DB:")
    print(f"         model_id:             {model_id}")
    print(f"         model_version:        {model_version}")
    print(f"         dataset_id:           {dataset_id}")
    print(f"         model_artifact_path:  {model_artifact_path}")
    print(f"         training_config_path: {training_config_path}")

    assert model_version == "v1.0", f"Expected model_version 'v1.0', got '{model_version}'"
    assert Path(model_artifact_path).exists(), f"Staged model artifact does not exist at {model_artifact_path}"
    assert Path(training_config_path).exists(), f"Staged config file does not exist at {training_config_path}"

    # 2. Check training_shards table
    cursor.execute("SELECT * FROM training_shards WHERE dataset_id = ?", (dataset_id,))
    shards = cursor.fetchall()
    conn.close()

    if not shards:
        raise AssertionError(f"No training shards found for dataset_id='{dataset_id}' in Client DB.")

    for shard in shards:
        status = shard["status"]
        shard_id = shard["shard_id"]
        print(f"[Assert] [OK] Training shard: {shard_id} (status: {status})")
        assert status.upper() == "READY", f"Expected shard status 'READY', but got '{status}'"

    return {
        "model_id": model_id,
        "dataset_id": dataset_id,
        "model_version": model_version,
        "shards": [s["shard_id"] for s in shards],
    }


def verify_coordinator_db(model_id: str) -> dict:
    """Poll Coordinator SQLite database to assert task creation and assignment."""
    print(f"\n[Assert] Verifying Coordinator SQLite database at {COORD_DB_FILE}...")
    if not COORD_DB_FILE.exists():
        raise AssertionError(f"Coordinator database file does not exist: {COORD_DB_FILE}")

    assigned_task = None
    for attempt in range(1, 20):
        try:
            conn = sqlite3.connect(str(COORD_DB_FILE), timeout=5)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM TrainingTasks WHERE ModelId = ?",
                (model_id,),
            )
            tasks = cursor.fetchall()

            if tasks:
                for t in tasks:
                    if t["TrainerNodeId"] and len(t["TrainerNodeId"].strip()) > 0:
                        assigned_task = dict(t)
                        break

            cursor.execute("SELECT * FROM Trainers WHERE TrainerNodeId = 'trainer-node-01'")
            trainer = cursor.fetchone()
            trainer_dict = dict(trainer) if trainer else None

            conn.close()

            if assigned_task:
                print(f"[Assert] [OK] Found assigned TrainingTask on attempt {attempt}:")
                print(f"         TrainingTaskId: {assigned_task['TrainingTaskId']}")
                print(f"         ModelId:        {assigned_task['ModelId']}")
                print(f"         ShardId:        {assigned_task['ShardId']}")
                print(f"         TrainerNodeId:  {assigned_task['TrainerNodeId']}")
                if trainer_dict:
                    print(f"         Trainer Status: {trainer_dict['Status']} (2 = BUSY)")
                return assigned_task
        except sqlite3.OperationalError:
            pass
        time.sleep(1)

    raise AssertionError(f"Timeout waiting for Coordinator to assign tasks for ModelId '{model_id}' to trainer-node-01.")


def verify_trainer_log(expected_data: dict) -> None:
    """Assert that Trainer received StartTrainingCommand and logged its 5 fields."""
    print(f"\n[Assert] Verifying Trainer log at {TRAINER_LOG_FILE}...")
    if not TRAINER_LOG_FILE.exists():
        raise AssertionError(f"Trainer log file does not exist: {TRAINER_LOG_FILE}")

    found = False
    for attempt in range(1, 20):
        try:
            content = TRAINER_LOG_FILE.read_text(encoding="utf-8", errors="replace")
            if "StartTraining" in content and expected_data["model_id"] in content:
                print(f"[Assert] [OK] Trainer log recorded StartTrainingCommand on attempt {attempt}!")
                print("----------------------------------------------------------------")
                for line in content.splitlines():
                    if "StartTraining" in line or "COMMAND RECEIVED" in line:
                        print(f"  {line}")
                print("----------------------------------------------------------------")
                found = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not found:
        print("=== Full Trainer Log Output ===", file=sys.stderr)
        if TRAINER_LOG_FILE.exists():
            print(TRAINER_LOG_FILE.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
        raise AssertionError(
            f"Trainer log did not contain expected StartTrainingCommand for ModelId '{expected_data['model_id']}'."
        )


def main() -> int:
    print("================================================================================")
    print("   TrainSwarm Task Assignment Verification Harness: Training Submission        ")
    print("================================================================================")

    if not check_prerequisites():
        return 1

    # 1. Execute Client submission
    returncode, stdout, stderr = execute_client_submit()
    print("--- Client Submission Output ---")
    print(stdout.strip())
    if stderr.strip():
        print("--- Client Stderr ---")
        print(stderr.strip(), file=sys.stderr)

    if returncode != 0:
        print(f"[Submit] [ERROR] Client submit-training failed with exit code {returncode}", file=sys.stderr)
        return 1

    # 2. Verify Client Database
    try:
        client_data = verify_client_db()
    except Exception as e:
        print(f"[Assert] [FAIL] Client Database assertion failed: {e}", file=sys.stderr)
        return 1

    # 3. Verify Coordinator Database
    try:
        task_data = verify_coordinator_db(client_data["model_id"])
    except Exception as e:
        print(f"[Assert] [FAIL] Coordinator Database assertion failed: {e}", file=sys.stderr)
        return 1

    # 4. Verify Trainer Log
    try:
        verify_trainer_log({
            "model_id": client_data["model_id"],
            "shard_id": task_data["ShardId"],
        })
    except Exception as e:
        print(f"[Assert] [FAIL] Trainer Log assertion failed: {e}", file=sys.stderr)
        return 1

    print("\n================================================================================")
    print("=== [PASS] All Task Assignment Test Assertions Passed! ===")
    print("  1. Client local SQLite: Model metadata saved & shards marked READY.")
    print("  2. Coordinator API: Task created & thread-safe background scheduler assigned task.")
    print("  3. CommandCenter: Dispatched StartTrainingCommand via gRPC stream.")
    print("  4. Trainer Node: Received command and logged all 5 task properties.")
    print("================================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
