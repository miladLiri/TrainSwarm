"""Teardown and cleanup utility for the Submit Training test environment.

Removes Docker containers, test networks, staged models, datasets, shards, and databases.
"""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
NETWORK_NAME = "trainswarm-test-net"
CONTAINERS = ["trainswarm-test-client", "trainswarm-test-coordinator"]

TARGET_DIRECTORIES = [
    SAMPLE_DIR / "artifacts",
    SAMPLE_DIR / "db",
    SAMPLE_DIR / "data",
    SAMPLE_DIR / "models",
    SAMPLE_DIR / "shards",
]

TARGET_PATTERNS = [
    "*.pt",
    "*.pt2",
    "*.json",
    "*.db",
    "*.sqlite",
    "*.tmp",
    "*.tmp.*",
]


def is_docker_available() -> bool:
    """Check if docker CLI is available in PATH."""
    return shutil.which("docker") is not None


def clean_docker() -> None:
    """Stop and remove test containers and test bridge network."""
    if not is_docker_available():
        print("[Clean] Docker not available on host. Skipping Docker container cleanup.")
        return

    print("[Clean] Removing Docker containers...")
    for container in CONTAINERS:
        res = subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [REMOVED] Container: {container}")

    print(f"[Clean] Removing Docker network '{NETWORK_NAME}'...")
    res = subprocess.run(["docker", "network", "rm", NETWORK_NAME], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  [REMOVED] Network: {NETWORK_NAME}")


def clean_artifacts() -> int:
    """Remove generated test directories and lingering test files."""
    removed_count = 0
    print("[Clean] Removing generated artifact directories...")
    for dir_path in TARGET_DIRECTORIES:
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                print(f"  [REMOVED] Directory: {dir_path.name}/")
                removed_count += 1
            except Exception as exc:
                print(f"  [WARN] Failed to delete '{dir_path}': {exc}", file=sys.stderr)

    # Remove files matching target patterns in SAMPLE_DIR
    for pattern in TARGET_PATTERNS:
        for file_path in SAMPLE_DIR.glob(pattern):
            if file_path.is_file() and file_path.name not in ("README.md",):
                try:
                    file_path.unlink()
                    print(f"  [REMOVED] File: {file_path.name}")
                    removed_count += 1
                except Exception as exc:
                    print(f"  [WARN] Failed to delete '{file_path}': {exc}", file=sys.stderr)

    return removed_count


def clean() -> None:
    """Run full cleanup suite."""
    print("================================================================================")
    print(f"=== [Clean] Cleaning Submit Training Test Environment in {SAMPLE_DIR.name} ===")
    print("================================================================================")
    clean_docker()
    removed = clean_artifacts()
    print(f"[SUCCESS] Cleanup completed. Removed {removed} local resource(s).")
    print("================================================================================")


if __name__ == "__main__":
    clean()
