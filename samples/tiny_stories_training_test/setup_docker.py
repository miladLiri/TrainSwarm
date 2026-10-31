"""
setup_docker.py

Docker hybrid cluster orchestration harness for TinyStories Multi-Round Distributed Training Test:
1. Runs Bootstrap Relay, Coordinator, and 3 P2P sidecars inside Docker containers.
2. Runs Client daemon and 2 Trainer daemons natively on the host (connecting over mapped ports).
3. Automatically tracks native background PIDs in .test_pids.json for clean teardown.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
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
DOCKER_NETWORK = "trainswarm-net"


def wait_for_http(url: str, name: str, container_name: str | None = None, max_seconds: int = 45) -> bool:
    """Poll HTTP health endpoint until healthy or timeout, printing container logs on failure."""
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

    if container_name:
        try:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "25", container_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if logs.stdout or logs.stderr:
                print(f"\n[SetupDocker] --- Recent container logs for '{container_name}' ---")
                print((logs.stdout or logs.stderr).strip())
                print("[SetupDocker] -----------------------------------------------------\n")
        except Exception:
            pass
    return False


def wait_for_tcp(port: int, name: str, container_name: str | None = None, max_seconds: int = 35) -> bool:
    """Poll TCP socket until port responds or timeout, printing container logs on failure."""
    print(f"[SetupDocker] Waiting for {name} listening on port {port}...", end="", flush=True)
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                print(f" OK ({time.time() - start:.1f}s)")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        print(".", end="", flush=True)
        time.sleep(1.0)
    print(" FAILED")

    if container_name:
        try:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "25", container_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if logs.stdout or logs.stderr:
                print(f"\n[SetupDocker] --- Container logs for '{container_name}' ---")
                print((logs.stdout or logs.stderr).strip())
                print("[SetupDocker] -----------------------------------------------------\n")
        except Exception:
            pass
    return False


def is_docker_available() -> bool:
    """Verifies that docker is installed and the Docker daemon is responding."""
    sys.stdout.flush()
    try:
        ver = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=False)
        if ver.returncode != 0:
            print("[SetupDocker] [ERROR] 'docker' command failed. Is Docker installed?", file=sys.stderr, flush=True)
            return False
    except FileNotFoundError:
        print("[SetupDocker] [ERROR] 'docker' executable not found in PATH.", file=sys.stderr, flush=True)
        return False

    try:
        info = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10, check=False)
        if info.returncode != 0:
            print("[SetupDocker] [ERROR] Docker daemon is not responding. Please start Docker Desktop/daemon.", file=sys.stderr, flush=True)
            return False
    except subprocess.TimeoutExpired:
        print("[SetupDocker] [ERROR] 'docker info' timed out after 10s. Docker daemon appears frozen.", file=sys.stderr, flush=True)
        return False
    except Exception as exc:
        print(f"[SetupDocker] [ERROR] Unexpected error connecting to Docker: {exc}", file=sys.stderr, flush=True)
        return False

    return True


def ensure_docker_network(net_name: str = DOCKER_NETWORK) -> bool:
    """Creates a user-defined bridge network if it does not already exist."""
    try:
        inspect = subprocess.run(["docker", "network", "inspect", net_name], capture_output=True, check=False)
        if inspect.returncode == 0:
            return True
        res = subprocess.run(["docker", "network", "create", net_name], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[SetupDocker] Created Docker network '{net_name}'.")
            return True
        print(f"[SetupDocker] [ERROR] Failed to create Docker network '{net_name}': {res.stderr}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[SetupDocker] [ERROR] Exception creating network '{net_name}': {exc}", file=sys.stderr)
        return False


def get_docker_mount_args(host_dir: Path, target_dir: str = "/data") -> list[str]:
    """Returns mount arguments for Docker CLI, handling Windows paths reliably."""
    posix_path = host_dir.resolve().as_posix()
    return ["--mount", f"type=bind,source={posix_path},target={target_dir}"]


def verify_container_mount(container_name: str, host_dir: Path, target_dir: str = "/data") -> bool:
    """Verifies that the container's volume mount is reading and writing to the host directory."""
    canary_name = f".mount_test_{int(time.time())}"
    canary_host = host_dir / canary_name
    try:
        canary_host.write_text("trainswarm_mount_verified", encoding="utf-8")
        res = subprocess.run(
            ["docker", "exec", container_name, "cat", f"{target_dir}/{canary_name}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        canary_host.unlink(missing_ok=True)
        if res.returncode == 0 and "trainswarm_mount_verified" in res.stdout:
            print(f"[SetupDocker] Bind mount verified for '{container_name}' -> {host_dir.name}")
            return True

        print(f"\n[SetupDocker] [WARNING] Bind mount check failed for '{container_name}'.", file=sys.stderr)
        print(f"[SetupDocker] [WARNING] Container cannot access host directory: {host_dir}", file=sys.stderr)
        if sys.platform == "win32" and host_dir.drive and host_dir.drive.upper() != "C:":
            print(f"[SetupDocker] [IMPORTANT] Your workspace is on Drive {host_dir.drive}.", file=sys.stderr)
            print(f"[SetupDocker] [IMPORTANT] In Docker Desktop, go to Settings -> Resources -> File Sharing", file=sys.stderr)
            print(f"[SetupDocker] [IMPORTANT] and make sure Drive {host_dir.drive} is added/enabled so Docker can access it.", file=sys.stderr)
        return False
    except Exception as exc:
        canary_host.unlink(missing_ok=True)
        print(f"[SetupDocker] [WARNING] Error checking mount for '{container_name}': {exc}", file=sys.stderr)
        return False


def build_docker_image(tag: str, context_path: Path, dockerfile_path: Path | None = None, force_rebuild: bool = False) -> bool:
    """Builds a Docker image with live console output utilizing Docker layer cache."""
    cmd = ["docker", "build"]
    if force_rebuild:
        cmd.append("--no-cache")
    cmd.extend(["-t", tag])
    if dockerfile_path:
        cmd.extend(["-f", str(dockerfile_path.resolve())])
    cmd.append(str(context_path.resolve()))

    print(f"[SetupDocker] Building Docker image '{tag}'...")
    try:
        res = subprocess.run(cmd, check=False)
        if res.returncode != 0:
            print(f"[SetupDocker] [ERROR] 'docker build -t {tag}' failed with exit code {res.returncode}.", file=sys.stderr)
            return False
        print(f"[SetupDocker] Successfully built image '{tag}'.")
        return True
    except Exception as exc:
        print(f"[SetupDocker] [ERROR] Failed to run docker build: {exc}", file=sys.stderr)
        return False


def start_docker_cluster(force_rebuild: bool = False) -> int:
    """Runs Coordinator, Relay, and 3 P2P sidecars in Docker; Client and Trainers natively."""
    if not is_docker_available():
        return 1

    import clean
    clean.init_runtime_dirs(clean_work=True, clean_reports=False)
    clean.stop_docker_containers()

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"

    for d in (db_dir, logs_dir, client_work, trainer1_work, trainer2_work):
        d.mkdir(parents=True, exist_ok=True)

    # 0. Ensure shared Docker bridge network
    if not ensure_docker_network(DOCKER_NETWORK):
        return 1

    # 1. Ensure Bootstrap Relay Docker image
    print("[SetupDocker] [1/8] Ensuring Bootstrap Relay Docker image 'trainswarm-relay'...")
    relay_context = SRC_DIR / "bootstrap-relay"
    relay_dockerfile = relay_context / "Dockerfile"
    if not build_docker_image("trainswarm-relay", relay_context, relay_dockerfile, force_rebuild=force_rebuild):
        return 1

    print("[SetupDocker] Launching Bootstrap Relay container (ports 4001, 8090)...")
    relay_cmd = [
        "docker", "run", "-d",
        "--name", "trainswarm-relay",
        "--network", DOCKER_NETWORK,
        "--add-host", "host.docker.internal:host-gateway",
        "-p", "4001:4001",
        "-p", "4001:4001/udp",
        "-p", "8090:8090",
        "-e", "P2P_RELAY_LISTEN_TCP=/ip4/0.0.0.0/tcp/4001",
        "-e", "P2P_RELAY_LISTEN_QUIC=/ip4/0.0.0.0/udp/4001/quic-v1",
        "-e", "P2P_RELAY_LISTEN_HTTP=8090",
        "-e", "P2P_RELAY_IDENTITY_PATH=/data/relay.key",
        "-e", "P2P_RELAY_LOG_LEVEL=info",
        "trainswarm-relay",
    ]
    relay_run = subprocess.run(relay_cmd, capture_output=True, text=True, check=False)
    if relay_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start relay container: {relay_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_http(RELAY_HTTP_URL, "Bootstrap Relay Container", container_name="trainswarm-relay", max_seconds=35):
        return 1

    # 2. Ensure Coordinator Docker image
    print("[SetupDocker] [2/8] Ensuring Coordinator Docker image 'trainswarm-coordinator'...")
    coord_context = SRC_DIR / "Coordinator"
    coord_dockerfile = coord_context / "TrainSwarm.Coordinator.Api" / "Dockerfile"
    if not build_docker_image("trainswarm-coordinator", coord_context, coord_dockerfile, force_rebuild=force_rebuild):
        return 1

    print("[SetupDocker] Launching Coordinator container (ports 8080, 8081)...")
    coord_cmd = [
        "docker", "run", "-d",
        "--name", "trainswarm-coordinator",
        "--network", DOCKER_NETWORK,
        "--add-host", "host.docker.internal:host-gateway",
        "-p", "8080:8080",
        "-p", "8081:8081",
        "-e", "ASPNETCORE_URLS=http://+:8080",
        "-e", "COORDINATOR_HTTP_PORT=8080",
        "-e", "COORDINATOR_GRPC_PORT=8081",
        "-e", "COORDINATOR_DB_CONNECTION_STRING=Data Source=/data/coordinator.db",
        "trainswarm-coordinator",
    ]
    coord_run = subprocess.run(coord_cmd, capture_output=True, text=True, check=False)
    if coord_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start coordinator container: {coord_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_http(COORD_HTTP_URL, "Coordinator Container", container_name="trainswarm-coordinator", max_seconds=45):
        return 1

    # Ensure P2P Node Docker image for sidecars
    print("[SetupDocker] Ensuring P2P Node Docker image 'trainswarm-p2p'...")
    p2p_context = SRC_DIR / "p2p-node"
    p2p_dockerfile = p2p_context / "Dockerfile"
    if not build_docker_image("trainswarm-p2p", p2p_context, p2p_dockerfile, force_rebuild=force_rebuild):
        return 1

    # 3. Start Client p2p-node container (gRPC 50051, P2P 9001)
    print("[SetupDocker] [3/8] Starting Client p2p-node container (gRPC 50051, P2P 9001)...")
    cp2p_cmd = [
        "docker", "run", "-d",
        "--name", "trainswarm-p2p-client",
        "--network", DOCKER_NETWORK,
        "--add-host", "host.docker.internal:host-gateway",
        "-p", "50051:50051",
        "-p", "9001:9001",
        "-p", "9001:9001/udp",
    ]
    cp2p_cmd.extend(get_docker_mount_args(client_work, "/data"))
    cp2p_cmd.extend([
        "-e", "RELAY_HOST=trainswarm-relay",
        "-e", "RELAY_PORT=4001",
        "-e", "RELAY_HTTP_PORT=8090",
        "-e", "P2P_PORT=9001",
        "-e", "GRPC_PORT=50051",
        "-e", "WORKING_DIR=/data",
        "-e", "IDENTITY_PATH=/data/client.key",
        "trainswarm-p2p",
    ])
    cp2p_run = subprocess.run(cp2p_cmd, capture_output=True, text=True, check=False)
    if cp2p_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start client p2p container: {cp2p_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_tcp(50051, "Client p2p-node Container", container_name="trainswarm-p2p-client", max_seconds=35):
        return 1
    verify_container_mount("trainswarm-p2p-client", client_work)

    # 4. Start Trainer 1 p2p-node container (gRPC 50052, P2P 9002)
    print("[SetupDocker] [4/8] Starting Trainer 1 p2p-node container (gRPC 50052, P2P 9002)...")
    t1p2p_cmd = [
        "docker", "run", "-d",
        "--name", "trainswarm-p2p-trainer1",
        "--network", DOCKER_NETWORK,
        "--add-host", "host.docker.internal:host-gateway",
        "-p", "50052:50052",
        "-p", "9002:9002",
        "-p", "9002:9002/udp",
    ]
    t1p2p_cmd.extend(get_docker_mount_args(trainer1_work, "/data"))
    t1p2p_cmd.extend([
        "-e", "RELAY_HOST=trainswarm-relay",
        "-e", "RELAY_PORT=4001",
        "-e", "RELAY_HTTP_PORT=8090",
        "-e", "P2P_PORT=9002",
        "-e", "GRPC_PORT=50052",
        "-e", "WORKING_DIR=/data",
        "-e", "IDENTITY_PATH=/data/trainer1.key",
        "trainswarm-p2p",
    ])
    t1p2p_run = subprocess.run(t1p2p_cmd, capture_output=True, text=True, check=False)
    if t1p2p_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start trainer1 p2p container: {t1p2p_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_tcp(50052, "Trainer 1 p2p-node Container", container_name="trainswarm-p2p-trainer1", max_seconds=35):
        return 1
    verify_container_mount("trainswarm-p2p-trainer1", trainer1_work)

    # 5. Start Trainer 2 p2p-node container (gRPC 50053, P2P 9003)
    print("[SetupDocker] [5/8] Starting Trainer 2 p2p-node container (gRPC 50053, P2P 9003)...")
    t2p2p_cmd = [
        "docker", "run", "-d",
        "--name", "trainswarm-p2p-trainer2",
        "--network", DOCKER_NETWORK,
        "--add-host", "host.docker.internal:host-gateway",
        "-p", "50053:50053",
        "-p", "9003:9003",
        "-p", "9003:9003/udp",
    ]
    t2p2p_cmd.extend(get_docker_mount_args(trainer2_work, "/data"))
    t2p2p_cmd.extend([
        "-e", "RELAY_HOST=trainswarm-relay",
        "-e", "RELAY_PORT=4001",
        "-e", "RELAY_HTTP_PORT=8090",
        "-e", "P2P_PORT=9003",
        "-e", "GRPC_PORT=50053",
        "-e", "WORKING_DIR=/data",
        "-e", "IDENTITY_PATH=/data/trainer2.key",
        "trainswarm-p2p",
    ])
    t2p2p_run = subprocess.run(t2p2p_cmd, capture_output=True, text=True, check=False)
    if t2p2p_run.returncode != 0:
        print(f"[SetupDocker] [ERROR] Failed to start trainer2 p2p container: {t2p2p_run.stderr}", file=sys.stderr)
        return 1

    if not wait_for_tcp(50053, "Trainer 2 p2p-node Container", container_name="trainswarm-p2p-trainer2", max_seconds=35):
        return 1
    verify_container_mount("trainswarm-p2p-trainer2", trainer2_work)

    creation_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    pids: list[int] = []

    # 6. Start Client daemon natively on host
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

    # 7. Start Trainer 1 (trainer-node-01) natively on host
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

    # 8. Start Trainer 2 (trainer-node-02) natively on host
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

    # Persist native Python PIDs for teardown
    with open(PIDS_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f, indent=2)

    print("\n" + "=" * 65)
    print(f"[+] Docker Hybrid Cluster spawned successfully!")
    print(f"[+] 5 Docker Containers: trainswarm-relay, trainswarm-coordinator, trainswarm-p2p-client, trainswarm-p2p-trainer1, trainswarm-p2p-trainer2")
    print(f"[+] Native Client/Trainer PIDs recorded in: {PIDS_FILE.name}")
    print("=" * 65 + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Docker Hybrid Cluster Bootstrap for TinyStories Test.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuilding Docker images even if they exist locally.")
    parser.add_argument("--clean", action="store_true", help="Tear down running containers and processes.")
    args = parser.parse_args()

    if args.clean:
        import clean
        return clean.main()

    print("=" * 65)
    print(" TinyStories Test: Docker Hybrid Cluster Bootstrap ")
    print("=" * 65)
    return start_docker_cluster(force_rebuild=args.rebuild)


if __name__ == "__main__":
    sys.exit(main())
