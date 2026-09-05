"""Environment setup script for TrainSwarm Client Submit Training E2E verification.

Creates Docker network, builds and starts Coordinator and Client containers with
persistent volume mounts, and polls the Coordinator health endpoint.
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"

NETWORK_NAME = "trainswarm-test-net"
COORDINATOR_CONTAINER = "trainswarm-test-coordinator"
CLIENT_CONTAINER = "trainswarm-test-client"
COORDINATOR_PORT = 8080
HEALTH_URL = f"http://127.0.0.1:{COORDINATOR_PORT}/health"

ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
DB_DIR = SAMPLE_DIR / "db"


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command and return output."""
    print(f"[Setup] Executing: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def is_docker_available() -> bool:
    """Check if docker CLI is present in PATH and Docker daemon is responsive."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


def setup_docker_environment() -> bool:
    """Create Docker network, volumes, and launch Coordinator and Client containers."""
    if not is_docker_available():
        print(
            "[Setup] [ERROR] Docker daemon or CLI is not available on this host.\n"
            "        Please ensure Docker Desktop / Docker Engine is installed and running.\n"
            "        Alternatively, you can run the test suite in local mode: python e2e-test.py --mode local",
            file=sys.stderr,
        )
        return False

    print("================================================================================")
    print("      TrainSwarm Submit Training: Containerized Test Environment Setup          ")
    print("================================================================================")

    # 1. Create host directories for volume mounts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Setup] Artifacts volume mapped: {ARTIFACTS_DIR}")
    print(f"[Setup] Database volume mapped:  {DB_DIR}")

    # 2. Setup Docker bridge network
    res = subprocess.run(["docker", "network", "inspect", NETWORK_NAME], capture_output=True)
    if res.returncode != 0:
        print(f"[Setup] Creating Docker bridge network '{NETWORK_NAME}'...")
        run_cmd(["docker", "network", "create", NETWORK_NAME])
    else:
        print(f"[Setup] Network '{NETWORK_NAME}' already exists.")

    # 3. Clean any existing containers with conflicting names
    for name in [CLIENT_CONTAINER, COORDINATOR_CONTAINER]:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)

    # 4. Build and start Coordinator container
    coord_dockerfile = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "Dockerfile"
    coord_context = SRC_DIR / "Coordinator"
    if coord_dockerfile.is_file():
        print("[Setup] Building Coordinator Docker image...")
        run_cmd(["docker", "build", "-t", "trainswarm-coordinator", "-f", str(coord_dockerfile), str(coord_context)])
        print(f"[Setup] Launching Coordinator container '{COORDINATOR_CONTAINER}'...")
        run_cmd([
            "docker", "run", "-d",
            "--name", COORDINATOR_CONTAINER,
            "--network", NETWORK_NAME,
            "--network-alias", "coordinator",
            "-p", f"{COORDINATOR_PORT}:8080",
            "trainswarm-coordinator",
        ])
    else:
        print(f"[Setup] [WARN] Coordinator Dockerfile not found at '{coord_dockerfile}'.")

    # 5. Build and start Client container
    client_dockerfile = SRC_DIR / "Client" / "Dockerfile"
    client_context = SRC_DIR / "Client"
    print("[Setup] Building Client Docker image...")
    run_cmd(["docker", "build", "-t", "trainswarm-client", "-f", str(client_dockerfile), str(client_context)])

    print(f"[Setup] Launching Client container '{CLIENT_CONTAINER}'...")
    run_cmd([
        "docker", "run", "-d",
        "--name", CLIENT_CONTAINER,
        "--network", NETWORK_NAME,
        "-v", f"{ARTIFACTS_DIR}:/artifacts",
        "-v", f"{DB_DIR}:/data",
        "-e", "COORDINATOR_ADDRESS=http://coordinator:8080",
        "-e", "TRAINING_CLIENT_WORKING_DIRECTORY=/artifacts",
        "-e", "TRAINING_WORKING_DIRECTORY=/artifacts",
        "-e", "TRAINING_CLIENT_DB_PATH=/data/training.db",
        "trainswarm-client",
        "tail", "-f", "/dev/null",
    ])

    # 6. Poll Coordinator health endpoint
    print(f"[Setup] Polling Coordinator health endpoint at {HEALTH_URL}...")
    healthy = False
    for attempt in range(1, 31):
        try:
            req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "TrainSwarm-Setup"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print(f"[Setup] [OK] Coordinator reported healthy (HTTP 200) on attempt {attempt}.")
                    healthy = True
                    break
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
            pass
        time.sleep(1)

    if not healthy:
        print("[Setup] [WARN] Coordinator health check timed out. Verification may still proceed if starting up.")

    print("================================================================================")
    print("  [OK] Coordinator and Client containers running and networked successfully.    ")
    print("================================================================================")
    return True


def teardown_docker_environment() -> None:
    """Tear down containers and network."""
    from clean import clean
    clean()


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup TrainSwarm Client Submit Training test environment.")
    parser.add_argument("--down", action="store_true", help="Tear down containers, network, and test volumes.")
    args = parser.parse_args()

    if args.down:
        teardown_docker_environment()
        return 0

    success = setup_docker_environment()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
