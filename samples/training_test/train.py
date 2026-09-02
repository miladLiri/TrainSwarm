"""
Sample training runner for the Distributed Training Engine test scenario.
Executes TrainingOrchestrator over local task with base_model_v1.pt2 and dataset1_shard1.pt,
producing base_model_v1_dataset1_shard1.safetensors delta artifact.
"""

import hashlib
import json
import logging
import sys
from pathlib import Path

# Add src to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distributed_training_engine.training import (
    TrainingOrchestrator,
    TrainingTask,
    ModelType,
)

SAMPLE_DIR = Path(__file__).resolve().parent


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file to verify immutability."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    # 1. Setup structured logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("sample_trainer")

    logger.info("=== Starting Distributed Training Engine Local Verification ===")

    # 2. Check input artifacts exist
    checkpoint_path = SAMPLE_DIR / "base_model_v1.pt2"
    shard_path = SAMPLE_DIR / "dataset1_shard1.pt"

    if not checkpoint_path.is_file() or not shard_path.is_file():
        logger.error(
            "Missing sample input files in %s. Please run 'python setup.py' first!",
            SAMPLE_DIR
        )
        sys.exit(1)

    initial_checkpoint_hash = compute_file_sha256(checkpoint_path)
    initial_shard_hash = compute_file_sha256(shard_path)
    logger.info("Verified input baseline model: %s (hash: %s...)", checkpoint_path.name, initial_checkpoint_hash[:12])
    logger.info("Verified input dataset shard: %s (hash: %s...)", shard_path.name, initial_shard_hash[:12])

    # 3. Construct TrainingTask DTO
    task_payload = {
        "training_task_id": "task-001",
        "baseline_model_id": "base_model",
        "baseline_model_version": "v1",
        "data_set_id": "dataset1",
        "data_set_shard_id": "shard1",
        "type": ModelType.CANONICAL_TORCH.value,
        "training": {
            "batch_size": 2,
            "shuffle": True,
            "epochs": 5,
            "gradient_accumulation_steps": 1,
            "max_steps": None,
            "max_grad_norm": 1.0,
            "seed": 42,
            "optimizer": {
                "type": "AdamW",
                "parameters": {
                    "learning_rate": 0.05,
                    "weight_decay": 0.01
                }
            },
            "scheduler": {
                "type": "CosineAnnealingLR",
                "parameters": {
                    "T_max": 5,
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

    task = TrainingTask.from_dict(task_payload)
    logger.info("Constructed TrainingTask DTO for training_task_id '%s'", task.training_task_id)

    # 4. Instantiate TrainingOrchestrator and run
    orchestrator = TrainingOrchestrator()
    logger.info("Instantiated TrainingOrchestrator. Running training lifecycle on working_directory: %s", SAMPLE_DIR)

    result = orchestrator.run(task=task, working_directory=SAMPLE_DIR)

    # 5. Verify Results & Invariants
    logger.info("=== Training Lifecycle Completed ===")
    logger.info("Training Result Summary:")
    print(json.dumps(result.to_dict(), indent=2))

    # Verify output delta artifact exists
    delta_path = Path(result.delta.path)
    assert delta_path.is_file(), f"Output delta file {delta_path} was not created!"
    logger.info(
        "[VERIFIED] Output delta artifact created: %s (%d bytes, %d tensors)",
        delta_path.name, result.delta.size_bytes, result.delta.tensor_count
    )

    # Verify input immutability
    post_checkpoint_hash = compute_file_sha256(checkpoint_path)
    post_shard_hash = compute_file_sha256(shard_path)
    assert post_checkpoint_hash == initial_checkpoint_hash, "CRITICAL: Input checkpoint file was modified!"
    assert post_shard_hash == initial_shard_hash, "CRITICAL: Input dataset shard file was modified!"
    logger.info("[VERIFIED] Input baseline model and shard remained strictly immutable (hashes matched).")

    # Verify loss reduction
    if len(result.metrics.get("loss_history", [])) >= 2:
        initial_loss = result.metrics["loss_history"][0]
        final_loss = result.metrics.get("final_loss", 0.0)
        logger.info("[METRICS] Initial batch loss: %.6f -> Final loss: %.6f", initial_loss, final_loss)

    logger.info("=== All verification checks passed successfully! ===")


if __name__ == "__main__":
    main()

