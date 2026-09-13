# Tasks: Model Update Follow-up & Distributed Aggregation Lifecycle

**Input**: Design documents from [`specs/020-update-model-followup/`](./)  
**Plan**: [`specs/020-update-model-followup/plan.md`](./plan.md)  
**Spec**: [`specs/020-update-model-followup/spec.md`](./spec.md)  
**Status**: Ready for Implementation  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify repository build integrity and dependencies across control plane and data plane.

- [X] T001 Verify Coordinator build and Python environment per quickstart.md in `src/Coordinator` and `src/Client`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema and repository updates that unblock all subsequent user stories.

- [X] T002 Update `CREATE_MODELS_TABLE_SQL` to define composite primary key `(model_id, model_version)` and handle schema initialization in `src/Client/infrastructure/persistence/database.py`
- [X] T003 [P] Update `IModelRepository` and `ModelRepository` to support composite key queries `get_by_model_id_and_version` and `get_all` in `src/Client/infrastructure/persistence/model_repository.py`
- [X] T004 [P] Add query methods `get_by_model_version_and_dataset` and `get_all` to `ITrainingShardRepository` and `TrainingShardRepository` in `src/Client/infrastructure/persistence/training_shard_repository.py`

**Checkpoint**: Database composite model keys and shard queries ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Coordinator Trainer Detachment and Lifecycle State Tracking (Priority: P1) 🎯 MVP

**Goal**: Implement `DetachTrainerAsync` in Coordinator `TrainerService` with status transition logic (`IDLE` if `isTrainingComplete == true`, `UNCLEAR` if `false`, safe no-op if not `BUSY`), expose `POST /api/trainers/detach`, and provide inspection endpoints `GET /api/trainers` and `GET /api/training-tasks`.

**Independent Test**: Register a trainer with the Coordinator, transition it to BUSY, call `POST /api/trainers/detach` with `isTrainingComplete=true` to assert transition to `IDLE`, then with `isTrainingComplete=false` to assert transition to `UNCLEAR`. Verify query GET endpoints return current state.

- [X] T005 [P] [US1] Create `DetachTrainerRequest.cs` and `DetachTrainerDto.cs` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/`
- [X] T006 [US1] Implement `DetachTrainerAsync` and `GetTrainersAsync` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainerService.cs`
- [X] T007 [P] [US1] Implement `GetTrainingTasksAsync` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T008 [US1] Expose `POST /api/trainers/detach` and `GET /api/trainers` endpoints in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainerController.cs`
- [X] T009 [US1] Expose `GET /api/training-tasks` endpoint in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainingTaskController.cs`
- [X] T010 [US1] Validate Coordinator build and API detachment/query responses via `dotnet build` in `src/Coordinator`

**Checkpoint**: User Story 1 complete. Coordinator can detach trainers and serve state inspection queries.

---

## Phase 4: User Story 2 - Client Training Update Ingestion, Trainer Detachment, and Automated Aggregation (Priority: P2)

**Goal**: In Client, call Coordinator adapter to detach trainer after saving shard update, evaluate all-shards-complete under a concurrency lock, trigger `AggregationOrchestrator` to synthesize version 2 checkpoint, and persist the new version record.

**Independent Test**: Simulate two shard updates arriving at the Client. Verify each update detaches the trainer via Coordinator adapter. Assert that upon the second update, the concurrency lock prevents duplicate triggers, aggregation executes, and version 2 `.pt2` checkpoint is saved in SQLite and disk.

- [X] T011 [P] [US2] Implement `detach_trainer` HTTP method in `src/Client/infrastructure/adapters/coordinator_adapter.py`
- [X] T012 [US2] Integrate `coordinator_adapter.detach_trainer` into `src/Client/application/commands/update_model/update_model_handler.py` following shard persistence
- [X] T013 [US2] Implement thread-safe shard completion evaluation under `threading.Lock` in `src/Client/application/commands/update_model/update_model_handler.py`
- [X] T014 [US2] Implement `AggregationOrchestrator` invocation and version increment persistence (`newVersion = base_version + 1`) in `src/Client/application/commands/update_model/update_model_handler.py`
- [X] T015 [US2] Add observable diagnostic and trace logging throughout update and aggregation flows in `src/Client/application/commands/update_model/update_model_handler.py`

**Checkpoint**: User Stories 1 and 2 complete. Shard updates automatically detach trainers and trigger aggregation upon round completion.

---

## Phase 5: User Story 3 - Client Training Submission Lock and State Guard (Priority: P3)

**Goal**: Add in-memory `submitted` boolean state guard to Client. Set to `True` upon task submission, reject overlapping submissions, and reset to `False` once model aggregation produces a new version checkpoint.

**Independent Test**: Verify initial `submitted == False`. Run `submit-training` and assert `submitted == True`. Attempt an immediate second submission and verify rejection with error. Process all shard updates to completion and verify `submitted == False`.

- [X] T016 [P] [US3] Add `submitted: bool` property with default `False` and setter to `ClientNode` and `ClientState` in `src/Client/application/state.py`
- [X] T017 [US3] Implement submission guard check and state update (`submitted = True`) in `src/Client/application/submit_training/submit_training_command_handler.py`
- [X] T018 [US3] Reset `submitted = False` in `src/Client/application/commands/update_model/update_model_handler.py` when aggregation successfully creates a new version

**Checkpoint**: User Stories 1, 2, and 3 complete. Client enforces safe single-flight submission concurrency.

---

## Phase 6: User Story 4 - Presentation Views: Active Shards Watch and Trained Version Export (Priority: P4)

**Goal**: Create application queries `GetTrainingShardsQuery` and `GetTrainedModelsQuery`, add a `watch-shards` CLI subcommand in Console UI, and add "Training Shards" and "Trained Versions" tabs with artifact export in the GUI.

**Independent Test**: Execute `python main.py watch-shards` to view active shard statuses. Launch `python main.py gui`, inspect both tabs, and test the "Export / Save Artifact" button to save a checkpoint to a chosen path.

- [X] T019 [P] [US4] Implement `GetTrainingShardsQuery`, `TrainingShardViewDto`, and `GetTrainingShardsQueryHandler` in `src/Client/application/queries/get_training_shards/`
- [X] T020 [P] [US4] Implement `GetTrainedModelsQuery`, `TrainedModelViewDto`, and `GetTrainedModelsQueryHandler` in `src/Client/application/queries/get_trained_models/`
- [X] T021 [US4] Implement `watch-shards` CLI subcommand with aligned table rendering and Enter/refresh loop in `src/Client/presentation/console_ui.py`
- [X] T022 [US4] Add "Training Shards" tab with table and refresh button in `src/Client/presentation/gui/main_window.py`
- [X] T023 [US4] Add "Trained Versions" tab with model version table and "Export / Save" file dialog in `src/Client/presentation/gui/main_window.py`

**Checkpoint**: User Stories 1 through 4 complete. Full observability and artifact export available across GUI and CLI.

---

## Phase 7: User Story 5 - Multi-Node Distributed Training Verification, Loss Evaluation, and Teardown Utility (Priority: P5)

**Goal**: Update `samples/full_distributed_training_test` to verify both trainers return to `IDLE` status on the Coordinator, assert version 2 artifact creation, evaluate and compare model training losses (`aggregated_loss < base_loss`), and provide `clean.py` for process teardown.

**Independent Test**: Execute `clean.py` to wipe lingering processes and artifacts. Execute `run_local.py` and verify all assertions (trainer idle state, v2 artifact, finite loss reduction) pass cleanly.

- [X] T024 [P] [US5] Create standalone process termination and directory cleanup script `clean.py` in `samples/full_distributed_training_test/clean.py`
- [X] T025 [US5] Update `verify.py` in `samples/full_distributed_training_test/verify.py` to query Coordinator for trainer `IDLE` status and assert version 2 artifact presence
- [X] T026 [US5] Implement PyTorch model evaluation step in `samples/full_distributed_training_test/verify.py` asserting finite loss and strict loss reduction (`aggregated_loss < base_loss`)
- [X] T027 [US5] Update multi-node local runner `samples/full_distributed_training_test/run_local.py` to integrate Coordinator check, loss evaluation, and teardown

**Checkpoint**: User Stories 1 through 5 complete. Multi-node integration test validates the entire distributed system.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: System verification, compilation check across all modules, and end-to-end execution.

- [X] T028 [P] Verify compilation of all services (`dotnet build src/Coordinator` and `python -m compileall src/Client src/Trainer`)
- [X] T029 Execute end-to-end multi-node distributed training test via `clean.py` and `run_local.py` in `samples/full_distributed_training_test/` per Constitution Principle VII
- [X] T030 Document end-to-end test execution output and prompt steps and results in final report

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS User Stories 2, 3, 4, 5.
- **User Story 1 (Phase 3)**: Independent control plane work; can run immediately or in parallel with Foundational.
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) and US1 Coordinator endpoints.
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) and integrates with US2 handler.
- **User Story 4 (Phase 6)**: Depends on Foundational (Phase 2) repositories.
- **User Story 5 (Phase 7)**: Depends on US1, US2, and US3 complete.
- **Polish (Phase 8)**: Depends on all user stories complete.

### Parallel Opportunities

- **Phase 2 (Foundational)**: T003 (ModelRepository) and T004 (TrainingShardRepository) can run in parallel.
- **Phase 3 (User Story 1)**: T005 (DTOs) and T007 (Task query) can run in parallel.
- **Phase 4 (User Story 2)**: T011 (CoordinatorAdapter) can run in parallel with Coordinator work.
- **Phase 6 (User Story 4)**: T019 (Shard queries) and T020 (Model queries) can run in parallel.
- **Phase 7 (User Story 5)**: T024 (`clean.py`) can run in parallel with Client/Coordinator enhancements.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (composite PK)
3. Complete Phase 3: User Story 1 (Coordinator Detach & Inspection API)
4. Validate Coordinator builds cleanly (`dotnet build`) and endpoints respond

### Incremental Delivery
1. Phase 1 + 2 + 3 → Coordinator detachment ready (MVP)
2. Phase 4 → Client automatic detachment and aggregation ready
3. Phase 5 → Double-submission lock active
4. Phase 6 → CLI & GUI inspection and artifact export active
5. Phase 7 + 8 → End-to-end multi-node verification, loss comparison, and clean teardown validated
