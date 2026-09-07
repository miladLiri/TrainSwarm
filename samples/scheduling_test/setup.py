"""Coordinator Scheduler Test Setup Script.

Starts the Coordinator Web API service locally using dotnet run with a dedicated SQLite database,
and polls the health endpoint until the server is ready.
"""

from __future__ import annotations
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
COORDINATOR_PROJ = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api"

DB_DIR = SAMPLE_DIR / "db"
DB_PATH = DB_DIR / "coordinator_scheduler.db"
PORT = int(os.environ.get("COORDINATOR_PORT", "5000"))
BASE_URL = f"http://localhost:{PORT}"
HEALTH_URL = f"{BASE_URL}/health"


def poll_health(timeout: int = 30) -> bool:
    """Poll Coordinator /health endpoint until it responds with 200 OK."""
    print(f"[Setup] Polling Coordinator health at {HEALTH_URL} (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(HEALTH_URL, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print("[Setup] Coordinator is healthy and ready!")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    print("[Setup] [ERROR] Coordinator failed to respond within timeout.", file=sys.stderr)
    return False


import argparse


def start_coordinator(new_window: bool = False) -> subprocess.Popen:
    """Launch Coordinator Web API process."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["COORDINATOR_DB_CONNECTION_STRING"] = f"Data Source={DB_PATH.resolve()}"
    env["ASPNETCORE_URLS"] = f"http://localhost:{PORT}"

    cmd = ["dotnet", "run", "--project", str(COORDINATOR_PROJ.resolve()), "--no-launch-profile"]

    creationflags = 0
    if new_window and sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        print(f"[Setup] Launching Coordinator in a separate command line window on port {PORT}...")
    else:
        print(f"[Setup] Launching Coordinator on port {PORT} with database at {DB_PATH}...")

    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=str(REPO_ROOT),
        creationflags=creationflags,
    )
    return proc


def main():
    parser = argparse.ArgumentParser(
        description="Coordinator Scheduler setup script - starts Coordinator service for testing."
    )
    parser.add_argument(
        "--new-window", "-w",
        action="store_true",
        help="Launch Coordinator in a new separate console window on Windows.",
    )
    args = parser.parse_args()

    # If already running and healthy, we're good
    if poll_health(timeout=3):
        print(f"[Setup] Coordinator is already running and ready on {BASE_URL}.")
        print("[Setup] In a separate command line, run: python test.py")
        sys.exit(0)

    proc = start_coordinator(new_window=args.new_window)
    if poll_health(timeout=35):
        print("\n" + "=" * 80)
        print(f"[Setup] Coordinator is running and healthy on {BASE_URL}")
        print("[Setup] In a separate command line, run: python test.py")
        print("[Setup] To stop Coordinator and clean database: python clean.py")
        if not args.new_window:
            print("[Setup] Or press Ctrl+C in this command line to shut down.")
        print("=" * 80 + "\n")

        if not args.new_window:
            try:
                proc.wait()
            except KeyboardInterrupt:
                print("\n[Setup] Stopping Coordinator...")
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/IM", "TrainSwarm.Coordinator.Api.exe", "/T"], capture_output=True)
                else:
                    proc.terminate()
                sys.exit(0)
        else:
            sys.exit(0)
    else:
        print("[Setup] [ERROR] Coordinator failed to become healthy within timeout.", file=sys.stderr)
        proc.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()


