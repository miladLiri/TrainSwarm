"""
setup.py

Native cluster orchestration harness for TinyStories Multi-Round Distributed Training Test:
1. Performs pre-flight cleanup and directory initialization.
2. Spawns native background processes:
   - Bootstrap Relay (HTTP 8090, P2P 4001)
   - Coordinator Web API (HTTP 8080, gRPC 8081)
   - Client P2P sidecar (gRPC 50051, P2P 9001)
   - Trainer 1 P2P sidecar (gRPC 50052, P2P 9002)
   - Trainer 2 P2P sidecar (gRPC 50053, P2P 9003)
   - Client daemon
   - Trainer 1 daemon (trainer-node-01)
   - Trainer 2 daemon (trainer-node-02)
3. Tracks all background process IDs in .test_pids.json for teardown.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
PIDS_FILE = SAMPLE_DIR / ".test_pids.json"

RELAY_HTTP_URL = "http://127.0.0.1:8090/health"
COORD_HTTP_URL = "http://127.0.0.1:8080/health"


def wait_for_http(url: str, name: str, max_seconds: int = 45) -> bool:
    """Poll HTTP health endpoint until healthy or timeout."""
    print(f"[Setup] Waiting for {name} health at {url}...", end="", flush=True)
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SetupHarness"})
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


def start_native_cluster() -> int:
    """Spawns all 8 native background processes and tracks PIDs."""
    import clean
    clean.init_runtime_dirs(clean_work=True, clean_reports=False)

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"

    creation_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    pids: list[int] = []

    # 1. Start Bootstrap Relay
    print("[Setup] [1/8] Starting Bootstrap Relay...")
    relay_bin = SRC_DIR / "bootstrap-relay" / "bin" / "relay.exe"
    relay_cmd = [str(relay_bin)] if relay_bin.exists() else ["go", "run", "./cmd/relay"]
    relay_log = open(logs_dir / "relay.log", "w", encoding="utf-8")
    relay_env = os.environ.copy()
    relay_env.update({
        "P2P_RELAY_LISTEN_TCP": "/ip4/0.0.0.0/tcp/4001",
        "P2P_RELAY_LISTEN_QUIC": "/ip4/0.0.0.0/udp/4001/quic-v1",
        "P2P_RELAY_LISTEN_HTTP": "8090",
        "P2P_RELAY_IDENTITY_PATH": str((WORK_DIR / "relay.key").resolve()),
        "P2P_RELAY_LOG_LEVEL": "info",
        "P2P_RELAY_MAX_RELAYED_BYTES": "209715200",
    })
    relay_proc = subprocess.Popen(
        relay_cmd,
        cwd=str(SRC_DIR / "bootstrap-relay"),
        env=relay_env,
        stdout=relay_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(relay_proc.pid)
    relay_log.close()

    if not wait_for_http(RELAY_HTTP_URL, "Bootstrap Relay", 30):
        print("[Setup] [ERROR] Bootstrap Relay failed to start.", file=sys.stderr)
        return 1

    # 2. Start Coordinator Web API
    print("[Setup] [2/8] Starting Coordinator API...")
    coord_log = open(logs_dir / "coordinator.log", "w", encoding="utf-8")
    coord_env = os.environ.copy()
    coord_env.update({
        "COORDINATOR_HTTP_PORT": "8080",
        "COORDINATOR_GRPC_PORT": "8081",
        "COORDINATOR_DB_CONNECTION_STRING": f"Data Source={(db_dir / 'coordinator.db').resolve()}",
        "ASPNETCORE_URLS": "http://+:8080",
    })
    coord_proj = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "TrainSwarm.Coordinator.Api.csproj"
    coord_dll = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "bin" / "Debug" / "net10.0" / "TrainSwarm.Coordinator.Api.dll"
    coord_cmd = ["dotnet", str(coord_dll)] if coord_dll.exists() else ["dotnet", "run", "--no-launch-profile", "--project", str(coord_proj)]
    coord_proc = subprocess.Popen(
        coord_cmd,
        env=coord_env,
        stdout=coord_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(coord_proc.pid)
    coord_log.close()

    if not wait_for_http(COORD_HTTP_URL, "Coordinator", 45):
        print("[Setup] [ERROR] Coordinator failed to start.", file=sys.stderr)
        return 1

    p2pd_bin = SRC_DIR / "p2p-node" / "bin" / "p2pd.exe"
    p2pd_base_cmd = [str(p2pd_bin)] if p2pd_bin.exists() else ["go", "run", "./cmd/p2pd"]

    # 3. Start Client p2p-node (gRPC 50051, P2P 9001)
    print("[Setup] [3/8] Starting Client p2p-node (gRPC 50051)...")
    cp2p_log = open(logs_dir / "client_p2p.log", "w", encoding="utf-8")
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
    cp2p_proc = subprocess.Popen(
        p2pd_base_cmd,
        cwd=str(SRC_DIR / "p2p-node"),
        env=cp2p_env,
        stdout=cp2p_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(cp2p_proc.pid)
    cp2p_log.close()

    # 4. Start Trainer 1 p2p-node (gRPC 50052, P2P 9002)
    print("[Setup] [4/8] Starting Trainer 1 p2p-node (gRPC 50052)...")
    t1p2p_log = open(logs_dir / "trainer1_p2p.log", "w", encoding="utf-8")
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
    t1p2p_proc = subprocess.Popen(
        p2pd_base_cmd,
        cwd=str(SRC_DIR / "p2p-node"),
        env=t1p2p_env,
        stdout=t1p2p_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(t1p2p_proc.pid)
    t1p2p_log.close()

    # 5. Start Trainer 2 p2p-node (gRPC 50053, P2P 9003)
    print("[Setup] [5/8] Starting Trainer 2 p2p-node (gRPC 50053)...")
    t2p2p_log = open(logs_dir / "trainer2_p2p.log", "w", encoding="utf-8")
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
    t2p2p_proc = subprocess.Popen(
        p2pd_base_cmd,
        cwd=str(SRC_DIR / "p2p-node"),
        env=t2p2p_env,
        stdout=t2p2p_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(t2p2p_proc.pid)
    t2p2p_log.close()

    time.sleep(3.5)

    # 6. Start Client daemon
    print("[Setup] [6/8] Starting Client daemon...")
    client_log = open(logs_dir / "client.log", "w", encoding="utf-8")
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
        "PYTHONPATH": f"{SRC_DIR / 'Client'}{os.pathsep}{SRC_DIR}",
    })
    client_proc = subprocess.Popen(
        [sys.executable, str(SRC_DIR / "Client" / "main.py")],
        cwd=str(SRC_DIR / "Client"),
        env=client_env,
        stdout=client_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(client_proc.pid)
    client_log.close()

    # 7. Start Trainer 1 (trainer-node-01)
    print("[Setup] [7/8] Starting Trainer 1 (trainer-node-01)...")
    t1_log = open(logs_dir / "trainer1.log", "w", encoding="utf-8")
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
    t1_proc = subprocess.Popen(
        [sys.executable, str(SRC_DIR / "Trainer" / "main.py")],
        cwd=str(SRC_DIR / "Trainer"),
        env=t1_env,
        stdout=t1_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(t1_proc.pid)
    t1_log.close()

    # 8. Start Trainer 2 (trainer-node-02)
    print("[Setup] [8/8] Starting Trainer 2 (trainer-node-02)...")
    t2_log = open(logs_dir / "trainer2.log", "w", encoding="utf-8")
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
    t2_proc = subprocess.Popen(
        [sys.executable, str(SRC_DIR / "Trainer" / "main.py")],
        cwd=str(SRC_DIR / "Trainer"),
        env=t2_env,
        stdout=t2_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    pids.append(t2_proc.pid)
    t2_log.close()

    time.sleep(3.0)

    # Persist PIDs for teardown
    with open(PIDS_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f, indent=2)

    print("\n" + "=" * 65)
    print(f"[+] All 8 background processes spawned successfully!")
    print(f"[+] Process IDs recorded in: {PIDS_FILE.name}")
    print("=" * 65 + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Native cluster bootstrap harness.")
    parser.add_argument("--keep-alive", action="store_true", help="Keep running to maintain cluster processes.")
    args = parser.parse_args()

    print("=" * 65)
    print(" TinyStories Test: Native Cluster Bootstrap ")
    print("=" * 65)
    rc = start_native_cluster()
    if rc != 0:
        return rc

    if args.keep_alive:
        print("[Setup] Running in keep-alive mode. Press Ctrl+C to terminate cluster.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[Setup] Received interrupt. Shutting down cluster...")
            import clean
            clean.main()

    return 0


if __name__ == "__main__":
    sys.exit(main())
