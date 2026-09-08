# Feature Specification: Completing Submit Flow

**Feature Branch**: `018-complete-submit-flow`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "Completing Submit Flow\n-----\n1- model data persistence in client\nin Client\nin models\\\n\tthere should be a Model Enity that saves general model data \n\tmodel_id: str -> model generated id when submited\n    \tmodel_type: str -> model type that is distrubuted training engine model type enum\n   \tmodel_version: str -> current version\n    \tdataset_id: str -> generated dataset id when training is submited\n\tmodel_artifact_path : str -> full path to model artifact : saved in submit training command handler\n\ttraining_config_path : str -> full path to model training config json file : saved in submit training command handler\nin infrastructure\\\n\tin persistence\\ there should be a new repository for the table storing the model data. called ModelRepository and it should has 2 method\n\tsave : get a Model entity and save it to models table\n\tget_by_model_id : it gets a model id in input and returns the Model entity corrispoinding that model id and if it does not exists riase exception \nin application\\\n\tin submit training command after shards data is persisted create the Modle entity instance and save it via model repository\n\tmake it another step in submitting and send logs and traces like othe steps\n-------\n2- dispatch commands in coordinator\nin Coordinator\nin commands\\ update StartTrainingCommand and remove its data and instead add this fields to it\n    public string ClientNodeId { get; set; }\n    public string ModelId { get; set; }\n    public string ModelVersion { get; set; }\n    public string DataSetId { get; set; }\n    public string ShardId { get; set; }\n\tin services\\SchedulerService\n\tif assigning process was successfull and training tasks were existed taht being assigned trainer in the current run (result was not empty)\n\tfor trainers that become busy and have a new training task now create a StartTrainingCommand and using command sender push it to trainer\nin services\\TrainingTaskService\n\tafter a training task is saved and befor sending save result back to client use the scheduling service and run assign tasks but \n\tAssign Task MUST be tread safe and probaboly inside lock and Assign Task MUST be exesuted in background and does not block the current thread \n\tbut it's log must not be vanished and logs in terminal must be consistant and tracalbe\nflow of scheduling and pushing commands must be clear and has proper loging and must be tracable via logs and check the steps and detail\n-----\n3- receive command in trainer\nin presentation\\\n\tin main.py move logic of registering trainers and listener and creating connection to startup.py and call it in main.py\nin application\\\n\tupdate start training command fileds as its updated in coordinator commands\n\tint start training command handler for now just log the received data\n-----\nsamples\\\nin samples there should be task_assignment_test\\\ninside this test in startup.py : first coordinator then the trainer and lastly client must be started (not dockerised -> using command line) \n\tthen create a simple canonical torch model a tiny canonical torchmodel dataset and save them as pt2 and pt file. and save training config.json file.\nthen there should be a submit.py file : using client cli submit a new training task for created model and data set\nverification : from logs of these 3 module tarinign task and model must be created in client database and shards and model artifact must be in client's working directory and create training task must be sent to coordinator\n\t\tinside coordiantor task must be saved and scheduler should be run and assing task to trainer then push start training to trainer\n\t\tand in trainer it must receive the command and log its values"

## Clarifications

### Session 2026-09-08

- Q: If persisting the `Model` entity fails in the client submission pipeline, how should the workflow proceed? → A: Abort the submission immediately, log the failure, leave shards in `CREATED` state, and do not contact the Coordinator (Option A).
- Q: If pushing the `StartTrainingCommand` to an assigned trainer fails during the scheduling cycle, how should the Coordinator handle the task assignment? → A: Revert the assignment in the database (resetting `TrainerNodeId` to empty and trainer status to `UNCLEAR`) and log the event (Option B).
- Q: How should `samples/task_assignment_test/startup.py` manage the running services across test steps? → A: Spawn Coordinator and Trainer as background processes with tracked PIDs, generate artifacts, allowing `submit.py` to run in the same terminal (Option A).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Client Model Metadata Persistence & Staging Tracking (Priority: P1)

As a distributed training client operator or system, I want model metadata (including model ID, type, version, dataset ID, and local artifact/config filesystem paths) to be persisted in a dedicated local `models` database table via a `ModelRepository` during the training submission workflow, so that model submissions are locally tracked and auditable alongside their partitioned shards.

**Why this priority**: Core persistence foundation for training submissions in the Client. Without model entity persistence, the client tracks individual shards but lacks top-level model record ownership, artifact path tracking, and queryability by `model_id`.

**Independent Test**: Instantiate a `Model` entity with staged model and configuration paths, invoke `ModelRepository.save(model)` to write to SQLite, and invoke `ModelRepository.get_by_model_id(model_id)` to verify accurate retrieval. Also assert that attempting to retrieve an unpersisted `model_id` raises a dedicated exception (`ModelNotFoundError`).

**Acceptance Scenarios**:

1. **Given** a new training submission executed via `SubmitTrainingCommandHandler`, **When** dataset shards have been partitioned and saved locally, **Then** the handler instantiates a `Model` entity containing `model_id`, `model_type`, `model_version`, `dataset_id`, `model_artifact_path` (staged `.pt2` file path), and `training_config_path` (staged configuration JSON file path).
2. **Given** the instantiated `Model` entity, **When** persisted via `ModelRepository.save()`, **Then** the record is stored in the `models` table in the client SQLite database.
3. **Given** model persistence in `SubmitTrainingCommandHandler`, **When** executed, **Then** it forms a distinct, observable step in the submission workflow with progress reporting (percentage updates) and structured log traces.
4. **Given** a persisted model record, **When** `ModelRepository.get_by_model_id(model_id)` is invoked with an existing identifier, **Then** the corresponding `Model` entity is returned with all attributes matching the persisted record.
5. **Given** a request for a non-existent `model_id`, **When** `ModelRepository.get_by_model_id(model_id)` is called, **Then** the repository raises a `ModelNotFoundError`.
6. **Given** an error or database failure during `ModelRepository.save()`, **When** the exception occurs, **Then** `SubmitTrainingCommandHandler` logs the error, leaves all persisted shards in `CREATED` state, halts further execution without contacting the Coordinator, and returns a failed `SubmitTrainingResult`.

---

### User Story 2 - Coordinator StartTrainingCommand Dispatch to Assigned Trainers (Priority: P2)

As a Coordinator scheduling service, I want newly assigned idle trainers to immediately receive an updated `StartTrainingCommand` pushed via gRPC when tasks are assigned during a scheduling cycle, so that trainers receive the exact metadata needed (`ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, `ShardId`) to execute distributed training.

**Why this priority**: Enables the control plane to actively drive training work to trainers. Without dispatching `StartTrainingCommand` upon successful assignment, scheduled tasks remain idle in the database and trainers never receive instructions to start.

**Independent Test**: Register an idle trainer and an unassigned training task in the Coordinator. Invoke `SchedulerService.AssignTasksAsync()`. Verify that the task is assigned to the trainer, trainer status becomes `BUSY`, and `ICommandCenter.SendAsync()` pushes a `StartTrainingCommand` with the 5 required fields to the trainer's command stream.

**Acceptance Scenarios**:

1. **Given** `StartTrainingCommand` in the Coordinator, **When** inspected, **Then** its properties are `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId` (with legacy fields `TrainingClientNodeId` and `SessionId` removed).
2. **Given** `SchedulerService.AssignTasksAsync()` completes a scheduling run where one or more training tasks are assigned to idle trainers, **When** evaluating the newly assigned tasks, **Then** for each assigned trainer that transitioned to `BUSY`, the scheduler constructs a `StartTrainingCommand` with the task's `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`.
3. **Given** constructed `StartTrainingCommand` instances, **When** dispatched, **Then** the scheduler uses `ICommandCenter` to push each command to the respective trainer node.
4. **Given** the scheduling and dispatch process, **When** executed, **Then** comprehensive, traceable logs detailing model selection, trainer assignment, and command dispatch outcomes are emitted to the logging pipeline.
5. **Given** a command dispatch failure when sending `StartTrainingCommand` to an assigned trainer via `ICommandCenter.SendAsync()`, **When** the error is caught, **Then** the scheduler reverts the task assignment in the database (resetting `TrainingTask.TrainerNodeId` to empty string) and marks the trainer's status as `UNCLEAR`, committing the reversion and emitting detailed diagnostic error logs.

---

### User Story 3 - Asynchronous Background Safe Task Scheduling (Priority: P3)

As a distributed coordinator API, I want training task registration to trigger task scheduling in a thread-safe background execution immediately before returning the creation response to the client, so that client submissions are not delayed by scheduler execution while task assignment and dispatch proceed concurrently and safely.

**Why this priority**: Guarantees responsive client API interactions and prevents thread blocking or deadlocks during task creation, while ensuring thread-safe scheduler execution and reliable terminal trace outputs.

**Independent Test**: Submit a batch of training tasks via `TrainingTaskService.CreateTrainingTaskAsync()`. Verify that the HTTP/service call returns successfully with generated task IDs before the background scheduling run finishes, and verify that scheduling executes under thread-safe synchronization (concurrency lock) without losing terminal logs.

**Acceptance Scenarios**:

1. **Given** a training task creation request in `TrainingTaskService`, **When** the tasks are persisted in the database and validated, **Then** `SchedulerService.AssignTasksAsync()` is initiated in the background before the save response is returned to the client.
2. **Given** concurrent calls to create tasks or run scheduling, **When** multiple operations invoke scheduling, **Then** execution is guarded by thread-safe synchronization (such as an asynchronous lock or semaphore) so that only one assignment cycle executes at a time.
3. **Given** background scheduler execution, **When** it runs asynchronously, **Then** its terminal output and logs remain intact, consistent, and traceable without being swallowed or truncated.
4. **Given** an error occurring inside the background scheduler execution, **When** an exception is raised, **Then** it is logged with full stack traces and does not crash the Coordinator host process or invalidate already-saved tasks.

---

### User Story 4 - Trainer Modular Startup and StartTrainingCommand Ingestion (Priority: P4)

As a Trainer node, I want my startup registration, coordinator connection guard, and gRPC command listener unified in `presentation/startup.py`, and my `StartTrainingCommand` handler updated to parse and log the new payload fields, so that trainer initialization is clean and task dispatch commands are observed.

**Why this priority**: Streamlines trainer initialization architecture, reduces duplication across entry points, and ensures the trainer data plane is fully compatible with the updated Coordinator command contract.

**Independent Test**: Launch the Trainer via `main.py` (which delegates registration and listener setup to `startup.py`). Send a synthetic `StartTrainingCommand` containing `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`. Assert that the command handler receives and logs all 5 fields clearly.

**Acceptance Scenarios**:

1. **Given** `presentation/startup.py` in the Trainer, **When** invoked by `main.py`, **Then** it encapsulates trainer registration with the Coordinator, connection health checking, and starting the background `TrainerCommandListener`.
2. **Given** the application model `StartTrainingCommand` in the Trainer, **When** deserialized from an incoming Coordinator command, **Then** it parses `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`.
3. **Given** `StartTrainingHandler.handle()` receiving the updated command, **When** executed, **Then** it logs the received model ID, dataset ID, shard ID, client node ID, and model version to standard output / logger.

---

### User Story 5 - Non-Dockerized End-to-End Verification Test Sample (Priority: P5)

As a QA or platform engineer, I want an end-to-end verification sample in `samples/task_assignment_test/` that starts the Coordinator, Trainer, and Client from the command line (without Docker), creates a synthetic canonical PyTorch model and dataset, submits a training task via the Client CLI, and validates that model metadata, Coordinator scheduling, and Trainer command reception occur successfully across the cluster, so that the complete submit and assignment flow is verifiable per Constitution Principle VII.

**Why this priority**: Required by the TrainSwarm Constitution (Principle VI: Real Functional Implementations, Principle VII: Executable Correctness) and explicit user instructions to prove the entire multi-service integration works end-to-end in real runtime execution.

**Independent Test**: Execute `startup.py` in `samples/task_assignment_test/` to spin up services and synthesize test assets, followed by `submit.py` to trigger client submission. Verify through process logs and database queries that the task is created, scheduled, and received by the trainer.

**Acceptance Scenarios**:

1. **Given** `samples/task_assignment_test/startup.py`, **When** executed, **Then** it starts Coordinator via dotnet CLI and Trainer via python CLI as detached background processes, records their process IDs to `.test_pids.txt`, waits for their readiness/health endpoints, generates a valid canonical PyTorch model checkpoint (`.pt2`), a tiny PyTorch dataset (`.pt`), and `training_config.json`, and returns ready.
2. **Given** `samples/task_assignment_test/submit.py`, **When** executed, **Then** it invokes the Client CLI (`python main.py submit-training ...`) using the generated model, dataset, and configuration.
3. **Given** the test execution, **When** verified, **Then**:
   - The Client SQLite database contains persisted records in both `models` and `training_shards` tables.
   - The Client working directory contains staged model artifacts (`.pt2`), configuration JSON, and partitioned dataset shards.
   - The Coordinator database reflects the saved training task and updates `TrainerNodeId` with the assigned trainer.
   - The Trainer process log confirms receipt of `StartTrainingCommand` with all 5 matching field values.
4. **Given** completion or teardown, **When** `clean.py` is invoked, **Then** all spawned processes are terminated cleanly and temporary databases/test directories are removed.

---

### Edge Cases

- **SQLite Database Lock Contention in Client**: How does `ModelRepository` handle database locks when writing the `Model` entity immediately following bulk shard insertion? Transactions must use appropriate busy timeouts and scoped connection management.
- **Duplicate Model ID Persistence**: What happens if `ModelRepository.save()` receives a `Model` with an ID that already exists? It must raise a descriptive persistence conflict error or enforce primary key constraints.
- **Model Persistence Failure Handling**: If `ModelRepository.save()` fails (e.g. database error, lock timeout, or constraint violation), `SubmitTrainingCommandHandler` immediately halts the workflow, leaves shards stored as `CREATED` in SQLite, logs diagnostic error traces, and does not dispatch task creation requests to the Coordinator.
- **Trainer Disconnection During Command Dispatch**: If pushing `StartTrainingCommand` to an assigned trainer fails via `ICommandCenter.SendAsync()`, `SchedulerService` catches the failure, reverts the assignment in the database (resetting `TrainingTask.TrainerNodeId` to empty string), updates `trainer.Status` to `UNCLEAR`, and logs the dispatch error, ensuring the unassigned task can be picked up by a healthy trainer in subsequent cycles.
- **Empty or Partial Shard List**: What happens if a submission contains zero shards or partitioning fails before model persistence? Model persistence must only occur after shards are successfully partitioned and persisted; if shard persistence fails, model persistence does not occur.
- **Coordinator Background Thread Concurrency**: If multiple clients submit training tasks simultaneously, does `AssignTasksAsync()` run concurrently? A thread-safe locking mechanism (`SemaphoreSlim(1, 1)`) must serialize scheduling executions while allowing background execution without blocking API HTTP request handling.
- **Missing Fields in Trainer Deserialization**: How does Trainer handle an incoming `StartTrainingCommand` payload missing one of the required fields? It must raise a descriptive validation error and log the malformed payload details without terminating the command listener loop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a `Model` entity in `Client/models/` (or `Client/domain/`) with fields `model_id: str`, `model_type: str`, `model_version: str`, `dataset_id: str`, `model_artifact_path: str`, and `training_config_path: str`.
- **FR-002**: System MUST define an `IModelRepository` interface and a SQLite implementation `ModelRepository` in `Client/infrastructure/persistence/` supporting `save(model: Model) -> None` and `get_by_model_id(model_id: str) -> Model`.
- **FR-003**: `ModelRepository.get_by_model_id()` MUST raise a `ModelNotFoundError` when the specified `model_id` does not exist in the database.
- **FR-004**: System MUST initialize a `models` table in the Client SQLite database schema idempotently with columns: `model_id TEXT PRIMARY KEY NOT NULL`, `model_type TEXT NOT NULL`, `model_version TEXT NOT NULL`, `dataset_id TEXT NOT NULL`, `model_artifact_path TEXT NOT NULL`, `training_config_path TEXT NOT NULL`.
- **FR-005**: `SubmitTrainingCommandHandler` in Client MUST persist the `Model` entity using `ModelRepository` as a dedicated, observable step immediately after shards data is persisted locally; if model persistence fails, the handler MUST abort the workflow, leave shards in `CREATED` status, and NOT contact the Coordinator.
- **FR-006**: `SubmitTrainingCommandHandler` MUST report progress and emit structured log traces for the model persistence step.
- **FR-007**: Coordinator `StartTrainingCommand` MUST be updated to contain properties `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`, removing legacy `TrainingClientNodeId` and `SessionId`.
- **FR-008**: Coordinator `SchedulerService.AssignTasksAsync()` MUST inspect newly assigned tasks and, for each assigned trainer transitioning to `BUSY`, create a `StartTrainingCommand` with the task's `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`.
- **FR-009**: Coordinator `SchedulerService` MUST push the constructed `StartTrainingCommand` to the assigned trainer via `ICommandCenter.SendAsync()`; if dispatch fails, the scheduler MUST revert the task assignment in the database (clearing `TrainerNodeId`), set the trainer's status to `UNCLEAR`, and log the failure.
- **FR-010**: Coordinator `TrainingTaskService.CreateTrainingTaskAsync()` MUST trigger `SchedulerService.AssignTasksAsync()` in the background before returning the task creation response to the client.
- **FR-011**: The background scheduling invocation in `TrainingTaskService` MUST be thread-safe (guarded against concurrent overlapping execution) and MUST NOT block the calling HTTP request thread.
- **FR-012**: The background scheduling invocation MUST preserve all logs and output them consistently to the terminal and logging system without losing trace visibility.
- **FR-013**: Trainer `presentation/main.py` MUST delegate trainer registration, coordinator connection guard, and command listener initialization to `presentation/startup.py`.
- **FR-014**: Trainer `StartTrainingCommand` application model MUST be updated to parse and represent `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`.
- **FR-015**: Trainer `StartTrainingHandler` MUST log all received command fields (`ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, `ShardId`) upon command reception.
- **FR-016**: A new test sample MUST be created in `samples/task_assignment_test/` containing `startup.py` (spawning Coordinator and Trainer as background processes with PIDs tracked in `.test_pids.txt`, waiting for readiness, and generating synthetic Torch model/dataset artifacts), `submit.py` (executing Client CLI training submission in the same terminal), and `clean.py` (terminating tracked background processes and deleting temporary databases/artifacts).
- **FR-017**: The test sample MUST verify end-to-end that client models and shards are persisted in the client database, tasks are created in the coordinator database, tasks are assigned to the trainer, and the trainer receives and logs the dispatched `StartTrainingCommand`.

### Key Entities

- **Model**: Client domain entity representing top-level metadata for a submitted model:
  - `model_id` (string, UUID)
  - `model_type` (string, engine enum value)
  - `model_version` (string)
  - `dataset_id` (string, UUID)
  - `model_artifact_path` (string, absolute or working-directory path to `.pt2`)
  - `training_config_path` (string, absolute or working-directory path to `.json`)
- **StartTrainingCommand**: Cross-service control-plane command DTO sent from Coordinator to Trainer:
  - `ClientNodeId` (string)
  - `ModelId` (string)
  - `ModelVersion` (string)
  - `DataSetId` (string)
  - `ShardId` (string)
- **TrainingTask**: Coordinator control-plane entity representing a single shard assignment for a model:
  - `TrainingTaskId` (Guid)
  - `ClientNodeId` (string)
  - `ModelId` (string)
  - `ModelVersion` (string)
  - `DataSetId` (string)
  - `ShardId` (string)
  - `TrainerNodeId` (string)
  - `SubmitTime` (DateTime)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Training submission workflow completes 100% of its steps (staging, sampling, smoke testing, shard partitioning, shard persistence, model persistence, and coordinator dispatch) without manual intervention.
- **SC-002**: Local model metadata is queryable via `get_by_model_id()` within 50ms of submission completion.
- **SC-003**: Task creation response is returned to the Client immediately without waiting for background scheduling and command push to complete.
- **SC-004**: 100% of newly assigned training tasks trigger a `StartTrainingCommand` dispatched to the assigned trainer node.
- **SC-005**: Trainer command listener successfully ingests and logs the dispatched command within 5 seconds of task assignment in the test environment.
- **SC-006**: End-to-end non-dockerized verification in `samples/task_assignment_test/` executes successfully with exit code 0, validating all assertions across Client, Coordinator, and Trainer.

## Assumptions

- **SQLite for Local Client Persistence**: Client uses local SQLite persistence via `DatabaseManager` as established in previous features (`specs/011-training-shard-persistence` and `specs/015-client-submit-training`).
- **Command Dispatch Transport**: The Coordinator uses the existing gRPC bidirectional streaming connection established by the Trainer via `TrainerCommandListener` and `ICommandCenter`.
- **Background Scheduling Mechanism**: In `TrainingTaskService`, background scheduling can be safely launched using standard .NET asynchronous patterns (`Task.Run` with dependency injection scope or hosted background service) guarded by `SemaphoreSlim(1, 1)` to guarantee thread safety.
- **Canonical PyTorch Format**: Test artifacts in `samples/task_assignment_test/` use the canonical PyTorch 2 format (`Simple1DCNN` exported as `.pt2` and dictionary tensors saved as `.pt`) compatible with `distributed_training_engine`.
- **No Docker Required for Sample**: Unlike `samples/submit_training_test/`, `samples/task_assignment_test/` runs all components as native host processes (dotnet CLI and python CLI), matching the user request.
