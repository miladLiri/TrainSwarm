# Quickstart & Verification Guide: Unified Training Metrics & Task Lifecycle Reporting

**Feature Branch**: `022-training-metrics-reporting`
**Spec Reference**: [spec.md](./spec.md)
**Status**: Ready for Verification

---

## Prerequisites

- Python 3.10+ with project virtual environment activated.
- PyTorch and Hugging Face Transformers installed (`torch`, `transformers`, `rich`, `safetensors`).

---

## Scenario 1: Standalone Zero-Argument Test Suite (`samples/training_report_test`)

This scenario proves dataset preparation, local adapter training via `distributed_training_engine`, report visualization, and clean resets without requiring background cluster daemons.

### Step 1: Download Baseline Model & Dataset
```powershell
cd samples/training_report_test
python download_artifacts.py
```
*Expected Outcome*: Downloads TinyStories-1M model weights and dataset sample under `artifacts/`.

### Step 2: Prepare Causal Decoder Artifacts
```powershell
python prepare_data.py
```
*Expected Outcome*:
- Produces tokenized PyTorch shard `artifacts/tinystories_train.pt` (`input_ids`, `attention_mask`, `labels`).
- Packages `artifacts/tinystories_base.tar.gz` with `model/` and `tokenizer/` inside.
- Writes `artifacts/causal_decoder_config.json`.

### Step 3: Run Fast Adapter Training Session
```powershell
python train.py
```
*Expected Outcome*:
- Executes local fine-tuning via `distributed_training_engine.training.TrainingOrchestrator` on the prepared shard.
- Prints step logs matching: `Step X/Y (Ep E/N) | Loss: L | PPL: P | Acc: A% | Speed: S tok/s | Time: Ts`.
- Generates `training_metrics.json` and parameter delta `.safetensors`.

### Step 4: Display Visual Training Report
```powershell
python show_report.py
```
*Expected Outcome*:
- Invokes `show_single_node_train_result.py` successfully pointing to `training_metrics.json`.
- Displays overview panel, summary deltas, ASCII loss/accuracy charts, and progression table without error.

### Step 5: Clean Up Outputs and Artifacts
```powershell
python clean.py
python clean_artifacts.py
cd ../..
```
*Expected Outcome*: All training runs, intermediate caches, and downloaded artifacts are cleanly deleted.

---

## Scenario 2: Verification of `show_training_task_result.py` Under All 4 States

Verify resilient display across all report availability combinations.

```powershell
cd samples/comaparision_test

# Test Case A: Neither report exists
python show_training_task_result.py
# Expected: Clean notification guiding user on how to run training, exit code 0.

# Test Case B: Only training metrics exists
# (Point to a valid training_metrics.json)
python show_training_task_result.py ./path/to/training_metrics.json
# Expected: Renders model convergence curves; displays yellow notice that lifecycle metrics were not found.

# Test Case C: Only lifecycle metrics exists
python show_training_task_result.py --lifecycle ./path/to/training_lifecycle_metrics.json
# Expected: Renders 6-step lifecycle duration breakdown; displays yellow notice that training metrics were not found.

# Test Case D: Both reports exist
python show_training_task_result.py ./path/to/training_metrics.json ./path/to/training_lifecycle_metrics.json
# Expected: Integrated display showing both lifecycle stage durations and model convergence metrics.

cd ../..
```

---

## Scenario 3: Compilability & Syntax Quality Gate

Validate 100% build integrity across all modified and created files per Constitution Principle VII:

```powershell
python -m py_compile src/distributed_training_engine/adapters/canonical_causal_decoder/training/canonical_causal_decoder_trainer.py
python -m py_compile src/Trainer/application/coordinator_commands/start_training/handler.py
python -m py_compile samples/comaparision_test/show_single_node_train_result.py
python -m py_compile samples/comaparision_test/show_training_task_result.py
python -m py_compile samples/training_report_test/download_artifacts.py
python -m py_compile samples/training_report_test/prepare_data.py
python -m py_compile samples/training_report_test/train.py
python -m py_compile samples/training_report_test/show_report.py
python -m py_compile samples/training_report_test/clean.py
python -m py_compile samples/training_report_test/clean_artifacts.py
```
*Expected Outcome*: Zero errors or warnings emitted.
