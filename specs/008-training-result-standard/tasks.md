# Tasks: Training Result Standard & Delta Artifacts

**Feature**: `008-training-result-standard`  
**Plan**: [plan.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/008-training-result-standard/plan.md)  
**Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/008-training-result-standard/spec.md)  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency configuration and environment preparation

- [X] T001 [P] Add `safetensors>=0.4.0` dependency to `src/Trainer/requirements.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Exception and error handling infrastructure required by all user stories

- [X] T002 [P] Update domain exceptions in `src/distributed_training_engine/training/exceptions.py` with explicit errors for delta calculation, tensor shape mismatch, and contract validation

---

## Phase 3: User Story 1 - Model Delta Calculation and Safetensors Artifact Export (Priority: P1) 🎯 MVP

**Goal**: Compute parameter differences (`delta = trained - base`) against the baseline model and export a lightweight `.safetensors` artifact to the workspace without mutating input files.

**Independent Test**: Provide `base_model_v1.pt2` and `dataset1_shard1.pt`, execute training adapter lifecycle, verify output `base_model_v1_dataset1_shard1.safetensors` contains difference tensors with identical keys and shapes, and confirm input files are unmodified.

### Implementation for User Story 1

- [X] T003 [US1] Implement immutable base model `state_dict` detached CPU snapshotting in `prepare()` in `src/distributed_training_engine/training/training_adapters/canonical_torch/canonical_torch_adapter.py`
- [X] T004 [US1] Implement parameter difference calculation (`delta[name] = trained[name] - base[name]`) with shape and key validation in `save_result()` in `src/distributed_training_engine/training/training_adapters/canonical_torch/canonical_torch_adapter.py`
- [X] T005 [US1] Implement `.safetensors` export using `safetensors.torch.save_file` to `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors` in `src/distributed_training_engine/training/training_adapters/canonical_torch/canonical_torch_adapter.py`

**Checkpoint**: At this point, the adapter captures baseline state, computes weight deltas, and saves `.safetensors` artifacts.

---

## Phase 4: User Story 2 - Standardized Training Task and Result Contracts (Priority: P2)

**Goal**: Standardize `TrainingTask` and `TrainingResult` DTO envelopes with explicit baseline model, dataset shard, execution telemetry, and delta metadata, eliminating `session_id`.

**Independent Test**: Instantiate `TrainingTask` and `TrainingResult`, serialize to JSON/dictionary, deserialize back, and verify camelCase wire keys and snake_case Python property access.

### Implementation for User Story 2

- [X] T006 [P] [US2] Update `TrainingTask` DTO with `training_task_id`, `baseline_model_id`, `baseline_model_version`, `data_set_id`, `data_set_shard_id`, removing `session_id`, with envelope validation and JSON serialization in `src/distributed_training_engine/training/training_task_model.py`
- [X] T007 [P] [US2] Implement updated `TrainingResult` DTO with `ExecutionInfo` and `DeltaArtifactInfo`, supporting camelCase JSON wire keys and snake_case Python property access in `src/distributed_training_engine/training/training_result.py`
- [X] T008 [US2] Update `TrainingOrchestrator` to record execution timing (`started_at`, `completed_at`, `duration_ms`), track `samples_trained`, and wire `TrainingResult` envelope in `src/distributed_training_engine/training/training_orchestrator.py`
- [X] T009 [US2] Update `CanonicalTorchAdapter.validate()` and file path resolution for `<baseline_model_id>_<baseline_model_version>.pt2` and `<data_set_id>_<data_set_shard_id>.pt` in `src/distributed_training_engine/training/training_adapters/canonical_torch/canonical_torch_adapter.py`
- [X] T010 [P] [US2] Update training package exports in `src/distributed_training_engine/training/__init__.py` and `src/distributed_training_engine/__init__.py`

**Checkpoint**: At this point, task dispatch and result reporting contracts are standardized and integrated across the engine.

---

## Phase 5: User Story 3 - Standalone Delta Verification Tooling (Priority: P3)

**Goal**: Provide a standalone CLI tool (`verify.py`) that loads a baseline model and delta artifact, applies weights, runs evaluation against the dataset shard, and confirms loss convergence.

**Independent Test**: Execute `python samples/training_test/verify.py` and verify parameter reconstruction parity ($<10^{-6}$), loss reduction, and clean exit code `0`.

### Implementation for User Story 3

- [X] T011 [US3] Implement `samples/training_test/verify.py` with hardcoded sample paths (`base_model_v1.pt2`, `dataset1_shard1.pt`, `base_model_v1_dataset1_shard1.safetensors`) to reconstruct model parameters (`base + delta`), evaluate loss against dataset shard, verify loss improvement, and exit with code 0/1

**Checkpoint**: At this point, delta correctness and reconstructibility can be verified independently without re-training.

---

## Phase 6: User Story 4 - Updated End-to-End Sample and Setup Workflow (Priority: P4)

**Goal**: Update sample scripts (`setup.py`, `train.py`, `README.md`) to follow the new artifact naming conventions and delta workflow for 3-step setup, train, and verify.

**Independent Test**: Sequentially run `python setup.py`, `python train.py`, and `python verify.py` in `samples/training_test/`, confirming exit code 0 for all three scripts.

### Implementation for User Story 4

- [X] T012 [P] [US4] Update `samples/training_test/setup.py` to generate `base_model_v1.pt2` and `dataset1_shard1.pt`
- [X] T013 [US4] Update `samples/training_test/train.py` to construct `TrainingTask` conforming to updated contract, execute orchestrator, and verify `.safetensors` delta artifact creation and input immutability
- [X] T014 [P] [US4] Update `samples/training_test/README.md` documenting the 3-step setup, train, and verify workflow with updated artifact naming conventions

**Checkpoint**: All sample scripts are aligned with the new delta artifacts and contracts.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verification, compilability check, and quality gate validation

- [X] T015 [P] Verify syntax and compilation of all modified Python files (`python -m py_compile`) across `src/` and `samples/` per Constitution Principle VII
- [X] T016 Execute full 3-step active verification workflow (`setup.py` -> `train.py` -> `verify.py`) per `specs/008-training-result-standard/quickstart.md` and confirm 100% loss convergence and delta parity

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 - blocks user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2.
- **User Story 2 (Phase 4)**: Depends on Phase 2 & Phase 3 (integrates delta calculation with result contracts).
- **User Story 3 (Phase 5)**: Depends on Phase 3 & Phase 4 (verifies generated delta artifacts).
- **User Story 4 (Phase 6)**: Depends on Phase 3, Phase 4 & Phase 5 (updates samples to end-to-end workflow).
- **Polish (Phase 7)**: Depends on all user stories being complete.

### Parallel Opportunities

- `T001` and `T002` can run in parallel.
- `T006`, `T007`, and `T010` in User Story 2 can be developed in parallel before wiring in `T008`/`T009`.
- `T012` and `T014` in User Story 4 can run in parallel.
- `T015` can verify compilation across files in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 & Core Contracts)
1. Complete Phase 1 (Setup) and Phase 2 (Foundations).
2. Complete Phase 3 (US1: Delta Calculation & Safetensors Export).
3. Complete Phase 4 (US2: Task/Result Contracts & Orchestrator Wiring).
4. Complete Phase 5 (US3: Verification Tooling).
5. Complete Phase 6 (US4: Sample Scripts).
6. Complete Phase 7 (Quality Gate Verification).
