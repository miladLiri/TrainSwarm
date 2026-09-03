# Implementation Plan: Distributed Training Engine — Aggregation Module

**Branch**: `010-distributed-training-aggregation` | **Date**: 2026-09-03 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/010-distributed-training-aggregation/spec.md)

**Input**: Feature specification from `/specs/010-distributed-training-aggregation/spec.md`

## Summary

Implement the model-agnostic aggregation subsystem within `distributed_training_engine` to collect completed trainer updates for a federated training round, load and validate SafeTensors parameter deltas, perform weighted Federated Averaging, and atomically create and publish the next model version while guaranteeing strict base model immutability. The architecture provides an abstract `AggregatorAdapter` base class, a dynamic `AggregatorAdapterRegistry`, and an `AggregationOrchestrator` lifecycle coordinator, backed by a concrete `CanonicalTorchAggregator` that handles PyTorch 2 `.pt2` ExportedProgram loading, tensor-wise weighted FedAvg with integer buffer rounding, and atomic temporary-file serialization without modifying existing training or partitioning behavior. In addition, deliver a complete, runnable, zero-mock end-to-end distributed training sample suite in `samples/distributed_training_test/` covering setup, partitioning, 5-worker parallel training, aggregation, and loss improvement verification.

## Technical Context

**Language/Version**: Python 3.10+ (PyTorch 2.x)

**Primary Dependencies**: `torch` (PyTorch 2.x with `torch.export`), `safetensors` (`safetensors.torch`), Python standard library (`pathlib`, `logging`, `typing`, `dataclasses`, `enum`, `abc`, `uuid`, `os`, `concurrent.futures`)

**Storage**: Local filesystem directories (`.pt2` PyTorch 2 ExportedProgram files for base and aggregated models, `.safetensors` files for parameter delta updates, `.pt` files for datasets and shards)

**Testing**: Active execution and standalone CLI validation scripts (`samples/distributed_training_test/setup.py`, `partition.py`, `train.py`, `aggregate.py`, `verify.py`, and interactive Python verification) per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux, macOS (Cross-platform Python execution)

**Project Type**: Data Plane Distributed Training Engine Library & CLI Verification Tooling

**Performance Goals**: Aggregation computation latency < 500ms for standard neural network architectures; memory footprint bounded to base model weights + delta tensors; single-pass weighted averaging across model parameters.

**Constraints**: Strict base model artifact immutability; strict conflict rejection if the target model version already exists (`ExistingModelVersionConflictError`); atomic temporary-file replacement on the same filesystem volume (`os.replace`); zero mocks or stubs.

**Scale/Scope**: Implementation of 7 aggregation core files, 1 concrete PyTorch aggregator adapter, package re-exports, 6 sample test suite scripts in `samples/distributed_training_test/`, and verification against existing training/partitioning workloads.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. The aggregation subsystem resides entirely within the Data Plane (`Client + Aggregator`), operating on local delta files and model checkpoints. It maintains zero dependency on Control Plane services (`Coordinator` or `Bootstrap`) and does not manage global cluster session state.
- **II. Language, Runtime, and Application Strictness**: PASS. Implemented strictly in Python using PyTorch as the designated training and model framework and SafeTensors for delta serialization.
- **III. Explicit Contracts & Boundaries**: PASS. `AggregationRequest`, `ModelUpdate`, and `AggregationResult` define explicit, strongly typed DTO boundaries with unambiguous validation rules.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Code is direct, modular, and explicit without speculative layers; descriptive structured logs are emitted at each phase; clear exception hierarchies.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero fake routines, zero test frameworks (using real runnable sample scripts for active verification), zero crypto, zero RCE.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Real SafeTensors delta loading, real PyTorch ExportedProgram loading/saving (`torch.export`), real tensor-wise weighted FedAvg computation, real atomic file operations, and a real 5-worker parallel training test suite.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Active verification using `samples/distributed_training_test/` confirms zero compilation/syntax errors, clean multi-process execution, and mathematical loss reduction post-aggregation.

## Project Structure

### Documentation (this feature)

```text
specs/010-distributed-training-aggregation/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model & state machine
├── quickstart.md        # Phase 1 verification guide
├── contracts/           # Phase 1 interface contracts
│   ├── aggregation-request.schema.json
│   ├── aggregation-result.schema.json
│   └── aggregator-adapter-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 task decomposition (/speckit-tasks output - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/distributed_training_engine/
├── __init__.py                                       # Re-exports training, partitioning, aggregation, and model_type
├── model_type.py                                     # ModelType enum (CANONICAL_TORCH)
│
├── training/                                         # Training module
│   ├── __init__.py
│   ├── exceptions.py
│   ├── trainer_adapter_registery.py
│   ├── trainer_adapter.py
│   ├── training_task_model.py
│   ├── training_result.py
│   └── training_orchecstrator.py
│
├── partitioning/                                     # Partitioning module
│   ├── __init__.py
│   ├── exceptions.py
│   ├── partitioner_adapter_registery.py
│   ├── partitioner_adapter.py
│   ├── partitioning_request.py
│   ├── sampling_result.py
│   ├── partitioning_result.py
│   └── partitioning_orchecstrator.py
│
├── aggregation/                                      # Aggregation module (to implement)
│   ├── __init__.py
│   ├── exceptions.py                                 # Aggregation-specific exception hierarchy
│   ├── aggregator_adapter_registery.py               # Aggregator adapter registry mapping ModelType
│   ├── aggregator_adapter.py                         # Model-agnostic AggregatorAdapter ABC
│   ├── aggregation_request.py                        # AggregationRequest & ModelUpdate DTOs
│   ├── aggregation_result.py                         # AggregationResult DTO
│   └── aggregation_orchestrator.py                   # AggregationOrchestrator coordinator
│
└── adapters/
    └── canonical_torch/
        ├── training/                                 # PyTorch trainer adapter
        │   ├── __init__.py
        │   ├── canonical_torch_trainer.py
        │   ├── canonical_torch_config.py
        │   ├── criterion_registry.py
        │   ├── optimizer_registry.py
        │   ├── scheduler_registry.py
        │   ├── criteria/
        │   ├── optimizers/
        │   └── schedulers/
        │
        ├── partitioning/                             # PyTorch dataset partitioner adapter
        │   ├── __init__.py
        │   └── canonical_torch_partitioner.py
        │
        └── aggragation/                              # PyTorch aggregator adapter (to implement)
            ├── __init__.py
            └── canonical_torch_aggregator.py         # CanonicalTorchAggregator implementation

samples/
└── distributed_training_test/                        # Runnable zero-mock verification suite (to implement)
    ├── setup.py                                      # Generates CNN model_0.pt2 and dataset.pt
    ├── partition.py                                  # Partitions dataset into 5 shards of 10 samples
    ├── train.py                                      # Trains 5 models in parallel producing 5 deltas
    ├── aggregate.py                                  # Runs AggregationOrchestrator to produce model_1.pt2
    ├── verify.py                                     # Evaluates and compares loss between model_0 and model_1
    └── README.md                                     # Execution instructions and architecture notes
```

**Structure Decision**: Implements the aggregation subsystem directly within the required `aggregation/` and `adapters/canonical_torch/aggragation/` folders, preserving existing module names and spellings (`aggregator_adapter_registery.py`, `aggregation_orchestrator.py`, `adapters/canonical_torch/aggragation/canonical_torch_aggregator.py`). Delivers a full end-to-end runnable sample suite in `samples/distributed_training_test/` satisfying all acceptance criteria and constitutional verification mandates.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No violations. Design strictly complies with all constitutional principles.)*
