"""Startup script for TrainSwarm Task Assignment Verification Test.

Spawns Coordinator Web API and Trainer node as detached background processes,
records PIDs to .test_pids.txt, verifies Coordinator and Trainer health,
and generates synthetic PyTorch 2 model checkpoint, dataset, and training configuration.
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
import urllib.error
import urllib.request
import torch
import torch.nn as nn
from torch.export import Dim, export, save

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"

COORDINATOR_PORT = 5050
COORDINATOR_GRPC_PORT = 5051
HEALTH_URL = f"http://127.0.0.1:{COORDINATOR_PORT}/health"

DB_DIR = SAMPLE_DIR / "db"
COORD_DB_FILE = DB_DIR / "coordinator.db"
CLIENT_DB_FILE = DB_DIR / "training.db"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
CLIENT_WORK_DIR = SAMPLE_DIR / "client_work"

PID_FILE = SAMPLE_DIR / ".test_pids.txt"
COORD_LOG_FILE = SAMPLE_DIR / "coordinator.log"
TRAINER_LOG_FILE = SAMPLE_DIR / "trainer.log"


class Simple1DCNN(nn.Module):
    """Canonical 1D CNN model satisfying PyTorch 2 export specifications."""

    def __init__(self, in_channels: int = 1, hidden_channels: int = 4, out_features: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, hidden_channels, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.pool = nn.AdaptiveAvgPool1d(4)
        self.fc = nn.Linear(hidden_channels * 4, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.relu(self.conv1(x))
        h = self.pool(h)
        h = torch.flatten(h, start_dim=1)
        return self.fc(h)


def is_dotnet_available() -> bool:
    """Check if dotnet CLI is present in PATH."""
    return shutil.which("dotnet") is not None


def is_python_available() -> bool:
    """Check if python executable is available."""
    return shutil.which("python") is not None or shutil.which(sys.executable) is not None


def kill_process_tree(pid: int) -> None:
    """Kill process and all of its child processes."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def save_pid(pid: int) -> None:
    """Save a spawned PID for cleanup."""
    with open(PID_FILE, "a", encoding="utf-8") as f:
        f.write(f"{pid}\n")


def free_port_if_in_use(port: int) -> None:
    """Check if port is currently in use and terminate the listening process."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess",
                ],
                capture_output=True,
                text=True,
            )
            pids = [line.strip() for line in res.stdout.strip().splitlines() if line.strip().isdigit()]
            for pid in pids:
                print(f"[Setup] Port {port} occupied by PID {pid}. Terminating process...")
                kill_process_tree(int(pid))
        except Exception:
            pass


def clean_prior_state() -> None:
    """Clean prior processes and directories."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pids = [int(line.strip()) for line in f if line.strip().isdigit()]
            for pid in pids:
                print(f"[Setup] Terminating recorded process PID {pid}...")
                kill_process_tree(pid)
            PID_FILE.unlink()
        except Exception as e:
            print(f"[Setup] [WARN] Could not clean recorded PIDs: {e}")

    free_port_if_in_use(COORDINATOR_PORT)
    free_port_if_in_use(COORDINATOR_GRPC_PORT)

    for log_file in [COORD_LOG_FILE, TRAINER_LOG_FILE]:
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                pass

    for directory in [DB_DIR, CLIENT_WORK_DIR]:
        if directory.exists():
            try:
                shutil.rmtree(directory)
            except Exception:
                pass


def generate_synthetic_artifacts() -> None:
    """Generate PyTorch 2 model checkpoint, dataset, and training config."""
    print("[Setup] Generating synthetic test artifacts...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Export PyTorch 2 Program
    torch.manual_seed(42)
    model = Simple1DCNN()
    model.eval()
    sample_x = torch.randn(2, 1, 8, dtype=torch.float32)
    batch_dim = Dim("batch", min=1)
    exported = export(model, (sample_x,), dynamic_shapes=({0: batch_dim},))
    model_path = ARTIFACTS_DIR / "test_model.pt2"
    save(exported, str(model_path))
    print(f"[Setup] [OK] Model checkpoint saved: {model_path.name} ({model_path.stat().st_size} bytes)")

    # 2. Canonical PyTorch Dataset (50 samples)
    num_samples = 50
    x_data = torch.randn(num_samples, 1, 8, dtype=torch.float32)
    weights = torch.tensor([1.5, -2.0, 0.5, -1.0, 2.0, -0.5, 1.0, -1.5], dtype=torch.float32)
    y_data = torch.matmul(x_data.squeeze(1), weights).unsqueeze(1) + torch.randn(num_samples, 1, dtype=torch.float32) * 0.05
    dataset_path = ARTIFACTS_DIR / "test_dataset.pt"
    torch.save({"x": x_data, "y": y_data}, str(dataset_path))
    print(f"[Setup] [OK] Canonical dataset saved: {dataset_path.name} ({num_samples} samples)")

    # 3. Training Config JSON
    config_data = {
        "batch_size": 2,
        "shuffle": True,
        "epochs": 1,
        "gradient_accumulation_steps": 1,
        "optimizer": "AdamW",
        "learning_rate": 0.001,
        "loss": "MSELoss",
        "weight_decay": 0.01,
        "scheduler": "CosineAnnealingLR",
    }
    config_path = ARTIFACTS_DIR / "training_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"[Setup] [OK] Training config saved: {config_path.name}")


def main() -> int:
    print("================================================================================")
    print("   TrainSwarm Task Assignment Verification Harness: Environment Startup        ")
    print("================================================================================")

    if not is_dotnet_available():
        print("[Setup] [ERROR] 'dotnet' CLI was not found in PATH.", file=sys.stderr)
        return 1

    if not is_python_available():
        print("[Setup] [ERROR] 'python' executable was not found.", file=sys.stderr)
        return 1

    clean_prior_state()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Start Coordinator via dotnet CLI
    coord_proj = SRC_DIR / "Coordinator" / "TrainSwarm.Coordinator.Api" / "TrainSwarm.Coordinator.Api.csproj"
    if not coord_proj.exists():
        print(f"[Setup] [ERROR] Coordinator project not found at {coord_proj}", file=sys.stderr)
        return 1

    coord_env = os.environ.copy()
    coord_env["COORDINATOR_DB_CONNECTION_STRING"] = f"Data Source={COORD_DB_FILE.resolve()}"
    coord_env["COORDINATOR_HTTP_PORT"] = str(COORDINATOR_PORT)
    coord_env["COORDINATOR_GRPC_PORT"] = str(COORDINATOR_GRPC_PORT)

    coord_log = open(COORD_LOG_FILE, "w", encoding="utf-8")
    print(f"[Setup] Starting Coordinator on HTTP port {COORDINATOR_PORT} and gRPC port {COORDINATOR_GRPC_PORT} via dotnet CLI...")
    coord_cmd = [
        "dotnet",
        "run",
        "--project",
        str(coord_proj),
    ]
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    coord_proc = subprocess.Popen(
        coord_cmd,
        env=coord_env,
        stdout=coord_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    save_pid(coord_proc.pid)

    # 2. Poll Coordinator health endpoint
    print(f"[Setup] Waiting for Coordinator health endpoint at {HEALTH_URL}...", flush=True)
    healthy = False
    for attempt in range(1, 40):
        try:
            req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "TaskAssignmentHarness"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print(f"[Setup] [OK] Coordinator healthy (HTTP 200) on attempt {attempt}.", flush=True)
                    healthy = True
                    break
        except Exception:
            pass
        time.sleep(1)

    if not healthy:
        print("[Setup] [ERROR] Coordinator failed to become healthy.", file=sys.stderr)
        coord_log.flush()
        if COORD_LOG_FILE.exists():
            print("=== Coordinator Output ===", file=sys.stderr)
            print(COORD_LOG_FILE.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
        kill_process_tree(coord_proc.pid)
        coord_log.close()
        return 1

    # 3. Start Trainer via python CLI
    trainer_script = SRC_DIR / "Trainer" / "main.py"
    if not trainer_script.exists():
        print(f"[Setup] [ERROR] Trainer script not found at {trainer_script}", file=sys.stderr)
        kill_process_tree(coord_proc.pid)
        coord_log.close()
        return 1

    trainer_env = os.environ.copy()
    trainer_env["COORDINATOR_ADDRESS"] = f"http://127.0.0.1:{COORDINATOR_PORT}"
    trainer_env["COORDINATOR_GRPC_ADDRESS"] = f"127.0.0.1:{COORDINATOR_GRPC_PORT}"
    trainer_env["TRAINER_NODE_ID"] = "trainer-node-01"
    trainer_env["TRAINER_WORKING_DIRECTORY"] = str(ARTIFACTS_DIR.resolve())
    trainer_env["PYTHONPATH"] = str(SRC_DIR / "Trainer")

    trainer_log = open(TRAINER_LOG_FILE, "w", encoding="utf-8")
    print(f"[Setup] Starting Trainer node 'trainer-node-01' via python CLI ({sys.executable})...")
    trainer_cmd = [sys.executable, str(trainer_script)]
    trainer_proc = subprocess.Popen(
        trainer_cmd,
        env=trainer_env,
        cwd=str(SRC_DIR / "Trainer"),
        stdout=trainer_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    save_pid(trainer_proc.pid)

    # 4. Verify Trainer registration in Coordinator SQLite DB
    print(f"[Setup] Verifying Trainer registration in SQLite database at {COORD_DB_FILE}...")
    verified = False
    expected_node_id = "trainer-node-01"
    expected_status = 1  # TrainerStatus.IDLE

    for attempt in range(1, 30):
        if COORD_DB_FILE.exists():
            try:
                conn = sqlite3.connect(str(COORD_DB_FILE), timeout=5)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT Id, TrainerNodeId, Status FROM Trainers WHERE TrainerNodeId = ?",
                    (expected_node_id,),
                )
                row = cursor.fetchone()
                conn.close()

                if row is not None:
                    trainer_id, trainer_node_id, status = row
                    print(
                        f"[Setup] [OK] Trainer registered on attempt {attempt}: "
                        f"Id={trainer_id}, NodeId='{trainer_node_id}', Status={status} (IDLE)"
                    )
                    if status == expected_status:
                        verified = True
                        break
            except sqlite3.OperationalError:
                pass
        time.sleep(1)

    if not verified:
        print("[Setup] [ERROR] Trainer failed to register with Coordinator in IDLE status.", file=sys.stderr)
        kill_process_tree(trainer_proc.pid)
        kill_process_tree(coord_proc.pid)
        return 1

    # 5. Generate test artifacts
    generate_synthetic_artifacts()

    print("\n================================================================================")
    print("=== [Setup] Environment is ready for submit.py! ===")
    print(f" Coordinator PID: {coord_proc.pid} (Port {COORDINATOR_PORT})")
    print(f" Trainer PID:     {trainer_proc.pid}")
    print(f" Artifacts:       {ARTIFACTS_DIR}")
    print("================================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
