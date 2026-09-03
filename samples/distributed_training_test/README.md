# Distributed Training & Aggregation End-to-End Sample

This directory contains a complete, runnable end-to-end verification scenario for the **Distributed Training Engine** demonstrating dataset partitioning, 5-worker parallel model training, weighted Federated Averaging aggregation, and convergence validation with zero mocks.

---

## Architecture Overview

```text
[ setup.py ]
    ├── Generates models/cnn_model_0.pt2 (PyTorch 2 ExportedProgram)
    └── Generates data/dataset.pt (50 samples)
         │
         ▼
[ partition.py ]
    └── Slices data/dataset.pt into 5 shards of 10 samples each via PartitioningOrchestrator
         │
         ▼
[ train.py ]
    └── Trains 5 worker tasks in parallel via ProcessPoolExecutor & TrainingOrchestrator
    └── Produces 5 .safetensors parameter delta artifacts in deltas/0/
         │
         ▼
[ aggregate.py ]
    └── AggregationOrchestrator computes sample-weighted Federated Averaging
    └── Atomically publishes models/cnn_model_1.pt2 (base model v0 remains unchanged)
         │
         ▼
[ verify.py ]
    └── Evaluates loss on dataset.pt for both cnn_model_0.pt2 and cnn_model_1.pt2
    └── Confirms loss_v1 < loss_v0 (successful convergence)
```

---

## File Structure

```text
samples/distributed_training_test/
├── setup.py        # Generates baseline CNN model (.pt2) and 50-sample dataset (.pt)
├── partition.py    # Partitions dataset into 5 shards of 10 samples each
├── train.py        # Executes 5 parallel training workers producing 5 delta files
├── aggregate.py    # Collects deltas and aggregates them into cnn_model_1.pt2
├── verify.py       # Compares evaluation loss of v0 vs v1 on the full dataset
├── clean.py        # Removes all generated models, datasets, shards, and deltas
└── README.md       # This file
```

---

## Prerequisites

- Python 3.10+ (PyTorch 2.x)
- `safetensors` installed
- `src/` directory added to `PYTHONPATH`

---

## Running the Complete Pipeline

Run each script in sequence from the sample directory:

### 1. Setup Base Model & Dataset
```powershell
python setup.py
```
**Outcome**: Creates `models/cnn_model_0.pt2` and `data/dataset.pt`.

### 2. Partition Dataset into Shards
```powershell
python partition.py
```
**Outcome**: Creates `data/shards/dataset_50_<shard_id>.pt` (5 files, 10 samples each) and a representative pre-flight sample.

### 3. Run Parallel Training across 5 Workers
```powershell
python train.py
```
**Outcome**: Trains 5 models in parallel using `ProcessPoolExecutor`, saving 5 `.safetensors` delta files in `deltas/0/`.

### 4. Aggregate Model Deltas into Next Version
```powershell
python aggregate.py
```
**Outcome**: Runs `AggregationOrchestrator` to compute weighted Federated Averaging, atomically publishing `models/cnn_model_1.pt2`.

### 5. Verify Model Convergence
```powershell
python verify.py
```
**Outcome**: Evaluates loss for both `cnn_model_0.pt2` and `cnn_model_1.pt2`, verifying that `cnn_model_1.pt2` achieves lower loss than `cnn_model_0.pt2` and exiting with code 0.

### 6. Cleanup Generated Artifacts
```powershell
python clean.py
```
**Outcome**: Removes all generated `models/`, `data/`, and `deltas/` artifacts, leaving a clean workspace.
