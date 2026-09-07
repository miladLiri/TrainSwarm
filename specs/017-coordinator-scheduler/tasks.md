# Tasks: Fair Model-Level Round-Robin Coordinator Scheduler

**Feature**: Fair Model-Level Round-Robin Coordinator Scheduler
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, and environment readiness.

- [X] T001 Setup directory structure for `samples/scheduling_test/` in `samples/scheduling_test/`
- [X] T002 [P] Verify Coordinator solution references and .NET 10 compilation toolchain in `src/Coordinator/TrainSwarm.Coordinator.slnx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain entities, persistence schema, migrations, in-memory state contracts, and DI configuration that MUST be completed before user story workflows can execute.

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [X] T003 Add `DateTime SubmitTime` property to `TrainingTask` entity in `src/Coordinator/TrainSwarm.Coordinator.Domain/Entities/TrainingTask.cs`
- [X] T004 Update `TrainingTaskConfiguration` to map `SubmitTime` column in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Configurations/TrainingTaskConfiguration.cs`
- [X] T005 Create and verify EF Core database migration for `SubmitTime` in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Migrations/`
- [X] T006 Update `TrainingTaskService.CreateTrainingTaskAsync` to populate `SubmitTime = DateTime.Now` upon task creation in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T007 [P] Define `ISchedulerCursorState` interface and `SchedulerCursorState` thread-safe singleton in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/ISchedulerCursorState.cs` and `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerCursorState.cs`
- [X] T008 [P] Define `AssignedTaskDto` response model in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/AssignedTaskDto.cs`
- [X] T009 Register `ISchedulerCursorState` as Singleton and `SchedulerService` as Scoped in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`

**Checkpoint**: Core domain, schema migration, cursor singleton, and DI foundation ready.

---

## Phase 3: User Story 1 - Fair Model-Level Task Assignment Across Idle Trainers (Priority: P1) 🎯 MVP

**Goal**: Implement fair model-level round-robin task allocation that distributes unassigned tasks across available idle trainers, preventing single-model starvation while maximizing trainer utilization.

**Independent Test**: Populate tasks across multiple models and provide idle trainers; invoke `POST /api/scheduler/assign` and confirm tasks distribute evenly across distinct models, all idle trainers are utilized up to task availability, and tasks within each model follow `SubmitTime ASC` with `TrainingTaskId ASC` tie-breaking.

- [X] T010 [US1] Implement core model grouping and intra-model FIFO ordering logic (`SubmitTime ASC`, `TrainingTaskId ASC`) in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T011 [US1] Implement round-robin model turn allocation loop that utilizes all idle trainers in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T012 [US1] Implement `SchedulingController` exposing `POST /api/scheduler/assign` returning `List<AssignedTaskDto>` in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/SchedulingController.cs`

**Checkpoint**: User Story 1 (MVP) is functional and can assign tasks across idle trainers using model-level round-robin.

---

## Phase 4: User Story 2 - Continuous In-Memory Cursor Rotation Across Invocations (Priority: P2)

**Goal**: Maintain the round-robin cursor across discrete scheduling invocations so that newly available trainers continue from the next model in rotation rather than restarting from the first model.

**Independent Test**: Schedule tasks for models A, B, C, D with 3 trainers (leaving D unassigned). Execute assignment again with 1 newly available trainer and verify Model D receives the assignment.

- [X] T013 [US2] Integrate `ISchedulerCursorState` in `SchedulerService` to read, advance, and persist cursor across separate HTTP requests in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T014 [US2] Implement dynamic pruning of exhausted models from active rotation in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`

**Checkpoint**: In-memory cursor accurately maintains rotation continuity across multiple independent requests.

---

## Phase 5: User Story 3 - Atomic Assignment, Concurrency Resilience, & Status Isolation (Priority: P3)

**Goal**: Ensure task assignments and trainer status mutations are committed atomically within a single database transaction, ensuring `BUSY`/`UNCLEAR` trainers are excluded and concurrency collisions are safely discarded/retried.

**Independent Test**: Attempt scheduling with mixed trainer statuses (`IDLE`, `BUSY`, `UNCLEAR`) and pre-assigned tasks; verify only `IDLE` trainers become `BUSY` and only unassigned tasks are assigned.

- [X] T015 [US3] Enforce strict eligibility checks (`trainer.Status == TrainerStatus.IDLE`, `string.IsNullOrEmpty(task.TrainerNodeId)`) in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`
- [X] T016 [US3] Implement single-transaction database persistence (`TrainingTask.TrainerNodeId` and `Trainer.Status = BUSY`) with concurrency exception handling in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/SchedulerService.cs`

**Checkpoint**: Assignments are atomic, thread-safe, and isolated to valid statuses.

---

## Phase 6: User Story 4 - State Reset & Administrative Lifecycle Management (Priority: P4)

**Goal**: Expose administrative endpoints to remove all trainer and task records on demand and reset the scheduler cursor for deterministic test lifecycle management.

**Independent Test**: Invoke `POST /api/trainers/clear` and `POST /api/training-tasks/clear` and verify database tables are empty and cursor is reset.

- [X] T017 [P] [US4] Implement `ClearTrainersAsync` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainerService.cs`
- [X] T018 [P] [US4] Implement `ClearTasksAsync` resetting in-memory cursor via `ISchedulerCursorState.Reset()` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [X] T019 [P] [US4] Expose `POST /api/trainers/clear` endpoint in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainerController.cs`
- [X] T020 [P] [US4] Expose `POST /api/training-tasks/clear` endpoint in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainingTaskController.cs`

**Checkpoint**: Tables and cursor can be reset deterministically via clean REST API endpoints.

---

## Phase 7: User Story 5 - Automated End-to-End Scheduling Verification Suite (Priority: P5)

**Goal**: Deliver a comprehensive live verification suite in `samples/scheduling_test/` covering all 12 test cases against the active Coordinator web service without mocks.

**Independent Test**: Execute `python setup.py` and `python test.py` in `samples/scheduling_test/` and observe all 12 test cases pass with formatted output and exit code 0.

- [X] T021 [US5] Implement `setup.py` to start Coordinator process, configure SQLite DB, and verify `/health` in `samples/scheduling_test/setup.py`
- [X] T022 [US5] Implement Test 1 (Single Model), Test 2 (Fairness), Test 3 (More Trainers), and Test 4 (Cursor Continuity) in `samples/scheduling_test/test.py`
- [X] T023 [US5] Implement Test 5 (FIFO Preservation), Test 6 (Imbalance Starvation Prevention), Test 7 (Status Filtering), and Test 8 (Zero Tasks) in `samples/scheduling_test/test.py`
- [X] T024 [US5] Implement Test 9 (Zero Idle Trainers), Test 10 (Pre-Assigned Tasks), Test 11 (Model Exhaustion), and Test 12 (Equal SubmitTime Tie-Break) in `samples/scheduling_test/test.py`
- [X] T025 [US5] Implement colorized terminal summary reporting and table clear teardowns between test cases in `samples/scheduling_test/test.py`
- [X] T026 [P] [US5] Create documentation detailing all 12 test cases, architectural rationale, and execution commands in `samples/scheduling_test/README.md`

**Checkpoint**: Complete 12-case zero-mock test suite operational and validating Coordinator scheduling.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verification of solution build integrity, compilability, clean code formatting, and end-to-end execution.

- [X] T027 Build Coordinator solution and verify zero compilation errors in `src/Coordinator/TrainSwarm.Coordinator.slnx`
- [X] T028 Run complete verification suite via `samples/scheduling_test/test.py` against running Coordinator and confirm 12/12 passing tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — executes immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2 — core MVP scheduling algorithm.
- **User Story 2 (Phase 4)**: Depends on Phase 3 — extends algorithm with cursor continuity.
- **User Story 3 (Phase 5)**: Depends on Phase 3 — hardens atomicity and status filtering.
- **User Story 4 (Phase 6)**: Depends on Phase 2 — table reset endpoints.
- **User Story 5 (Phase 7)**: Depends on Phases 3, 4, 5, 6 — verifies all functionality end-to-end.
- **Polish (Phase 8)**: Depends on Phase 7 completion.

### Parallel Opportunities

- **Foundational Phase**: T007 [P] (`ISchedulerCursorState`), T008 [P] (`AssignedTaskDto`) can run in parallel.
- **User Story 4**: T017 [P], T018 [P], T019 [P], T020 [P] can run in parallel across Trainer and TrainingTask services/controllers.
- **User Story 5**: T026 [P] (`README.md`) can be drafted in parallel with test harness scripts.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. Validate basic model-level round-robin assignment with `POST /api/scheduler/assign`.

### Incremental Delivery
1. Phase 1 + Phase 2 → Entity schema, migration, and DI foundation ready.
2. Phase 3 (US1) → Core scheduling MVP delivered.
3. Phase 4 (US2) → Multi-request cursor continuity delivered.
4. Phase 5 (US3) → Concurrency collision and status isolation hardened.
5. Phase 6 (US4) → Administrative table clear endpoints delivered.
6. Phase 7 (US5) → 12-case zero-mock test suite completed.
7. Phase 8 (Polish) → Solution build and full verification passed.
