"""
Test submission and cluster monitoring script for Canonical Causal Decoder Training Test.
Submits the training task through the Client CLI, triggering:
1. Smoke test via CanonicalCausalDecoderPartitioner.CreateSample()
2. Dataset sharding into 2 shards via CanonicalCausalDecoderPartitioner.CreateShards()
3. Task registration with Coordinator
4. Coordinator scheduling to both Trainer 1 and Trainer 2
5. P2P artifact transfers (model archive and dataset shards)
6. Local Hugging Face Trainer fine-tuning on both nodes
7. Delta updates serialization (.safetensors) and P2P upload to Client
8. Sample-weighted Federated Averaging and version 1 model archive (.gz) aggregation
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
DB_PATH = WORK_DIR / "db" / "training.db"


def check_service_health(url: str, name: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SubmitScript"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def poll_training_completion(timeout_seconds: int = 180) -> tuple[list[dict], dict]:
    print(f"[Submit] Polling Client database for training and aggregation completion (timeout: {timeout_seconds}s)...")
    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout_seconds:
        if not DB_PATH.exists():
            time.sleep(1.0)
            continue

        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query shards
            cursor.execute("SELECT id, model_id, shard_id, status, trainer_node_id, sample_count, update_artifact_path FROM training_shards")
            shard_rows = [dict(row) for row in cursor.fetchall()]

            # Query new aggregated model version
            cursor.execute("SELECT id, model_id, model_version, model_type, model_artifact_path FROM models WHERE model_version != '0'")
            model_rows = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if shard_rows:
                statuses = [r["status"] for r in shard_rows]
                if statuses != last_status:
                    last_status = statuses
                    elapsed = time.time() - start_time
                    trainers = [r.get("trainer_node_id") or "-" for r in shard_rows]
                    print(f"[Submit] [{elapsed:4.1f}s] Shards ({len(shard_rows)}): {statuses} | Trainers: {trainers} | Aggregated models: {len(model_rows)}")

                all_completed = len(shard_rows) >= 2 and all(str(s).lower() == "completed" for s in statuses)
                has_aggregated = len(model_rows) > 0 and Path(model_rows[0]["model_artifact_path"]).is_file()

                if all_completed and has_aggregated:
                    elapsed = time.time() - start_time
                    print(f"[Submit] [SUCCESS] All {len(shard_rows)} shards completed and Model v{model_rows[0]['model_version']} aggregated after {elapsed:.1f}s!")
                    return shard_rows, model_rows[0]

        except Exception:
            pass

        time.sleep(2.0)

    raise TimeoutError(f"Training workflow did not complete within {timeout_seconds} seconds.")


def main() -> int:
    print("================================================================================")
    print("    Canonical Causal Decoder Training Test: Submit Task & Run Cluster           ")
    print("================================================================================")

    # 1. Health checks
    if not check_service_health("http://127.0.0.1:8080/health", "Coordinator"):
        print("[Submit] [ERROR] Coordinator is not running or unhealthy at http://127.0.0.1:8080/health", file=sys.stderr)
        print("[Submit] Please run `python setup.py` first to boot the cluster.", file=sys.stderr)
        return 1

    if not check_service_health("http://127.0.0.1:8090/health", "Relay"):
        print("[Submit] [ERROR] Bootstrap Relay is not running at http://127.0.0.1:8090/health", file=sys.stderr)
        return 1

    model_path = ARTIFACTS_DIR / "tinystories_base.gz"
    dataset_path = ARTIFACTS_DIR / "tinystories_train.pt"
    config_path = ARTIFACTS_DIR / "causal_decoder_config.json"

    for artifact in [model_path, dataset_path, config_path]:
        if not artifact.is_file():
            print(f"[Submit] [ERROR] Required artifact missing: {artifact}", file=sys.stderr)
            print("[Submit] Please run `python setup.py` to generate test assets.", file=sys.stderr)
            return 1

    client_work = WORK_DIR / "client_artifacts"
    client_work.mkdir(parents=True, exist_ok=True)

    # 2. Invoke Client CLI submit-training
    cmd = [
        sys.executable,
        str(SRC_DIR / "Client" / "main.py"),
        "submit-training",
        "--model-type", "canonical_causal_decoder",
        "--model-path", str(model_path.resolve()),
        "--dataset-path", str(dataset_path.resolve()),
        "--model-version", "0",
        "--training-config", str(config_path.resolve()),
    ]

    env = os.environ.copy()
    env.update({
        "P2P_GRPC_HOST": "127.0.0.1",
        "P2P_GRPC_PORT": "50051",
        "TRAINING_CLIENT_DB_PATH": str(DB_PATH.resolve()),
        "TRAINING_WORKING_DIRECTORY": str(client_work.resolve()),
        "TRAINING_CLIENT_WORKING_DIRECTORY": str(client_work.resolve()),
        "WORKING_DIR": str(client_work.resolve()),
        "COORDINATOR_ADDRESS": "http://127.0.0.1:8080",
        "PYTHONPATH": f"{SRC_DIR / 'Client'}{os.pathsep}{SRC_DIR}",
    })

    print(f"[Submit] Submitting task via Client CLI...")
    print(f"[Submit] Command: {' '.join(cmd)}")
    sub_res = subprocess.run(cmd, cwd=str(SRC_DIR / "Client"), env=env)
    if sub_res.returncode != 0:
        print("[Submit] [ERROR] Client submission command failed.", file=sys.stderr)
        return sub_res.returncode

    # 3. Monitor cluster training execution until completion
    try:
        shards, new_model = poll_training_completion(timeout_seconds=180)
        print("\n[Submit] --- Cluster Execution Summary ---")
        for s in shards:
            print(f"  Shard {s['shard_id']}: status={s['status']}, samples={s['sample_count']}, trainer={s['trainer_node_id']}")
        print(f"  New Model: version={new_model['model_version']}, artifact={new_model['model_artifact_path']}")
        print("================================================================================")
        return 0
    except TimeoutError as exc:
        print(f"\n[Submit] [TIMEOUT] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
