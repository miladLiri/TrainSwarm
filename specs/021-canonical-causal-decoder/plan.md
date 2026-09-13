# Implementation Plan: Canonical Causal Decoder Model

**Branch**: `021-canonical-causal-decoder` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-canonical-causal-decoder/spec.md`

---

## Summary

Implement the **Canonical Causal Decoder Model** adapter suite for the distributed training engine, enabling fine-tuning, sharding, and aggregation of Hugging Face causal language model transformer decoders across TrainSwarm clusters:
1. **Engine Core Registrations**: Register `ModelType.CANONICAL_CAUSAL_DECODER = "canonical_causal_decoder"` and map adapter implementations in `TrainerAdapterRegistery`, `PartitionerAdapterRegistery`, and `AggregatorAdapterRegistery`.
2. **Adapter Suite Implementation** (`src/distributed_training_engine/adapters/canonical_causal_decoder/`):
   - `training/`: `CanonicalCausalDecoderTrainer` implementing the 4-phase lifecycle (`validate`, `prepare`, `train`, `save_result`) using Hugging Face `AutoModelForCausalLM`, `AutoTokenizer`, and `Trainer`, with parameter delta extraction serialized to `.safetensors`. Strongly-typed configuration parser in `canonical_causal_decoder_config.py`.
   - `partitioning/`: `CanonicalCausalDecoderPartitioner` providing `CreateSample()` and `CreateShards()` for `.pt` dictionary datasets with `input_ids`, `attention_mask`, and `labels`.
   - `aggregation/`: `CanonicalCausalDecoderAggregator` providing `LoadDelta()`, `ValidateDelta()`, architecture-agnostic sample-weighted Federated Averaging ($\Delta W_{\text{avg}} = \sum \frac{n_i}{N} \Delta W_i$), and atomic `.gz` version publishing.
3. **Open-Closed Principle Compliance**: All model-agnostic engine orchestrators, data models, and abstractions outside of `adapters/` and presentation layers remain 100% untouched.
4. **Presentation Adaptations**:
   - Client GUI Submit Training tab dynamically prompts for `model_type` first, adjusting file selectors (`.gz`/`.tar.gz` model archive, `.pt` dataset) and training parameter inputs (`CanonicalCausalDecoderTrainingConfig`).
   - Client Console UI CLI `submit-training` prioritizes `--model-type`.
5. **End-to-End Verification Sample**: Create `samples/canonical_causal_decoder_training_test/` (`setup.py`, `submit.py`, `verify.py`, `clean.py`) running Coordinator, Relay, Client, and 2 Trainers natively on TinyStories-1M, measuring perplexity improvement.

---

## Technical Context

**Language/Version**: Python 3.10+ (Client, Trainer, Engine), .NET 10 (Coordinator), Go 1.22+ (Relay, Sidecar)

**Primary Dependencies**:
- Distributed Training Engine & Trainer: `torch>=2.2.0`, `transformers>=4.40.0`, `safetensors>=0.4.0`, `datasets` (for sample generation).
- Client Presentation: PyQt6 (GUI), `argparse` (CLI), `tarfile` (standard library).
- Cluster Communication: `grpcio`, `protobuf`, `requests`.

**Storage**:
- Models: Compressed `.gz` or `.tar.gz` archive containing `model/` (Hugging Face transformer weights) and `tokenizer/` (Hugging Face tokenizer assets).
- Datasets & Shards: PyTorch `.pt` dictionary tensor files containing `input_ids`, `attention_mask`, `labels`.
- Updates: `.safetensors` parameter delta files.
- Metadata: Client local SQLite database (`training.db`).

**Testing / Verification**: Automated live command-line test harness in `samples/canonical_causal_decoder_training_test/` using native host processes on real TinyStories-1M data (zero mocks per Constitution Principles V, VI, & VII).

**Target Platform**: Windows / Linux / macOS native execution.

**Project Type**: Distributed System: Engine Adapter Suite, Client GUI/CLI presentation layer, and Native E2E Test Suite.

**Performance Goals**:
- Trainer baseline parameter snapshot executed on CPU in < 500ms for lightweight transformer models.
- Parameter delta computation and `.safetensors` serialization executed in < 1 second.
- Sample-weighted Federated Averaging across updates completed in < 2 seconds.
- Client GUI dynamically adapts form layouts within 100ms of model type selection.

**Constraints**:
- Strict adherence to Open-Closed Principle: Zero changes to engine orchestrators or model-agnostic core outside of `adapters/`.
- Zero mocks, zero unit tests; verification via real executables and validation loss/perplexity evaluation.
- Atomic new version archive serialization to prevent publishing corrupted or partial model artifacts.

**Scale/Scope**: 4 primary areas: Adapter suite (`training`, `partitioning`, `aggregation`), engine registries & enum, Client presentation (GUI & CLI), and `samples/canonical_causal_decoder_training_test/`.

---

## Constitution Check

*GATE: Passed before Phase 0 research. Re-checked and confirmed after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control/data plane separation | **PASS** | Coordinator remains strictly in the control plane (task scheduling and assignment); never handles model archives, shards, or deltas. Client owns training sessions and aggregation. |
| **II. Language Strictness** | .NET for Coordinator, Python for Client/Trainer | **PASS** | Adapter suite and presentation changes are entirely Python; no language boundaries violated. |
| **III. Explicit Contracts** | Versioned contracts & DTOs | **PASS** | Formal contracts established in `contracts/adapter-contracts.md` and `contracts/training-config.schema.json`. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, clear | **PASS** | Direct delegation to standard Hugging Face `Trainer` and `safetensors`; zero speculative frameworks. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero crypto | **PASS** | Real functional implementations only; E2E multi-service test harness in `samples/canonical_causal_decoder_training_test/`. |
| **VI. Real Functional Implementations** | Real HF models, real datasets | **PASS** | Actual `TinyStories-1M` weights, real PyTorch tokenized tensors, real `.safetensors` delta math. |
| **VII. Verification & Compilability** | Build & executable correctness | **PASS** | Mandatory validation via `python -m py_compile`, active E2E execution (`setup.py`, `submit.py`, `verify.py`), and perplexity assertion. |

---

## Project Structure

### Documentation (this feature)

```text
specs/021-canonical-causal-decoder/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architecture research and decisions
├── data-model.md        # Phase 1 data model and entity definitions
├── quickstart.md        # Phase 1 verification and run guide
├── contracts/           # Phase 1 interface and schema contracts
│   ├── adapter-contracts.md
│   ├── training-config.schema.json
│   └── cli-presentation-contract.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Layout

```text
src/distributed_training_engine/
├── model_type.py                                              # Add CANONICAL_CAUSAL_DECODER = "canonical_causal_decoder"
├── training/trainer_adapter_registery.py                      # Register CanonicalCausalDecoderTrainer
├── partitioning/partitioner_adapter_registery.py              # Register CanonicalCausalDecoderPartitioner
├── aggregation/aggregator_adapter_registery.py                # Register CanonicalCausalDecoderAggregator
└── adapters/
    └── canonical_causal_decoder/
        ├── __init__.py                                        # Package exports
        ├── training/
        │   ├── __init__.py
        │   ├── canonical_causal_decoder_config.py             # Strongly-typed config parser for HF TrainingArguments
        │   └── canonical_causal_decoder_trainer.py            # TrainerAdapter (validate, prepare, train, save_result)
        ├── partitioning/
        │   ├── __init__.py
        │   └── canonical_causal_decoder_partitioner.py        # PartitionerAdapter (CreateSample, CreateShards)
        └── aggregation/
            ├── __init__.py
            └── canonical_causal_decoder_aggregator.py         # AggregatorAdapter (LoadDelta, ValidateDelta, FedAvg, CreateNewVersion)

src/Client/presentation/
├── gui/
│   └── main_window.py                                         # Dynamic Model Engine Type selection & HF parameter panel
└── console_ui.py                                              # CLI submit-training --model-type support

samples/canonical_causal_decoder_training_test/
├── setup.py                                                   # Spawns services natively, downloads TinyStories-1M, prepares .gz & .pt
├── submit.py                                                  # Submits training, runs 2 trainers, aggregates v1 model
├── verify.py                                                  # Evaluates validation loss and perplexity on v0 and v1
└── clean.py                                                   # Terminates background processes and cleans test directory
```

---

## Complexity Tracking

> **Zero constitution violations. No complexity exceptions required.**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | N/A |
