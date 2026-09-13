"""
One-Command Local End-to-End Canonical Causal Decoder Training Runner (without Docker).

Orchestrates the entire multi-node lifecycle in a single execution context:
1. Downloads and packages TinyStories-1M model (.gz) and dataset (.pt) from Hugging Face Hub
2. Launches Relay, Coordinator, 3 p2p-node sidecars, Client daemon, and 2 Trainers
3. Verifies health and Coordinator registration
4. Executes task submission via Client CLI with --model-type canonical_causal_decoder
5. Polls Client SQLite until both shards are completed and version 1 model is aggregated
6. Evaluates validation loss and perplexity comparison via verify.py
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
if str(SAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(SAMPLE_DIR))

REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
PIDS_FILE = SAMPLE_DIR / ".test_pids.json"

RELAY_HTTP_URL = "http://127.0.0.1:8090/health"
COORD_HTTP_URL = "http://127.0.0.1:8080/health"


def clean_ports() -> None:
    import clean
    clean.kill_processes_on_ports(clean.TEST_PORTS)


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
    print("   Canonical Causal Decoder: Full End-to-End Distributed Training Runner        ")
    print("================================================================================\n")

    # 1. Ensure test artifacts exist
    import setup
    setup.prepare_hf_artifacts()

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
            "P2P_RELAY_MAX_RELAYED_BYTES": "209715200",
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
        print("[6/8] Starting Client daemon...")
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
            "OVERRIDE_SHARD_SIZE": "40",
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

        # Track PIDs in .test_pids.json
        pids = [proc.pid for proc in procs]
        with open(PIDS_FILE, "w", encoding="utf-8") as f:
            json.dump(pids, f)

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
            "--model-type", "canonical_causal_decoder",
            "--model-path", str((ARTIFACTS_DIR / "tinystories_base.gz").resolve()),
            "--dataset-path", str((ARTIFACTS_DIR / "tinystories_train.pt").resolve()),
            "--model-version", "0",
            "--training-config", str((ARTIFACTS_DIR / "causal_decoder_config.json").resolve()),
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
        timeout = 180

        while time.time() - start_poll < timeout:
            if db_file.exists():
                try:
                    conn = sqlite3.connect(str(db_file))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT shard_id, status, trainer_node_id, sample_count FROM training_shards")
                    rows = [dict(r) for r in cur.fetchall()]
                    cur.execute("SELECT model_version, model_artifact_path FROM models WHERE model_version != '0'")
                    m_rows = [dict(r) for r in cur.fetchall()]
                    conn.close()

                    if rows:
                        statuses = [r["status"] for r in rows]
                        elapsed = time.time() - start_poll
                        v1_ready = len(m_rows) > 0 and Path(m_rows[0]["model_artifact_path"]).is_file()
                        trainers = [r["trainer_node_id"] or "-" for r in rows]
                        print(f"[{elapsed:4.1f}s] Shards ({len(rows)}): {statuses} | V1 Model Ready: {v1_ready} | Trainers: {trainers}")
                        if len(rows) >= 2 and all(str(s).lower() == "completed" for s in statuses) and v1_ready:
                            print(f"\n[OK] All {len(rows)} shards completed and Model v{m_rows[0]['model_version']} aggregated in {elapsed:.1f}s!\n")
                            time.sleep(1.0)
                            completed = True
                            break
                except Exception:
                    pass
            time.sleep(2.0)

        if not completed:
            print("[ERROR] Training execution timed out before completion!", file=sys.stderr)
            print("\n=== Trainer 1 Log ===", file=sys.stderr)
            print((logs_dir / "trainer1.log").read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
            print("\n=== Trainer 2 Log ===", file=sys.stderr)
            print((logs_dir / "trainer2.log").read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
            print("\n=== Client Log ===", file=sys.stderr)
            print((logs_dir / "client.log").read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
            return 1

        # --- Phase 3: Assertions ---
        print("--------------------------------------------------------------------------------")
        print("   Verifying Results and Perplexity via verify.py                               ")
        print("--------------------------------------------------------------------------------")
        verify_cmd = [
            sys.executable,
            str(SAMPLE_DIR / "verify.py"),
        ]
        verify_res = subprocess.run(verify_cmd, cwd=str(SAMPLE_DIR), check=False)
        assert verify_res.returncode == 0, f"Verification script failed with code {verify_res.returncode}!"

        print("\n================================================================================")
        print("   >>> SUCCESS: CANONICAL CAUSAL DECODER TEST PASSED 100% (WITHOUT DOCKER) <<<   ")
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
        PIDS_FILE.unlink(missing_ok=True)
        print("[Teardown] Complete.")


if __name__ == "__main__":
    sys.exit(main())
