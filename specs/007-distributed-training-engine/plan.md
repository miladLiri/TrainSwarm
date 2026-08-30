# Implementation Plan: Distributed Training Engine

**Branch**: `007-distributed-training-engine` | **Date**: 2026-08-30 | **Spec**: [Distributed Training Engine](spec.md)

**Input**: Feature specification from `/specs/007-distributed-training-engine/spec.md`

## Summary

Implement a modular, extensible Python distributed training engine under `src/distributed_training_engine/` designed to execute local training tasks. The architecture enforces strict decoupling between the generic `TrainingOrchestrator` lifecycle (`validate` -> `prepare` -> `train` -> `save_result`) and training-type specific implementations. The initial supported adapter is `canonical_torch`, which executes single-input/single-output PyTorch 2 exported programs (`.pt2`) over canonical dataset shards (`.pt`), utilizing pluggable registries for optimizers (`AdamW`, `SGD`), schedulers (`ConstantLR`, `LinearLR`, `StepLR`, `ExponentialLR`, `CosineAnnealingLR`), and criteria (`MSELoss`, `L1Loss`, `SmoothL1Loss`, `CrossEntropyLoss`, `BCEWithLogitsLoss`). A comprehensive end-to-end verification harness will be provided under `samples/training_test/`.

---

## Technical Context

**Language/Version**: Python 3.10+ / 3.11+
**Primary Dependencies**: PyTorch 2.x (`torch`, `torch.export`), standard library (`dataclasses`, `typing`, `pathlib`, `logging`, `random`)
**Storage**: Local filesystem working directory (reading input `<checkpoint_version>.pt2` and `<dataset_shard_id>.pt`, writing output `trained_<task_id>.pt2`)
**Testing**: Active execution verification harness (`samples/training_test/setup.py`, `samples/training_test/train.py`, `README.md`) per TrainSwarm Constitution
**Target Platform**: Windows, Linux, macOS (auto-detects CUDA GPU when available, falls back to CPU)
**Project Type**: Python core library / engine package located in `src/distributed_training_engine/`
**Performance Goals**: Sample MLP task executes and converges in < 5 seconds; zero memory leaks across DataLoader iterations
**Constraints**: Single-precision `torch.float32`, immutable input artifacts, no global checkpoint version ownership, zero mock/placeholder implementations
**Scale/Scope**: Local single-node task training engine with polymorphic adapter architecture

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Compliance Status | Rationale / Evidence |
| :--- | :--- | :--- | :--- |
| **I. Semi-Distributed Architecture** | Data plane separation; local state only | **PASS** | `TrainingOrchestrator` executes local tasks only; no coordinator/aggregator state or peer networking is owned by this engine. |
| **II. Language & Runtime Strictness** | Python + PyTorch for trainer data plane | **PASS** | Implemented purely in Python using PyTorch 2.x (`torch.export`, autograd). |
| **III. Explicit Contracts & Boundaries** | DTOs for boundaries; explicit schemas | **PASS** | `TrainingTask`, `CanonicalTorchTrainingConfig`, typed parameter DTOs, and `TrainingResult` strictly define boundaries. |
| **IV. Engineering Standards (MVP)** | Simple, explicit code; observable logging | **PASS** | Modular structure, zero premature abstractions, comprehensive structured logging across all lifecycle milestones. |
| **V. Prohibitions (Zero Mocks / No Tests)** | No mock classes, no test frameworks; active verification | **PASS** | Zero mocks/stubs; runnable verification scripts (`samples/training_test/setup.py` & `train.py`) execute real autograd training. |
| **VI. Real Functional Implementations** | Spec-complete real operational logic | **PASS** | Real PyTorch 2 export loading, real `DataLoader`, autograd gradient backward, optimizer update, and artifact saving. |
| **VII. Verification & Compilability** | Compilability & active execution quality gate | **PASS** | Code will be verified via `python -m py_compile` and executed directly via `train.py`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/007-distributed-training-engine/
├── spec.md                  # Feature specification
├── plan.md                  # Implementation plan
├── research.md              # Phase 0 research findings
├── data-model.md            # Phase 1 domain entities & DTOs
├── quickstart.md            # Phase 1 verification guide
├── contracts/               # Phase 1 contract schemas
│   ├── training-task-schema.json
│   ├── training-result-schema.json
│   └── adapter-api.md
└── checklists/
    └── requirements.md      # Specification quality checklist
```

### Source Code Layout

```text
src/
└── distributed_training_engine/
    ├── __init__.py
    └── training/
        ├── __init__.py
        ├── model_type.py
        ├── training_task_model.py
        ├── training_result.py
        ├── training_adapter.py
        ├── training_adapter_registry.py
        ├── training_orchestrator.py
        │
        └── training_adapters/
            ├── __init__.py
            └── canonical_torch/
                ├── __init__.py
                ├── canonical_torch_config.py
                ├── canonical_torch_adapter.py
                ├── optimizer_registry.py
                ├── scheduler_registry.py
                ├── criterion_registry.py
                │
                ├── optimizers/
                │   ├── __init__.py
                │   ├── adamw_parameters.py
                │   └── sgd_parameters.py
                │
                ├── schedulers/
                │   ├── __init__.py
                │   ├── constant_lr_parameters.py
                │   ├── linear_lr_parameters.py
                │   ├── step_lr_parameters.py
                │   ├── exponential_lr_parameters.py
                │   └── cosine_annealing_lr_parameters.py
                │
                └── criteria/
                    ├── __init__.py
                    ├── mse_loss_parameters.py
                    ├── l1_loss_parameters.py
                    ├── smooth_l1_loss_parameters.py
                    ├── cross_entropy_loss_parameters.py
                    └── bce_with_logits_loss_parameters.py

samples/
└── training_test/
    ├── README.md
    ├── setup.py
    └── train.py
```

**Structure Decision**: Standard Python modular package under `src/distributed_training_engine/` adhering strictly to section 29 of the specification, paired with a sample verification suite in `samples/training_test/`.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| *None* | N/A | Fully compliant with TrainSwarm Constitution. |
