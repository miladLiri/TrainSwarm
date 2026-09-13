# Feature Specification: Model Update Follow-up & Distributed Aggregation Lifecycle

**Feature Branch**: `020-update-model-followup`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description:
```text
update model follow up

this specificaiton expads the functionality of the update model command handler in Client/applicaion/commands/update_model_command

1- in coordinator
in coordinator in application in trainer service we need a new method called DetachTrainer
in DetachTrainerRequest this might be trainer node id and a bool IsTrainingCompelete
inside method it should first look up trainer with trainer node id if its status was not busy do nothing and return errorOr success 
and if it was busy
if IsTrainingComplete was true then status must be changed to idle
if IsTrainingComplete was false then status must be unknown
in api layer there must be a api coorisponding this service in TrainerController

-----

2- in client
in infrastructure\adapters\coordinator_adapter.py
there should be a method for calling the api for detach trainer and handle its result 

in application\
    in update_model_command after saving result in local db it should uses the coordinator adapter and detach the trainer with trainer node id and is training complete as true

    after detaching the trainer handler must do a check if all the shards with current model id and current model version and dataset id is complete or not and this check must happen in lock so no concurrency effects the check 
    if its complete it should use the aggregation orchestrator and creates a aggregation request and do the aggregation process 
    the whole update model process must be have proper logging and tracablity for console and gui

    in state.py create a new state variable that called Submitted with default value of false
    when submitting task is done in its command handler must update the state of submitted to true
    and if it was true does not get new training for submit and reject the request with an error

    in update_model_command_handler if aggregation is happend and new version created make submitted to false 

in presentaion\
    in gui\ as a tab and in console_ui as a switch make an option to watch current training shards
    in a table with model id, version, shard id and status wiht a referech button 

    also in gui\ created tab for trained versions that shows each model id with its version that is trained and a save button that get the location and save the artifact to taht location

    for these presentation services create required query and query handler in /application/queries

-----

3- in samples/
    update full_distributed_training_test verify taht after both trainer send tahtir update expects a new version artifact and in a evaluation test load both models and compare their traing loss 
    and also trainers must back to idle status 
    for checking coordianator you can wirte get services in coordinator application TranerService and TrainingTaskService and expose api for them
    
    also create a clean.py taht stop the services and clean the created artifacts

    run the test and make sure it works correctly and prompt the steps and result
```

## Clarifications

### Session 2026-09-13

- Q: How should model version identifiers be formatted and incremented when transitioning from the initial training submission to the aggregated model checkpoint? → A: Require integer-compatible version strings (e.g., "1"), converting to integer for aggregation and incrementing by +1 (e.g., "2") (Option A).
- Q: How should the Client local database store and identify multiple trained versions for the same model ID? → A: Use a composite primary key (model_id, model_version) in the models table, keeping each version as a distinct record (Option A).
- Q: How should the console UI expose the switch to watch current training shards and handle its refresh action? → A: Dedicated CLI subcommand `watch-shards` that renders an aligned table and prompts the user to press Enter to refresh or 'q' to quit (Option A).
- Q: What assertion criteria should determine whether the model loss evaluation passes in `full_distributed_training_test`? → A: Strictly assert `aggregated_loss < base_loss` alongside finite value checks (no NaN/Inf), tuning dataset and steps to guarantee reduction (Option A).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coordinator Trainer Detachment and Lifecycle State Tracking (Priority: P1)

As a distributed training control plane coordinator, I want to expose a detach trainer service and API endpoint so that when a trainer node finishes its work or disconnects, its execution state transitions back to IDLE (if complete) or UNCLEAR/UNKNOWN (if incomplete) only when currently BUSY, allowing the cluster to safely reassign or monitor trainer resources.

**Why this priority**: Foundational control plane lifecycle management. Without an explicit detachment mechanism, trainers remain locked in BUSY status on the Coordinator indefinitely following training completion, preventing subsequent task scheduling and cluster status auditing.

**Independent Test**: Register a trainer with the Coordinator, transition it to BUSY, invoke the detach API with `is_training_complete=true`, and assert via query API that its status transitions to IDLE. Then test with `is_training_complete=false` and assert transition to UNCLEAR. Test when the trainer is already IDLE and assert a successful no-op.

**Acceptance Scenarios**:

1. **Given** a registered trainer with status `BUSY`, **When** a detach request is received with `is_training_complete=true`, **Then** the Coordinator updates the trainer record's status to `IDLE` in the database, emits structured audit logs, and returns a successful result.
2. **Given** a registered trainer with status `BUSY`, **When** a detach request is received with `is_training_complete=false`, **Then** the Coordinator updates the trainer record's status to `UNCLEAR` (unknown) in the database, logs the incomplete detachment, and returns a successful result.
3. **Given** a registered trainer with status `IDLE` or `UNCLEAR`, **When** a detach request is received, **Then** the Coordinator does not modify the trainer status and returns a successful result.
4. **Given** an invalid or unknown `trainer_node_id`, **When** a detach request is received, **Then** the Coordinator returns a distinct failure/validation error.
5. **Given** the Coordinator REST API, **When** `POST /api/trainers/detach` is called with a JSON payload containing `trainerNodeId` and `isTrainingComplete`, **Then** it maps the request to the application service and returns HTTP 200 OK or appropriate error codes.
6. **Given** the Coordinator application services `TrainerService` and `TrainingTaskService`, **When** queried, **Then** they provide query methods (`GetTrainersAsync` and `GetTrainingTasksAsync`) exposed via GET endpoints on `TrainerController` and `TrainingTaskController` to inspect real-time cluster state.

---

### User Story 2 - Client Training Update Ingestion, Trainer Detachment, and Automated Aggregation (Priority: P2)

As a distributed training client node, I want the update model command handler to detach the trainer via the Coordinator adapter upon receiving and persisting a shard training update, evaluate under a thread-safe lock whether all shards for the active session are completed, and automatically trigger the model aggregation orchestrator to produce a new model version artifact when all shards finish.

**Why this priority**: Essential distributed training closure. Completes the round lifecycle by persisting local shard updates, freeing cluster trainers in the control plane, and synthesizing fine-tuned weights into an updated model version without manual intervention.

**Independent Test**: Simulate two training shard updates arriving at the Client. Verify that each update triggers a Coordinator adapter detach call. Verify that after the second shard update, the concurrency lock prevents duplicate triggers, the aggregation orchestrator executes federated averaging on the two updates, and a new model checkpoint file is saved in the working directory.

**Acceptance Scenarios**:

1. **Given** a completed shard training result received by `UpdateModelCommandHandler`, **When** the shard record and update delta artifact path are persisted to the local database, **Then** the handler invokes `CoordinatorAdapter.detach_trainer` with the trainer node ID and `is_training_complete=True`.
2. **Given** a completed trainer detachment, **When** the handler evaluates shard completion, **Then** the check is executed inside a thread-safe concurrency lock to prevent race conditions from concurrent update submissions.
3. **Given** all dataset shards for the current `(model_id, model_version, dataset_id)` are marked `COMPLETED` in the database, **When** evaluated under lock, **Then** the handler constructs an `AggregationRequest` and invokes `AggregationOrchestrator.Aggregate()`.
4. **Given** successful aggregation execution, **When** the new version checkpoint is written to disk, **Then** the new model version is registered/persisted in the local models store.
5. **Given** one or more shards are still pending completion, **When** an update arrives, **Then** the handler records the shard and detaches the trainer, but does not trigger the aggregation orchestrator.
6. **Given** any step in the update model and aggregation flow, **When** progress changes or errors occur, **Then** comprehensive structured log events are emitted for terminal output and GUI monitoring.

---

### User Story 3 - Client Training Submission Lock and State Guard (Priority: P3)

As a distributed training operator, I want the Client state to maintain an in-memory `submitted` boolean guard that is set to `true` upon task submission, rejects overlapping training submissions while active, and automatically resets to `false` when model aggregation finishes, so that concurrent or conflicting training jobs cannot corrupt in-flight sessions.

**Why this priority**: Ensures system consistency and operational safety. Prevents operators or automated scripts from initiating competing training jobs on top of an unresolved active submission round.

**Independent Test**: Check that default state is `submitted = False`. Execute a training submission and verify state transitions to `submitted = True`. Attempt to submit another training job and verify the handler immediately rejects it with a clear error. Execute shard updates and aggregation to completion, and verify state resets to `submitted = False`.

**Acceptance Scenarios**:

1. **Given** the initial startup of the Client application, **When** inspecting `ClientState.submitted`, **Then** its default value is `False`.
2. **Given** a successful training submission executed through `SubmitTrainingCommandHandler`, **When** shards are saved and tasks registered, **Then** `ClientState.submitted` is updated to `True`.
3. **Given** `ClientState.submitted` is `True`, **When** another training submission is requested via CLI or GUI, **Then** the submission is immediately rejected with a descriptive validation error (e.g., "A training task is already submitted and in progress").
4. **Given** `ClientState.submitted` is `True`, **When** the final shard update is processed and model aggregation successfully creates a new version artifact, **Then** `UpdateModelCommandHandler` sets `ClientState.submitted` back to `False`.

---

### User Story 4 - Presentation Views: Active Shards Watch and Trained Version Export (Priority: P4)

As a Client operator using either the GUI or Console UI, I want dedicated views to inspect the live status of all training shards for active models with a refresh option, and a dedicated GUI tab to view completed model versions and export/save their model artifacts to a chosen directory, backed by decoupled Clean Architecture application queries.

**Why this priority**: Operational visibility and usability. Operators need real-time feedback on which shards are training vs completed, and a straightforward way to extract trained model checkpoints for downstream inference or deployment.

**Independent Test**: Invoke `GetTrainingShardsQuery` and `GetTrainedModelsQuery` handlers directly against the database and assert correct DTO lists. Launch the GUI and verify the "Training Shards" table and "Trained Versions" table with functional Save file dialog. In the Console UI, run the `--watch-shards` switch/subcommand to verify formatted terminal table output.

**Acceptance Scenarios**:

1. **Given** the application layer `Client/application/queries/`, **When** inspected, **Then** it contains `GetTrainingShardsQuery` and `GetTrainedModelsQuery` with dedicated query handlers that query local repositories and return clean view DTOs.
2. **Given** the Client GUI, **When** opening the application, **Then** a dedicated "Training Shards" tab displays a table with columns: Model ID, Version, Shard ID, and Status, accompanied by a "Refresh" button that re-executes `GetTrainingShardsQuery`.
3. **Given** the Client GUI, **When** switching to the "Trained Versions" tab, **Then** it displays a list of trained models (Model ID, Version, Path), and each record or selection provides an "Export / Save" action that opens a system file dialog and saves the artifact to the user's selected location.
4. **Given** the Client Console CLI, **When** invoked with a watch shards switch/subcommand (e.g. `python main.py watch-shards`), **Then** it queries the active shards and renders an aligned tabular view in the terminal with a refresh/polling option.

---

### User Story 5 - Multi-Node Distributed Training Verification, Loss Evaluation, and Teardown Utility (Priority: P5)

As an integration test developer or QA engineer, I want the `full_distributed_training_test` sample updated to verify that both trainers return to IDLE status on the Coordinator, that an aggregated model version artifact is generated, that an evaluation step compares training loss between base and aggregated models, and that a dedicated `clean.py` script stops background services and cleans up artifacts.

**Why this priority**: Fulfills Constitution Principle VI (Zero Mocks) and Principle VII (Executable Correctness). Provides concrete, executable proof that the entire distributed training loop, aggregation, control-plane status reversion, and weight improvements function in real runtime execution.

**Independent Test**: Run `samples/full_distributed_training_test/clean.py` to ensure a clean slate. Execute `run_local.py` (or test runner). Verify that after both trainers complete their shards, the Coordinator reports both trainers as IDLE, the Client creates a new version artifact, the evaluation script executes forward passes comparing base vs aggregated loss, and all steps output clean diagnostic logs.

**Acceptance Scenarios**:

1. **Given** `samples/full_distributed_training_test/clean.py`, **When** executed, **Then** it forcefully terminates any lingering processes running on the test ports (4001, 8090, 8080, 8081, 50051-50053, 9001-9003) and deletes generated test databases, artifacts, and working directory caches.
2. **Given** `samples/full_distributed_training_test/run_local.py` and `verify.py`, **When** the multi-node test completes, **Then** it queries the Coordinator API to assert that both Trainer 1 and Trainer 2 have transitioned back to status `IDLE`.
3. **Given** the completion of all shard training updates, **When** verified, **Then** the test asserts that a new aggregated model version artifact (e.g., version 2 `.pt2` checkpoint) exists in the Client working directory and has a valid file size.
4. **Given** the base model checkpoint and the newly aggregated model checkpoint, **When** evaluated on the test dataset in an evaluation verification step, **Then** training/evaluation losses are computed for both models, outputting a comparative loss metric that confirms the aggregated weights produce valid loss values without numerical divergence (no NaN or Inf).
5. **Given** test execution, **When** running, **Then** each phase (setup, submission, training, detachment, aggregation, coordinator query verification, loss evaluation) prompts clear, human-readable progress and verification results to standard output.

---

### Edge Cases

- **Detach for Non-Existent Trainer**: If `DetachTrainer` is called with an unrecognized `TrainerNodeId`, the Coordinator returns a descriptive error without crashing or mutating other records.
- **Concurrent Shard Updates**: If two trainers submit update deltas simultaneously, Client locks the aggregation check so that exactly one aggregation process executes and no duplicate version checkpoints are produced.
- **Premature Detach Call**: If a trainer attempts detachment while not recorded as `BUSY` (e.g., already `IDLE`), the Coordinator treats it as a safe no-op and returns success.
- **Aggregation Failure Handling**: If delta artifacts are corrupted or missing during aggregation, the orchestrator logs the exception, leaves the existing model version intact, and does NOT reset `submitted` to false until the error state is handled or cleared.
- **Double Submission Rejection**: If an operator clicks "Submit" twice in GUI or triggers concurrent CLI submissions, the second call is immediately rejected because `submitted` is `True`.
- **Export Destination Errors**: If the user selects an unwritable or protected directory when saving an aggregated model artifact in the GUI, a user-friendly error message is displayed without crashing the GUI.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Coordinator Control Plane
- **FR-001**: Coordinator `TrainerService` MUST implement `DetachTrainerAsync(DetachTrainerRequest request, CancellationToken ct)` taking `TrainerNodeId` and boolean `IsTrainingComplete`.
- **FR-002**: In `DetachTrainerAsync`, if the trainer record is not found or its current status is not `BUSY`, the service MUST perform no state changes and return a successful result.
- **FR-003**: In `DetachTrainerAsync`, if the trainer is `BUSY`:
  - If `IsTrainingComplete` is `true`, status MUST transition to `TrainerStatus.IDLE`.
  - If `IsTrainingComplete` is `false`, status MUST transition to `TrainerStatus.UNCLEAR`.
- **FR-004**: Coordinator `TrainerController` MUST expose `POST /api/trainers/detach` accepting `DetachTrainerDto` and returning HTTP 200 OK on success.
- **FR-005**: Coordinator MUST expose GET endpoints (`GET /api/trainers` and `GET /api/training-tasks`) backed by `TrainerService.GetTrainersAsync()` and `TrainingTaskService.GetTrainingTasksAsync()` to enable control-plane state inspection.

#### Client Infrastructure & Application
- **FR-006**: Client `CoordinatorAdapter` MUST implement `detach_trainer(trainer_node_id: str, is_training_complete: bool) -> bool` that sends an HTTP POST to `/api/trainers/detach` and handles success and failure responses.
- **FR-007**: `UpdateModelCommandHandler` MUST invoke `CoordinatorAdapter.detach_trainer(trainer_node_id, is_training_complete=True)` after saving the shard update result and delta path in the local SQLite database.
- **FR-008**: `UpdateModelCommandHandler` MUST evaluate shard completion under a concurrency lock (`threading.Lock` or equivalent) to verify whether all shards for the active `(model_id, model_version, dataset_id)` have transitioned to status `COMPLETED`.
- **FR-009**: When all shards for the active model version are `COMPLETED`, `UpdateModelCommandHandler` MUST parse the base model version as an integer, construct an `AggregationRequest` with `baseModelVersion=int(model_version)` and `newVersion=int(model_version) + 1`, invoke `AggregationOrchestrator.Aggregate()`, and persist the resulting aggregated model checkpoint as a new `Model` entity in the `models` table under composite primary key `(model_id, str(new_version))`.
- **FR-010**: `ClientState` in `Client/application/state.py` MUST include a `submitted: bool` property defaulting to `False`.
- **FR-011**: `SubmitTrainingCommandHandler` MUST set `ClientState.submitted = True` upon successfully submitting a training task and registering it with the Coordinator.
- **FR-012**: `SubmitTrainingCommandHandler` MUST reject new submission requests with an error if `ClientState.submitted` is currently `True`.
- **FR-013**: `UpdateModelCommandHandler` MUST reset `ClientState.submitted = False` once aggregation completes and the new model version artifact is created.
- **FR-014**: The update model and aggregation workflow MUST emit structured, observable progress logs accessible to both console output and GUI logging listeners.

#### Client Presentation & Queries
- **FR-015**: Client application layer MUST provide query models and handlers in `Client/application/queries/`:
  - `GetTrainingShardsQuery` and `GetTrainingShardsQueryHandler` returning a list of active/completed shard DTOs.
  - `GetTrainedModelsQuery` and `GetTrainedModelsQueryHandler` returning a list of trained model version DTOs.
- **FR-016**: Client GUI MUST include a "Training Shards" tab displaying a table of shards (Model ID, Version, Shard ID, Status) and a functional "Refresh" button.
- **FR-017**: Client GUI MUST include a "Trained Versions" tab displaying completed model IDs, versions, and an "Export / Save" button that opens a file dialog and copies the model artifact to the designated path.
- **FR-018**: Client Console UI MUST provide a dedicated `watch-shards` subcommand (e.g. `python main.py watch-shards`) that queries active shards, renders an aligned tabular view with Model ID, Version, Shard ID, and Status, and prompts the user to press Enter to refresh or 'q' to quit.

#### Sample Verification & Test Automation
- **FR-019**: `samples/full_distributed_training_test` MUST verify that both trainers transition back to `IDLE` status on the Coordinator following training completion.
- **FR-020**: `samples/full_distributed_training_test` MUST verify that a new model version artifact is generated in the Client working directory after both trainers submit their updates.
- **FR-021**: `samples/full_distributed_training_test` MUST include a model evaluation step that loads both the base model checkpoint and the aggregated checkpoint, evaluates them against test samples, asserts both loss values are finite numbers (no NaN or Inf), and asserts strict loss reduction (`aggregated_loss < base_loss`).
- **FR-022**: A standalone script `samples/full_distributed_training_test/clean.py` MUST be created to terminate all background test processes on required ports and purge ephemeral test files and artifacts.

---

### Key Entities

- **Trainer Detachment Record**:
  - `TrainerNodeId`: Unique network/cluster identifier of the trainer node.
  - `IsTrainingComplete`: Boolean indicating if the assigned training task completed successfully (`True`) or failed/aborted (`False`).
  - `TargetStatus`: Resulting `TrainerStatus` (`IDLE` if complete, `UNCLEAR` if incomplete, unchanged if not `BUSY`).
- **Client Submission State**:
  - `submitted`: In-memory boolean flag indicating whether an active training submission is currently running.
- **Training Shard View DTO**:
  - `model_id`: Model identifier.
  - `model_version`: Current model version.
  - `dataset_id`: Dataset identifier.
  - `shard_id`: Shard partition identifier.
  - `status`: Lifecycle status (`created`, `ready`, `training`, `completed`, `failed`).
  - `trainer_node_id`: Assigned trainer node identifier.
- **Trained Model Version DTO**:
  - `model_id`: Model identifier.
  - `model_version`: Trained/aggregated version number.
  - `model_type`: Distributed training engine model type.
  - `artifact_path`: Absolute filesystem path to the model checkpoint.
- **Model Evaluation Metric**:
  - `base_model_loss`: Evaluation loss computed using the initial base model checkpoint.
  - `aggregated_model_loss`: Evaluation loss computed using the newly aggregated model checkpoint.
  - `loss_delta`: Difference or relative change confirming model weights were updated.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of participating trainers transition from `BUSY` back to `IDLE` status in the Coordinator database upon verified completion of training updates.
- **SC-002**: Automatic model aggregation is triggered within 5 seconds of the final shard reaching `COMPLETED` status, producing a valid new version model artifact.
- **SC-003**: 100% of duplicate training submission attempts made while a training round is active (`submitted == True`) are rejected with an explicit error.
- **SC-004**: Users can query and view active shard statuses and exported model versions with zero manual database access through both GUI and CLI interfaces.
- **SC-005**: Full distributed multi-node training test executes from start to finish without Docker, validates shard completion, confirms Coordinator idle states, and outputs a comparative loss evaluation with zero mock components.
- **SC-006**: Execution of `clean.py` terminates 100% of lingering background processes on test ports and resets test directories to a clean baseline state.

---

## Assumptions

- **Version Numbering**: Aggregated model versions increment numerically as integers (e.g., base version `1` increments to version `2`), directly matching `AggregationRequest.baseModelVersion` and `AggregationRequest.newVersion` contracts.
- **Incomplete Status Mapping**: When `IsTrainingComplete` is `false`, the Coordinator maps the trainer status to `TrainerStatus.UNCLEAR` (enum value 0), representing an unconfirmed or failed trainer state.
- **Persistence Source of Truth**: The Client's local SQLite database (`models` and `training_shards` tables) remains the authoritative local store for shard and model version tracking.
- **Thread Safety Mechanism**: The Client update model command handler uses a process-level re-entrant or thread lock (`threading.Lock`) to guard the all-shards-complete check and prevent concurrent aggregation calls.
- **Loss Evaluation Metric**: In the verification sample, evaluating loss using standard PyTorch forward passes on a validation batch is sufficient to prove that the model weights are loaded, functional, and computationally valid.
