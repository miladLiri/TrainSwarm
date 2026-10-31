"""
setup_docker.py

Docker hybrid cluster orchestration harness for TinyStories Multi-Round Distributed Training Test:
1. Runs Bootstrap Relay and Coordinator inside Docker containers using direct `docker run` CLI commands.
2. Runs P2P sidecars, Client daemon, and 2 Trainer daemons natively on the host.
3. Automatically tracks all background PIDs in .test_pids.json for clean teardown.
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
    print(f"[SetupDocker] Waiting for {name} health at {url}...", end="", flush=True)
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SetupDockerHarness"})
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


def start_docker_cluster() -> int:
    """Runs Coordinator and Relay in Docker, sidecars/trainers natively."""
    import clean
    clean.init_runtime_dirs(clean_work=True, clean_reports=False)
    clean.stop_docker_containers()

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"

    # Verify Docker CLI is accessible
    try:
        ver = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=False)
        if ver.returncode != 0:
            print("[SetupDocker] [ERROR] Docker command failed. Is Docker running?", file=sys.stderr)
            return 1
    except FileNotFoundError:
        print("[SetupDocker] [ERROR] 'docker' executable not found in PATH.", file=sys.stderr)
        return 1

    # 1. Build or ensure Bootstrap Relay image
    print("[SetupDocker] [1/8] Ensuring Bootstrap Relay Docker image 'trainswarm-relay'...")
    relay_build = subprocess.run(
        ["docker", "build", "-t", "trainswarm-relay", str(SRC_DIR / "bootstrap-relay")],
        capture_output=True,
        text=True,
        check=False,
    )
    if relay_build.returncode != 0:
        print(f"[SetupDocker] [WARN] Relay build error: {relay_build.stderr[:200]}...")

    print("[SetupDocker] Launching Bootstrap Relay container (ports 4001, 8090)...")
    relay_run = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", "trainswarm-relay",
            "-p", "4001:4001",
            "-p", "8090:8090",
            "trainswarm-relay"
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if relay_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start relay container: {relay_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_http(RELAY_HTTP_URL, "Bootstrap Relay Container", 35):
        return 1

    # 2. Build or ensure Coordinator image
    print("[SetupDocker] [2/8] Ensuring Coordinator Docker image 'trainswarm-coordinator'...")
    coord_build = subprocess.run(
        [
            "docker", "build",
            "-t", "trainswarm-coordinator",
            "-f", str(SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "Dockerfile"),
            str(SRC_DIR / "Coordinator")
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if coord_build.returncode != 0:
        print(f"[SetupDocker] [WARN] Coordinator build error: {coord_build.stderr[:200]}...")

    print("[SetupDocker] Launching Coordinator container (ports 8080, 8081)...")
    coord_run = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", "trainswarm-coordinator",
            "-p", "8080:8080",
            "-p", "8081:8081",
            "trainswarm-coordinator"
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if coord_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start coordinator container: {coord_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_http(COORD_HTTP_URL, "Coordinator Container", 45):
        return 1

    creation_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    pids: list[int] = []

    p2pd_bin = SRC_DIR / "p2p-node" / "bin" / "p2pd.exe"
    p2pd_base_cmd = [str(p2pd_bin)] if p2pd_bin.exists() else ["go", "run", "./cmd/p2pd"]

    # 3. Start Client p2p-node (gRPC 50051, P2P 9001)
    print("[SetupDocker] [3/8] Starting Client p2p-node (gRPC 50051)...")
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
    print("[SetupDocker] [4/8] Starting Trainer 1 p2p-node (gRPC 50052)...")
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
    print("[SetupDocker] [5/8] Starting Trainer 2 p2p-node (gRPC 50053)...")
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
    print("[SetupDocker] [6/8] Starting Client daemon...")
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
    print("[SetupDocker] [7/8] Starting Trainer 1 (trainer-node-01)...")
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
    print("[SetupDocker] [8/8] Starting Trainer 2 (trainer-node-02)...")
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
    print(f"[+] Docker Hybrid Cluster spawned successfully!")
    print(f"[+] Native sidecar/trainer PIDs recorded in: {PIDS_FILE.name}")
    print("=" * 65 + "\n")
    return 0


def main() -> int:
    print("=" * 65)
    print(" TinyStories Test: Docker Hybrid Cluster Bootstrap ")
    print("=" * 65)
    return start_docker_cluster()


if __name__ == "__main__":
    sys.exit(main())
