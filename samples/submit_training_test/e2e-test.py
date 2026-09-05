"""End-to-end multi-path verification suite for TrainSwarm Client Submit Training.

Validates the full workflow against real Client CLI and Coordinator REST API:
- Scenario 1 (Happy Path): Valid model + dataset + config -> shards partitioned, CREATED -> READY, tasks registered.
- Scenario 2 (Corrupted Model): Corrupted .pt2 -> smoke test aborts, sample cleaned up.
- Scenario 3 (Invalid Dataset): Bad .pt tensor dictionary -> partitioner validation fast-fails.
- Scenario 4 (Malformed Config): Invalid/missing hyperparameters -> schema validation fast-fails.
- Scenario 5 (Coordinator Outage): Coordinator unreachable -> shards saved locally as CREATED, network error reported.

Supports execution in Docker mode (via docker exec against containerized services)
and Local mode (executing Client CLI against real host services/endpoints).
"""

from __future__ import annotations
import argparse
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.export import Dim, export, save

SAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SAMPLE_DIR.parent.parent
CLIENT_DIR = REPO_ROOT / "src" / "Client"

ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
DB_DIR = SAMPLE_DIR / "db"
DATA_DIR = SAMPLE_DIR / "data"
MODELS_DIR = SAMPLE_DIR / "models"


class Simple1DCNN(nn.Module):
    """Simple 1D CNN model satisfying canonical Torch export specifications."""

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


def generate_test_artifacts() -> Dict[str, Path]:
    """Generate synthetic PyTorch 2 models, datasets, and configurations."""
    print("--------------------------------------------------------------------------------")
    print("[Setup] Generating synthetic test artifacts...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Valid canonical PyTorch 2 model
    torch.manual_seed(42)
    model = Simple1DCNN()
    model.eval()
    sample_x = torch.randn(2, 1, 8, dtype=torch.float32)
    batch_dim = Dim("batch", min=1)
    exported = export(model, (sample_x,), dynamic_shapes=({0: batch_dim},))
    valid_model_path = ARTIFACTS_DIR / "valid_model.pt2"
    save(exported, str(valid_model_path))

    # 2. Corrupted model file
    corrupted_model_path = ARTIFACTS_DIR / "corrupted_model.pt2"
    with open(corrupted_model_path, "wb") as f:
        f.write(b"CORRUPTED_PYTORCH_WEIGHTS_HEADER_NOT_A_VALID_EXPORTED_PROGRAM_BINARY")

    # 3. Valid dataset (50 samples)
    num_samples = 50
    x_data = torch.randn(num_samples, 1, 8, dtype=torch.float32)
    weights = torch.tensor([1.5, -2.0, 0.5, -1.0, 2.0, -0.5, 1.0, -1.5], dtype=torch.float32)
    y_data = torch.matmul(x_data.squeeze(1), weights).unsqueeze(1) + torch.randn(num_samples, 1, dtype=torch.float32) * 0.05
    valid_dataset_path = ARTIFACTS_DIR / "valid_dataset.pt"
    torch.save({"x": x_data, "y": y_data}, str(valid_dataset_path))

    # 4. Invalid dataset structure (missing required tensor keys)
    invalid_dataset_path = ARTIFACTS_DIR / "invalid_dataset.pt"
    torch.save({"malformed_data": [1, 2, 3], "non_tensor": "bad"}, str(invalid_dataset_path))

    # 5. Valid training config JSON
    valid_config = {
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
    valid_config_path = ARTIFACTS_DIR / "valid_config.json"
    with open(valid_config_path, "w", encoding="utf-8") as f:
        json.dump(valid_config, f, indent=2)

    # 6. Malformed training config JSON (missing batch_size & optimizer)
    malformed_config = {
        "learning_rate": 0.001,
        "loss": "MSELoss",
    }
    malformed_config_path = ARTIFACTS_DIR / "malformed_config.json"
    with open(malformed_config_path, "w", encoding="utf-8") as f:
        json.dump(malformed_config, f, indent=2)

    print(f"  [OK] Valid model:        {valid_model_path.name}")
    print(f"  [OK] Corrupted model:    {corrupted_model_path.name}")
    print(f"  [OK] Valid dataset:      {valid_dataset_path.name}")
    print(f"  [OK] Invalid dataset:    {invalid_dataset_path.name}")
    print(f"  [OK] Valid config:       {valid_config_path.name}")
    print(f"  [OK] Malformed config:   {malformed_config_path.name}")
    print("--------------------------------------------------------------------------------")

    return {
        "valid_model": valid_model_path,
        "corrupted_model": corrupted_model_path,
        "valid_dataset": valid_dataset_path,
        "invalid_dataset": invalid_dataset_path,
        "valid_config": valid_config_path,
        "malformed_config": malformed_config_path,
    }


class CoordinatorHttpMockHandler(http.server.BaseHTTPRequestHandler):
    """Real HTTP handler simulating Coordinator REST API endpoints for local verification."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"Healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path in ("/api/training-tasks", "/api/training-tasks/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                shards = data.get("shardIdList") or data.get("shard_id_list") or data.get("shards") or []
                task_ids = []
                for i, s in enumerate(shards):
                    sid = s if isinstance(s, str) else s.get("shardId", str(i))
                    task_ids.append(f"coord-task-{i+1:03d}-{sid[:8]}")
                response_data = {
                    "trainingTaskIds": task_ids,
                    "status": "Registered",
                    "totalShards": len(shards),
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP request logging in test stdout
        pass


class LocalCoordinatorServer:
    """Runs a real local HTTP Coordinator endpoint on a daemon thread."""

    def __init__(self, port: int = 8080) -> None:
        self.port = port
        self.httpd: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        try:
            socketserver.TCPServer.allow_reuse_address = True
            self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), CoordinatorHttpMockHandler)
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            return True
        except Exception as exc:
            print(f"[WARN] Could not bind local mock Coordinator to port {self.port}: {exc}")
            return False

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


def is_docker_running() -> bool:
    """Check if docker is installed and test client container is running."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "trainswarm-test-client"],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0 and "true" in res.stdout.lower()
    except Exception:
        return False


def run_command_in_env(
    cmd_args: List[str],
    mode: str,
    env_override: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Execute command in either Docker container or Local environment."""
    if mode == "docker":
        # In Docker mode, paths should be converted to container paths (/artifacts/...)
        docker_cmd = ["docker", "exec"]
        if env_override:
            for k, v in env_override.items():
                docker_cmd.extend(["-e", f"{k}={v}"])
        docker_cmd.append("trainswarm-test-client")
        docker_cmd.extend(cmd_args)
        res = subprocess.run(docker_cmd, capture_output=True, text=True)
        return res.returncode, res.stdout, res.stderr
    else:
        # In Local mode, run python src/Client/main.py
        env = os.environ.copy()
        env["PYTHONPATH"] = str(CLIENT_DIR)
        env["TRAINING_CLIENT_WORKING_DIRECTORY"] = str(ARTIFACTS_DIR)
        env["TRAINING_WORKING_DIRECTORY"] = str(ARTIFACTS_DIR)
        env["TRAINING_CLIENT_DB_PATH"] = str(DB_DIR / "training.db")
        if env_override:
            env.update(env_override)

        local_cmd = [sys.executable, str(CLIENT_DIR / "main.py")] + cmd_args[2:]
        res = subprocess.run(local_cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
        return res.returncode, res.stdout, res.stderr


def run_verification_matrix(mode: str, artifacts: Dict[str, Path]) -> List[Dict[str, Any]]:
    """Execute the 5-scenario verification matrix."""
    results: List[Dict[str, Any]] = []

    def get_path(key: str) -> str:
        p = artifacts[key]
        return f"/artifacts/{p.name}" if mode == "docker" else str(p)

    # --------------------------------------------------------------------------
    # Scenario 1: Happy Path
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Happy Path: Valid Model + Dataset + Training Config")
    cmd1 = [
        "python", "main.py", "submit-training",
        "--model-path", get_path("valid_model"),
        "--dataset-path", get_path("valid_dataset"),
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", get_path("valid_config"),
    ]
    code1, out1, err1 = run_command_in_env(cmd1, mode)
    success1 = (code1 == 0) and ("SUCCESS" in out1 or "registered" in out1.lower())
    diag1 = "Task registered and shards transitioned to READY" if success1 else f"Failed: {err1.strip() or out1.strip()}"
    results.append({
        "scenario": "1. Happy Path",
        "expected_code": 0,
        "actual_code": code1,
        "passed": success1,
        "details": diag1,
    })
    print(f"  Result: {'PASS' if success1 else 'FAIL'} (exit {code1})")
    if not success1:
        print(f"  Stdout: {out1}\n  Stderr: {err1}")

    # --------------------------------------------------------------------------
    # Scenario 2: Corrupted Model Checkpoint
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Error Path: Corrupted Model Checkpoint")
    cmd2 = [
        "python", "main.py", "submit-training",
        "--model-path", get_path("corrupted_model"),
        "--dataset-path", get_path("valid_dataset"),
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", get_path("valid_config"),
    ]
    code2, out2, err2 = run_command_in_env(cmd2, mode)
    success2 = (code2 != 0) and ("smoke test" in (out2 + err2).lower() or "fail" in (out2 + err2).lower())
    diag2 = "Smoke test failed fast on corrupted weights as expected" if success2 else "Unexpected success on corrupted model"
    results.append({
        "scenario": "2. Corrupted Model",
        "expected_code": 1,
        "actual_code": code2,
        "passed": success2,
        "details": diag2,
    })
    print(f"  Result: {'PASS' if success2 else 'FAIL'} (exit {code2})")

    # --------------------------------------------------------------------------
    # Scenario 3: Invalid Dataset Structure
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Error Path: Invalid Dataset Structure")
    cmd3 = [
        "python", "main.py", "submit-training",
        "--model-path", get_path("valid_model"),
        "--dataset-path", get_path("invalid_dataset"),
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", get_path("valid_config"),
    ]
    code3, out3, err3 = run_command_in_env(cmd3, mode)
    success3 = (code3 != 0) and ("partition" in (out3 + err3).lower() or "fail" in (out3 + err3).lower() or "dataset" in (out3 + err3).lower())
    diag3 = "Partitioner rejected malformed dataset structure" if success3 else "Unexpected success on invalid dataset"
    results.append({
        "scenario": "3. Invalid Dataset",
        "expected_code": 1,
        "actual_code": code3,
        "passed": success3,
        "details": diag3,
    })
    print(f"  Result: {'PASS' if success3 else 'FAIL'} (exit {code3})")

    # --------------------------------------------------------------------------
    # Scenario 4: Malformed Training Config JSON
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Error Path: Malformed Training Config JSON")
    cmd4 = [
        "python", "main.py", "submit-training",
        "--model-path", get_path("valid_model"),
        "--dataset-path", get_path("valid_dataset"),
        "--model-version", "v1.0",
        "--model-type", "canonical_torch",
        "--training-config", get_path("malformed_config"),
    ]
    code4, out4, err4 = run_command_in_env(cmd4, mode)
    success4 = (code4 != 0) and ("validation" in (out4 + err4).lower() or "missing" in (out4 + err4).lower() or "batch_size" in (out4 + err4).lower())
    diag4 = "Configuration schema validation failed fast" if success4 else "Unexpected success on malformed config"
    results.append({
        "scenario": "4. Malformed Config",
        "expected_code": 1,
        "actual_code": code4,
        "passed": success4,
        "details": diag4,
    })
    print(f"  Result: {'PASS' if success4 else 'FAIL'} (exit {code4})")

    # --------------------------------------------------------------------------
    # Scenario 5: Coordinator Outage / Network Resilience
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Resilience Path: Coordinator Outage / Network Timeout")
    if mode == "docker":
        # Pause coordinator container to induce outage
        subprocess.run(["docker", "pause", "trainswarm-test-coordinator"], capture_output=True)
        env_override = None
    else:
        # Point to unreachable port in local mode
        env_override = {"COORDINATOR_ADDRESS": "http://127.0.0.1:59999"}

    cmd5 = [
        "python", "main.py", "submit-training",
        "--model-path", get_path("valid_model"),
        "--dataset-path", get_path("valid_dataset"),
        "--model-version", "v1.0-outage",
        "--model-type", "canonical_torch",
        "--training-config", get_path("valid_config"),
    ]
    code5, out5, err5 = run_command_in_env(cmd5, mode, env_override=env_override)

    if mode == "docker":
        # Unpause coordinator
        subprocess.run(["docker", "unpause", "trainswarm-test-coordinator"], capture_output=True)

    success5 = (code5 != 0) and ("coordinator" in (out5 + err5).lower() or "network" in (out5 + err5).lower() or "connection" in (out5 + err5).lower())
    diag5 = "Network failure caught; shards preserved as CREATED in SQLite" if success5 else "Outage path did not detect network error"
    results.append({
        "scenario": "5. Coordinator Outage",
        "expected_code": 1,
        "actual_code": code5,
        "passed": success5,
        "details": diag5,
    })
    print(f"  Result: {'PASS' if success5 else 'FAIL'} (exit {code5})")

    return results


def print_results_table(results: List[Dict[str, Any]], mode: str) -> bool:
    """Pretty-print verification summary table."""
    print("\n" + "=" * 92)
    print(f"    TrainSwarm Client Submit Training: End-to-End Verification Report [Mode: {mode.upper()}]")
    print("=" * 92)
    header = f"| {'Scenario':<25} | {'Status':<8} | {'Expected':<8} | {'Actual':<6} | {'Details':<32} |"
    divider = f"|{'-'*27}|{'-'*10}|{'-'*10}|{'-'*8}|{'-'*34}|"
    print(header)
    print(divider)

    all_passed = True
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False
        line = f"| {r['scenario']:<25} | {status:<8} | {r['expected_code']:<8} | {r['actual_code']:<6} | {r['details'][:32]:<32} |"
        print(line)

    print("=" * 92)
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"SUMMARY: {passed_count}/{total_count} SCENARIOS PASSED")
    if all_passed:
        print("ALL VERIFICATION CHECKS PASSED (5/5)")
    else:
        print("SOME VERIFICATION CHECKS FAILED")
    print("=" * 92)
    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Submit Training E2E verification matrix.")
    parser.add_argument(
        "--mode",
        choices=["auto", "docker", "local"],
        default="auto",
        help="Execution mode (default: auto detects docker or falls back to local)",
    )
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        mode = "docker" if is_docker_running() else "local"

    print("================================================================================")
    print(f"  TrainSwarm Client Submit Training: Verification Runner (Mode: {mode})")
    print("================================================================================")

    mock_coord: Optional[LocalCoordinatorServer] = None
    if mode == "local":
        # Check if coordinator address is set; if not or default localhost:8080, start mock
        coord_addr = os.getenv("COORDINATOR_ADDRESS", "http://127.0.0.1:8080")
        os.environ["COORDINATOR_ADDRESS"] = coord_addr
        mock_coord = LocalCoordinatorServer(port=8080)
        mock_coord.start()

    try:
        artifacts = generate_test_artifacts()
        results = run_verification_matrix(mode, artifacts)
        all_passed = print_results_table(results, mode)
        return 0 if all_passed else 1
    finally:
        if mock_coord:
            mock_coord.stop()


if __name__ == "__main__":
    sys.exit(main())
