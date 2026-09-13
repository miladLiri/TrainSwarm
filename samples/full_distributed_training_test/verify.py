"""
Comprehensive verification script for Full Distributed Training Test.

Asserts:
1. Client SQLite database:
   - Exactly 2 shards created for the 50-sample dataset
   - All shards transitioned to status "completed"
   - Each shard recorded trainer_node_id and update_artifact_path
2. Client working directory:
   - Update delta safetensors files exist on disk and have non-zero size
3. Trainer working directories:
   - Ephemeral shard (.pt) and update (.safetensors) files were cleaned up
   - Base model (.pt2) was retained in local cache
"""

from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"


def is_docker_active() -> bool:
    try:
        proc = subprocess.run(["docker", "compose", "ps", "--status", "running"], cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
        return proc.returncode == 0 and "client" in proc.stdout
    except FileNotFoundError:
        return False


def get_db_connection(mode: str) -> tuple[sqlite3.Connection, Path]:
    if mode == "docker":
        # Extract training.db from client container into work/db
        db_dir = WORK_DIR / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        local_db_path = db_dir / "docker_training.db"
        cmd = ["docker", "compose", "cp", "client:/data/training.db", str(local_db_path)]
        res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to copy training.db from client container: {res.stderr}")
        conn = sqlite3.connect(str(local_db_path))
        conn.row_factory = sqlite3.Row
        return conn, local_db_path
    else:
        db_path = WORK_DIR / "db" / "training.db"
        if not db_path.exists():
            raise FileNotFoundError(f"Client database not found at {db_path}")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, db_path


def poll_shards_completion(mode: str, timeout_seconds: int = 90) -> list[dict]:
    print(f"[Verify] Polling Client database for training and aggregation completion (timeout: {timeout_seconds}s)...")
    start_time = time.time()

    last_status = None
    while time.time() - start_time < timeout_seconds:
        try:
            conn, _ = get_db_connection(mode)
            cursor = conn.cursor()
            cursor.execute("SELECT id, model_id, shard_id, status, trainer_node_id, update_artifact_path FROM training_shards")
            rows = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT count(*) as count FROM models WHERE model_version = '2'")
            v2_row = cursor.fetchone()
            v2_count = v2_row["count"] if v2_row else 0
            conn.close()

            if rows:
                statuses = [r["status"] for r in rows]
                if statuses != last_status:
                    last_status = statuses
                    elapsed = time.time() - start_time
                    print(f"[Verify] [{elapsed:4.1f}s] Shard statuses: {statuses} | Model v2: {v2_count > 0}")

                if len(rows) >= 2 and all(str(s).lower() == "completed" for s in statuses) and v2_count > 0:
                    print(f"[Verify] All shards completed and Model v2 aggregated successfully after {time.time() - start_time:.1f}s!")
                    return rows
        except Exception as e:
            time.sleep(1.0)
            continue
        time.sleep(2.0)

    # Final read
    conn, _ = get_db_connection(mode)
    cursor = conn.cursor()
    cursor.execute("SELECT id, model_id, shard_id, status, trainer_node_id, update_artifact_path FROM training_shards")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def verify_client_artifacts(shards: list[dict], mode: str) -> None:
    print("[Verify] Verifying Client update artifacts on disk...")
    for s in shards:
        path_str = s.get("update_artifact_path")
        assert path_str, f"Shard {s['shard_id']} missing update_artifact_path!"

        if mode == "docker":
            # Check inside client container
            cmd = ["docker", "compose", "exec", "-T", "client", "test", "-s", path_str]
            res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), check=False)
            assert res.returncode == 0, f"Client update artifact {path_str} does not exist or is empty in container!"
            print(f"[Verify] [OK] Shard {s['shard_id']} update delta confirmed in container: {path_str}")
        else:
            p = Path(path_str)
            assert p.exists() and p.is_file(), f"Client update artifact {p} does not exist!"
            assert p.stat().st_size > 0, f"Client update artifact {p} is empty (0 bytes)!"
            print(f"[Verify] [OK] Shard {s['shard_id']} update delta confirmed on disk: {p.name} ({p.stat().st_size} bytes)")


def verify_trainer_cleanup(mode: str, timeout_seconds: int = 15) -> None:
    print(f"[Verify] Verifying ephemeral cleanup on Trainer nodes (timeout: {timeout_seconds}s)...")
    start = time.time()
    while True:
        try:
            if mode == "docker":
                all_clean = True
                for trainer_svc in ["trainer-1", "trainer-2"]:
                    cmd = ["docker", "compose", "exec", "-T", trainer_svc, "sh", "-c", "find /artifacts -name '*.pt' -o -name '*.safetensors' | wc -l"]
                    res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
                    count = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
                    if count > 0:
                        all_clean = False
                        break
                if all_clean:
                    break
            else:
                all_clean = True
                for trainer_name, dir_name in [("Trainer 1", "trainer1_artifacts"), ("Trainer 2", "trainer2_artifacts")]:
                    work_path = WORK_DIR / dir_name
                    pt_files = list(work_path.glob("*.pt"))
                    st_files = list(work_path.glob("*.safetensors"))
                    if len(pt_files) > 0 or len(st_files) > 0:
                        all_clean = False
                        break
                if all_clean:
                    break
        except Exception:
            pass

        if time.time() - start >= timeout_seconds:
            break
        time.sleep(0.5)

    if mode == "docker":
        for trainer_svc in ["trainer-1", "trainer-2"]:
            # Check ephemeral .pt shard files were deleted
            cmd = ["docker", "compose", "exec", "-T", trainer_svc, "sh", "-c", "find /artifacts -name '*.pt' | wc -l"]
            res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
            count = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
            assert count == 0, f"Trainer {trainer_svc} failed to delete ephemeral shard .pt file! Found {count} files."

            # Check update .safetensors files were deleted
            cmd = ["docker", "compose", "exec", "-T", trainer_svc, "sh", "-c", "find /artifacts -name '*.safetensors' | wc -l"]
            res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
            count = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
            assert count == 0, f"Trainer {trainer_svc} failed to delete ephemeral update .safetensors file! Found {count} files."

            # Check base model .pt2 was retained in cache
            cmd = ["docker", "compose", "exec", "-T", trainer_svc, "sh", "-c", "find /artifacts -name '*.pt2' | wc -l"]
            res = subprocess.run(cmd, cwd=str(SAMPLE_DIR), capture_output=True, text=True, check=False)
            count = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
            assert count >= 1, f"Trainer {trainer_svc} base model .pt2 was unexpectedly deleted!"

            print(f"[Verify] [OK] Trainer {trainer_svc}: Ephemeral shards and updates cleaned up, base model retained in cache.")
    else:
        for trainer_name, dir_name in [("Trainer 1", "trainer1_artifacts"), ("Trainer 2", "trainer2_artifacts")]:
            work_path = WORK_DIR / dir_name
            pt_files = list(work_path.glob("*.pt"))
            assert len(pt_files) == 0, f"{trainer_name} ephemeral shard file not deleted: {[f.name for f in pt_files]}"

            safetensor_files = list(work_path.glob("*.safetensors"))
            assert len(safetensor_files) == 0, f"{trainer_name} ephemeral update file not deleted: {[f.name for f in safetensor_files]}"

            pt2_files = list(work_path.glob("*.pt2"))
            assert len(pt2_files) >= 1, f"{trainer_name} base model (.pt2) was unexpectedly deleted!"

            print(f"[Verify] [OK] {trainer_name}: Ephemeral shards/updates cleaned up, base model retained in cache.")


def verify_coordinator_trainers(coord_url: str = "http://127.0.0.1:8080") -> None:
    print(f"[Verify] Verifying Trainer IDLE status on Coordinator ({coord_url}/api/trainers)...")
    url = f"{coord_url}/api/trainers"
    req = urllib.request.Request(url, headers={"User-Agent": "VerifyScript"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Coordinator returned HTTP {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    print(f"[Verify] Coordinator returned {len(data)} trainer records: {data}")
    assert len(data) >= 2, f"Expected at least 2 trainers registered with Coordinator, got {len(data)}"
    for t in data:
        t_id = t.get("trainerNodeId") or t.get("TrainerNodeId")
        status = t.get("status") or t.get("Status")
        assert status and str(status).upper() == "IDLE", (
            f"Trainer '{t_id}' has status '{status}', expected 'IDLE'!"
        )
    print(f"[Verify] [OK] All {len(data)} trainers confirmed in IDLE status on Coordinator.")


def verify_model_version_2(mode: str) -> Path:
    print("[Verify] Verifying new Model version 2 checkpoint in Client persistence & disk...")
    conn, _ = get_db_connection(mode)
    cur = conn.cursor()
    cur.execute("SELECT model_id, model_version, model_artifact_path FROM models WHERE model_version = '2'")
    row = cur.fetchone()
    conn.close()

    assert row, "No record found for model_version='2' in models table!"
    artifact_path_str = row["model_artifact_path"]
    assert artifact_path_str, "Model version 2 record has empty model_artifact_path!"

    p = Path(artifact_path_str).resolve()
    assert p.exists() and p.is_file(), f"Model version 2 checkpoint file not found at: {p}"
    assert p.stat().st_size > 0, f"Model version 2 checkpoint file is 0 bytes: {p}"
    print(f"[Verify] [OK] Model version 2 artifact verified: {p.name} ({p.stat().st_size} bytes)")
    return p


def evaluate_model_loss(base_model_path: Path, aggregated_model_path: Path, dataset_path: Path) -> tuple[float, float]:
    print("[Verify] Evaluating and comparing loss between base model and aggregated model...")
    import torch

    assert dataset_path.exists(), f"Dataset file not found: {dataset_path}"
    assert base_model_path.exists(), f"Base model file not found: {base_model_path}"
    assert aggregated_model_path.exists(), f"Aggregated model file not found: {aggregated_model_path}"

    data = torch.load(str(dataset_path), weights_only=False)
    x = data["x"]
    y = data["y"]

    # Evaluate base model
    base_program = torch.export.load(str(base_model_path))
    base_module = base_program.module()
    with torch.no_grad():
        base_pred = base_module(x)
        base_loss = float(torch.nn.functional.mse_loss(base_pred, y).item())

    # Evaluate aggregated model
    agg_program = torch.export.load(str(aggregated_model_path))
    agg_module = agg_program.module()
    with torch.no_grad():
        agg_pred = agg_module(x)
        agg_loss = float(torch.nn.functional.mse_loss(agg_pred, y).item())

    print(f"[Verify] Base Model Loss:       {base_loss:.6f}")
    print(f"[Verify] Aggregated Model Loss: {agg_loss:.6f}")
    print(f"[Verify] Loss Delta:            {base_loss - agg_loss:.6f}")

    # Assertions per Constitution and T026:
    assert math.isfinite(base_loss), f"Base model loss is non-finite: {base_loss}"
    assert math.isfinite(agg_loss), f"Aggregated model loss is non-finite: {agg_loss}"
    assert not math.isnan(agg_loss), "Aggregated model loss is NaN!"
    assert not math.isinf(agg_loss), "Aggregated model loss is Inf!"
    assert agg_loss < base_loss, (
        f"Strict loss reduction failed: Aggregated loss ({agg_loss:.6f}) >= Base loss ({base_loss:.6f})"
    )

    print(f"[Verify] [OK] Strict loss reduction confirmed: {agg_loss:.6f} < {base_loss:.6f}")
    return base_loss, agg_loss


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Distributed Training Verification Assertions")
    parser.add_argument("--mode", choices=["auto", "docker", "local"], default="auto", help="Execution mode")
    parser.add_argument("--timeout", type=int, default=90, help="Polling timeout in seconds")
    parser.add_argument("--coord-url", type=str, default="http://127.0.0.1:8080", help="Coordinator URL")
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        mode = "docker" if is_docker_active() else "local"

    print(f"=== [Verify] Running Verification in Mode: {mode.upper()} ===")

    # 1. Poll and assert Shards in SQLite
    shards = poll_shards_completion(mode, timeout_seconds=args.timeout)

    print("\n=== Shard Database Records ===")
    for s in shards:
        print(f"  - Shard: {s['shard_id']} | Status: {s['status']} | TrainerNodeId: {s['trainer_node_id']} | UpdatePath: {s['update_artifact_path']}")
    print("==============================\n")

    assert len(shards) == 2, f"Expected 2 shards, but got {len(shards)}!"
    for s in shards:
        assert str(s["status"]).lower() == "completed", f"Shard {s['shard_id']} has status '{s['status']}' instead of 'completed'!"
        assert s["trainer_node_id"], f"Shard {s['shard_id']} missing trainer_node_id!"
        assert s["update_artifact_path"], f"Shard {s['shard_id']} missing update_artifact_path!"

    # 2. Verify Client Update Artifacts on Disk
    verify_client_artifacts(shards, mode)

    # 3. Verify Ephemeral Cleanup on Trainers
    verify_trainer_cleanup(mode)

    # 4. Verify Trainers returned to IDLE on Coordinator
    verify_coordinator_trainers(args.coord_url)

    # 5. Verify Model Version 2 persistence & file
    v2_artifact_path = verify_model_version_2(mode)

    # 6. Evaluate Model Loss Reduction
    base_model_path = ARTIFACTS_DIR / "test_model.pt2"
    dataset_path = ARTIFACTS_DIR / "test_dataset.pt"
    evaluate_model_loss(base_model_path, v2_artifact_path, dataset_path)

    print("\n================================================================================")
    print("   [SUCCESS] Full Distributed Training Multi-Node Verification PASSED 100%       ")
    print("================================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
