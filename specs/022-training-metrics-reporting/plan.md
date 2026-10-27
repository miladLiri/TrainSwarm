# Implementation Plan: Unified Training Metrics & Task Lifecycle Reporting

**Branch**: `022-training-metrics-reporting` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-training-metrics-reporting/spec.md`

---

## Summary

This feature unifies training metrics collection and lifecycle duration reporting across TrainSwarm:
1. **Canonical Causal Decoder Training Parity**: Update `CanonicalCausalDecoderTrainer` in `src/distributed_training_engine/adapters/canonical_causal_decoder/` to compute running token accuracy, perplexity, and throughput matching `samples/comaparision_test/train_single_node.py`, logging steps to stdout and continuously persisting `training_metrics.json` directly readable by `show_single_node_train_result.py`.
2. **Coordinator Command Handler Lifecycle Timing**: Instrument `StartTrainingHandler` at `src/Trainer/application/coordinator_commands/start_training/handler.py` to record execution durations for all 6 stages into `training_lifecycle_metrics.json` with failure and timestamp tracking.
3. **Unified Terminal Inspection Tool**: Implement `show_training_task_result.py` in `samples/comaparision_test/` using `rich` with multi-path resolution and resilient fallbacks for missing reports.
4. **Standalone Verification Harness**: Create `samples/training_report_test/` containing zero-argument scripts (`download_artifacts.py`, `prepare_data.py`, `train.py`, `show_report.py`, `clean.py`, and `clean_artifacts.py`) demonstrating data preparation, quick local adapter training, report display, and resets.

---

## Technical Context

**Language/Version**: Python 3.10+ (distributed training engine, Trainer, comparison tools, and test harness)

**Primary Dependencies**:
- PyTorch & Hugging Face: `torch>=2.2.0`, `transformers>=4.40.0`, `safetensors>=0.4.0`
- Terminal Display & CLI: `rich`
- File & Protocol I/O: Standard library (`json`, `tarfile`, `time`, `pathlib`, `os`, `shutil`)

**Storage**:
- Training Metrics: `training_metrics.json` (atomic replacement via `.tmp`)
- Task Lifecycle Metrics: `training_lifecycle_metrics.json`
- Model Artifacts: `tinystories_base.tar.gz` (or `.gz`) containing `model/` and `tokenizer/`
- Dataset Shards: PyTorch tensor dictionary `.pt` containing `input_ids`, `attention_mask`, `labels`
- Updates: `.safetensors` parameter deltas

**Testing / Verification**: Automated zero-argument execution of `samples/training_report_test/` and Python compilation checks (`python -m py_compile`) per Constitution Principle VII.

**Target Platform**: Windows / Linux / macOS native execution.

**Project Type**: Engine Adapter Enhancement, Coordinator Command Handler Observability, Inspection Tooling, and Test Suite.

**Performance Goals**:
- Adapter step log formatting and token accuracy computation overhead < 2ms per forward step.
- Task lifecycle timing recorded with millisecond precision without blocking P2P operations.
- `show_training_task_result.py` and `show_single_node_train_result.py` render in < 3 seconds.
- Standalone `samples/training_report_test/train.py` completes in < 30 seconds on CPU.

**Constraints**:
- Strictly preserve existing configuration deserialization and mapping from `CanonicalCausalDecoderTrainingConfig` to `TrainingArguments`.
- Do not save intermediate model checkpoint weights to worker disk during training (track best metrics in JSON only).
- All scripts in `samples/training_report_test` must execute with zero required command-line arguments.
- Zero mocks per Constitution Principle VI.

**Scale/Scope**:
- `src/distributed_training_engine/adapters/canonical_causal_decoder/training/canonical_causal_decoder_trainer.py`
- `src/Trainer/application/coordinator_commands/start_training/handler.py`
- `samples/comaparision_test/show_single_node_train_result.py`
- `samples/comaparision_test/show_training_task_result.py`
- `samples/training_report_test/` (6 scripts)

---

## Constitution Check

*GATE: Passed before Phase 0 research. Re-checked and confirmed after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control/data plane boundaries | **PASS** | Coordinator remains in control plane; Trainer lifecycle and engine adapter execute strictly in data plane. |
| **II. Language Strictness** | Language boundaries respected | **PASS** | Trainer, engine adapter, and test harnesses implemented in Python. |
| **III. Explicit Contracts** | Versioned contracts & schemas | **PASS** | Formal JSON schemas created in `contracts/training-metrics.schema.json` and `contracts/lifecycle-metrics.schema.json`. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, no bloat | **PASS** | Reuses established `TrainerCallback` and atomic JSON writes; no speculative dependencies. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero stubs | **PASS** | Real functional implementations only; real tensor math and live file writes. |
| **VI. Real Functional Implementations** | Operational integrity | **PASS** | Real model fine-tuning, real metric calculations, and real file lifecycle operations. |
| **VII. Verification & Compilability** | Build and runtime checks | **PASS** | Concrete verification via `py_compile` and runnable test scripts in `samples/training_report_test/`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/022-training-metrics-reporting/
├── spec.md                              # Feature specification
├── plan.md                              # This implementation plan
├── research.md                          # Phase 0 architecture research and decisions
├── data-model.md                        # Phase 1 data model and entity definitions
├── quickstart.md                        # Phase 1 verification and run guide
├── contracts/                           # Phase 1 interface and schema contracts
│   ├── training-metrics.schema.json
│   ├── lifecycle-metrics.schema.json
│   └── cli-presentation-contracts.md
└── checklists/
    └── requirements.md                  # Spec quality checklist
```

### Source Code Layout

```text
src/
├── distributed_training_engine/
│   └── adapters/
│       └── canonical_causal_decoder/
│           └── training/
│               └── canonical_causal_decoder_trainer.py     # Enhance training loop & MetricsTrackingCallback
└── Trainer/
    └── application/
        └── coordinator_commands/
            └── start_training/
                └── handler.py                              # Integrate TaskLifecycleRecorder & JSON export

samples/
├── comaparision_test/
│   ├── show_single_node_train_result.py                    # Add optional CLI path argument & fallback search
│   └── show_training_task_result.py                        # New: unified inspection tool with resilient fallback
└── training_report_test/                                    # New: self-contained zero-argument test suite
    ├── download_artifacts.py                               # Copied from comaparision_test
    ├── prepare_data.py                                     # Formats .pt shard, packages .tar.gz, writes config
    ├── train.py                                            # Minimal local training run via engine
    ├── show_report.py                                      # Invokes report viewer
    ├── clean.py                                            # Removes training & report outputs
    └── clean_artifacts.py                                  # Removes downloaded & prepared assets
```

---

## Complexity Tracking

> Zero constitution violations; no complexity justifications needed.
