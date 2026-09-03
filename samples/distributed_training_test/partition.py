"""
Sample partitioning runner for distributed training test scenario.
Partitions data/dataset.pt into 5 shards of 10 samples each using PartitioningOrchestrator.
"""

import sys
from pathlib import Path

# Add src to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distributed_training_engine.model_type import ModelType
from distributed_training_engine.partitioning import (
    PartitioningOrchestrator,
    PartitioningRequest,
)

SAMPLE_DIR = Path(__file__).resolve().parent
DATA_DIR = SAMPLE_DIR / "data"
SHARDS_DIR = DATA_DIR / "shards"
SAMPLE_OUTPUT_DIR = DATA_DIR / "sample"


def partition_dataset() -> None:
    print(f"=== [Partition] Slicing Dataset in {DATA_DIR} ===")

    dataset_path = DATA_DIR / "dataset.pt"
    if not dataset_path.is_file():
        print(f"[ERROR] Dataset file not found at '{dataset_path}'. Please run setup.py first!", file=sys.stderr)
        sys.exit(1)

    # Clean existing shards dir if needed for deterministic reruns
    if SHARDS_DIR.exists():
        for f in SHARDS_DIR.glob("*"):
            if f.is_file():
                f.unlink()
    SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    request = PartitioningRequest(
        model_type=ModelType.CANONICAL_TORCH,
        datasetPath=dataset_path,
        shardsOutputDirectory=SHARDS_DIR,
        sampleOutputDirecotry=SAMPLE_OUTPUT_DIR,
        datasetId="dataset_50",
    )

    orchestrator = PartitioningOrchestrator(request)

    # Also extract a representative pre-flight sample
    sample_result = orchestrator.GetSample()
    print(f"[OK] Representative sample created: {Path(sample_result.sample_path).name} ({sample_result.sample_count} sample)")

    # Slice into 5 shards of 10 samples
    shard_sample_size = 10
    result = orchestrator.CreateShards(shardSampleSize=shard_sample_size)

    print(f"[OK] Partitioned dataset '{result.dataset_id}' into {result.shard_count} shards:")
    for idx, shard in enumerate(result.shards):
        p = Path(shard.artifact_path)
        print(f"     Shard {idx + 1}: {p.name} ({shard.sample_count} samples, {p.stat().st_size} bytes)")

    if result.shard_count != 5:
        print(f"[FAIL] Expected 5 shards, got {result.shard_count}", file=sys.stderr)
        sys.exit(1)

    print("=== [Partition] Dataset partitioning completed successfully! ===")


if __name__ == "__main__":
    partition_dataset()
