# CLI Presentation Contracts: Unified Training Metrics & Task Lifecycle Reporting

**Feature Branch**: `022-training-metrics-reporting`
**Spec Reference**: [spec.md](../spec.md)
**Status**: Completed

---

## 1. `show_single_node_train_result.py` (CLI Contract)

### Usage
```bash
python samples/comaparision_test/show_single_node_train_result.py [METRICS_JSON_PATH]
```

### Arguments
- `METRICS_JSON_PATH` (optional string): Path to `training_metrics.json`.
  - If omitted: searches `./training_metrics.json`, then `./single_node_finetuning/training_metrics.json`.
  - If neither exists: prints a clean warning and exits with code 0.

### Output
- Terminal Rich panels with:
  1. Overview & Hardware metadata.
  2. Training Loss, Perplexity, and Token Accuracy summary deltas.
  3. Detailed Training Time & Efficiency report.
  4. ASCII Convergence curves for Loss and Accuracy.
  5. Progression Snapshot Table (last 10 steps).

---

## 2. `show_training_task_result.py` (CLI Contract)

### Usage
```bash
python samples/comaparision_test/show_training_task_result.py [METRICS_JSON_PATH] [LIFECYCLE_JSON_PATH]
```

### Arguments
- `METRICS_JSON_PATH` (optional string): Path to `training_metrics.json`.
- `LIFECYCLE_JSON_PATH` (optional string): Path to `training_lifecycle_metrics.json`.

### Path Discovery Order (when arguments omitted)
1. Checks `./training_metrics.json` and `./training_lifecycle_metrics.json`.
2. Checks `./work/training_metrics.json` and `./work/training_lifecycle_metrics.json`.
3. Checks `./single_node_finetuning/training_metrics.json` and `./single_node_finetuning/training_lifecycle_metrics.json`.

### Resilience Contracts
- **Both reports present**: Renders Task Lifecycle Stage Duration Breakdown table followed by Model Convergence Metrics and ASCII charts.
- **Only training metrics present**: Renders Model Convergence Metrics and prints an informational notice: `[yellow]Notice: Lifecycle metrics file not found. Showing training metrics only.[/yellow]`.
- **Only lifecycle metrics present**: Renders Task Lifecycle Stage Duration Breakdown and prints an informational notice: `[yellow]Notice: Training metrics file not found. Showing task lifecycle only.[/yellow]`.
- **Neither report present**: Displays a user guidance panel instructing how to run training first; exits cleanly with code 0 (no uncaught exceptions).

---

## 3. `samples/training_report_test/` Test Suite Contracts

All scripts in this directory MUST be callable with **zero arguments** (`sys.argv` ignored or defaulted).

| Script | Contract / Behavior | Output Assets |
|---|---|---|
| `download_artifacts.py` | Sourced from `samples/comaparision_test/download_artifacts.py`. Downloads model weights and dataset sample. | `artifacts/model/`, `artifacts/dataset/` |
| `prepare_data.py` | Tokenizes sample slice into PyTorch tensor dictionary shard with prompt label masking (-100); packages `tinystories_base.tar.gz` and writes config. | `artifacts/tinystories_base.tar.gz`, `artifacts/tinystories_train.pt`, `artifacts/causal_decoder_config.json` |
| `train.py` | Runs minimal local training run using `distributed_training_engine` (e.g. 20 samples, 2 steps, batch size 2). | `work/training_metrics.json`, delta `.safetensors` |
| `show_report.py` | Calls `show_single_node_train_result.py` on the generated metrics file to display terminal visualization. | Standard visual terminal output |
| `clean.py` | Deletes output artifacts created by `train.py` and `show_report.py`. | Removes `work/`, `training_metrics.json`, plot files |
| `clean_artifacts.py` | Deletes assets created by `download_artifacts.py` and `prepare_data.py`. | Removes `artifacts/`, `fine-tuning-dataset/` |
