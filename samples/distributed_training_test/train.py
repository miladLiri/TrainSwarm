"""
Sample multi-trainer parallel runner for distributed training test scenario.
Executes 5 training tasks in parallel over the 5 partitioned shards using ProcessPoolExecutor,
producing 5 .safetensors delta artifacts in deltas/0/.
"""

import concurrent.futures
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add src to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distributed_training_engine.model_type import ModelType
from distributed_training_engine.training import (
    TrainingOrchestrator,
    TrainingTask,
)

SAMPLE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SAMPLE_DIR / "models"
DATA_DIR = SAMPLE_DIR / "data"
SHARDS_DIR = DATA_DIR / "shards"
DELTAS_DIR = SAMPLE_DIR / "deltas" / "0"


def _worker_train_task(args: Tuple[Dict[str, Any], str]) -> Dict[str, Any]:
    """Worker process function to execute training task in parallel."""
    task_dict, work_dir_str = args
    import sys
    from pathlib import Path

    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from distributed_training_engine.training import TrainingOrchestrator, TrainingTask

    task_obj = TrainingTask.from_dict(task_dict)
    orchestrator = TrainingOrchestrator()
    result = orchestrator.run(task=task_obj, working_directory=work_dir_str)
    return {
        "task_id": result.training_task_id,
        "delta_filename": result.delta.filename,
        "delta_path": result.delta.path,
        "samples_trained": result.samples_trained,
        "final_loss": result.metrics.get("loss", 0.0),
    }


def run_parallel_training() -> List[str]:
    print(f"=== [Train] Starting Multi-Trainer Parallel Training in {DELTAS_DIR} ===")

    base_model_path = MODELS_DIR / "cnn_model_0.pt2"
    if not base_model_path.is_file():
        print(f"[ERROR] Base model not found: '{base_model_path}'. Run setup.py first!", file=sys.stderr)
        sys.exit(1)

    shard_files = sorted(list(SHARDS_DIR.glob("dataset_50_*.pt")))
    if len(shard_files) != 5:
        print(f"[ERROR] Expected 5 shard files in '{SHARDS_DIR}', found {len(shard_files)}. Run partition.py first!", file=sys.stderr)
        sys.exit(1)

    # Clean and prepare deltas directory
    if DELTAS_DIR.exists():
        shutil.rmtree(DELTAS_DIR)
    DELTAS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy base model into deltas directory so trainer can locate baseline_model_id_version.pt2
    dest_base = DELTAS_DIR / "cnn_model_0.pt2"
    shutil.copy2(base_model_path, dest_base)
    print(f"[OK] Staged base model in work dir: {dest_base.name}")

    # Copy shards into deltas directory so trainer can locate dataset_id_shard_id.pt
    for s in shard_files:
        shutil.copy2(s, DELTAS_DIR / s.name)
    print(f"[OK] Staged {len(shard_files)} shards in work dir.")

    # Prepare 5 task payloads
    tasks: List[Tuple[Dict[str, Any], str]] = []
    for idx, shard_file in enumerate(shard_files):
        # Extract shard id from filename: dataset_50_<shard_id>.pt
        shard_id = shard_file.stem[len("dataset_50_"):]
        task_id = f"task-00{idx + 1}"

        task_payload = {
            "training_task_id": task_id,
            "baseline_model_id": "cnn_model",
            "baseline_model_version": "0",
            "data_set_id": "dataset_50",
            "data_set_shard_id": shard_id,
            "type": ModelType.CANONICAL_TORCH.value,
            "training": {
                "batch_size": 2,
                "shuffle": True,
                "epochs": 5,
                "gradient_accumulation_steps": 1,
                "max_steps": None,
                "max_grad_norm": 1.0,
                "seed": 42 + idx * 7,
                "optimizer": {
                    "type": "AdamW",
                    "parameters": {
                        "learning_rate": 0.05,
                        "weight_decay": 0.001
                    }
                },
                "scheduler": {
                    "type": "CosineAnnealingLR",
                    "parameters": {
                        "T_max": 15,
                        "eta_min": 0.001
                    }
                },
                "loss": {
                    "type": "MSELoss",
                    "parameters": {
                        "reduction": "mean"
                    }
                }
            }
        }
        tasks.append((task_payload, str(DELTAS_DIR)))

    print(f"Launching 5 parallel trainer workers using ProcessPoolExecutor...")
    delta_paths: List[str] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_worker_train_task, t) for t in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            print(
                f"[OK] Completed {res['task_id']}: delta='{res['delta_filename']}' "
                f"(samples={res['samples_trained']}, final_loss={res['final_loss']:.4f})"
            )
            delta_paths.append(res['delta_path'])

    if len(delta_paths) != 5:
        print(f"[FAIL] Expected 5 delta artifacts, got {len(delta_paths)}", file=sys.stderr)
        sys.exit(1)

    print("=== [Train] Multi-trainer parallel execution completed successfully! ===")
    return delta_paths


if __name__ == "__main__":
    run_parallel_training()
