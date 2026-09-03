# Quickstart: Distributed Training Engine — Aggregation Subsystem

**Feature**: `010-distributed-training-aggregation`  
**Date**: 2026-09-03  
**Status**: Complete

---

## 1. Prerequisites

- Python 3.10+ (PyTorch 2.x with `torch.export` support)
- `safetensors` Python library
- Repository environment initialized with `src/` on `PYTHONPATH`

```powershell
$env:PYTHONPATH = "C:\Users\azure-dev\dev\TrainSwarm\src"
```

---

## 2. End-to-End Sample Workflow (`samples/distributed_training_test/`)

The repository includes a complete end-to-end distributed training and aggregation scenario demonstrating dataset partitioning, parallel training across 5 workers, weighted Federated Averaging, and loss improvement verification.

### Step 1: Generate Base Model and Dataset
Run `setup.py` to create the canonical baseline PyTorch CNN model (`model_0.pt2`) and a 50-sample dataset (`dataset.pt`):

```powershell
cd C:\Users\azure-dev\dev\TrainSwarm\samples\distributed_training_test
python setup.py
```
**Expected Outcome**:
- `model_0.pt2` generated via `torch.export.export` and saved via `torch.export.save`.
- `dataset.pt` containing 50 samples generated and saved.

### Step 2: Partition Dataset into Shards
Run `partition.py` to partition `dataset.pt` into 5 shards of 10 samples each:

```powershell
python partition.py
```
**Expected Outcome**:
- 5 shard files created in `shards/`: `dataset_<shard_uuid>.pt`, each with 10 samples.

### Step 3: Execute Parallel Multi-Trainer Round
Run `train.py` to launch 5 parallel training jobs (one per shard) producing 5 parameter delta artifacts:

```powershell
python train.py
```
**Expected Outcome**:
- 5 `.safetensors` delta files created in `deltas/0/`.
- Training finishes with exit code 0.

### Step 4: Aggregate Deltas into Next Model Version
Run `aggregate.py` to execute sample-weighted Federated Averaging across all 5 deltas and publish `model_1.pt2`:

```powershell
python aggregate.py
```
**Expected Outcome**:
- All deltas validated and combined via weighted FedAvg.
- `model_1.pt2` published atomically.
- Baseline `model_0.pt2` remains untouched.
- Operation prints `AggregationResult` JSON.

### Step 5: Verify Model Convergence & Loss Reduction
Run `verify.py` to evaluate both `model_0.pt2` and `model_1.pt2` against `dataset.pt`:

```powershell
python verify.py
```
**Expected Outcome**:
- Both models evaluate cleanly without error.
- Evaluated loss for `model_1.pt2` is strictly lower than `model_0.pt2`.
- Script prints verification summary and exits with code 0.

---

## 3. Direct Python Engine API Usage

```python
from pathlib import Path
from distributed_training_engine.model_type import ModelType
from distributed_training_engine.aggregation.aggregation_request import AggregationRequest, ModelUpdate
from distributed_training_engine.aggregation.aggregation_orchecstrator import AggregationOrchestrator

# 1. Prepare request referencing base model and trainer delta artifacts
request = AggregationRequest(
    modelId="cnn_model",
    baseModelVersion=0,
    baseModelPath="models/cnn_model_0.pt2",
    newVersion=1,
    newVersionOutputDirectory="models",
    updates=[
        ModelUpdate(samplesTrained=10, deltaPath="deltas/task_001.safetensors"),
        ModelUpdate(samplesTrained=10, deltaPath="deltas/task_002.safetensors"),
        ModelUpdate(samplesTrained=10, deltaPath="deltas/task_003.safetensors"),
    ]
)

# 2. Instantiate orchestrator for canonical PyTorch
orchestrator = AggregationOrchestrator(model_type=ModelType.CANONICAL_TORCH)

# 3. Execute aggregation
result = orchestrator.aggregate(request)

# 4. Inspect result
print(f"Aggregated {result.updatesCount} updates into new model: {result.modelPath}")
```
