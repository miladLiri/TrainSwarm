# Distributed Training Engine Test Scenario

This directory contains a standalone, runnable test scenario for the **Distributed Training Engine**.

---

## 1. Overview

The test demonstrates end-to-end execution of a local training task conforming to the canonical PyTorch (`canonical_torch`) specification:
1. **Model Contract**: PyTorch 2 exported program (`checkpoint-001.pt2`) wrapping a 2-layer MLP (`SimpleMLP`).
2. **Dataset Contract**: 10-sample tensor shard (`shard-001.pt`) containing float32 `x` and `y` tensors.
3. **Orchestrator Execution**: Type-agnostic `TrainingOrchestrator` resolves `CanonicalTorchAdapter` and drives the complete four-phase lifecycle (`validate` -> `prepare` -> `train` -> `save_result`).
4. **Registries & Config**: Instantiates `AdamW` optimizer, `CosineAnnealingLR` scheduler, and `MSELoss` criterion via typed parameter DTOs.
5. **Invariants**: Input artifacts remain strictly immutable; the locally trained model is saved as `trained_task-001.pt2` without claiming global checkpoint version ownership.

---

## 2. Prerequisites

- Python 3.10+
- PyTorch 2.x (`torch`)

```bash
pip install torch torchvision
```

---

## 3. How to Run

### Step 1: Generate Test Artifacts

Generate `checkpoint-001.pt2` and `shard-001.pt`:

```bash
python samples/training_test/setup.py
```

Expected output:
```text
=== Generating Canonical Training Test Artifacts in samples/training_test ===
Exporting PyTorch 2 program using torch.export.export()...
[OK] Exported checkpoint saved: checkpoint-001.pt2 (... bytes)
[OK] Dataset shard saved: shard-001.pt (10 samples, ... bytes)
=== Artifact generation completed successfully! ===
```

### Step 2: Run Training Task

Execute the training task via `TrainingOrchestrator`:

```bash
python samples/training_test/train.py
```

Expected output:
```text
[INFO] sample_trainer: === Starting Distributed Training Engine Local Verification ===
[INFO] sample_trainer: Verified input checkpoint: checkpoint-001.pt2
[INFO] sample_trainer: Verified input dataset shard: shard-001.pt
[INFO] distributed_training_engine.orchestrator: Starting training task execution [task_id=task-001, ...]
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: VALIDATE
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: PREPARE
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: TRAIN
[INFO] distributed_training_engine.canonical_torch_adapter: Epoch 1/5 completed [last_loss=..., total_steps=5]
...
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: SAVE_RESULT
[INFO] sample_trainer: [VERIFIED] Output artifact created: trained_task-001.pt2
[INFO] sample_trainer: [VERIFIED] Input checkpoint and shard remained strictly immutable (hashes matched).
[INFO] sample_trainer: === All verification checks passed successfully! ===
```

---

## 4. Evaluation & Invariant Verification

When `train.py` executes:
1. **Compilation & Syntax**: Confirms syntax and imports across all `distributed_training_engine` modules.
2. **Pre-flight Validation**: Validates the `TrainingTask` schema and file existence before training begins.
3. **Autograd Optimization**: Applies autograd updates with gradient clipping and learning rate decay.
4. **Immutability Check**: Computes SHA-256 hashes of `checkpoint-001.pt2` and `shard-001.pt` before and after training to verify zero mutation.
5. **Output Checkpoint**: Verifies `trained_task-001.pt2` exists and is loadable as a valid PyTorch 2 ExportedProgram.
