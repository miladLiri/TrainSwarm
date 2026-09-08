"""
Setup and orchestration harness for the full distributed training verification test.
Boots the full network (Relay, Coordinator, Client + sidecar, 2 Trainers + sidecars).

Execution Modes:
1. Docker Compose Mode (Default when docker is installed)
2. Local Multi-Process Mode (Fallback or explicitly via --mode local)
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
PIDS_FILE = WORK_DIR / "pids.json"

RELAY_HTTP_URL = "http://127.0.0.1:8090/health"
COORD_HTTP_URL = "http://127.0.0.1:8080/health"


def is_docker_available() -> bool:
    try:
        proc = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, check=False)
        return proc.returncode == 0
    except FileNotFoundError:
        return False


def stop_local_processes() -> None:
    print("[Setup] Cleaning up previous local test processes...")
    if PIDS_FILE.exists():
        try:
            with open(PIDS_FILE, "r", encoding="utf-8") as f:
                pids = json.load(f)
            for pid in pids:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
                    else:
                        os.kill(pid, 9)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Setup] Warning stopping processes by PID: {e}")
        finally:
            PIDS_FILE.unlink(missing_ok=True)

    # Free test ports if still bound by orphaned processes
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


def stop_docker_compose() -> None:
    print("[Setup] Stopping Docker Compose stack...")
    subprocess.run(["docker", "compose", "down", "-v"], cwd=str(SAMPLE_DIR), check=False)


def wait_for_http(url: str, name: str, max_seconds: int = 60) -> bool:
    print(f"[Setup] Waiting for {name} health endpoint at {url}...", end="", flush=True)
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


def run_docker_setup() -> int:
    print("=== [Setup] Starting Full Distributed Training Stack via Docker Compose ===")
    stop_docker_compose()

    print("[Setup] Building and launching containers in detached mode...")
    cmd = ["docker", "compose", "up", "--build", "-d"]
    res = subprocess.run(cmd, cwd=str(SAMPLE_DIR))
    if res.returncode != 0:
        print("[Setup] [ERROR] Docker Compose failed to start.", file=sys.stderr)
        return res.returncode

    if not wait_for_http(RELAY_HTTP_URL, "Bootstrap Relay", 60):
        print("[Setup] [ERROR] Relay failed healthcheck.", file=sys.stderr)
        return 1

    if not wait_for_http(COORD_HTTP_URL, "Coordinator", 60):
        print("[Setup] [ERROR] Coordinator failed healthcheck.", file=sys.stderr)
        return 1

    # Wait for trainers and client to initialize
    print("[Setup] Giving nodes time to register with Coordinator and discover P2P identity...")
    time.sleep(5.0)

    print("=== [Setup] Docker Compose environment successfully initialized! ===")
    return 0


def run_local_setup() -> int:
    print("=== [Setup] Starting Full Distributed Training Stack via Local Subprocesses ===")
    stop_local_processes()

    # Clean and initialize directories
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"
    seed_artifacts = WORK_DIR / "seed_artifacts"

    for d in [db_dir, logs_dir, client_work, trainer1_work, trainer2_work, seed_artifacts]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy seed artifacts
    for f in ARTIFACTS_DIR.glob("*"):
        shutil.copy2(f, seed_artifacts / f.name)

    creation_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    pids = []

    # 1. Start Relay
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
        print("[Setup] [ERROR] Relay failed to start.", file=sys.stderr)
        stop_local_processes()
        return 1

    # 2. Start Coordinator
    print("[Setup] [2/8] Starting Coordinator...")
    coord_log = open(logs_dir / "coordinator.log", "w", encoding="utf-8")
    coord_env = os.environ.copy()
    coord_env.update({
        "COORDINATOR_HTTP_PORT": "8080",
        "COORDINATOR_GRPC_PORT": "8081",
        "COORDINATOR_DB_CONNECTION_STRING": f"Data Source={(db_dir / 'coordinator.db').resolve()}",
        "ASPNETCORE_URLS": "http://+:8080",
    })
    coord_proj = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "TrainSwarm.Coordinator.Api.csproj"
    coord_proc = subprocess.Popen(
        ["dotnet", "run", "--project", str(coord_proj)],
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
        stop_local_processes()
        return 1

    p2pd_bin = SRC_DIR / "p2p-node" / "bin" / "p2pd.exe"
    p2pd_base_cmd = [str(p2pd_bin)] if p2pd_bin.exists() else ["go", "run", "./cmd/p2pd"]

    # 3. Start Client p2p-node (gRPC 50051, P2P 9001)
    print("[Setup] [3/8] Starting Client p2p-node (port 50051)...")
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
    print("[Setup] [4/8] Starting Trainer 1 p2p-node (port 50052)...")
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
    print("[Setup] [5/8] Starting Trainer 2 p2p-node (port 50053)...")
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

    # Allow p2p nodes to initialize and connect to relay
    time.sleep(4.0)

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

    # 7. Start Trainer 1
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

    # 8. Start Trainer 2
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

    # Save PIDs
    with open(PIDS_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f)

    time.sleep(3.0)
    print("=== [Setup] Local multi-node test environment successfully initialized! ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Distributed Training Test Setup Harness")
    parser.add_argument("--mode", choices=["auto", "docker", "local"], default="auto", help="Execution mode")
    parser.add_argument("--stop", "--down", action="store_true", help="Stop running services and exit")
    args = parser.parse_args()

    if args.stop:
        if is_docker_available():
            stop_docker_compose()
        stop_local_processes()
        print("[Setup] Teardown complete.")
        return 0

    # Ensure artifacts exist
    if not (ARTIFACTS_DIR / "test_model.pt2").exists():
        import data_generator
        data_generator.generate(ARTIFACTS_DIR)

    mode = args.mode
    if mode == "auto":
        mode = "docker" if is_docker_available() else "local"

    if mode == "docker":
        return run_docker_setup()
    else:
        return run_local_setup()


if __name__ == "__main__":
    sys.exit(main())
