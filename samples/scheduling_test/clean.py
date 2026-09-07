"""Teardown and database cleanup utility for the Coordinator Scheduler test environment.

Removes SQLite test databases, WAL/journal files, and generated db directories.
"""

from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
API_DIR = REPO_ROOT / "src" / "Coordinator" / "TrainSwarm.Coordinator.Api"

DB_DIRS = [
    SAMPLE_DIR / "db",
]

TARGET_PATTERNS = [
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    "*.log",
]

# Additional specific test db prefixes to clean up if lingering in repo root or Api dir
ROOT_DB_NAMES = [
    "coordinator_scheduler.db",
    "coordinator_scheduler_test.db",
    "coordinator_scheduler_live_test.db",
]


def stop_running_coordinator() -> None:
    """Stop any running TrainSwarm.Coordinator.Api process to release SQLite file locks."""
    print("[Clean] Checking for active Coordinator processes holding file locks...")
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["taskkill", "/F", "/IM", "TrainSwarm.Coordinator.Api.exe", "/T"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                print("  [STOPPED] Terminated running TrainSwarm.Coordinator.Api.exe process.")
                time.sleep(1.0)
            else:
                print("  [INFO] No active TrainSwarm.Coordinator.Api.exe processes found.")
        else:
            res = subprocess.run(["pkill", "-f", "TrainSwarm.Coordinator.Api"], capture_output=True)
            if res.returncode == 0:
                print("  [STOPPED] Terminated running TrainSwarm.Coordinator.Api process.")
                time.sleep(1.0)
            else:
                print("  [INFO] No active TrainSwarm.Coordinator.Api processes found.")
    except Exception as exc:
        print(f"  [WARN] Could not stop Coordinator process: {exc}", file=sys.stderr)


def _safe_unlink(path: Path, max_retries: int = 3, delay: float = 0.5) -> bool:
    """Safely delete a file with retry logic in case of transient locks."""
    for attempt in range(max_retries):
        try:
            path.unlink()
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
        except FileNotFoundError:
            return True
    return False


def clean_db_files() -> int:
    """Remove SQLite database files and directories."""
    removed_count = 0
    print("[Clean] Cleaning database files and directories...")

    # 1. Clean files inside DB_DIRS and remove directories
    for db_dir in DB_DIRS:
        if db_dir.exists():
            for item in db_dir.iterdir():
                try:
                    if item.is_file() and _safe_unlink(item):
                        print(f"  [REMOVED] DB File: {item.relative_to(SAMPLE_DIR)}")
                        removed_count += 1
                except Exception as exc:
                    print(f"  [WARN] Failed to delete '{item}': {exc}", file=sys.stderr)
            try:
                shutil.rmtree(db_dir, ignore_errors=True)
                if not db_dir.exists():
                    print(f"  [REMOVED] Directory: {db_dir.name}/")
                    removed_count += 1
            except Exception as exc:
                print(f"  [WARN] Failed to remove '{db_dir}': {exc}", file=sys.stderr)

    # 2. Clean matching patterns in SAMPLE_DIR
    for pattern in TARGET_PATTERNS:
        for file_path in SAMPLE_DIR.glob(pattern):
            if file_path.is_file():
                try:
                    if _safe_unlink(file_path):
                        print(f"  [REMOVED] File: {file_path.name}")
                        removed_count += 1
                except Exception as exc:
                    print(f"  [WARN] Failed to delete '{file_path}': {exc}", file=sys.stderr)

    # 3. Clean lingering test databases in repo root
    for db_name in ROOT_DB_NAMES:
        for root_file in REPO_ROOT.glob(f"{db_name}*"):
            if root_file.is_file():
                try:
                    if _safe_unlink(root_file):
                        print(f"  [REMOVED] Root DB File: {root_file.name}")
                        removed_count += 1
                except Exception as exc:
                    print(f"  [WARN] Failed to delete '{root_file}': {exc}", file=sys.stderr)

    # 4. Clean lingering test databases in Coordinator.Api
    if API_DIR.exists():
        for pattern in TARGET_PATTERNS:
            for api_file in API_DIR.glob(pattern):
                if api_file.is_file():
                    try:
                        if _safe_unlink(api_file):
                            print(f"  [REMOVED] Api DB File: {api_file.name}")
                            removed_count += 1
                    except Exception as exc:
                        print(f"  [WARN] Failed to delete '{api_file}': {exc}", file=sys.stderr)

    return removed_count


def clean(stop_coordinator: bool = True) -> None:
    print("=" * 80)
    print("=== [Clean] Cleaning Coordinator Scheduler Test Databases ===")
    print("=" * 80)
    if stop_coordinator:
        stop_running_coordinator()
    removed = clean_db_files()
    print("-" * 80)
    if removed > 0:
        print(f"[SUCCESS] Cleanup completed. Removed {removed} database resource(s).")
    else:
        print("[SUCCESS] Cleanup completed. No lingering database files found.")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean up SQLite test databases generated by the Coordinator Scheduler test suite."
    )
    parser.add_argument(
        "--no-kill",
        action="store_true",
        help="Do not attempt to terminate running Coordinator instances before cleaning database files.",
    )
    args = parser.parse_args()
    clean(stop_coordinator=not args.no_kill)


if __name__ == "__main__":
    main()

