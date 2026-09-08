"""
Test execution script for Full Distributed Training Test.
Submits the training task through the Client CLI, triggering:
1. Dataset sharding and local SQLite model/shard staging
2. Registration with Coordinator
3. Coordinator scheduling to both Trainer 1 and Trainer 2
4. Inbound P2P transfers: task retrieval, model transfer, shard transfer
5. Local PyTorch training on both trainers
6. Update delta transmission over P2P and Client SQLite completion
7. Ephemeral cleanup on trainers
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"


def is_docker_active() -> bool:
    try:
        proc = subprocess.run(["docker", "compose", "ps", "--status", "running"], cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
        return proc.returncode == 0 and "client" in proc.stdout
    except FileNotFoundError:
        return False


def run_docker_test() -> int:
    print("=== [Test] Submitting Training Task via Docker Client Container ===")
    cmd = [
        "docker", "compose", "exec", "-T", "client",
        "python", "main.py", "submit-training",
        "--model-path", "/seed_artifacts/test_model.pt2",
        "--dataset-path", "/seed_artifacts/test_dataset.pt",
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", "/seed_artifacts/training_config.json",
    ]
    print(f"[Test] Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(SAMPLE_DIR))
    if res.returncode == 0:
        print("=== [Test] Task submission executed successfully via Docker! ===")
    else:
        print("[Test] [ERROR] Submission failed.", file=sys.stderr)
    return res.returncode


def run_local_test() -> int:
    print("=== [Test] Submitting Training Task via Local Client CLI ===")
    db_path = (WORK_DIR / "db" / "training.db").resolve()
    client_work = (WORK_DIR / "client_artifacts").resolve()
    model_path = (ARTIFACTS_DIR / "test_model.pt2").resolve()
    dataset_path = (ARTIFACTS_DIR / "test_dataset.pt").resolve()
    config_path = (ARTIFACTS_DIR / "training_config.json").resolve()

    cmd = [
        sys.executable,
        str(SRC_DIR / "Client" / "main.py"),
        "submit-training",
        "--model-path", str(model_path),
        "--dataset-path", str(dataset_path),
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", str(config_path),
    ]

    env = os.environ.copy()
    env.update({
        "P2P_GRPC_HOST": "127.0.0.1",
        "P2P_GRPC_PORT": "50051",
        "TRAINING_CLIENT_DB_PATH": str(db_path),
        "TRAINING_WORKING_DIRECTORY": str(client_work),
        "TRAINING_CLIENT_WORKING_DIRECTORY": str(client_work),
        "WORKING_DIR": str(client_work),
        "COORDINATOR_ADDRESS": "http://127.0.0.1:8080",
        "PYTHONPATH": f"{SRC_DIR / 'Client'}{os.pathsep}{SRC_DIR}",
    })

    print(f"[Test] Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(SRC_DIR / "Client"), env=env)
    if res.returncode == 0:
        print("=== [Test] Task submission executed successfully locally! ===")
    else:
        print("[Test] [ERROR] Submission failed.", file=sys.stderr)
    return res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Distributed Training Test Runner")
    parser.add_argument("--mode", choices=["auto", "docker", "local"], default="auto", help="Execution mode")
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        mode = "docker" if is_docker_active() else "local"

    if mode == "docker":
        return run_docker_test()
    else:
        return run_local_test()


if __name__ == "__main__":
    sys.exit(main())
