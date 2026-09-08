# Tasks: Completing Submit Flow

**Feature**: Completing Submit Flow
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, and environment readiness.

- [X] T001 Setup directory structure for `samples/task_assignment_test/` in `samples/task_assignment_test/`
- [X] T002 [P] Create `src/Client/models/` directory and package export in `src/Client/models/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain entities, persistence schema, repository contracts, and command DTOs that MUST be completed before user story workflows can execute.

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [X] T003 Implement `Model` domain entity dataclass in `src/Client/domain/model.py`
- [X] T004 Add `ModelNotFoundError` and `ModelPersistenceError` exceptions in `src/Client/infrastructure/persistence/exceptions.py`
- [X] T005 Update SQLite schema in `DatabaseManager` to create `models` table and index in `src/Client/infrastructure/persistence/database.py`
- [X] T006 Implement `IModelRepository` interface and `ModelRepository` SQLite class with `save()` and `get_by_model_id()` in `src/Client/infrastructure/persistence/model_repository.py`
- [X] T007 [P] Re-export `ModelRepository` and exceptions in `src/Client/infrastructure/persistence/__init__.py`
- [X] T008 Update `StartTrainingCommand` class with 5 properties (`ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, `ShardId`) in `src/Coordinator/TrainSwarm.Coordinator.Application/Commands/StartTrainingCommand.cs`
- [X] T009 [P] Update `CommandDispatchController` and `DispatchStartTrainingDto` to align with the revised `StartTrainingCommand` in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/CommandDispatchController.cs`

**Checkpoint**: Foundation ready - Client model persistence and Coordinator command contracts are established.

---

## Phase 3: User Story 1 - Client Model Metadata Persistence & Staging Tracking (Priority: P1) 🎯 MVP

**Goal**: Persist model metadata in the Client `models` table via `ModelRepository` as a dedicated observable step immediately following shard persistence in `SubmitTrainingCommandHandler`, aborting if save fails.

**Independent Test**: Execute `SubmitTrainingCommandHandler` with valid inputs; verify `Model` entity is saved in SQLite and retrievable via `ModelRepository.get_by_model_id(model_id)`; verify `ModelNotFoundError` on missing ID; verify failure aborts before contacting Coordinator.

- [X] T010 [US1] Register `ModelRepository` in Client DI container in `src/Client/dependency_injection/container.py`
- [X] T011 [US1] Update `SubmitTrainingCommandHandler` constructor to accept `ModelRepository` and wire it from `src/Client/main.py`
- [X] T012 [US1] Integrate Step 7 in `SubmitTrainingCommandHandler.handle()` to instantiate and save `Model` entity with progress reporting and logs in `src/Client/application/submit_training/submit_training_command_handler.py`
- [X] T013 [US1] Implement failure handling in `SubmitTrainingCommandHandler` to abort workflow, retain shards as `CREATED`, and return error if model persistence fails in `src/Client/application/submit_training/submit_training_command_handler.py`

**Checkpoint**: User Story 1 (MVP) is fully functional and model metadata is persisted and retrievable in the Client.

---

## Phase 4: User Story 2 - Coordinator StartTrainingCommand Dispatch to Assigned Trainers (Priority: P2)

**Goal**: When Coordinator scheduler assigns tasks to idle trainers, construct `StartTrainingCommand` with the 5 task properties and push it to the trainer via `ICommandCenter`, reverting DB assignment if dispatch fails.

**Independent Test**: Register an idle trainer and task; invoke `SchedulerService.AssignTasksAsync()`; verify `StartTrainingCommand` is sent via `ICommandCenter`; verify DB rollback (`task.TrainerNodeId = ""` and `trainer.Status = UNCLEAR`) if dispatch fails.

- [X] T014 [US2] Inject `ICommandCenter` into `SchedulerService` constructor in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T015 [US2] Implement command construction and dispatch loop pushing `StartTrainingCommand` to assigned trainers via `ICommandCenter.SendAsync` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T016 [US2] Implement rollback handling in `SchedulerService` (clearing `TrainerNodeId`, setting status `UNCLEAR`, committing reversion) if command dispatch fails in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T017 [US2] Add detailed tracing and structured logging for scheduling decisions, command dispatch, and rollback in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`

**Checkpoint**: User Story 2 is functional; assigned trainers receive `StartTrainingCommand` with rollback protection.

---

## Phase 5: User Story 3 - Asynchronous Background Safe Task Scheduling (Priority: P3)

**Goal**: Trigger task scheduling asynchronously in the background using `IServiceScopeFactory` and `SemaphoreSlim` synchronization upon task creation in `TrainingTaskService`, returning creation results to the client without blocking while preserving terminal logs.

**Independent Test**: Invoke `CreateTrainingTaskAsync()`; assert response returns immediately before background scheduling concludes; verify concurrency lock guards background execution; verify background logs are emitted to the terminal.

- [X] T018 [US3] Add static/singleton `SemaphoreSlim` locking synchronization for scheduler runs in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T019 [US3] Inject `IServiceScopeFactory` into `TrainingTaskService` to create isolated scopes for background scheduling in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T020 [US3] Trigger background `AssignTasksAsync()` via `Task.Run()` within a scoped service provider in `TrainingTaskService.CreateTrainingTaskAsync()` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T021 [US3] Implement comprehensive logging with `[BackgroundScheduler]` tag to ensure background logs are fully visible in terminal output in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`

**Checkpoint**: User Story 3 is functional; task creation triggers non-blocking, thread-safe background scheduling.

---

## Phase 6: User Story 4 - Trainer Modular Startup and StartTrainingCommand Ingestion (Priority: P4)

**Goal**: Refactor Trainer `presentation/startup.py` to encapsulate registration, connection guard, and `TrainerCommandListener` initialization; update `StartTrainingCommand` and `StartTrainingHandler` to parse and log the 5 command fields.

**Independent Test**: Launch Trainer via `main.py`; verify `startup.py` registers with Coordinator and launches listener; send a `StartTrainingCommand`; verify Trainer parses and logs all 5 fields.

- [X] T022 [US4] Move `TrainerCommandListener` initialization and start logic into `run_startup()` in `src/Trainer/presentation/startup.py`
- [X] T023 [US4] Update `src/Trainer/main.py` to call consolidated `run_startup(container)` and manage clean listener shutdown in `src/Trainer/main.py`
- [X] T024 [P] [US4] Update `StartTrainingCommand` dataclass in Trainer with `client_node_id`, `model_id`, `model_version`, `data_set_id`, and `shard_id` in `src/Trainer/application/coordinator_commands/start_training/command.py`
- [X] T025 [US4] Update `StartTrainingHandler.handle()` to log all 5 received command fields and update state in `src/Trainer/application/coordinator_commands/start_training/handler.py`

**Checkpoint**: User Story 4 is functional; Trainer startup is consolidated and incoming commands are ingested and logged.

---

## Phase 7: User Story 5 - Non-Dockerized End-to-End Verification Test Sample (Priority: P5)

**Goal**: Provide a complete, standalone command-line test harness in `samples/task_assignment_test/` that starts Coordinator and Trainer as detached background processes, generates test artifacts, runs Client CLI submit-training, and verifies end-to-end correctness without Docker.

**Independent Test**: Run `python startup.py` and `python submit.py` in `samples/task_assignment_test/`; verify that Client DB has model & shards, Coordinator DB has assigned tasks, Trainer logs receive the command, and `python clean.py` cleanly tears down processes.

- [X] T026 [US5] Implement `startup.py` to spawn Coordinator & Trainer background processes, record PIDs to `.test_pids.txt`, wait for health, and synthesize PyTorch model (`.pt2`), dataset (`.pt`), and `training_config.json` in `samples/task_assignment_test/startup.py`
- [X] T027 [US5] Implement `submit.py` to invoke Client CLI `submit-training`, query Client and Coordinator SQLite databases, verify Trainer log output, and assert end-to-end success in `samples/task_assignment_test/submit.py`
- [X] T028 [US5] Implement `clean.py` to kill recorded processes in `.test_pids.txt`, release ports, and clean temporary databases/artifacts in `samples/task_assignment_test/clean.py`
- [X] T029 [P] [US5] Create `README.md` with detailed architecture diagram, walkthrough, and execution instructions in `samples/task_assignment_test/README.md`

**Checkpoint**: User Story 5 is functional; complete end-to-end flow is validated against live processes without Docker.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Build integrity verification, code quality, and end-to-end operational execution.

- [X] T030 [P] Verify compilation of Coordinator solution with `dotnet build src/Coordinator/TrainSwarm.Coordinator.slnx`
- [X] T031 [P] Verify Python syntax across Client, Trainer, and test sample using `python -m py_compile`
- [X] T032 Execute full end-to-end verification via `quickstart.md` (`startup.py`, `submit.py`, `clean.py`) and confirm exit code 0

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user story phases.
- **User Story 1 (Phase 3, MVP)**: Depends on Phase 2 - Client model persistence.
- **User Story 2 (Phase 4)**: Depends on Phase 2 - Coordinator command dispatch.
- **User Story 3 (Phase 5)**: Depends on Phase 4 (integrates with SchedulerService).
- **User Story 4 (Phase 6)**: Depends on Phase 2 - Trainer command ingestion.
- **User Story 5 (Phase 7)**: Depends on Phases 3, 4, 5, and 6 (exercises all services together).
- **Polish (Phase 8)**: Depends on all prior phases.

### User Story Dependencies

- **User Story 1 (P1)**: Independent of Coordinator/Trainer changes; can be implemented and validated directly in Client.
- **User Story 2 (P2)**: Independent of Client changes; updates Coordinator scheduler and command dispatch.
- **User Story 3 (P3)**: Integrates `SchedulerService` into `TrainingTaskService` background execution.
- **User Story 4 (P4)**: Independent of Client changes; aligns Trainer command contract with Coordinator.
- **User Story 5 (P5)**: End-to-end integration harness validating US1 through US4.

### Parallel Opportunities

- Within Phase 1: `T002` can run in parallel with `T001`.
- Within Phase 2: `T007` and `T009` can run in parallel.
- Once Foundational (Phase 2) is complete:
  - Developer A can implement US1 (Client persistence: `T010`-`T013`).
  - Developer B can implement US2 & US3 (Coordinator dispatch & background: `T014`-`T021`).
  - Developer C can implement US4 (Trainer startup & command: `T022`-`T025`).
- Within Polish: `T030` and `T031` can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (`T001`, `T002`)
2. Complete Phase 2: Foundational (`T003`-`T009`)
3. Complete Phase 3: User Story 1 (`T010`-`T013`)
4. **STOP and VALIDATE**: Verify `ModelRepository.save()` and `get_by_model_id()` work with SQLite in Client CLI.

### Incremental Delivery
1. Phase 1 + 2: Core entities and database schemas ready.
2. Phase 3 (US1): Client persists model metadata upon submission.
3. Phase 4 (US2): Coordinator pushes `StartTrainingCommand` on task assignment.
4. Phase 5 (US3): Coordinator triggers thread-safe background scheduling.
5. Phase 6 (US4): Trainer unifies startup and logs received command fields.
6. Phase 7 (US5): Live end-to-end verification harness runs seamlessly.
7. Phase 8: Full compilability and executable validation pass.
