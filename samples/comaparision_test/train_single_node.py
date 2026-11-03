"""
train_single_node.py

Runs single-node fine-tuning of TinyStories-1M using the distributed_training_engine:
1. Prepares required data structures using prepare_data.py (5000 samples, 1 shard, base model archive).
2. Executes training for 5 epochs with 5000 samples using TrainingOrchestrator and CanonicalCausalDecoderTrainer.
3. Applies the saved update result (.safetensors delta) onto the base model using AggregationOrchestrator
   to produce the new version artifact (tinystories_1.gz).
4. Unpacks the new version into single_node_finetuning/best_checkpoint/ and updates training_metrics.json
   and training_lifecycle_metrics.json so all downstream test and visualization scripts remain workable and compatible.
"""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import tarfile
import time
import torch

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repo src/ and script directory are on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Use all available CPU cores when running on CPU
if not torch.cuda.is_available() and hasattr(os, "cpu_count"):
    num_cpus = os.cpu_count() or 1
    torch.set_num_threads(max(1, num_cpus))

from distributed_training_engine.model_type import ModelType
from distributed_training_engine.training import (
    TrainingOrchestrator,
    TrainingTask,
)
from distributed_training_engine.aggregation import (
    AggregationOrchestrator,
    AggregationRequest,
    ModelUpdate,
)
import prepare_data

# ==============================================================================
# HARDCODED HYPERPARAMETERS & CONFIGURATION
# ==============================================================================
# Paths
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model"
BASE_MODEL_ARCHIVE = ARTIFACTS_DIR / "tinystories_base.tar.gz"
DATASET_SHARD = ARTIFACTS_DIR / "tinystories_train.pt"
WORK_DIR = SCRIPT_DIR / "work"
OUTPUT_DIR = SCRIPT_DIR / "single_node_finetuning"
BEST_CHECKPOINT_DIR = OUTPUT_DIR / "best_checkpoint"
METRICS_FILE = OUTPUT_DIR / "training_metrics.json"
LIFECYCLE_FILE = OUTPUT_DIR / "training_lifecycle_metrics.json"

# Optimization & Batching
BATCH_SIZE = 16                   # Batch size per step
GRAD_ACCUM_STEPS = 2              # Effective batch size = 128
LEARNING_RATE = 1e-4              # Calibrated fine-tuning learning rate
WEIGHT_DECAY = 0.01               # Weight decay for regularization
MAX_SEQ_LENGTH = 288              # Matches prepare_data.py sequence length

# Steps & Epochs
NUM_EPOCHS = 5                    # 5 epochs
MAX_TRAIN_SAMPLES = 5000          # 5,000 samples (single shard)
SEED = 42                         # Random seed for reproducibility
WARMUP_STEPS = 20         

# ==============================================================================


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def unpack_model_archive(archive_path: Path, destination_dir: Path) -> None:
    """Extracts model and tokenizer directories from a .gz archive into destination."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = destination_dir / "_unpack_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(str(archive_path), "r:*") as tar:
            tar.extractall(path=str(temp_dir))

        model_dir = temp_dir / "model"
        tokenizer_dir = temp_dir / "tokenizer"

        if not model_dir.is_dir():
            nested = list(temp_dir.glob("**/model"))
            if nested and nested[0].is_dir():
                model_dir = nested[0]

        if not tokenizer_dir.is_dir():
            nested_tok = list(temp_dir.glob("**/tokenizer"))
            if nested_tok and nested_tok[0].is_dir():
                tokenizer_dir = nested_tok[0]

        # Copy model files directly to destination
        if model_dir.is_dir():
            for item in model_dir.iterdir():
                dest_file = destination_dir / item.name
                if item.is_file():
                    shutil.copy2(str(item), str(dest_file))
                elif item.is_dir():
                    if dest_file.exists():
                        shutil.rmtree(dest_file, ignore_errors=True)
                    shutil.copytree(str(item), str(dest_file))

        # Copy tokenizer files directly to destination
        if tokenizer_dir.is_dir():
            for item in tokenizer_dir.iterdir():
                dest_file = destination_dir / item.name
                if not dest_file.exists():
                    if item.is_file():
                        shutil.copy2(str(item), str(dest_file))
                    elif item.is_dir():
                        shutil.copytree(str(item), str(dest_file))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Single Node Fine-Tuning using Distributed Training Engine")
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("NUM_EPOCHS", NUM_EPOCHS)), help="Number of training epochs")
    parser.add_argument("--samples", type=int, default=int(os.environ.get("MAX_TRAIN_SAMPLES", MAX_TRAIN_SAMPLES)), help="Number of samples")
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("BATCH_SIZE", BATCH_SIZE)), help="Batch size per step")
    parser.add_argument("--max-steps", type=int, default=int(os.environ["MAX_STEPS"]) if "MAX_STEPS" in os.environ and os.environ["MAX_STEPS"] else None, help="Max steps limit")
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(SEED)

    epochs = args.epochs
    samples = args.samples
    batch_size = args.batch_size
    max_steps = args.max_steps

    overall_start_time = time.time()
    iso_start_time = datetime.now(timezone.utc).isoformat()
    lifecycle_steps = []

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 65)
    print(" Single Node Fine-Tuning: TinyStories-1M (distributed_training_engine) ")
    print("=" * 65)
    print(f"[*] Target Device:       {device.type.upper()}")
    if device.type == "cuda":
        print(f"[*] GPU Model:           {torch.cuda.get_device_name(0)}")
        print(f"[*] VRAM Available:      {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
    else:
        print(f"[*] CPU Cores / Threads: {torch.get_num_threads()}")
    print(f"[*] Training Epochs:     {epochs}")
    print(f"[*] Training Samples:    {samples:,} (single shard)")
    print(f"[*] Batch Size:          {batch_size} (grad_accum={GRAD_ACCUM_STEPS})")
    if max_steps:
        print(f"[*] Max Steps Limit:     {max_steps}")
    print(f"[*] Output Directory:    {OUTPUT_DIR.resolve()}")
    print(f"[*] Best Checkpoint:     {BEST_CHECKPOINT_DIR.resolve()}")
    print("=" * 65 + "\n")

    # Step 1: Ensure Data & Base Model are Prepared
    t_prep_start = time.time()
    print("[1/4] Preparing required data and model artifacts using prepare_data.py...")
    prepare_data.package_model_archive()
    prepare_data.prepare_dataset_shard(max_samples=samples, max_seq_length=MAX_SEQ_LENGTH)
    prepare_data.write_training_config()

    if not BASE_MODEL_ARCHIVE.is_file():
        raise FileNotFoundError(f"Base model archive not found at '{BASE_MODEL_ARCHIVE}'")
    if not DATASET_SHARD.is_file():
        raise FileNotFoundError(f"Dataset shard not found at '{DATASET_SHARD}'")

    prep_dur = time.time() - t_prep_start
    lifecycle_steps.append({
        "step_number": 1,
        "name": "Data & Model Artifact Preparation",
        "status": "COMPLETED",
        "duration_sec": round(prep_dur, 2),
        "details": {"samples": samples, "model_archive": BASE_MODEL_ARCHIVE.name, "shard": DATASET_SHARD.name},
    })

    # Step 2: Stage Artifacts into Work Directory
    t_stage_start = time.time()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    work_model = WORK_DIR / BASE_MODEL_ARCHIVE.name
    work_shard = WORK_DIR / DATASET_SHARD.name

    if not work_model.exists() or work_model.stat().st_size != BASE_MODEL_ARCHIVE.stat().st_size:
        print(f"[*] Staging base model archive into '{work_model.name}'...")
        shutil.copyfile(BASE_MODEL_ARCHIVE, work_model)

    if not work_shard.exists() or work_shard.stat().st_size != DATASET_SHARD.stat().st_size:
        print(f"[*] Staging dataset shard into '{work_shard.name}'...")
        shutil.copyfile(DATASET_SHARD, work_shard)

    stage_dur = time.time() - t_stage_start
    lifecycle_steps.append({
        "step_number": 2,
        "name": "Artifact Staging",
        "status": "COMPLETED",
        "duration_sec": round(stage_dur, 2),
        "details": {"work_dir": str(WORK_DIR)},
    })

    # Step 3: Run Training with TrainingOrchestrator
    print("\n[2/4] Initializing TrainingOrchestrator and dispatching TrainingTask...")
    task_config = {
        "seed": SEED,
        "batch_size": batch_size,
        "epochs": epochs,
        "max_steps": max_steps,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "gradient_accumulation_steps": GRAD_ACCUM_STEPS,
        "max_grad_norm": 1.0,
        "scheduler_type": "cosine",
        "warmup_steps": WARMUP_STEPS,
        "warmup_ratio": 0.0,
        "fp16": False,
        "bf16": False,
        "shuffle": True,
    }

    task = TrainingTask(
        training_task_id="single_node_train_task_001",
        baseline_model_id="tinystories",
        baseline_model_version="base",
        data_set_id="tinystories",
        data_set_shard_id="train",
        type="canonical_causal_decoder",
        training=task_config,
    )

    t0_train = time.time()
    training_orchestrator = TrainingOrchestrator()
    train_result = training_orchestrator.run(task=task, working_directory=WORK_DIR)
    train_elapsed = time.time() - t0_train

    print("\n" + "=" * 65)
    print(f"[+] Local training completed in {train_elapsed:.2f}s!")
    print(f"[+] Samples trained: {train_result.samples_trained:,}")
    print(f"[+] Final loss:      {train_result.metrics.get('final_loss')}")
    print(f"[+] Delta artifact:  {train_result.delta.filename} ({train_result.delta.size_bytes:,} bytes)")
    print("=" * 65 + "\n")

    delta_path = Path(train_result.delta.path)
    if not delta_path.is_file():
        raise FileNotFoundError(f"Delta artifact was not generated at '{delta_path}'")

    lifecycle_steps.append({
        "step_number": 3,
        "name": "Model Training (CanonicalCausalDecoderTrainer)",
        "status": "COMPLETED",
        "duration_sec": round(train_elapsed, 2),
        "details": {
            "samples_trained": train_result.samples_trained,
            "final_loss": train_result.metrics.get("final_loss"),
            "delta_filename": train_result.delta.filename,
        },
    })

    # Step 4: Apply Update Result using AggregationOrchestrator to Create New Version
    t_agg_start = time.time()
    print("[3/4] Applying saved delta update to base model using AggregationOrchestrator...")

    target_version_archive = OUTPUT_DIR / "tinystories_1.gz"
    if target_version_archive.exists():
        target_version_archive.unlink()

    agg_request = AggregationRequest(
        modelId="tinystories",
        baseModelVersion=0,
        baseModelPath=work_model,
        newVersion=1,
        newVersionOutputDirectory=OUTPUT_DIR,
        updates=[
            ModelUpdate(
                samplesTrained=train_result.samples_trained,
                deltaPath=delta_path,
            )
        ],
    )

    agg_orchestrator = AggregationOrchestrator(model_type=ModelType.CANONICAL_CAUSAL_DECODER)
    agg_result = agg_orchestrator.Aggregate(agg_request)
    agg_dur = time.time() - t_agg_start

    published_archive = Path(agg_result.model_path)
    print("\n" + "=" * 65)
    print("[+] Model Aggregation Completed Successfully!")
    print(f"[+] Published Version: {agg_result.new_model_version}")
    print(f"[+] Aggregated Updates: {agg_result.updates_count}")
    print(f"[+] Published Archive: {published_archive.resolve()} ({published_archive.stat().st_size:,} bytes)")
    print("=" * 65 + "\n")

    lifecycle_steps.append({
        "step_number": 4,
        "name": "Model Aggregation (AggregationOrchestrator)",
        "status": "COMPLETED",
        "duration_sec": round(agg_dur, 2),
        "details": {
            "published_version": agg_result.new_model_version,
            "archive_bytes": published_archive.stat().st_size,
        },
    })

    # Step 5: Unpack new version for downstream test & evaluation scripts
    t_deploy_start = time.time()
    print(f"[4/4] Deploying new model version to '{BEST_CHECKPOINT_DIR}' for downstream evaluation...")
    unpack_model_archive(published_archive, BEST_CHECKPOINT_DIR)
    unpack_model_archive(published_archive, OUTPUT_DIR)
    deploy_dur = time.time() - t_deploy_start

    lifecycle_steps.append({
        "step_number": 5,
        "name": "New Version Deployment",
        "status": "COMPLETED",
        "duration_sec": round(deploy_dur, 2),
        "details": {"destination": str(BEST_CHECKPOINT_DIR)},
    })

    # Sync metrics files for visualization scripts
    work_metrics = WORK_DIR / "training_metrics.json"
    if work_metrics.is_file():
        shutil.copyfile(work_metrics, METRICS_FILE)
        shutil.copyfile(work_metrics, SCRIPT_DIR / "training_metrics.json")

    total_time = time.time() - overall_start_time
    iso_end_time = datetime.now(timezone.utc).isoformat()

    # Generate training_lifecycle_metrics.json
    lifecycle_data = {
        "task_metadata": {
            "client_node_id": "single-node",
            "model_id": "tinystories",
            "model_version": "1",
            "data_set_id": "tinystories",
            "shard_id": "train",
            "status": "COMPLETED",
            "total_elapsed_sec": round(total_time, 2),
            "start_time": iso_start_time,
            "end_time": iso_end_time,
            "error": None,
        },
        "steps": lifecycle_steps,
    }

    for target_path in [LIFECYCLE_FILE, SCRIPT_DIR / "training_lifecycle_metrics.json", WORK_DIR / "training_lifecycle_metrics.json"]:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(lifecycle_data, f, indent=2)

    print("\n" + "=" * 65)
    print(f"[✓] End-to-end single-node training & aggregation completed in {total_time:.2f}s.")
    print(f"[✓] Best checkpoint published at: '{BEST_CHECKPOINT_DIR.resolve()}'")
    print(f"[✓] Metrics saved to:             '{METRICS_FILE.resolve()}'")
    print(f"[✓] Lifecycle report saved to:    '{LIFECYCLE_FILE.resolve()}'")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
