"""
train.py

Runs a fast local training session using distributed_training_engine and CanonicalCausalDecoderTrainer.
Does not start background cluster daemons or require external network connectivity.
Runs without command-line arguments.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sys
import time

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
WORK_DIR = SCRIPT_DIR / "work"
CONFIG_PATH = ARTIFACTS_DIR / "causal_decoder_config.json"
MODEL_ARCHIVE = ARTIFACTS_DIR / "tinystories_base.tar.gz"
DATASET_SHARD = ARTIFACTS_DIR / "tinystories_train.pt"


def main() -> None:
    print("=" * 65)
    print(" Canonical Causal Decoder: Local Fast Training Session ")
    print("=" * 65)

    if not (MODEL_ARCHIVE.is_file() and DATASET_SHARD.is_file() and CONFIG_PATH.is_file()):
        print("[!] Required artifacts missing in './artifacts/'.")
        print("[*] Please run 'python download_artifacts.py' followed by 'python prepare_data.py' first.\n")
        sys.exit(1)

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # Stage artifacts into work/ for the adapter
    work_model = WORK_DIR / MODEL_ARCHIVE.name
    work_shard = WORK_DIR / DATASET_SHARD.name

    if not work_model.exists():
        print(f"[*] Staging model archive into work directory: '{work_model.name}'...")
        shutil.copyfile(MODEL_ARCHIVE, work_model)

    if not work_shard.exists():
        print(f"[*] Staging dataset shard into work directory: '{work_shard.name}'...")
        shutil.copyfile(DATASET_SHARD, work_shard)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    # Ensure quick execution (small max_steps if not already set)
    config_data["max_steps"] = min(config_data.get("max_steps", 4) or 4, 4)

    from distributed_training_engine.training import TrainingOrchestrator
    from distributed_training_engine.training.training_task_model import TrainingTask

    task = TrainingTask(
        training_task_id="report_test_task_001",
        baseline_model_id="tinystories",
        baseline_model_version="base",
        data_set_id="tinystories",
        data_set_shard_id="train",
        type="canonical_causal_decoder",
        training=config_data,
    )

    print(f"[*] Dispatching task '{task.training_task_id}' to distributed_training_engine...")
    print(f"[*] Planned steps: {config_data['max_steps']}, Batch size: {config_data.get('batch_size', 2)}\n")

    start_time = time.time()
    orchestrator = TrainingOrchestrator()
    result = orchestrator.run(task=task, working_directory=WORK_DIR)
    elapsed = time.time() - start_time

    print("\n" + "=" * 65)
    print(f"[+] Training completed in {elapsed:.2f}s!")
    print(f"[+] Samples trained: {result.samples_trained}")
    print(f"[+] Final loss:      {result.metrics.get('final_loss')}")
    print(f"[+] Weight delta:    {result.delta.filename} ({result.delta.size_bytes:,} bytes)")

    # Copy training_metrics.json to script dir for convenient single-command reporting
    metrics_src = WORK_DIR / "training_metrics.json"
    metrics_dst = SCRIPT_DIR / "training_metrics.json"
    if metrics_src.is_file():
        shutil.copyfile(metrics_src, metrics_dst)
        print(f"[+] Exported metrics: '{metrics_dst.name}'")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
