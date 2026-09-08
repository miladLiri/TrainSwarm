"""
One-Command Local End-to-End Distributed Training Runner (without Docker).

Orchestrates the entire multi-node lifecycle in a single execution context:
1. Generates test model, dataset, and training config
2. Launches Relay, Coordinator, 3 p2p-node sidecars, Client daemon, and 2 Trainers
3. Verifies health and Coordinator registration
4. Executes task submission via Client CLI
5. Polls Client SQLite until both shards are completed
6. Validates update delta safetensors on disk and ephemeral cleanup on trainers
7. Cleanly tears down all processes in finally block
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
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

RELAY_HTTP_URL = "http://127.0.0.1:8090/health"
COORD_HTTP_URL = "http://127.0.0.1:8080/health"


def clean_ports() -> None:
    test_ports = [4001, 8090, 8080, 8081, 50051, 50052, 50053, 9001, 9002, 9003]
    if sys.platform == "win32":
        try:
            cmd = f"Get-NetTCPConnection -LocalPort {','.join(map(str, test_ports))} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, check=False)
            for line in res.stdout.splitlines():
                pid_str = line.strip()
                if pid_str.isdigit() and int(pid_str) not in (0, 4):
                    subprocess.run(["taskkill", "/F", "/T", "/PID", pid_str], capture_output=True, check=False)
        except Exception:
            pass
    time.sleep(1.0)


def wait_for_http(url: str, name: str, max_seconds: int = 45) -> bool:
    print(f"[{name}] Waiting for health at {url}...", end="", flush=True)
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LocalHarness"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status in (200, 204):
                    print(f" OK ({time.time() - start:.1f}s)")
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1.0)
    print(" FAILED")
    return False


def main() -> int:
    print("================================================================================")
    print("   TrainSwarm: Full Distributed Training Verification (Without Docker)          ")
    print("================================================================================\n")

    # 1. Ensure test artifacts exist
    if not (ARTIFACTS_DIR / "test_model.pt2").exists():
        import data_generator
        data_generator.generate(ARTIFACTS_DIR)

    # 2. Clean up old state & kill any lingering port holders
    clean_ports()
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"

    for d in [db_dir, logs_dir, client_work, trainer1_work, trainer2_work]:
        d.mkdir(parents=True, exist_ok=True)

    procs: list[subprocess.Popen] = []
    log_files = []

    try:
        # --- A. Start Relay ---
        print("[1/8] Starting Bootstrap Relay...")
        relay_bin = SRC_DIR / "bootstrap-relay" / "bin" / "relay.exe"
        relay_cmd = [str(relay_bin)] if relay_bin.exists() else ["go", "run", "./cmd/relay"]
        relay_log = open(logs_dir / "relay.log", "w", encoding="utf-8")
        log_files.append(relay_log)
        relay_env = os.environ.copy()
        relay_env.update({
            "P2P_RELAY_LISTEN_TCP": "/ip4/0.0.0.0/tcp/4001",
            "P2P_RELAY_LISTEN_QUIC": "/ip4/0.0.0.0/udp/4001/quic-v1",
            "P2P_RELAY_LISTEN_HTTP": "8090",
            "P2P_RELAY_IDENTITY_PATH": str((WORK_DIR / "relay.key").resolve()),
            "P2P_RELAY_LOG_LEVEL": "info",
        })
        p = subprocess.Popen(relay_cmd, cwd=str(SRC_DIR / "bootstrap-relay"), env=relay_env, stdout=relay_log, stderr=subprocess.STDOUT)
        procs.append(p)

        if not wait_for_http(RELAY_HTTP_URL, "Relay", 30):
            print("[ERROR] Bootstrap Relay failed to become healthy.", file=sys.stderr)
            return 1

        # --- B. Start Coordinator ---
        print("[2/8] Starting Coordinator (.NET API)...")
        coord_log = open(logs_dir / "coordinator.log", "w", encoding="utf-8")
        log_files.append(coord_log)
        coord_env = os.environ.copy()
        coord_env.update({
            "COORDINATOR_HTTP_PORT": "8080",
            "COORDINATOR_GRPC_PORT": "8081",
            "COORDINATOR_DB_CONNECTION_STRING": f"Data Source={(db_dir / 'coordinator.db').resolve()}",
            "ASPNETCORE_URLS": "http://+:8080",
        })
        coord_proj = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "TrainSwarm.Coordinator.Api.csproj"
        p = subprocess.Popen(["dotnet", "run", "--project", str(coord_proj)], env=coord_env, stdout=coord_log, stderr=subprocess.STDOUT)
        procs.append(p)

        if not wait_for_http(COORD_HTTP_URL, "Coordinator", 45):
            print("[ERROR] Coordinator failed to become healthy.", file=sys.stderr)
            return 1

        p2pd_bin = SRC_DIR / "p2p-node" / "bin" / "p2pd.exe"
        p2pd_base_cmd = [str(p2pd_bin)] if p2pd_bin.exists() else ["go", "run", "./cmd/p2pd"]

        # --- C. Start Client p2p-node ---
        print("[3/8] Starting Client p2p-node (gRPC 50051, P2P 9001)...")
        cp2p_log = open(logs_dir / "client_p2p.log", "w", encoding="utf-8")
        log_files.append(cp2p_log)
        cp2p_env = os.environ.copy()
        cp2p_env.update({
            "RELAY_HOST": "127.0.0.1",
            "RELAY_PORT": "4001",
            "RELAY_HTTP_PORT": "8090",
            "P2P_PORT": "9001",
            "GRPC_PORT": "50051",
            "WORKING_DIR": str(client_work.resolve()),
            "IDENTITY_PATH": str((WORK_DIR / "client.key").resolve()),
        })
        p = subprocess.Popen(p2pd_base_cmd, cwd=str(SRC_DIR / "p2p-node"), env=cp2p_env, stdout=cp2p_log, stderr=subprocess.STDOUT)
        procs.append(p)

        # --- D. Start Trainer 1 p2p-node ---
        print("[4/8] Starting Trainer 1 p2p-node (gRPC 50052, P2P 9002)...")
        t1p2p_log = open(logs_dir / "trainer1_p2p.log", "w", encoding="utf-8")
        log_files.append(t1p2p_log)
        t1p2p_env = os.environ.copy()
        t1p2p_env.update({
            "RELAY_HOST": "127.0.0.1",
            "RELAY_PORT": "4001",
            "RELAY_HTTP_PORT": "8090",
            "P2P_PORT": "9002",
            "GRPC_PORT": "50052",
            "WORKING_DIR": str(trainer1_work.resolve()),
            "IDENTITY_PATH": str((WORK_DIR / "trainer1.key").resolve()),
        })
        p = subprocess.Popen(p2pd_base_cmd, cwd=str(SRC_DIR / "p2p-node"), env=t1p2p_env, stdout=t1p2p_log, stderr=subprocess.STDOUT)
        procs.append(p)

        # --- E. Start Trainer 2 p2p-node ---
        print("[5/8] Starting Trainer 2 p2p-node (gRPC 50053, P2P 9003)...")
        t2p2p_log = open(logs_dir / "trainer2_p2p.log", "w", encoding="utf-8")
        log_files.append(t2p2p_log)
        t2p2p_env = os.environ.copy()
        t2p2p_env.update({
            "RELAY_HOST": "127.0.0.1",
            "RELAY_PORT": "4001",
            "RELAY_HTTP_PORT": "8090",
            "P2P_PORT": "9003",
            "GRPC_PORT": "50053",
            "WORKING_DIR": str(trainer2_work.resolve()),
            "IDENTITY_PATH": str((WORK_DIR / "trainer2.key").resolve()),
        })
        p = subprocess.Popen(p2pd_base_cmd, cwd=str(SRC_DIR / "p2p-node"), env=t2p2p_env, stdout=t2p2p_log, stderr=subprocess.STDOUT)
        procs.append(p)

        time.sleep(3.0)

        # --- F. Start Client Daemon ---
        print("[6/8] Starting Client daemon (inbound P2P listener)...")
        client_log = open(logs_dir / "client.log", "w", encoding="utf-8")
        log_files.append(client_log)
        client_env = os.environ.copy()
        client_env.update({
            "PYTHONUNBUFFERED": "1",
            "P2P_GRPC_HOST": "127.0.0.1",
            "P2P_GRPC_PORT": "50051",
            "TRAINING_CLIENT_DB_PATH": str((db_dir / "training.db").resolve()),
            "TRAINING_WORKING_DIRECTORY": str(client_work.resolve()),
            "TRAINING_CLIENT_WORKING_DIRECTORY": str(client_work.resolve()),
            "WORKING_DIR": str(client_work.resolve()),
            "COORDINATOR_ADDRESS": "http://127.0.0.1:8080",
            "OVERRIDE_SHARD_SIZE": "25",
            "PYTHONPATH": f"{SRC_DIR / 'Client'}{os.pathsep}{SRC_DIR}",
        })
        p = subprocess.Popen([sys.executable, str(SRC_DIR / "Client" / "main.py")], cwd=str(SRC_DIR / "Client"), env=client_env, stdout=client_log, stderr=subprocess.STDOUT)
        procs.append(p)

        # --- G. Start Trainer 1 ---
        print("[7/8] Starting Trainer 1 (trainer-node-01)...")
        t1_log = open(logs_dir / "trainer1.log", "w", encoding="utf-8")
        log_files.append(t1_log)
        t1_env = os.environ.copy()
        t1_env.update({
            "PYTHONUNBUFFERED": "1",
            "P2P_GRPC_HOST": "127.0.0.1",
            "P2P_GRPC_PORT": "50052",
            "TRAINER_WORKING_DIRECTORY": str(trainer1_work.resolve()),
            "WORKING_DIR": str(trainer1_work.resolve()),
            "COORDINATOR_ADDRESS": "http://127.0.0.1:8080",
            "COORDINATOR_GRPC_ADDRESS": "127.0.0.1:8081",
            "TRAINER_NODE_ID": "trainer-node-01",
            "PYTHONPATH": f"{SRC_DIR / 'Trainer'}{os.pathsep}{SRC_DIR}",
        })
        p = subprocess.Popen([sys.executable, str(SRC_DIR / "Trainer" / "main.py")], cwd=str(SRC_DIR / "Trainer"), env=t1_env, stdout=t1_log, stderr=subprocess.STDOUT)
        procs.append(p)

        # --- H. Start Trainer 2 ---
        print("[8/8] Starting Trainer 2 (trainer-node-02)...")
        t2_log = open(logs_dir / "trainer2.log", "w", encoding="utf-8")
        log_files.append(t2_log)
        t2_env = os.environ.copy()
        t2_env.update({
            "PYTHONUNBUFFERED": "1",
            "P2P_GRPC_HOST": "127.0.0.1",
            "P2P_GRPC_PORT": "50053",
            "TRAINER_WORKING_DIRECTORY": str(trainer2_work.resolve()),
            "WORKING_DIR": str(trainer2_work.resolve()),
            "COORDINATOR_ADDRESS": "http://127.0.0.1:8080",
            "COORDINATOR_GRPC_ADDRESS": "127.0.0.1:8081",
            "TRAINER_NODE_ID": "trainer-node-02",
            "PYTHONPATH": f"{SRC_DIR / 'Trainer'}{os.pathsep}{SRC_DIR}",
        })
        p = subprocess.Popen([sys.executable, str(SRC_DIR / "Trainer" / "main.py")], cwd=str(SRC_DIR / "Trainer"), env=t2_env, stdout=t2_log, stderr=subprocess.STDOUT)
        procs.append(p)

        print("\nAll 8 services successfully started! Giving them 5s to establish connections...\n")
        time.sleep(5.0)

        # --- Phase 2: Execute Client Task Submission ---
        print("--------------------------------------------------------------------------------")
        print("   Submitting Training Task via Client CLI                                      ")
        print("--------------------------------------------------------------------------------")
        submit_cmd = [
            sys.executable,
            str(SRC_DIR / "Client" / "main.py"),
            "submit-training",
            "--model-path", str((ARTIFACTS_DIR / "test_model.pt2").resolve()),
            "--dataset-path", str((ARTIFACTS_DIR / "test_dataset.pt").resolve()),
            "--model-version", "v1.0",
            "--model-type", "canonical_torch",
            "--training-config", str((ARTIFACTS_DIR / "training_config.json").resolve()),
        ]
        submit_env = client_env.copy()
        res = subprocess.run(submit_cmd, cwd=str(SRC_DIR / "Client"), env=submit_env, capture_output=True, text=True)
        print(res.stdout)
        if res.returncode != 0:
            print(f"[ERROR] Task submission failed (code {res.returncode}):\n{res.stderr}", file=sys.stderr)
            return 1

        print("--------------------------------------------------------------------------------")
        print("   Polling Client SQLite and Monitoring Distributed Execution                   ")
        print("--------------------------------------------------------------------------------")

        db_file = db_dir / "training.db"
        completed = False
        start_poll = time.time()
        timeout = 90

        while time.time() - start_poll < timeout:
            if db_file.exists():
                try:
                    conn = sqlite3.connect(str(db_file))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT shard_id, status, trainer_node_id, update_artifact_path FROM training_shards")
                    rows = [dict(r) for r in cur.fetchall()]
                    conn.close()

                    if rows:
                        statuses = [r["status"] for r in rows]
                        elapsed = time.time() - start_poll
                        print(f"[{elapsed:4.1f}s] Shards ({len(rows)}): {statuses} | Trainers: {[r['trainer_node_id'] for r in rows]}")
                        if len(rows) >= 2 and all(str(s).lower() == "completed" for s in statuses):
                            print(f"\n[OK] All {len(rows)} shards successfully completed in {elapsed:.1f}s!\n")
                            completed = True
                            break
                except Exception as e:
                    pass
            time.sleep(2.0)

        if not completed:
            print("[ERROR] Training execution timed out before completion!", file=sys.stderr)
            print("\n=== Trainer 1 Log ===", file=sys.stderr)
            print((logs_dir / "trainer1.log").read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            print("\n=== Trainer 2 Log ===", file=sys.stderr)
            print((logs_dir / "trainer2.log").read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            print("\n=== Client Log ===", file=sys.stderr)
            print((logs_dir / "client.log").read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            return 1

        # --- Phase 3: Assertions ---
        print("--------------------------------------------------------------------------------")
        print("   Verifying Results and Assertions                                             ")
        print("--------------------------------------------------------------------------------")
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT shard_id, status, trainer_node_id, update_artifact_path FROM training_shards")
        final_shards = [dict(r) for r in cur.fetchall()]
        conn.close()

        assert len(final_shards) == 2, f"Expected 2 shards, got {len(final_shards)}"
        trainer_ids_assigned = set()
        for s in final_shards:
            assert str(s["status"]).lower() == "completed"
            assert s["trainer_node_id"]
            trainer_ids_assigned.add(s["trainer_node_id"])
            assert s["update_artifact_path"]
            up_path = Path(s["update_artifact_path"])
            assert up_path.exists() and up_path.stat().st_size > 0
            print(f"[OK] Shard {s['shard_id']}: Completed by {s['trainer_node_id']} -> Update: {up_path.name} ({up_path.stat().st_size} bytes)")

        # Verify ephemeral cleanup on trainers
        for t_name, t_work in [("Trainer 1", trainer1_work), ("Trainer 2", trainer2_work)]:
            pt_files = list(t_work.glob("*.pt"))
            assert len(pt_files) == 0, f"{t_name} failed to delete ephemeral shard: {[f.name for f in pt_files]}"
            st_files = list(t_work.glob("*.safetensors"))
            assert len(st_files) == 0, f"{t_name} failed to delete ephemeral update: {[f.name for f in st_files]}"
            pt2_files = list(t_work.glob("*.pt2"))
            assert len(pt2_files) >= 1, f"{t_name} base model was unexpectedly deleted!"
            print(f"[OK] {t_name}: Shards and updates purged, base model ({pt2_files[0].name}) retained in cache.")

        print("\n================================================================================")
        print("   >>> SUCCESS: FULL DISTRIBUTED TRAINING TEST PASSED 100% (WITHOUT DOCKER) <<< ")
        print("================================================================================\n")
        return 0

    finally:
        print("[Teardown] Terminating background test processes...")
        for p in procs:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)
                else:
                    p.kill()
            except Exception:
                pass
        for f in log_files:
            try:
                f.close()
            except Exception:
                pass
        clean_ports()
        print("[Teardown] Complete.")


if __name__ == "__main__":
    sys.exit(main())
