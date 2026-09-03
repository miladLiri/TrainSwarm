# Quickstart: Validating Dataset Partitioning & Reorganization

**Feature**: `009-dataset-partitioning`  
**Date**: 2026-09-03  
**Status**: Active

This guide describes how to validate the dataset partitioning subsystem and folder reorganization end-to-end using real runnable Python commands per Constitution Principle VII (Active Execution Verification).

---

## 1. Prerequisites

- Python 3.10+ installed with PyTorch (`torch`) available in the environment.
- Current working directory set to repository root: `C:\Users\azure-dev\dev\TrainSwarm`.

---

## 2. Validation Scenario 1: Preserving Training Functionality

Validate that the reorganization of `distributed_training_engine` did not break existing training capabilities:

```bash
# 1. Generate canonical sample model and dataset shard
python samples/training_test/setup.py

# 2. Run local canonical PyTorch training workflow
python samples/training_test/train.py

# 3. Verify reconstructed model parameters and delta validity
python samples/training_test/verify.py
```

**Expected Outcome**:
- All three scripts exit with code 0.
- `base_model_v1.pt2` and `dataset1_shard1.pt` generated.
- Model delta `.safetensors` artifact generated without errors.
- Verification confirms mathematical reconstruction parity and loss reduction.

---

## 3. Validation Scenario 2: Dataset Representative Sampling (`GetSample()`)

Validate that `PartitioningOrchestrator.GetSample()` extracts a single representative sample in canonical format:

```python
from pathlib import Path
from distributed_training_engine import ModelType
from distributed_training_engine.partitioning import (
    PartitioningRequest,
    PartitioningOrchestrator,
    PartitionerAdapterRegistry
)
from distributed_training_engine.adapters.canonical_torch.partitioning import (
    CanonicalTorchPartitioner
)

# Register adapter
PartitionerAdapterRegistry.Register(ModelType.CANONICAL_TORCH, CanonicalTorchPartitioner)

# Define directories
test_dir = Path("samples/partitioning_test")
test_dir.mkdir(parents=True, exist_ok=True)
sample_out = test_dir / "samples"
shards_out = test_dir / "shards"

request = PartitioningRequest(
    model_type=ModelType.CANONICAL_TORCH,
    datasetPath=Path("samples/training_test/dataset1_shard1.pt"),
    shardsOutputDirectory=shards_out,
    sampleOutputDirecotry=sample_out,
    datasetId="dataset-test-001"
)

orchestrator = PartitioningOrchestrator(request)
sampling_result = orchestrator.GetSample()
print("Sampling result:", sampling_result)
```

**Expected Outcome**:
- `samples/partitioning_test/samples/dataset-test-001_sample.pt` is created on disk.
- `sampling_result.sampleCount == 1`.
- Tensor shapes inside the sample match `{"x": shape [1, 4], "y": shape [1, 1]}`.

---

## 4. Validation Scenario 3: Shard Partitioning (`CreateShards()`)

Validate that `PartitioningOrchestrator.CreateShards()` slices a dataset into UUID-named shards and preserves remainders:

```python
# Create 3 shards from 10-sample dataset using shardSampleSize = 4 (4, 4, 2)
result = orchestrator.CreateShards(shardSampleSize=4)
print(f"Produced {result.shardCount} shards:")
for shard in result.shards:
    print(f"  Shard ID: {shard.shardId} -> {shard.sampleCount} samples at {shard.artifactPath}")
```

**Expected Outcome**:
- `result.shardCount == 3`.
- Shards 1 & 2 contain 4 samples each; shard 3 contains 2 samples (final partial shard preserved).
- Files named `dataset-test-001_<uuid>.pt` exist in `shards_out`.
- Slices contain exactly the original dataset tensors in deterministic order without loss.

---

## 5. Validation Scenario 4: Collision Prevention (`ExistingShardConflictError`)

Validate that calling `CreateShards()` on a non-empty directory raises an exception:

```python
import pytest
from distributed_training_engine.partitioning.exceptions import ExistingShardConflictError

try:
    orchestrator.CreateShards(shardSampleSize=4)
    print("FAILED: Expected ExistingShardConflictError")
except ExistingShardConflictError as exc:
    print(f"PASSED: Collision prevented -> {exc}")
```

**Expected Outcome**:
- `ExistingShardConflictError` is raised with descriptive context.
- No files are modified or overwritten.
