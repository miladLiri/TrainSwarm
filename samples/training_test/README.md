# Distributed Training Engine Test Scenario

This directory contains a standalone, runnable test scenario for the **Distributed Training Engine** using standardized delta artifacts and result contracts.

---

## 1. Overview

The test demonstrates end-to-end execution of a local training task conforming to the canonical PyTorch (`canonical_torch`) specification:
1. **Model Contract**: Baseline PyTorch 2 exported program (`base_model_v1.pt2`) wrapping a 2-layer MLP (`SimpleMLP`).
2. **Dataset Contract**: 10-sample tensor shard (`dataset1_shard1.pt`) containing float32 `x` and `y` tensors.
3. **Orchestrator Execution**: Type-agnostic `TrainingOrchestrator` resolves `CanonicalTorchAdapter` and drives the complete four-phase lifecycle (`validate` -> `prepare` -> `train` -> `save_result`).
4. **Delta Artifact Export**: Calculates parameter deltas against immutable baseline weights ($\Delta = W_{\text{trained}} - W_{\text{base}}$) and saves a compact `.safetensors` artifact: `base_model_v1_dataset1_shard1.safetensors`.
5. **Standalone Verification**: `verify.py` reconstructs model parameters from base model + delta and validates forward loss reduction.
6. **Invariants**: Input artifacts remain strictly immutable (zero file mutation); delta artifacts contain matching parameter keys and shapes.

---

## 2. Prerequisites

- Python 3.10+
- PyTorch 2.x (`torch`)
- `safetensors`

```bash
pip install torch safetensors
```

---

## 3. How to Run (3-Step Workflow)

### Step 1: Generate Test Artifacts

Generate `base_model_v1.pt2` and `dataset1_shard1.pt`:

```bash
python samples/training_test/setup.py
```

Expected output:
```text
=== Generating Canonical Training Test Artifacts in samples/training_test ===
Exporting PyTorch 2 program using torch.export.export()...
[OK] Exported checkpoint saved: base_model_v1.pt2 (... bytes)
[OK] Dataset shard saved: dataset1_shard1.pt (10 samples, ... bytes)
=== Artifact generation completed successfully! ===
```

### Step 2: Run Training Task & Export Delta

Execute the training task via `TrainingOrchestrator`:

```bash
python samples/training_test/train.py
```

Expected output:
```text
[INFO] sample_trainer: === Starting Distributed Training Engine Local Verification ===
[INFO] sample_trainer: Verified input baseline model: base_model_v1.pt2 (hash: ...)
[INFO] sample_trainer: Verified input dataset shard: dataset1_shard1.pt (hash: ...)
[INFO] distributed_training_engine.orchestrator: Starting training task execution [task_id=task-001, ...]
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: VALIDATE
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: PREPARE
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: TRAIN
[INFO] distributed_training_engine.canonical_torch_adapter: Epoch 1/5 completed [last_loss=..., total_steps=5]
...
[INFO] distributed_training_engine.orchestrator: Executing lifecycle phase: SAVE_RESULT
[INFO] distributed_training_engine.canonical_torch_adapter: Computing model delta and saving safetensors artifact to: .../base_model_v1_dataset1_shard1.safetensors
[INFO] sample_trainer: [VERIFIED] Output delta artifact created: base_model_v1_dataset1_shard1.safetensors (... bytes, 4 tensors)
[INFO] sample_trainer: [VERIFIED] Input baseline model and shard remained strictly immutable (hashes matched).
[INFO] sample_trainer: === All verification checks passed successfully! ===
```

### Step 3: Verify & Reconstruct Model

Run standalone mathematical reconstruction and evaluation loss verification:

```bash
python samples/training_test/verify.py
```

Expected output:
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
[SUCCESS] Total loss reduction: 0.803930
[SUCCESS] Standalone delta verification completed with exit code 0.
```

---

## 4. Evaluation & Invariant Verification

When the test suite executes:
1. **Compilation & Syntax**: Confirms syntax and imports across all `distributed_training_engine` modules.
2. **Pre-flight Validation**: Validates `TrainingTask` schema and file existence before training begins.
3. **Autograd Optimization**: Applies autograd updates with gradient clipping and learning rate decay.
4. **Immutability Check**: Computes SHA-256 hashes of `base_model_v1.pt2` and `dataset1_shard1.pt` before and after training to verify zero mutation.
5. **Delta Validation**: Verifies `base_model_v1_dataset1_shard1.safetensors` is produced, is loadable via `safetensors`, and mathematically reconstructs trained model weights.

