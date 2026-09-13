"""
Setup and orchestration harness for Canonical Causal Decoder Training Test.
Boots the full cluster natively without Docker:
1. Downloads roneneldan/TinyStories-1M model and dataset from Hugging Face Hub
2. Packages artifacts/tinystories_base.gz (containing model/ and tokenizer/ dirs)
3. Generates tokenized artifacts/tinystories_train.pt and artifacts/tinystories_val.pt
4. Generates artifacts/causal_decoder_config.json
5. Spawns Bootstrap Relay, Coordinator, Client, 2 Trainers, and 3 P2P sidecars
6. Tracks all background process IDs in .test_pids.json for reliable teardown
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

SAMPLE_DIR = Path(__file__).resolve().parent
if str(SAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(SAMPLE_DIR))
REPO_ROOT = SAMPLE_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
PIDS_FILE = SAMPLE_DIR / ".test_pids.json"

RELAY_HTTP_URL = "http://127.0.0.1:8090/health"
COORD_HTTP_URL = "http://127.0.0.1:8080/health"


def wait_for_http(url: str, name: str, max_seconds: int = 45) -> bool:
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


def prepare_hf_artifacts() -> None:
    """Download TinyStories-1M model and dataset, packaging into .gz and .pt test assets."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    base_model_archive = ARTIFACTS_DIR / "tinystories_base.gz"
    train_dataset_path = ARTIFACTS_DIR / "tinystories_train.pt"
    val_dataset_path = ARTIFACTS_DIR / "tinystories_val.pt"
    config_path = ARTIFACTS_DIR / "causal_decoder_config.json"

    # 1. Check if model archive already exists
    if not base_model_archive.is_file():
        print("[Setup] Sourcing Hugging Face TinyStories-1M model and tokenizer...")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        model_name = "roneneldan/TinyStories-1M"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)

        temp_dir = Path(tempfile.mkdtemp(prefix="hf_export_"))
        temp_model = temp_dir / "model"
        temp_tok = temp_dir / "tokenizer"
        temp_model.mkdir(parents=True, exist_ok=True)
        temp_tok.mkdir(parents=True, exist_ok=True)

        print("[Setup] Saving model and tokenizer to temporary staging directory...")
        model.save_pretrained(str(temp_model))
        tokenizer.save_pretrained(str(temp_tok))

        print(f"[Setup] Packaging into model archive: {base_model_archive}...")
        with tarfile.open(str(base_model_archive), "w:gz") as tar:
            tar.add(str(temp_model), arcname="model")
            tar.add(str(temp_tok), arcname="tokenizer")

        shutil.rmtree(temp_dir, ignore_errors=True)
        size_mb = base_model_archive.stat().st_size / (1024 * 1024)
        print(f"[Setup] Packaged {base_model_archive.name} ({size_mb:.2f} MB).")
    else:
        print(f"[Setup] Model archive already exists: {base_model_archive}")

    # 2. Check if datasets already exist
    if not (train_dataset_path.is_file() and val_dataset_path.is_file()):
        print("[Setup] Sourcing Hugging Face TinyStories dataset slice...")
        from datasets import load_dataset
        from transformers import AutoTokenizer
        import torch

        tokenizer = AutoTokenizer.from_pretrained("roneneldan/TinyStories-1M")
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Load small slice (100 samples)
        ds = load_dataset("roneneldan/TinyStories", split="train[:100]")
        texts = [t for t in ds["text"] if t and len(t.strip()) > 20]
        if len(texts) < 60:
            # Fallback text samples if fewer filtered
            texts = texts + ["Once upon a time there was a little friendly robot. It loved to learn new things every day."] * 60

        print(f"[Setup] Tokenizing {len(texts)} samples with seq_len=64...")
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=64,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = tokenized["input_ids"]
        attention_mask = tokenized["attention_mask"]
        labels = input_ids.clone()

        # Split: 80 train, 20 val (or proportional)
        split_idx = min(80, int(len(input_ids) * 0.8))
        train_dict = {
            "input_ids": input_ids[:split_idx],
            "attention_mask": attention_mask[:split_idx],
            "labels": labels[:split_idx],
        }
        val_dict = {
            "input_ids": input_ids[split_idx:],
            "attention_mask": attention_mask[split_idx:],
            "labels": labels[split_idx:],
        }

        torch.save(train_dict, str(train_dataset_path))
        torch.save(val_dict, str(val_dataset_path))
        print(f"[Setup] Saved {train_dataset_path.name} ({len(train_dict['input_ids'])} samples)")
        print(f"[Setup] Saved {val_dataset_path.name} ({len(val_dict['input_ids'])} samples)")
    else:
        print(f"[Setup] Datasets already exist: {train_dataset_path.name}, {val_dataset_path.name}")

    # 3. Create causal_decoder_config.json
    if not config_path.is_file():
        cfg = {
            "seed": 42,
            "batch_size": 2,
            "epochs": 1,
            "max_steps": 4,
            "learning_rate": 0.0001,
            "weight_decay": 0.01,
            "gradient_accumulation_steps": 1,
            "max_grad_norm": 1.0,
            "scheduler_type": "linear",
            "warmup_steps": 0,
            "warmup_ratio": 0.0,
            "fp16": False,
            "bf16": False,
            "shuffle": True,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        print(f"[Setup] Created {config_path.name}")


def start_local_cluster() -> int:
    """Spawns all 8 background processes and tracks PIDs."""
    import clean
    clean.main()

    db_dir = WORK_DIR / "db"
    logs_dir = WORK_DIR / "logs"
    client_work = WORK_DIR / "client_artifacts"
    trainer1_work = WORK_DIR / "trainer1_artifacts"
    trainer2_work = WORK_DIR / "trainer2_artifacts"

    for d in [db_dir, logs_dir, client_work, trainer1_work, trainer2_work]:
        d.mkdir(parents=True, exist_ok=True)

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
        print("[Setup] [ERROR] Relay failed to start.", file=sys.stderr)
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

    time.sleep(4.0)
    print(f"[Setup] Spawned {len(pids)} background processes (Coordinator, Relay, Client, 2 Trainers, 3 Sidecars).")
    print(f"[Setup] PIDs tracked in {PIDS_FILE.name}.")
    print("=== [Setup] Environment successfully initialized! ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical Causal Decoder Test Setup Harness")
    parser.add_argument("--stop", action="store_true", help="Stop running services and exit")
    args = parser.parse_args()

    if args.stop:
        import clean
        return clean.main()

    print("================================================================================")
    print("    Canonical Causal Decoder Training Test: Environment Setup                   ")
    print("================================================================================")
    prepare_hf_artifacts()
    return start_local_cluster()


if __name__ == "__main__":
    sys.exit(main())
