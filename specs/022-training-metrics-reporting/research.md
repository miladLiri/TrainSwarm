# Architecture Research & Technical Decisions: Unified Training Metrics & Task Lifecycle Reporting

**Feature Branch**: `022-training-metrics-reporting`
**Spec Reference**: [spec.md](./spec.md)
**Status**: Completed

---

## 1. Overview & Research Scope

This feature establishes parity between single-node reference training benchmarks (`samples/comaparision_test/train_single_node.py`) and the distributed training engine's `canonical_causal_decoder` adapter, introduces granular stage timing in the Trainer coordinator command handler (`StartTrainingHandler`), provides unified visual inspection tooling, and supplies an automated zero-argument verification harness in `samples/training_report_test`.

---

## 2. Research Decisions & Technical Tradeoffs

### Decision 1: Metric Callback Architecture & Parity with `train_single_node.py`

- **Context**: In `samples/comaparision_test/train_single_node.py`, the training loop uses a custom `TinyStoriesTrainer(Trainer)` that overrides `compute_loss()` to calculate token-level classification accuracy and track total token throughput across steps. Additionally, `MetricsTrackingCallback(TrainerCallback)` intercepts `on_step_end` to compute windowed average loss, accuracy, and perplexity ($e^{\min(\text{loss}, 20)}$), printing terminal progress and writing metrics to disk.
- **Decision**: In `src/distributed_training_engine/adapters/canonical_causal_decoder/training/canonical_causal_decoder_trainer.py`, introduce an internal `_CanonicalCausalDecoderTrainer(Trainer)` subclass and `_MetricsTrackingCallback(TrainerCallback)`.
  - Override `compute_loss(model, inputs, return_outputs=False, **kwargs)`:
    - During training, compute token predictions using `shift_logits.argmax(dim=-1)` compared to `shift_labels` (where labels != -100).
    - Accumulate token counts and batch accuracy in running window deques/lists.
  - In `_MetricsTrackingCallback`:
    - Every `logging_steps` (configured from `config` or defaulted to 5), calculate rolling metrics: `loss`, `perplexity`, `accuracy`, `learning_rate`, `tokens_per_sec`, `total_tokens`, `elapsed_sec`, `vram_allocated_mb`.
    - Print formatted stdout logs matching:
      `Step {step:4d}/{total_steps} (Ep {epoch:.2f}/{num_epochs}) | Loss: {loss:.4f} | PPL: {ppl:6.2f} | Acc: {acc:5.2f}% | Speed: {tok_s:5.0f} tok/s | Time: {elapsed:5.1f}s [*BEST*]`
    - Persist updated JSON metrics on disk atomically.
- **Constraints Maintained**: The existing logic for parsing `CanonicalCausalDecoderTrainingConfig` and converting it into Hugging Face `TrainingArguments` remains 100% intact.
- **Clarification Applied (from spec)**: Intermediate checkpoint weights directories will **not** be saved to disk on workers (saving full weights to disk is omitted to conserve I/O in distributed environments); best step/loss/accuracy are recorded in `training_metrics.json` and terminal logs.
- **Alternatives Considered**:
  - *Standard Hugging Face `evaluate()` callback*: Rejected because causal LM evaluation during training adds substantial overhead, whereas computing accuracy on shifted logits in `compute_loss` during the forward pass costs negligible time and exactly mirrors `train_single_node.py`.

---

### Decision 2: Atomic Real-Time Metric Persistence (`training_metrics.json`)

- **Context**: Visualizers like `show_single_node_train_result.py` read `training_metrics.json` during or immediately following training runs. If a process writes to `training_metrics.json` directly with standard file writes, concurrent readers or abrupt interruptions can encounter partial or corrupt JSON.
- **Decision**: Persist metrics via an atomic file replacement strategy:
  1. Write serialized JSON to a temporary file: `training_metrics.json.tmp`.
  2. Flush and close the file.
  3. Perform `os.replace("training_metrics.json.tmp", "training_metrics.json")`.
- **Schema Alignment**:
  - `metadata`: Contains `model_name`, `device`, `device_name`, `total_parameters`, `batch_size`, `grad_accum_steps`, `effective_batch_size`, `learning_rate`, `max_seq_length`, `total_planned_steps`, `num_epochs`, `steps_per_epoch`, `start_time`.
  - `steps`: Array of records (`step`, `epoch`, `loss`, `perplexity`, `accuracy`, `learning_rate`, `tokens_per_sec`, `total_tokens`, `elapsed_sec`, `vram_allocated_mb`).
  - `summary`: Populated at completion with `status`, `total_steps`, `total_epochs_trained`, `total_elapsed_sec`, `total_tokens_processed`, `average_tokens_per_sec`, initial/final/best values for `loss`, `perplexity`, and `accuracy`, and `best_step` / `best_epoch`.
- **Alternatives Considered**:
  - *Append-only JSON Lines (`.jsonl`)*: Rejected because `show_single_node_train_result.py` expects a structured JSON document with metadata, steps, and summary dictionaries.

---

### Decision 3: Task Lifecycle Timing Architecture (`StartTrainingHandler`)

- **Context**: In `src/Trainer/application/coordinator_commands/start_training/handler.py`, the Trainer handles incoming tasks through 6 sequential steps:
  1. Querying training task specification over P2P.
  2. Checking local cache and streaming base model over P2P.
  3. Streaming dataset shard over P2P.
  4. Executing local training via PyTorch engine.
  5. Transmitting weight delta to Client over P2P.
  6. Cleaning up ephemeral artifacts.
- **Decision**: Implement a `TaskLifecycleRecorder` helper class to track stage transitions cleanly:
  - Each stage is tracked using a start timestamp (`time.time()`), end timestamp, and computed duration in seconds (`round(end_time - start_time, 4)`).
  - Maintains state dictionary:
    ```json
    {
      "task_metadata": {
        "client_node_id": "...",
        "model_id": "...",
        "model_version": "...",
        "data_set_id": "...",
        "shard_id": "...",
        "status": "COMPLETED",
        "total_elapsed_sec": 12.345,
        "start_time": "2026-10-27T15:00:00Z",
        "end_time": "2026-10-27T15:00:12Z"
      },
      "steps": [
        {
          "step_number": 1,
          "name": "Query Training Task Specification",
          "status": "COMPLETED",
          "start_time": "...",
          "end_time": "...",
          "duration_sec": 0.12,
          "details": "..."
        },
        ...
      ]
    }
    ```
  - In case of an exception at any stage:
    - Mark the failing step status as `"FAILED"`.
    - Record error message and stack trace excerpt in the step details.
    - Set overall `task_metadata.status` to `"FAILED"`.
    - Save the lifecycle report to disk (`training_lifecycle_metrics.json`) inside the `finally` block before re-raising.
- **Alternatives Considered**:
  - *Python `logging` timestamps only*: Insufficient for automated parsing and visual rendering in user inspection tools.

---

### Decision 4: Unified Terminal Inspection Tool (`show_training_task_result.py`)

- **Context**: Users currently use `show_single_node_train_result.py` to inspect training runs. A new tool is required in `samples/comaparision_test/` that can display both training metrics and the 6-stage lifecycle execution metrics.
- **Decision**: Create `samples/comaparision_test/show_training_task_result.py` using `rich`:
  - Path Resolution Hierarchy:
    - Supports CLI arguments: `python show_training_task_result.py [metrics_path] [lifecycle_path]`.
    - Fallback candidates: Checks `./`, `./work/`, and `./single_node_finetuning/` for `training_metrics.json` and `training_lifecycle_metrics.json`.
  - Resilience:
    - If `training_lifecycle_metrics.json` is present: renders task metadata panel and a stage duration table showing step number, name, duration (formatted in human-readable seconds/minutes), percentage of total time, and status.
    - If `training_metrics.json` is present: renders run overview, loss/perplexity/accuracy deltas, step history table, and ASCII line charts.
    - If one file is missing: cleanly prints an alert panel (e.g. `[yellow]Notice: Lifecycle metrics file not found. Showing training metrics only.[/yellow]`) without crashing.
    - If both files are missing: displays a helpful error panel and exits cleanly with return code 0.
- **Decision on `show_single_node_train_result.py` Enhancements**:
  - Update `show_single_node_train_result.py` to accept `sys.argv[1]` for the metrics file path, falling back to check `./training_metrics.json` and `./single_node_finetuning/training_metrics.json`.

---

### Decision 5: Test Harness Architecture (`samples/training_report_test`)

- **Context**: A standalone sample suite must be provided under `samples/training_report_test` that exercises dataset preparation, model archiving, minimal local training with the adapter, report generation, and clean resets, with zero arguments required for any script.
- **Decision**: Structure `samples/training_report_test` as follows:
  1. `download_artifacts.py`: Replicated from `samples/comaparision_test/download_artifacts.py`, downloads TinyStories-1M model weights and dataset sample.
  2. `prepare_data.py`:
     - Reads raw dataset (from `fine-tuning-dataset/train.json` or `artifacts/dataset/data00.json`).
     - Tokenizes a small slice of instruction story pairs (e.g., 50 samples) with sequence length 128, applying label masking (`labels = -100` for prompt tokens).
     - Saves tokenized tensors dictionary (`input_ids`, `attention_mask`, `labels`) to `artifacts/tinystories_train.pt`.
     - Packages `artifacts/tinystories_base.tar.gz` containing `model/` and `tokenizer/` directories.
     - Writes `artifacts/causal_decoder_config.json` containing calibrated training hyperparameters (e.g., batch_size=2, epochs=1, max_steps=4, learning_rate=1e-4).
  3. `train.py`:
     - Sets up working directory `work/`.
     - Constructs a `TrainingTask` envelope referencing the prepared model archive and dataset shard.
     - Runs the training session locally using `distributed_training_engine.training.TrainingOrchestrator` (or `CanonicalCausalDecoderTrainer`).
     - Outputs `training_metrics.json` and parameter delta artifact in `work/` (and/or current directory).
  4. `show_report.py`:
     - Discovers `training_metrics.json` and invokes `show_single_node_train_result.py` (via module import or subprocess).
     - Also prints task report via `show_training_task_result.py`.
  5. `clean.py`:
     - Deletes `work/`, `single_node_finetuning/`, `training_metrics.json`, plot files, and intermediate training outputs.
  6. `clean_artifacts.py`:
     - Deletes `artifacts/` and `fine-tuning-dataset/`.

---

## 3. Summary of Research Decisions

| Area | Decision | Primary Benefit |
|---|---|---|
| **Adapter Training** | Subclass `Trainer` and implement `MetricsTrackingCallback` | Exact accuracy, loss, and token throughput parity with `train_single_node.py` |
| **Worker Storage** | Track best metrics in JSON; do not write full model checkpoint weights to disk | Eliminates heavy disk I/O on distributed workers |
| **Lifecycle Timing** | Wrap `StartTrainingHandler` with `TaskLifecycleRecorder` | Millisecond-level tracking across all 6 handler stages with failure capture |
| **Viewer Usability** | Multi-path resolution with resilient fallback for missing reports | Zero-crash execution whether viewing training runs, cluster tasks, or both |
| **Test Suite** | Zero-argument scripts in `samples/training_report_test` | Fast, automated E2E validation without multi-daemon cluster boot |
