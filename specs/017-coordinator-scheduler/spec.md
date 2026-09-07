# Feature Specification: Fair Model-Level Round-Robin Coordinator Scheduler

**Feature Branch**: `feature/scheduler`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "Coordinator Scheduler: in Coordinator in Domain add a DateTime SubmitTime to TrainingTask and in related service in saving a TrainingTask set it to DateTime.Now then Apply required migration; in Application in trainer service create a Clear Trainers that remove all the trainers and in training task service create Clear Tasks that delete all the tasks; in services create SchedulerService that has one method : Assign Tasks with zero input; assign task responsibility is to check tasks without trainer and check the Idle trainers and assign tasks to them based on scheduling algorithm and for result returns the assigned training tasks; The Algorithm: fair model-level round-robin scheduler assigning unassigned TrainingTask records to available Trainer records, assign each trainer at most one task, treat trainers as identical, prevent starvation, preserve FIFO within model by SubmitTime ASC and tie-breaker TrainingTaskId ASC, utilize all available idle trainers without reducing utilization, task eligibility string.IsNullOrEmpty(task.TrainerNodeId), trainer eligibility trainer.Status == TrainerStatus.IDLE, in-memory scheduler cursor representing next model, round-robin rotation advancing and removal of exhausted models, deterministic trainer selection (TrainerNodeId ASC), atomic assignment with concurrency protection and retry, fairness guarantee; in Api in controllers create SchedulingController that runs assign task method of scheduling service and returns assigned tasks, in trainer controller and training task controller add an api for clear services; test in samples/ create scheduling_test with setup.py running coordinator, test.py testing 12 test cases using coordinator apis and printing pass/fail results beautifully, clearing tables via clear apis, and readme.md explaining test cases, importance, and run instructions."

## Clarifications

### Session 2026-09-07

- **Q: What exact REST routes and HTTP methods should the Coordinator expose for assigning tasks and clearing trainer and task tables?** → **A: `POST /api/scheduler/assign` for assigning tasks; `POST /api/trainers/clear` and `POST /api/training-tasks/clear` for clearing tables (Option A).**
- **Q: Should invoking `ClearTasksAsync` reset the in-memory scheduler cursor to its initial state?** → **A: Yes, `ClearTasksAsync` resets the in-memory cursor so test cases and fresh batches start deterministically (Option A).**
- **Q: What response schema should `POST /api/scheduler/assign` return upon successful task assignment?** → **A: List of assigned task objects directly in the JSON response body: `[{ trainingTaskId, modelId, trainerNodeId, shardId, submitTime }]` (Option A).**
- **Q: Should `SubmitTime` be populated using `DateTime.UtcNow` or `DateTime.Now` when creating `TrainingTask` records?** → **A: `DateTime.Now` (local system time) as specified in the original description (Option B).**

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fair Model-Level Task Assignment Across Idle Trainers (Priority: P1)

As a distributed machine learning platform operator, I want the Coordinator to assign pending training tasks across available compute trainers using a fair round-robin strategy grouped by model identity, so that no single model with a high volume of tasks starves tasks belonging to other models while fully utilizing all idle trainers.

**Why this priority**: Core scheduling functionality. Without round-robin model rotation and idle trainer utilization, tasks from smaller or newly submitted models would wait indefinitely behind massive backlogs, or trainers would sit idle unnecessarily.

**Independent Test**: Populate multiple models with varying quantities of pending tasks (e.g., Model A with 10 tasks, Model B with 1 task, Model C with 1 task) and provide multiple idle trainers. Trigger task assignment via `POST /api/scheduler/assign`. Verify that the assigned tasks distribute evenly across distinct models (A, B, C, A, A, A...) rather than consuming all capacity on Model A, and verify every idle trainer receives a task until tasks or trainers are exhausted.

**Acceptance Scenarios**:

1. **Given** 3 idle trainers and pending tasks for Model A, Model B, and Model C, **When** `POST /api/scheduler/assign` executes, **Then** exactly 1 task from Model A, 1 task from Model B, and 1 task from Model C are assigned respectively to the 3 trainers.
2. **Given** 5 idle trainers and pending tasks where Model A has 3 tasks and Model B has 1 task, **When** `POST /api/scheduler/assign` executes, **Then** 4 tasks are assigned (Model A task 1, Model B task 1, Model A task 2, Model A task 3), leaving the 5th trainer idle because no unassigned tasks remain.
3. **Given** idle trainers and multiple pending tasks for the same model with distinct submission timestamps, **When** task assignment selects tasks for that model, **Then** tasks are assigned strictly in first-in-first-out (FIFO) order according to their submission timestamp (`SubmitTime ASC`).
4. **Given** multiple tasks belonging to the same model having identical submission timestamps, **When** tasks are evaluated for assignment, **Then** tasks are selected deterministically using the task identifier (`TrainingTaskId ASC`) as an unambiguous tie-breaker.

---

### User Story 2 - Continuous In-Memory Cursor Rotation Across Invocations (Priority: P2)

As a platform scheduler, I want the system to maintain an in-memory cursor tracking the next model in rotation across successive scheduling invocations, so that newly available trainers do not continuously restart assignments from the first model in database order.

**Why this priority**: Prevents front-queue bias across multiple scheduling cycles. If each scheduling tick resets to the first model returned by a database query, earlier models would receive disproportionate resources over time.

**Independent Test**: Queue one task for each of Model A, Model B, Model C, and Model D with 3 idle trainers. Execute assignment (assigning A, B, C; leaving D queued). Introduce 1 new idle trainer and execute assignment again. Verify that the 4th assignment selects Model D rather than restarting at Model A.

**Acceptance Scenarios**:

1. **Given** pending tasks across models A, B, C, and D, and 3 idle trainers, **When** the first scheduling run completes, **Then** trainers are assigned to A, B, and C, and the scheduler cursor positions at Model D.
2. **Given** the scheduler cursor positioned at Model D and 1 idle trainer becomes available, **When** the next scheduling run executes, **Then** the idle trainer is assigned to Model D.
3. **Given** a model whose pending tasks have all been assigned, **When** subsequent scheduling turns are evaluated, **Then** the exhausted model is immediately excluded from the active rotation without wasting scheduling turns.

---

### User Story 3 - Atomic Assignment, Concurrency Resilience, & Status Isolation (Priority: P3)

As a distributed coordinator, I want task assignment and trainer status updates to be committed atomically and strictly isolated to eligible entities, so that busy or unverified trainers never receive tasks, already assigned tasks are never duplicated, and concurrent scheduling attempts resolve safely.

**Why this priority**: Data integrity and cluster safety. Two workers or scheduling passes must never assign the same task twice or assign tasks to trainers that are offline, unverified, or actively training.

**Independent Test**: Register trainers in `IDLE`, `BUSY`, and `UNCLEAR` statuses alongside unassigned and previously assigned tasks. Execute scheduling. Verify that only `IDLE` trainers transition to `BUSY` and receive previously unassigned tasks.

**Acceptance Scenarios**:

1. **Given** trainers with statuses `IDLE`, `BUSY`, and `UNCLEAR`, **When** scheduling executes, **Then** only trainers with status `IDLE` receive task assignments; `BUSY` and `UNCLEAR` trainers remain untouched.
2. **Given** tasks that already have a non-empty `TrainerNodeId` assigned, **When** scheduling runs, **Then** those tasks are excluded from scheduling evaluation and retain their existing assignment.
3. **Given** a successful assignment of a task to an idle trainer, **When** committed to the database, **Then** `TrainingTask.TrainerNodeId` is set to the trainer's node ID and `Trainer.Status` is set to `BUSY` within a single database transaction.
4. **Given** a race condition where a task or trainer is claimed concurrently during a scheduling cycle, **When** the update fails, **Then** the scheduler retries the turn and assigns another eligible task/trainer without producing inconsistent state.

---

### User Story 4 - State Reset & Administrative Lifecycle Management (Priority: P4)

As an integration test harness or administrative operator, I want dedicated service methods and API endpoints to clear all registered trainers and training tasks on demand, so that test suites and management routines can establish a pristine, deterministic state between test scenarios.

**Why this priority**: Essential for automated verification, continuous integration, and clean teardown without requiring manual database dropping or schema reconstruction.

**Independent Test**: Populate the database with multiple trainers and tasks. Issue `POST /api/trainers/clear` and `POST /api/training-tasks/clear`. Query the database to verify that both tables contain zero rows and the cursor is reset.

**Acceptance Scenarios**:

1. **Given** a database populated with trainer records, **When** `POST /api/trainers/clear` is invoked, **Then** all trainer records are permanently removed and HTTP 200 OK is returned.
2. **Given** a database populated with training task records, **When** `POST /api/training-tasks/clear` is invoked, **Then** all training task records are permanently removed, the in-memory scheduler cursor is reset to its initial state, and HTTP 200 OK is returned.

---

### User Story 5 - Automated End-to-End Scheduling Verification Suite (Priority: P5)

As a test engineer, I want a complete test sample in `samples/scheduling_test/` containing a Coordinator startup script (`setup.py`), a comprehensive 12-case test suite (`test.py`), and documentation (`README.md`), so that all fairness, FIFO, rotation, status filtering, and concurrency guarantees are verifiably validated against the live Coordinator service.

**Why this priority**: Mandatory per TrainSwarm Constitution Principle VII (Verification, Compilability, and Executable Correctness) and explicit user instructions to ensure zero-mock verification of all specified behaviors.

**Independent Test**: Launch the Coordinator using `setup.py`, execute `test.py`, and observe that all 12 defined test cases execute in sequence, display clear formatted pass/fail outputs with diagnostic details, clear database tables between tests, and exit with status code 0.

**Acceptance Scenarios**:

1. **Given** a live Coordinator instance, **When** `samples/scheduling_test/test.py` is executed, **Then** it sequentially runs Test 1 through Test 12.
2. **Given** each test case execution, **When** the test completes, **Then** the suite verifies exact task-to-trainer assignments, prints a formatted summary to standard output, and executes table clearance before the next case.
3. **Given** `samples/scheduling_test/README.md`, **When** reviewed, **Then** it clearly details the purpose, significance, and execution commands for all 12 test cases.

---

### Edge Cases

- **Zero Pending Tasks**: When scheduling runs with idle trainers but no unassigned tasks, the scheduler returns an empty assignment list immediately; all trainers remain `IDLE`.
- **Zero Idle Trainers**: When unassigned tasks exist but all trainers are `BUSY` or `UNCLEAR`, the scheduler makes zero assignments; all tasks remain unassigned.
- **Empty Queues Throughout Rotation**: When all tasks across all models are completed or assigned, the in-memory rotation list is cleared and the cursor resets gracefully.
- **Equal Submission Timestamps**: When multiple tasks within the same model have identical `SubmitTime` values, the tie is deterministically broken using `TrainingTaskId ASC`.
- **Exhaustion of Single Model During Multi-Trainer Run**: When a model has fewer tasks than available trainers (e.g. Model A has 1 task, Model B has 3 tasks, 4 trainers available), Model A receives 1 assignment and is removed from rotation; remaining turns allocate exclusively to Model B.
- **Node Identifier Determinism**: When multiple trainers are idle, they are selected deterministically by sorting on `TrainerNodeId ASC`.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Domain & Persistence Layer

- **FR-001**: `TrainingTask` entity in `TrainSwarm.Coordinator.Domain.Entities` MUST include a property `DateTime SubmitTime { get; set; }`.
- **FR-002**: `TrainingTaskConfiguration` in Coordinator Infrastructure MUST map `SubmitTime` to the database schema.
- **FR-003**: Coordinator Infrastructure MUST provide an Entity Framework Core migration that adds the `SubmitTime` column to the `TrainingTasks` table.
- **FR-004**: `TrainingTaskService.CreateTrainingTaskAsync` MUST set `SubmitTime = DateTime.Now` on each created `TrainingTask` before persisting it to the database.

#### Application Services Layer

- **FR-005**: `TrainerService` in `TrainSwarm.Coordinator.Application.Services` MUST provide a `ClearTrainersAsync(CancellationToken ct = default)` method that removes all `Trainer` records from the database and returns a success result.
- **FR-006**: `TrainingTaskService` in `TrainSwarm.Coordinator.Application.Services` MUST provide a `ClearTasksAsync(CancellationToken ct = default)` method that removes all `TrainingTask` records from the database, resets the in-memory scheduler cursor to its initial state, and returns a success result.
- **FR-007**: Coordinator Application MUST implement `SchedulerService` in `TrainSwarm.Coordinator.Application.Services` with a method `AssignTasksAsync(CancellationToken ct = default)` that accepts zero input arguments and returns the list of assigned `TrainingTask` records as a direct collection.
- **FR-008**: `SchedulerService` MUST identify unassigned tasks as those satisfying `string.IsNullOrEmpty(task.TrainerNodeId)`. Tasks with an existing non-empty `TrainerNodeId` MUST NOT participate in scheduling.
- **FR-009**: `SchedulerService` MUST identify eligible trainers as those satisfying `trainer.Status == TrainerStatus.IDLE`. Trainers with `BUSY` or `UNCLEAR` status MUST NOT be assigned tasks.
- **FR-010**: `SchedulerService` MUST group unassigned tasks by `TrainingTask.ModelId`, creating an independent queue per model.
- **FR-011**: Within each model queue, tasks MUST be sorted strictly in ascending order of `SubmitTime ASC`, using `TrainingTaskId ASC` as a deterministic tie-breaker for identical timestamps.
- **FR-012**: `SchedulerService` MUST maintain an in-memory cursor representing the next model eligible to receive a scheduling turn across successive invocations; this cursor MUST reset to its initial state when `ClearTasksAsync` is called or when all task queues are completely empty.
- **FR-013**: In each scheduling turn, `SchedulerService` MUST search from the current cursor for the next model with pending tasks, select that model's oldest pending task, and advance the cursor to the subsequent model.
- **FR-014**: If a selected model has no remaining unassigned tasks after an assignment, it MUST be removed from the active rotation for that cycle.
- **FR-015**: When multiple idle trainers are available, `SchedulerService` MUST repeatedly execute scheduling decisions until either no idle trainers remain or no unassigned tasks remain, maximizing trainer utilization.
- **FR-016**: Trainer selection from the pool of idle trainers MUST be deterministic, ordering eligible trainers by `TrainerNodeId ASC`.
- **FR-017**: Assignment of each task to a trainer MUST update `TrainingTask.TrainerNodeId = trainer.TrainerNodeId` and `Trainer.Status = TrainerStatus.BUSY`, persisted atomically within a database transaction.
- **FR-018**: If a concurrent modification invalidates an assignment before persistence, `SchedulerService` MUST discard the failed selection and retry scheduling for remaining eligible resources.

#### API Controllers Layer

- **FR-019**: Coordinator API MUST implement `SchedulingController` under route `api/scheduler` exposing `POST /api/scheduler/assign` that executes `SchedulerService.AssignTasksAsync` and returns HTTP 200 OK directly containing a JSON list of assigned task objects: `[{ trainingTaskId, modelId, trainerNodeId, shardId, submitTime }]`.
- **FR-020**: `TrainerController` MUST expose an HTTP POST endpoint at `POST /api/trainers/clear` that executes `TrainerService.ClearTrainersAsync` and returns HTTP 200 OK.
- **FR-021**: `TrainingTaskController` MUST expose an HTTP POST endpoint at `POST /api/training-tasks/clear` that executes `TrainingTaskService.ClearTasksAsync` and returns HTTP 200 OK.

#### Samples & Automated Verification Suite

- **FR-022**: A sample suite MUST be created under `samples/scheduling_test/` containing `setup.py`, `test.py`, and `README.md`.
- **FR-023**: `samples/scheduling_test/setup.py` MUST start the Coordinator web API process and confirm readiness before test execution.
- **FR-024**: `samples/scheduling_test/test.py` MUST execute all 12 required test cases via the Coordinator HTTP APIs:
  - **Test 1**: Single model (FIFO assignment, remaining tasks stay unassigned).
  - **Test 2**: Basic model fairness (Round-robin turn allocation across models A, B, C).
  - **Test 3**: More trainers than models (Full utilization of idle trainers beyond single round).
  - **Test 4**: Model with only one task & cursor continuity across separate scheduling calls.
  - **Test 5**: Strict FIFO ordering preservation within a single model.
  - **Test 6**: Large volume imbalance (Model A with 10 tasks, Models B and C with 1 task; starvation prevention).
  - **Test 7**: Trainer status filtering (Only `IDLE` receive tasks; `BUSY` and `UNCLEAR` excluded).
  - **Test 8**: Zero tasks (Trainers remain `IDLE`, zero assignments returned).
  - **Test 9**: Zero idle trainers (Tasks remain unassigned, zero assignments returned).
  - **Test 10**: Pre-assigned task isolation (Tasks with existing `TrainerNodeId` are ignored).
  - **Test 11**: Model exhaustion removal (Model removed from rotation once queue empty; remaining capacity goes to active models).
  - **Test 12**: Deterministic tie-breaking for tasks with identical `SubmitTime` via `TrainingTaskId ASC`.
- **FR-025**: `samples/scheduling_test/test.py` MUST cleanly format test results to standard output indicating pass/fail status and assignment details, and clear all trainer and task records between test runs using the clear endpoints.
- **FR-026**: `samples/scheduling_test/README.md` MUST detail each test case, explain its architectural significance, and document step-by-step instructions for executing the test suite.

---

### Key Entities

- **TrainingTask (Coordinator Domain)**: Represents a scheduled computational task partitioned for a model.
  - `TrainingTaskId`: `Guid` unique primary identifier.
  - `ClientNodeId`: `string` identifier of the submitting client.
  - `ModelId`: `string` identifier of the machine learning model.
  - `ModelVersion`: `string` version descriptor.
  - `DataSetId`: `string` dataset identifier.
  - `ShardId`: `string` partition identifier.
  - `TrainerNodeId`: `string` identifier of assigned trainer (empty if unassigned).
  - `SubmitTime`: `DateTime` timestamp recording task creation time (`DateTime.Now`).
- **Trainer (Coordinator Domain)**: Represents a registered worker node in the control plane.
  - `Id`: `Guid` unique primary identifier.
  - `TrainerNodeId`: `string` identifier of the trainer node.
  - `Status`: `TrainerStatus` enum (`UNCLEAR`, `IDLE`, `BUSY`).
- **AssignedTaskResponseDto**: Representation of an assigned task returned by `POST /api/scheduler/assign`.
  - `TrainingTaskId`: `Guid` identifier of the task.
  - `ModelId`: `string` model identifier.
  - `TrainerNodeId`: `string` identifier of the assigned trainer node.
  - `ShardId`: `string` dataset partition identifier.
  - `SubmitTime`: `DateTime` task submission timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Starvation Prevention**: In a mixed workload with one dominant model (10+ tasks) and minor models (1 task each), minor models receive scheduling turns within the first round of assignments across idle trainers.
- **SC-002**: **Trainer Utilization**: 100% of available idle trainers are assigned tasks on each scheduling invocation as long as unassigned tasks remain in the queue.
- **SC-003**: **FIFO Integrity**: 100% of tasks assigned within any individual model adhere strictly to `SubmitTime ASC` (and `TrainingTaskId ASC` tie-breaking).
- **SC-004**: **Status Safety**: 0% of tasks are assigned to trainers whose status is `BUSY` or `UNCLEAR`.
- **SC-005**: **Zero Mocks**: All 12 automated verification test cases execute against the live Coordinator HTTP API and SQLite database with zero mocks or simulated calls.
- **SC-006**: **Clean Lifecycle**: Invoking clear endpoints guarantees 0 lingering records in `Trainers` and `TrainingTasks` tables and resets the scheduler cursor, allowing 100% independent and repeatable test runs.

---

## Assumptions

- **Single Coordinator Instance**: The in-memory cursor is maintained within a single active Coordinator instance (e.g. singleton or persistent application service). Multi-instance distributed coordination is out of scope for the current MVP.
- **Timestamp Precision**: `SubmitTime` uses standard .NET `DateTime.Now` persisted via SQLite/EF Core. In scenarios where multiple tasks are created in the same millisecond or batch, the secondary tie-breaker `TrainingTaskId ASC` provides deterministic ordering.
- **HTTP Endpoint Routing**: Standard REST routes are provided: `POST /api/scheduler/assign`, `POST /api/trainers/clear`, and `POST /api/training-tasks/clear`.
- **Test Harness Environment**: Python 3.x with `requests` library is used in `samples/scheduling_test/` to interact with Coordinator HTTP endpoints.
