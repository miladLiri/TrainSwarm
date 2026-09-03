# Quickstart & Validation Guide: Training Result Standard & Delta Artifacts

**Feature**: `008-training-result-standard`  
**Date**: 2026-09-02  
**Status**: Ready for Validation  

---

## Overview

This guide details the three-step end-to-end execution workflow for generating canonical training artifacts, training via the orchestrator to produce a `.safetensors` model weight delta, and validating the delta through standalone mathematical reconstruction and loss verification.

---

## Prerequisites

1. **Python Runtime**: Python 3.10+ with `torch` and `safetensors` installed.
2. **Repository Root**: Run commands from the `TrainSwarm` root directory.

```powershell
pip install safetensors
```

---

## End-to-End Validation Workflow

### Step 1: Generate Sample Base Model and Dataset Shard

Generate the baseline PyTorch 2 exported program (`base_model_v1.pt2`) and dataset shard (`dataset1_shard1.pt`):

```powershell
python samples/training_test/setup.py
```

**Expected Output**:
```text
=== Generating Canonical Training Test Artifacts in .../samples/training_test ===
Exporting PyTorch 2 program using torch.export.export()...
[OK] Exported checkpoint saved: base_model_v1.pt2 (... bytes)
[OK] Dataset shard saved: dataset1_shard1.pt (10 samples, ... bytes)
=== Artifact generation completed successfully! ===
```

---

### Step 2: Execute Local Training and Generate Delta Artifact

Run the training runner to dispatch a `TrainingTask` through `TrainingOrchestrator`, snapshot baseline weights, execute the autograd training loop, compute parameter differences, and save the delta artifact:

```powershell
python samples/training_test/train.py
```

**Expected Output**:
```text
=== Starting Distributed Training Engine Local Verification ===
Verified input checkpoint: base_model_v1.pt2
Verified input dataset shard: dataset1_shard1.pt
Constructed TrainingTask DTO for task_id 'task-001'
...
=== Training Lifecycle Completed ===
Training Result Summary:
{
  "trainingTaskId": "task-001",
  "baseModelId": "base_model",
  "baseModelVersion": "v1",
  "datasetId": "dataset1",
  "datasetShardId": "shard1",
  "samplesTrained": 50,
  "metrics": {
    "loss_history": [ ... ],
    "device": "cpu",
    "total_steps": 25
  },
  "execution": {
    "startedAt": "2026-09-02T...",
    "completedAt": "2026-09-02T...",
    "durationMs": ...
  },
  "delta": {
    "filename": "base_model_v1_dataset1_shard1.safetensors",
    "path": ".../samples/training_test/base_model_v1_dataset1_shard1.safetensors",
    "format": "safetensors",
    "tensorCount": 4,
    "sizeBytes": ...
  }
}
[VERIFIED] Output artifact created: base_model_v1_dataset1_shard1.safetensors
[VERIFIED] Input checkpoint and shard remained strictly immutable (hashes matched).
[METRICS] Initial batch loss: ... -> Final loss: ...
=== All verification checks passed successfully! ===
```

---

### Step 3: Standalone Verification & Reconstruction

Run the standalone verification tool to reconstruct the trained model from base model + delta and verify convergence:

```powershell
python samples/training_test/verify.py
```

**Expected Output**:
```text
=== Starting Standalone Delta Verification Tooling ===
Loaded baseline model: base_model_v1.pt2
Loaded delta artifact: base_model_v1_dataset1_shard1.safetensors (4 tensors)
Loaded dataset shard: dataset1_shard1.pt (10 samples)
Baseline model evaluation loss: 0.845210
Applying delta tensors to base model parameters...
[OK] Parameter 'fc1.weight' delta applied (shape: torch.Size([8, 4]))
[OK] Parameter 'fc1.bias' delta applied (shape: torch.Size([8]))
[OK] Parameter 'fc2.weight' delta applied (shape: torch.Size([1, 8]))
[OK] Parameter 'fc2.bias' delta applied (shape: torch.Size([1]))
Reconstructed model evaluation loss: 0.041280
[SUCCESS] Verification passed: Reconstructed loss (0.041280) < Baseline loss (0.845210).
[SUCCESS] Exit code: 0
```

---

## Invariant Checks Reference

| Check | Expected Result |
|-------|-----------------|
| Base Model Immutability | SHA-256 hash before == SHA-256 hash after training |
| Dataset Shard Immutability | SHA-256 hash before == SHA-256 hash after training |
| Delta Filename | `base_model_v1_dataset1_shard1.safetensors` |
| Delta Size | >60% smaller than full `.pt2` export |
| Reconstruction Loss | Reconstructed loss significantly lower than baseline loss |
| Process Exit Code | 0 on clean completion |
