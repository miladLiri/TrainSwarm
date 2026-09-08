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
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
WORK_DIR = SAMPLE_DIR / "work"


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
    print(f"[Verify] Polling Client database for training completion (timeout: {timeout_seconds}s)...")
    start_time = time.time()

    last_status = None
    while time.time() - start_time < timeout_seconds:
        try:
            conn, _ = get_db_connection(mode)
            cursor = conn.cursor()
            cursor.execute("SELECT id, model_id, shard_id, status, trainer_node_id, update_artifact_path FROM training_shards")
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if rows:
                statuses = [r["status"] for r in rows]
                if statuses != last_status:
                    last_status = statuses
                    elapsed = time.time() - start_time
                    print(f"[Verify] [{elapsed:4.1f}s] Shard statuses: {statuses}")

                if len(rows) >= 2 and all(str(s).lower() == "completed" for s in statuses):
                    print(f"[Verify] All shards completed successfully after {time.time() - start_time:.1f}s!")
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


def verify_trainer_cleanup(mode: str) -> None:
    print("[Verify] Verifying ephemeral cleanup on Trainer nodes...")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Distributed Training Verification Assertions")
    parser.add_argument("--mode", choices=["auto", "docker", "local"], default="auto", help="Execution mode")
    parser.add_argument("--timeout", type=int, default=90, help="Polling timeout in seconds")
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

    print("\n================================================================================")
    print("   [SUCCESS] Full Distributed Training Multi-Node Verification PASSED 100%       ")
    print("================================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
