# Feature Specification: Training Client — Submit Training Application Command, Dual Presentation, and Shard Lifecycle

**Feature Branch**: `015-client-submit-training`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "Add 'submit training' feature to TrainSwarm Client with application command handler, dual presentation (CLI and PyQt6 GUI), SQLite lifecycle updates, and containerized E2E test sample: 1. Application Command & Handler (src/Client/application/submit_training/): Implement SubmitTrainingCommand and SubmitTrainingCommandHandler accepting model_path, dataset_path, model_version, model_type, and training_config JSON dictionary. create result dto if required. The handler generates UUIDs for model_id and dataset_id, validates inputs, stages the model checkpoint into working_directory/{model_id} as {model_id}_{model_version}.pt2, and saves the training config in a json file beside the .pt2 file and uses PartitioningOrchestrator to generate a representative sample, executes SmokeTestCommand via SmokeTestCommandHandler to determine recommended_samples_per_shard (cleaning up the sample file afterwards and aborting with user diagnostic notification if smoke test fails), partitions dataset into {working_directory}/shards/{dataset_id}/, persists shards locally in SQLite via TrainingShardRepository with initial status CREATED, submits CreateTrainingTaskDto to Coordinator via CoordinatorAdapter, and upon successful coordinator response updates shard statuses from CREATED to READY via a new repository update method. 2. Domain & Persistence Extension: Extend TrainingShardStatus with CREATED enum value and add update_status(shard_ids, status) method to ITrainingShardRepository and TrainingShardRepository with atomic transaction execution. 3. Presentation Interfaces: - CLI / Console UI (src/Client/presentation/console_ui.py): Extend console UI to support non-interactive CLI arguments (--model-path, --dataset-path, --model-version, --model-type, --training-config <path.json>). - GUI (src/Client/presentation/gui/): Implement a modern, minimalist PyQt6 desktop interface with a Submit Training tab featuring file pickers, dropdown for enum value for example model type, scheduler type and others, hyperparameter form inputs, background QThread worker isolating UI from command execution, and real-time status and log displays, and manage loadings and you can have a tab for logs. 4. Packaging & Docker: Add torch>=2.2.0 and safetensors to requirements.txt for core and Docker headless execution; create requirements-gui.txt for PyQt6 desktop GUI; update src/Client/Dockerfile and Client README.md. 5. End-to-End Verification Sample (samples/submit_training_test/): Implement setup.py to spin up Coordinator and Client containers via Docker, manage networks/environment configuration, and verify communication; implement clean.py to tear down containers and test artifacts; implement e2e-test.py to synthesize test .pt2 models and .pt datasets, execute test matrix via docker exec on Client CLI covering happy path, corrupted model, invalid dataset format, malformed hyperparameter config, and coordinator unreachable, pretty-printing pass/fail status and output diagnostics."

## Clarifications

### Session 2026-09-05

- **Q1: Model and Dataset Identifiers Generation**: How should `model_id` and `dataset_id` be provided in the submit training command?
  - **A**: The system automatically generates unique UUID strings for both `model_id` and `dataset_id` upon command execution.
- **Q2: Artifact Staging and Directory Layout**: How should artifact files (staged model checkpoint, training configuration JSON, smoke test sample, and partitioned shards) be stored?
  - **A**: The base model file is staged into `{working_directory}/{model_id}/{model_id}_{model_version}.pt2`, with the training configuration saved as `{model_id}_{model_version}_config.json` beside it. Temporary smoke test sample files are placed in `{working_directory}/` as `{dataset_id}_sample.pt` and deleted immediately after the smoke test run finishes. Partitioned shards are placed into a dedicated `{working_directory}/shards/{dataset_id}/` folder.
- **Q3: Shard Lifecycle & Database Status Transitions**: How should local shard persistence handle records before and after Coordinator task registration?
  - **A**: Introduce a new `TrainingShardStatus.CREATED` status. Shards are bulk-saved into SQLite as `CREATED` prior to contacting the Coordinator. Once the Coordinator returns created `trainingTaskIds`, the repository method `update_status(shard_ids, status)` atomically updates the persisted records from `CREATED` to `READY`. If the Coordinator call fails or is unreachable, the records remain in `CREATED` state.
- **Q4: Console CLI Invocation Mode**: How should the command-line interface accept inputs?
  - **A**: Support non-interactive CLI flags (`--model-path`, `--dataset-path`, `--model-version`, `--model-type`, `--training-config <path.json>`) for automation and testing.
- **Q5: GUI Technology and Codebase Location**: Where should the desktop GUI be placed and which framework should it use?
  - **A**: Located under `src/Client/presentation/gui/` using **PyQt6**, cleanly structured with views, controllers, and background `QThread` workers to decouple presentation from command dispatch.
- **Q6: Dependency Packaging & Headless Docker Separation**: How should dependencies be organized between core training and desktop GUI?
  - **A**: Core training dependencies (`torch>=2.2.0`, `safetensors`) belong in `requirements.txt` for headless CLI and Docker execution. `PyQt6` is placed in a separate `requirements-gui.txt` so containerized environments remain headless and lightweight.
- **Q7: End-to-End Verification Execution Mode**: How should `samples/submit_training_test/` execute and clean up tests?
  - **A**: `setup.py` manages Docker containers and network connectivity. `e2e-test.py` executes `docker exec` against the running Client container CLI to run a multi-path test suite. `clean.py` (and `setup.py --down`) stops and removes containers and test artifacts.
- **Q8: Smoke Test Working Directory & Staging Isolation**: How should the smoke test execution locate the staged model and sample dataset files given that `CanonicalTorchTrainer` expects checkpoints and shard files directly within its working directory?
  - **A**: Set the smoke test working directory to `{working_directory}/{model_id}`, placing the temporary `{dataset_id}_sample.pt` alongside the staged model inside that folder (Option A).
- **Q9: PyQt6 GUI Progress Display and Navigation**: How should the PyQt6 desktop interface handle tab navigation and progress visibility when a training submission begins?
  - **A**: Remain on the "Submit Training" tab displaying an inline progress bar and status banner, leaving the "Logs" tab as an optional view for detailed diagnostics (Option B).
- **Q10: Container Volume Mount & Working Directory Configuration**: How should test artifacts and working directory storage be mounted and configured in the Client Docker container?
  - **A**: The Client Dockerfile defines a volume `/artifacts` (or `./Artifacts`) as the default working directory (`TRAINING_CLIENT_WORKING_DIRECTORY=/artifacts`), and `setup.py` mounts a local `./artifacts` directory from the host to `/artifacts` in the container.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Training Submission Orchestration (Priority: P1)

As a machine learning engineer or data scientist, I want to execute a single `SubmitTrainingCommand` that validates model and dataset paths, determines optimal shard sizing via an automated smoke test, slices the dataset into shards, registers them in local storage, and schedules them with the Coordinator, so that complex multi-step pre-training preparation is handled reliably in a single automated workflow.

**Why this priority**: Core value driver of the feature. Without the application command and handler orchestrating validation, sampling, smoke testing, partitioning, local persistence, and coordinator communication, training jobs cannot be submitted to the swarm.

**Independent Test**: Provide valid `.pt2` model checkpoint and `.pt` dataset files along with a training configuration dictionary. Execute `SubmitTrainingCommandHandler.handle(command)`. Verify that inputs are validated, model is staged, a smoke test calculates recommended shard size, shards are partitioned, saved to SQLite as `CREATED`, successfully registered with Coordinator, updated to `READY`, and a structured `SubmitTrainingResult` is returned.

**Acceptance Scenarios**:

1. **Given** valid file paths for a PyTorch model (`.pt2`) and dataset (`.pt`), a model version string, supported model type (`canonical_torch`), and valid training configuration JSON, **When** `SubmitTrainingCommandHandler.handle()` is executed, **Then** it generates UUIDs for `model_id` and `dataset_id`, stages the model checkpoint into `{working_directory}/{model_id}/{model_id}_{model_version}.pt2`, and saves the training config JSON beside it.
2. **Given** staged model and dataset inputs in `{working_directory}/{model_id}/`, **When** the handler triggers `PartitioningOrchestrator.get_sample()`, **Then** a representative sample is extracted to `{working_directory}/{model_id}/{dataset_id}_sample.pt`.
3. **Given** the extracted sample, **When** the handler triggers `SmokeTestCommandHandler.handle()` using `{working_directory}/{model_id}` as the working directory, **Then** training runs on the sample, derives `recommended_samples_per_shard`, and automatically deletes `{dataset_id}_sample.pt` from `{working_directory}/{model_id}/`.
4. **Given** a successful smoke test result, **When** the handler calls `PartitioningOrchestrator.create_shards(shardSampleSize=recommended_samples_per_shard)`, **Then** shards are generated into `{working_directory}/shards/{dataset_id}/`.
5. **Given** generated shards, **When** persisted to the local SQLite database, **Then** all shards are saved with status `CREATED`.
6. **Given** persisted `CREATED` shards, **When** `CoordinatorAdapter.create_training_task()` succeeds and returns `trainingTaskIds`, **Then** the local shard records in SQLite are atomically updated to status `READY` and a successful `SubmitTrainingResult` is returned containing model ID, dataset ID, shard count, and assigned task IDs.
7. **Given** a failure in the smoke test run (e.g. incompatible model/loss architecture), **When** `SmokeTestCommandHandler` reports `success = False`, **Then** the handler cleans up the temporary sample file, halts further partitioning, logs diagnostic error information, and returns a failed `SubmitTrainingResult` with descriptive error details.
8. **Given** a network failure or error status from the Coordinator API after shards are partitioned and saved, **When** `CoordinatorAdapter` raises an exception, **Then** the shards remain stored in the local SQLite database with status `CREATED`, and a failure result is returned to notify the user.

---

### User Story 2 - Local Shard Lifecycle Management & Atomic Status Transitions (Priority: P2)

As a client persistence layer, I want local dataset shards to accurately reflect their lifecycle status (`CREATED` when partitioned locally, `READY` when accepted by the Coordinator) using an atomic batch update operation in SQLite, so that local state remains completely synchronized with swarm scheduling and resilient to partial failures.

**Why this priority**: Guarantees data integrity between local storage and the remote Coordinator. Without distinct lifecycle states and atomic update methods, client restarts or network outages could cause untracked or duplicated task submissions.

**Independent Test**: Insert multiple shards with status `CREATED` using `TrainingShardRepository.bulk_save()`. Invoke `TrainingShardRepository.update_status(shard_ids, TrainingShardStatus.READY)`. Query the database and verify that all specified records have transitioned to `READY` within a single atomic transaction, while unreferenced shards remain unchanged.

**Acceptance Scenarios**:

1. **Given** the domain model `TrainingShardStatus`, **When** inspected, **Then** it includes `CREATED = "created"` in addition to `READY`, `TRAINING`, `COMPLETED`, and `FAILED`.
2. **Given** a list of existing shard IDs and a target `TrainingShardStatus`, **When** `TrainingShardRepository.update_status(shard_ids, status)` is called, **Then** it updates the `status` column for all matching records in SQLite within an atomic transaction.
3. **Given** an empty list of shard IDs, **When** `update_status()` is called, **Then** it completes as a no-op without database errors.
4. **Given** a database failure or connection timeout during status update, **When** an exception occurs, **Then** the transaction rolls back cleanly, leaving all records in their previous state.

---

### User Story 3 - Headless Console UI & Non-Interactive CLI Interface (Priority: P3)

As an automated script, CI/CD pipeline, or terminal operator, I want to invoke the `submit-training` command via command-line arguments flags (`--model-path`, `--dataset-path`, `--model-version`, `--model-type`, `--training-config <path.json>`), so that training tasks can be submitted non-interactively and integrated into automated testing pipelines.

**Why this priority**: Required for automation, scriptability, containerized execution, and the end-to-end verification test suite.

**Independent Test**: Run `python main.py submit-training --model-path <path> --dataset-path <path> --model-version v1.0 --model-type canonical_torch --training-config config.json`. Verify that the CLI parses arguments, validates file existence, invokes `SubmitTrainingCommandHandler`, and prints clear high-level progress logs (staging, smoke testing, partitioning, database save, coordinator dispatch) and exit code 0 on success or non-zero on failure.

**Acceptance Scenarios**:

1. **Given** valid CLI arguments flags, **When** `python main.py submit-training` is executed, **Then** the CLI parses arguments, loads the training config JSON, constructs `SubmitTrainingCommand`, and executes the handler.
2. **Given** missing or invalid arguments (e.g. non-existent model file or malformed config JSON), **When** invoked, **Then** the CLI prints a descriptive validation error to stderr and exits with a non-zero exit code.
3. **Given** an ongoing submission, **When** progress events occur (smoke test start, throughput measured, shards created, coordinator submission), **Then** high-level progress messages are printed to the console in real time.
4. **Given** an execution failure at any step, **When** the handler returns a failure result or raises an error, **Then** the CLI formats the error message clearly, displays diagnostic suggestions, and exits with code 1.

---

### User Story 4 - Modern Minimalist PyQt6 Desktop Graphical User Interface (Priority: P4)

As a desktop user, I want a modern, clean graphical user interface built with PyQt6 featuring a dedicated "Submit Training" tab, file pickers, model/scheduler dropdowns, hyperparameter forms, and background worker threads, so that I can configure and monitor training submissions visually without blocking the application window.

**Why this priority**: Provides an accessible, user-friendly desktop experience for non-CLI operators while adhering to strict UI/business logic separation.

**Independent Test**: Launch the PyQt6 desktop interface. Navigate to the "Submit Training" tab. Select model and dataset files using file dialogs, pick model type and scheduler from dropdowns, enter hyperparameters, and click "Submit Training". Verify that input gathering constructs the command, dispatches it on a background `QThread`, displays loading spinners/progress indicators without freezing the UI, and streams real-time log output to a dedicated Logs tab or panel.

**Acceptance Scenarios**:

1. **Given** the GUI application in `src/Client/presentation/gui/`, **When** launched, **Then** it presents a modern, minimalistic window with tabs including "Submit Training" and "Logs".
2. **Given** the "Submit Training" tab, **When** rendered, **Then** it provides file pickers for model checkpoint (`.pt2`) and dataset (`.pt`), text inputs for model version, dropdowns for model type (`canonical_torch`), criterion/loss type, optimizer type, and scheduler type, and input fields for batch size, epochs, and learning rate.
3. **Given** user submission trigger, **When** the "Submit Training" button is clicked, **Then** input validation runs; if valid, inputs are serialized into `SubmitTrainingCommand` and passed to a background worker thread (`QThread`).
4. **Given** a running background submission, **When** processing occurs, **Then** the main UI thread remains responsive (no freezing), keeps the user on the 'Submit Training' tab showing an inline progress bar and current phase status banner (staging, smoke testing, partitioning, coordinator registration), while simultaneously streaming detailed log lines to the 'Logs' tab.
5. **Given** completion of submission (success or failure), **When** the worker thread finishes, **Then** the UI updates loading indicators, re-enables input controls, and displays a prominent success banner with task IDs or an error dialog with diagnostic details.

---

### User Story 5 - Containerized End-to-End Verification Sample Suite & Multi-Path Matrix (Priority: P5)

As a QA engineer and developer, I want a complete end-to-end verification sample in `samples/submit_training_test/` with automated Docker lifecycle management (`setup.py`, `clean.py`) and a comprehensive test runner (`e2e-test.py`), so that the entire submission pipeline can be validated across happy and failure paths in an isolated, reproducible environment.

**Why this priority**: Guarantees verification of cross-service integration (Client CLI + SQLite + Coordinator Web API) under real network and container configurations without mocks.

**Independent Test**: Run `python setup.py` to launch Coordinator and Client containers in Docker and verify connectivity. Run `python e2e-test.py` to execute synthetic model/dataset generation and test all submission paths via `docker exec` against the Client CLI. Verify that test results are pretty-printed with clear PASS/FAIL indicators. Run `python clean.py` to verify full teardown.

**Acceptance Scenarios**:

1. **Given** `samples/submit_training_test/setup.py`, **When** executed, **Then** it provisions a shared Docker bridge network, mounts the host `./artifacts` directory to `/artifacts` in the Client container (configured as its working directory), spins up Coordinator and Client containers with proper environment variables, waits for HTTP health readiness, and prompts confirmation that the connection is established.
2. **Given** `samples/submit_training_test/e2e-test.py`, **When** executed, **Then** it generates valid PyTorch 2 models (`.pt2`), valid datasets (`.pt`), corrupted model files, and malformed dataset files.
3. **Given** generated test artifacts, **When** `e2e-test.py` runs its test matrix, **Then** it executes the Client CLI via `docker exec` across 5 distinct test paths:
   - **Path 1 (Happy Path)**: Valid inputs, successful smoke test, successful partitioning, SQLite persistence as `CREATED`, Coordinator registration, updated to `READY`.
   - **Path 2 (Corrupted/Invalid Model)**: Corrupted checkpoint fails smoke test, cleans up sample, rejects submission.
   - **Path 3 (Invalid Dataset Format)**: Unrecognized tensor structure fails partitioner validation, halts before smoke test.
   - **Path 4 (Malformed Hyperparameter Config)**: Invalid JSON or unsupported optimizer fails parameter validation immediately.
   - **Path 5 (Coordinator Unreachable)**: Coordinator stopped/unreachable, shards remain locally saved with status `CREATED`, failure reported.
4. **Given** test execution, **When** each test completes, **Then** `e2e-test.py` prints a clean, human-readable summary displaying test name, expected outcome, actual result, and PASS/FAIL status.
5. **Given** `samples/submit_training_test/clean.py`, **When** executed, **Then** it stops and removes all test containers, removes the Docker network, and deletes temporary test artifacts.

---

### Edge Cases

- **Model Staging Overwrite Collision**: If `{working_directory}/{model_id}/{model_id}_{model_version}.pt2` already exists (e.g. from an aborted earlier run), staging must safely overwrite or cleanly isolate the checkpoint.
- **Empty Dataset Partitioning**: If a dataset contains fewer samples than required for a single batch or sample, input validation must reject the command before smoke test execution.
- **Smoke Test Zero Monotonic Duration**: If smoke test execution runs too quickly to register positive elapsed time, the smoke test handler treats throughput as invalid and the submit handler aborts partitioning.
- **Partial Coordinator Failure**: If the Coordinator API returns HTTP 500 or times out after shards are persisted in SQLite, local shards remain safely recorded as `CREATED` so they are not lost or orphaned.
- **GUI Thread Crash Protection**: If an unhandled exception occurs in the background `QThread`, it must be caught and signaled to the main UI thread via PyQt signals without crashing the desktop application.
- **Headless Docker Environment Display Guard**: If PyQt6 is imported or launched in an environment without an active `DISPLAY` or `WAYLAND_DISPLAY`, the client must output a user-friendly error instructing the user to run CLI mode.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `SubmitTrainingCommand` in `src/Client/application/submit_training/submit_training_command.py` accepting `model_path`, `dataset_path`, `model_version`, `model_type`, and `training_config`.
- **FR-002**: `SubmitTrainingCommand` MUST validate that `model_path` and `dataset_path` point to existing files, `model_version` is a non-empty string, `model_type` is a valid `ModelType` value, and `training_config` is a dictionary.
- **FR-003**: System MUST provide `SubmitTrainingResult` in `src/Client/application/submit_training/submit_training_result.py` encapsulating `success`, `model_id`, `dataset_id`, `shard_count`, `training_task_ids`, `recommended_samples_per_shard`, and `error`.
- **FR-004**: System MUST provide `SubmitTrainingCommandHandler` in `src/Client/application/submit_training/submit_training_command_handler.py` exposing `handle(command: SubmitTrainingCommand) -> SubmitTrainingResult`.
- **FR-005**: `SubmitTrainingCommandHandler` MUST generate unique UUID string identifiers for `model_id` and `dataset_id` upon invocation.
- **FR-006**: `SubmitTrainingCommandHandler` MUST create directory `{working_directory}/{model_id}/`, stage the input model file to `{working_directory}/{model_id}/{model_id}_{model_version}.pt2`, and serialize `training_config` to `{working_directory}/{model_id}/{model_id}_{model_version}_config.json`.
- **FR-007**: `SubmitTrainingCommandHandler` MUST invoke `PartitioningOrchestrator.get_sample()` to extract a representative sample into `{working_directory}/{model_id}/{dataset_id}_sample.pt`.
- **FR-008**: `SubmitTrainingCommandHandler` MUST construct a `TrainingTask` model referencing `{dataset_id}_sample.pt` and execute `SmokeTestCommandHandler.handle()` with working directory set to `{working_directory}/{model_id}`.
- **FR-009**: `SubmitTrainingCommandHandler` MUST delete the temporary `{working_directory}/{model_id}/{dataset_id}_sample.pt` file upon smoke test completion regardless of success or failure.
- **FR-010**: If the smoke test fails (`SmokeTestResult.success == False`), `SubmitTrainingCommandHandler` MUST halt execution, refrain from partitioning shards, and return `SubmitTrainingResult` with `success = False` and the smoke test error message.
- **FR-011**: If the smoke test succeeds, `SubmitTrainingCommandHandler` MUST invoke `PartitioningOrchestrator.create_shards(shardSampleSize=recommended_samples_per_shard)` targeting `{working_directory}/shards/{dataset_id}/`.
- **FR-012**: System MUST extend `TrainingShardStatus` enum in `src/Client/domain/training_shard.py` to include `CREATED = "created"`.
- **FR-013**: System MUST add `update_status(shard_ids: List[str], status: TrainingShardStatus) -> None` to `ITrainingShardRepository` and `TrainingShardRepository` in `src/Client/infrastructure/persistence/training_shard_repository.py`.
- **FR-014**: `TrainingShardRepository.update_status()` MUST execute the status update for all specified shard IDs inside an atomic SQLite transaction (`BEGIN IMMEDIATE`).
- **FR-015**: `SubmitTrainingCommandHandler` MUST persist generated shards into SQLite via `TrainingShardRepository.bulk_save()` with initial status `TrainingShardStatus.CREATED`.
- **FR-016**: `SubmitTrainingCommandHandler` MUST submit `CreateTrainingTaskDto` to the Coordinator via `CoordinatorAdapter.create_training_task()`.
- **FR-017**: Upon receiving `trainingTaskIds` from the Coordinator, `SubmitTrainingCommandHandler` MUST invoke `TrainingShardRepository.update_status()` to update the persisted shards to `TrainingShardStatus.READY`.
- **FR-018**: If `CoordinatorAdapter` fails or raises an exception, `SubmitTrainingCommandHandler` MUST catch the exception, leave local shard statuses as `CREATED`, and return `SubmitTrainingResult(success=False, error=str(e))`.
- **FR-019**: System MUST wire `SubmitTrainingCommandHandler` into `DIContainer` in `src/Client/dependency_injection/container.py`.
- **FR-020**: System MUST extend `ConsoleUI` and CLI entry point in `src/Client/presentation/console_ui.py` and `src/Client/main.py` to support non-interactive CLI flags: `--model-path`, `--dataset-path`, `--model-version`, `--model-type`, and `--training-config`.
- **FR-021**: System MUST implement a PyQt6 desktop GUI application under `src/Client/presentation/gui/` with tabs for "Submit Training" and "Logs".
- **FR-022**: The PyQt6 GUI MUST provide file selection dialogs, model type dropdowns, scheduler dropdowns, hyperparameter input forms, display an inline progress bar and phase status banner on the Submit Training tab during execution while streaming detailed logs to the Logs tab, and execute submissions on a background `QThread` without blocking the main event loop.
- **FR-023**: System MUST update `src/Client/requirements.txt` to include `torch>=2.2.0` and `safetensors`, and create `src/Client/requirements-gui.txt` containing `PyQt6>=6.6.0`.
- **FR-024**: System MUST update `src/Client/Dockerfile` to install core headless training dependencies, declare a `/artifacts` volume configured as `TRAINING_CLIENT_WORKING_DIRECTORY`, and document container execution in `src/Client/README.md`.
- **FR-025**: System MUST provide an end-to-end verification sample suite under `samples/submit_training_test/` containing `setup.py`, `clean.py`, and `e2e-test.py`.
- **FR-026**: `samples/submit_training_test/setup.py` MUST configure Docker networking, mount host `./artifacts` to `/artifacts` in the Client container, start Coordinator and Client containers, and verify readiness.
- **FR-027**: `samples/submit_training_test/e2e-test.py` MUST synthesize PyTorch models and datasets and execute test cases via `docker exec` against the Client CLI covering: happy path, invalid model, invalid dataset, invalid hyperparameters, and coordinator failure.
- **FR-028**: `samples/submit_training_test/clean.py` MUST stop and remove test containers, networks, and synthesized test artifacts.

### Key Entities

- **SubmitTrainingCommand**: Application command DTO containing `model_path`, `dataset_path`, `model_version`, `model_type`, and `training_config`.
- **SubmitTrainingResult**: Structured result DTO containing execution success status, generated `model_id`, `dataset_id`, `shard_count`, `training_task_ids`, `recommended_samples_per_shard`, and error details.
- **TrainingShard**: Domain entity representing a partitioned dataset shard, updated with status `CREATED` prior to coordinator dispatch and `READY` after coordinator acknowledgement.
- **CreateTrainingTaskDto**: Infrastructure adapter DTO serializing task creation requests sent to the Coordinator REST API.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of submitted training workflows validate model and dataset inputs and calculate optimal shard sample sizes via real smoke test execution before partitioning the full dataset.
- **SC-002**: Shard records are persisted in SQLite with status `CREATED` prior to external API dispatch, preventing lost shard data in 100% of Coordinator timeout or failure scenarios.
- **SC-003**: 100% of successfully acknowledged Coordinator submissions update local shard statuses to `READY` via an atomic database transaction.
- **SC-004**: The client CLI completes non-interactive command execution (`submit-training`) and returns standard exit codes (0 for success, 1 for failure) across automated scripts.
- **SC-005**: The PyQt6 desktop GUI executes submission workflows on a background thread without dropping frames or triggering "application not responding" (ANR) events during compute-heavy smoke test runs.
- **SC-006**: The end-to-end test suite (`samples/submit_training_test/`) passes 5/5 test matrix scenarios (happy path, bad model, bad dataset, bad config, coordinator outage) in a containerized environment with clear pass/fail reporting.
- **SC-007**: Temporary smoke test artifacts (`{working_directory}/{model_id}/{dataset_id}_sample.pt`) and model deltas are deleted in 100% of runs, maintaining zero junk accumulation in the working directory.

---

## Assumptions

- Python 3.11+ is the standard runtime for the TrainSwarm Client application.
- The `distributed_training_engine` package is available in the Python environment, providing `PartitioningOrchestrator`, `TrainingOrchestrator`, and `ModelType`.
- PyTorch (`torch>=2.2.0`) is installed in the core environment, supporting `.pt2` model program inspection and `.pt` dataset tensor operations.
- Desktop environments running the GUI have an active display server (X11, Wayland, or Windows Desktop) with PyQt6 installed.
- Docker and Docker Compose (or Docker CLI) are available on the host system to run the end-to-end verification sample in `samples/submit_training_test/`.
- The Coordinator service exposes `POST /api/training-tasks` accepting `CreateTrainingTaskDto` wire JSON format and returning `{ "trainingTaskIds": [...] }`.
