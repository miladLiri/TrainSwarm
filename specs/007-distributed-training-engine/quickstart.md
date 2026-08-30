# Quickstart & Verification Guide: Distributed Training Engine

**Feature**: [Distributed Training Engine](spec.md)
**Status**: Complete
**Date**: 2026-08-30

This document outlines how to execute and verify the distributed training engine end-to-end using the sample testing harness under `samples/training_test/`.

---

## 1. Prerequisites

- Python 3.10+ installed
- PyTorch 2.x installed (`pip install torch torchvision`)

---

## 2. Directory Layout & Test Files

```text
samples/training_test/
├── setup.py        # Generates checkpoint-001.pt2 (2-layer MLP) and shard-001.pt (10 float32 samples)
├── train.py        # Instantiates TrainingTask and TrainingOrchestrator, executes training, verifies result
└── README.md       # Step-by-step instructions for running and evaluating the test
```

---

## 3. Step-by-Step Execution

### Step 1: Generate Sample Model & Dataset Shard

Run the setup script from the workspace root or the sample directory:

```bash
python samples/training_test/setup.py
```

**Expected Outcome**:
- Creates `samples/training_test/checkpoint-001.pt2` (a PyTorch 2 exported program wrapping a 2-layer MLP).
- Creates `samples/training_test/shard-001.pt` (containing a dictionary `{"x": tensor([10, 4]), "y": tensor([10, 1])}` with `float32` dtype).
- Logs confirmation of artifact generation.

### Step 2: Run Training Task with Orchestrator

Run the training execution script:

```bash
python samples/training_test/train.py
```

**Expected Outcome**:
- `TrainingOrchestrator` receives the `TrainingTask` and the working directory `samples/training_test`.
- Resolves `CanonicalTorchAdapter` through `TrainingAdapterRegistry`.
- Executes:
  1. `validate()`: Confirms schema, valid hyperparameters, and presence of `checkpoint-001.pt2` and `shard-001.pt`.
  2. `prepare()`: Loads the exported model and dataset, constructs `TensorDataset` and `DataLoader`.
  3. `train()`: Creates `MSELoss`, `AdamW`, and `CosineAnnealingLR` from their registries; executes the autograd training loop; logs step metrics.
  4. `save_result()`: Saves the newly trained model to `samples/training_test/trained_task-001.pt2` via `torch.export.save()` and returns `TrainingResult`.
- Prints the `TrainingResult` summary and logs confirming that loss decreased and the original `checkpoint-001.pt2` and `shard-001.pt` remain unmodified.

---

## 4. Verification Checkpoints

| Checkpoint | Validation Criterion | Pass Condition |
| :--- | :--- | :--- |
| **Input Immutability** | Compare SHA-256 hash or modification timestamp of `checkpoint-001.pt2` and `shard-001.pt` before and after training | Hashes and timestamps are identical |
| **Artifact Generation** | Verify existence of `samples/training_test/trained_task-001.pt2` | File exists and can be loaded via `torch.export.load()` |
| **Result Metrics** | Inspect returned `TrainingResult` | `final_loss < initial_loss`, `training_steps >= 1`, `output_checkpoint_path` matches artifact |
| **Logging Traceability** | Verify console logging stream | Structured logs emitted for `VALIDATE`, `PREPARE`, `TRAIN`, `SAVE_RESULT` milestones |
