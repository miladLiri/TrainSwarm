# Implementation Plan: Distributed Training Engine — Partitioning Module and Folder Structure

**Branch**: `009-dataset-partitioning` | **Date**: 2026-09-03 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/009-dataset-partitioning/spec.md)

**Input**: Feature specification from `/specs/009-dataset-partitioning/spec.md`

## Summary

Refactor the `distributed_training_engine` to introduce a dedicated `partitioning` module responsible for extracting representative dataset samples and slicing raw datasets into discrete, fixed-size training shards by sample count. Reorganize the package layout into `model_type.py`, `training/`, `aggregation/` (placeholder scaffolding), `partitioning/`, and `adapters/canonical_torch/` (`training/`, `aggragation/`, `partitioning/`). The architecture provides a model-agnostic `PartitionerAdapter` abstraction, a dynamic `PartitionerAdapterRegistry`, and a `PartitioningOrchestrator` workflow coordinator, backed by a concrete `CanonicalTorchPartitioner` that writes UUID-named shards (`<datasetId>_<shardId>.pt`), preserves remainder shards, and strictly prevents collisions on non-empty output directories while maintaining 100% backward-compatible execution for existing training workloads.

## Technical Context

**Language/Version**: Python 3.10+ (PyTorch 2.x)

**Primary Dependencies**: `torch` (PyTorch 2.x), Python standard library (`pathlib`, `uuid`, `logging`, `typing`, `dataclasses`, `enum`, `abc`)

**Storage**: Local filesystem directories (read-only input `.pt` datasets, output `<datasetId>_<shardId>.pt` serialized tensor shards, output `<datasetId>_sample.pt` representative sample artifacts)

**Testing**: Active execution and standalone CLI validation scripts (`samples/training_test/setup.py`, `samples/training_test/train.py`, `samples/training_test/verify.py`, interactive Python verification) per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux, macOS (Cross-platform Python execution)

**Project Type**: Data Plane Distributed Training Engine Library & CLI Verification Tooling

**Performance Goals**: Partitioning overhead < 100ms for standard dataset sizes; zero-copy tensor slicing via PyTorch views prior to serialization; 100% sample retention with zero duplicate samples.

**Constraints**: Strict input dataset immutability; strict empty-directory collision detection for shard output directories (`ExistingShardConflictError`); atomic sample file replacement; zero mocks or stubs.

**Scale/Scope**: Reorganization of `src/distributed_training_engine/`, implementation of 7 partitioning core files, 1 concrete PyTorch adapter, scaffolding for aggregation, and verification against existing sample workloads.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. The partitioning subsystem operates strictly within the data plane (Client / Trainer dataset preparation). It maintains zero dependency on control-plane services (`Coordinator` or `Bootstrap`) and does not own or distribute global session state.
- **II. Language, Runtime, and Application Strictness**: PASS. Implemented exclusively in Python using PyTorch as the designated training data format.
- **III. Explicit Contracts & Boundaries**: PASS. `PartitioningRequest`, `SamplingResult`, and `PartitioningResult` define strongly typed DTO boundaries with unambiguous validation rules.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Code is direct, modular, and explicit without speculative layers; descriptive structured logs are emitted at each phase; clear exception hierarchies.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero fake routines, zero test frameworks (using real runnable scripts for active verification), zero crypto, zero RCE.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Real tensor loading (`torch.load`), deterministic sample slicing, real shard persistence (`torch.save`), real UUID generation, and real filesystem conflict checks.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Active verification using `samples/training_test/` confirms zero compilation/syntax errors and 100% functional correctness post-reorganization.

## Project Structure

### Documentation (this feature)

```text
specs/009-dataset-partitioning/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model & state machine
├── quickstart.md        # Phase 1 verification guide
├── contracts/           # Phase 1 interface contracts
│   ├── partitioning-request.schema.json
│   ├── partitioning-result.schema.json
│   ├── sampling-result.schema.json
│   └── partitioner-adapter-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 task decomposition (/speckit-tasks output - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/distributed_training_engine/
├── __init__.py                                       # Re-exports training, partitioning, and model_type symbols
├── model_type.py                                     # ModelType enum (moved from training/)
│
├── training/                                         # Existing training module (reorganized)
│   ├── __init__.py
│   ├── exceptions.py
│   ├── trainer_adapter_registery.py                  # Renamed from training_adapter_registry.py
│   ├── trainer_adapter.py                            # Renamed from training_adapter.py
│   ├── training_task_model.py
│   ├── training_result.py
│   └── training_orchecstrator.py                     # Renamed from training_orchestrator.py
│
├── aggregation/                                      # Scaffolding placeholders (blank for future implementation)
│   ├── __init__.py
│   ├── exceptions.py
│   ├── aggregator_adapter_registery.py
│   ├── aggregator_adapter.py
│   ├── aggregation_request.py
│   ├── aggregation_result.py
│   └── aggregation_orchecstrator.py
│
├── partitioning/                                     # Dedicated partitioning module
│   ├── __init__.py
│   ├── exceptions.py                                 # Partitioning-specific exception hierarchy
│   ├── partitioner_adapter_registery.py              # Partitioner adapter registry mapping ModelType
│   ├── partitioner_adapter.py                        # Model-agnostic PartitionerAdapter ABC
│   ├── partitioning_request.py                       # PartitioningRequest DTO
│   ├── sampling_result.py                            # SamplingResult DTO
│   ├── partitioning_result.py                        # PartitionedShard & PartitioningResult DTOs
│   └── partitioning_orchecstrator.py                 # PartitioningOrchestrator coordinator
│
└── adapters/
    └── canonical_torch/
        ├── training/                                 # Moved from training/training_adapters/canonical_torch/
        │   ├── __init__.py
        │   ├── canonical_torch_trainer.py            # Renamed from canonical_torch_adapter.py
        │   ├── canonical_torch_config.py
        │   ├── criterion_registry.py
        │   ├── optimizer_registry.py
        │   ├── scheduler_registry.py
        │   ├── criteria/
        │   ├── optimizers/
        │   └── schedulers/
        │
        ├── aggragation/                              # Scaffolding placeholder for future aggregator
        │   ├── __init__.py
        │   └── canonical_torch_aggregator.py
        │
        └── partitioning/                             # Concrete PyTorch dataset partitioner
            ├── __init__.py
            └── canonical_torch_partitioner.py        # CanonicalTorchPartitioner implementation
```

**Structure Decision**: Reorganizes `src/distributed_training_engine/` into distinct subsystem directories (`training/`, `partitioning/`, `aggregation/`) with concrete adapter implementations grouped under `adapters/<model_type>/`. Backward-compatible aliases and re-exports in package `__init__.py` files ensure existing callers (`samples/training_test/train.py`, etc.) continue running without interruption.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No violations. Design strictly complies with all constitutional principles.)*
