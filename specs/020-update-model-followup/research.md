# Architecture & Technical Research: Model Update Follow-up & Distributed Aggregation Lifecycle

**Feature**: `020-update-model-followup`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Coordinator Detachment & Query Inspection Architecture

### Context
In TrainSwarm's semi-distributed architecture, the Coordinator (ASP.NET Core Web API in C#) tracks trainer node liveness and task scheduling. When a trainer completes a task or disconnects, the control plane needs an explicit endpoint to transition the trainer back to `IDLE` (if completed) or `UNCLEAR` (if incomplete). Furthermore, test harnesses and clients require read-only inspection endpoints to monitor trainer and task states without directly accessing the Coordinator SQLite database.

### Decision
1. **`DetachTrainerAsync` in `TrainerService`**:
   - Accepts `DetachTrainerRequest(string TrainerNodeId, bool IsTrainingComplete)`.
   - Queries `Trainers` table via EF Core.
   - If trainer not found or current status is not `TrainerStatus.BUSY`: no-op, return `Result.Success`.
   - If `BUSY`:
     - If `IsTrainingComplete == true`: transition status to `TrainerStatus.IDLE`.
     - If `IsTrainingComplete == false`: transition status to `TrainerStatus.UNCLEAR`.
   - Persists state and logs audit message.
2. **REST Endpoint**:
   - `POST /api/trainers/detach` on `TrainerController` accepting `DetachTrainerDto` (`TrainerNodeId`, `IsTrainingComplete`), returning HTTP 200 OK.
3. **Query Inspection Endpoints**:
   - `GET /api/trainers` on `TrainerController` backed by `TrainerService.GetTrainersAsync()` returning all registered trainers.
   - `GET /api/training-tasks` on `TrainingTaskController` backed by `TrainingTaskService.GetTrainingTasksAsync()` returning all scheduled tasks.

### Rationale
- Safe idempotency: Detaching a trainer that is already IDLE or not found does not throw exceptions or corrupt state.
- Strictly decoupled control plane: The Coordinator only tracks availability status and does not touch weights or shards.

---

## 2. Client Shard Completion Synchronization & Automated Aggregation

### Context
When trainers complete local PyTorch fine-tuning, they push update deltas to the Client via P2P. The Client's `UpdateModelCommandHandler` receives each update, writes it to SQLite, and must now:
1. Notify the Coordinator to detach the trainer as `IDLE`.
2. Check if all shards for the active round are completed.
3. If all are completed, trigger `AggregationOrchestrator` to synthesize a new model checkpoint.
Because multiple trainers may complete and transmit update deltas concurrently over separate gRPC/network threads, the completion check and aggregation trigger must be thread-safe.

### Decision
1. **Thread Synchronization**:
   - Use an internal `threading.Lock` within `UpdateModelCommandHandler` (`self._aggregation_lock = threading.Lock()`).
   - The entire sequence—querying shard statuses, verifying all-shards-complete, invoking aggregation, persisting the new version, and resetting `submitted`—executes within `with self._aggregation_lock:`.
2. **Aggregation Invocation**:
   - When all shards for `(model_id, model_version, dataset_id)` have status `TrainingShardStatus.COMPLETED`:
     - Resolve base model path from `ModelRepository.get_by_model_id_and_version(model_id, model_version)`.
     - Parse `base_version = int(model_version)` and compute `new_version = base_version + 1`.
     - Build `ModelUpdate` list mapping `shard.sample_count` to `samplesTrained` and `shard.update_artifact_path` to `deltaPath`.
     - Construct `AggregationRequest(modelId=model_id, baseModelVersion=base_version, baseModelPath=base_path, newVersion=new_version, newVersionOutputDirectory=out_dir, updates=model_updates)`.
     - Invoke `AggregationOrchestrator(model_type=model.model_type).Aggregate(request)`.
     - Persist new `Model` entity with `model_version=str(new_version)` and `model_artifact_path=result.new_model_artifact_path`.
     - Set `client_state.submitted = False`.

### Alternatives Considered
- *Asyncio Lock*: Rejected because Client command handlers run synchronously in thread pools / worker threads; standard re-entrant `threading.Lock` provides universal thread safety.
- *Database Trigger or Polling Daemon*: Rejected as overly complex; inline lock evaluation upon final shard completion ensures zero-latency aggregation without background polling overhead.

---

## 3. Client Submission Guard (`Submitted` Flag)

### Context
To prevent conflicting or overlapping training rounds on the same client, the Client must track whether an active training job is in progress and reject subsequent submissions until the active round completes.

### Decision
1. **State Variable**:
   - Add `submitted: bool = False` to `ClientNode` in `Client/application/state.py`.
   - Expose `@property def submitted(self) -> bool` and `def set_submitted(self, value: bool) -> None` on `ClientState`.
2. **Submission Rejection**:
   - In `SubmitTrainingCommandHandler`: inspect `client_state.submitted`. If `True`, return `SubmitTrainingResult(success=False, error="A training task is already submitted and in progress.")` immediately before partitioning or contacting Coordinator.
   - Upon successful task registration with Coordinator: `client_state.set_submitted(True)`.
3. **Reset**:
   - In `UpdateModelCommandHandler`: when aggregation completes and the new model version is saved, call `client_state.set_submitted(False)`.

---

## 4. SQLite Schema & Composite Primary Key for Model Versions

### Context
The current `models` table defines `model_id TEXT PRIMARY KEY NOT NULL`. In an iterative training workflow, a model advances from version `1` to version `2`, `3`, etc., retaining the same `model_id`. Storing version 2 with a single `model_id` primary key would overwrite version 1. The user specifically requests a "Trained Versions" GUI tab showing each model ID with its trained versions.

### Decision
1. **Schema Migration / Definition**:
   - Update `CREATE_MODELS_TABLE_SQL` in `Client/infrastructure/persistence/database.py`:
     ```sql
     CREATE TABLE IF NOT EXISTS models (
         model_id TEXT NOT NULL,
         model_type TEXT NOT NULL,
         model_version TEXT NOT NULL,
         dataset_id TEXT NOT NULL,
         model_artifact_path TEXT NOT NULL,
         training_config_path TEXT NOT NULL,
         PRIMARY KEY (model_id, model_version)
     );
     ```
   - In `database.py.initialize()`, ensure table migration checks: if existing `models` table has single primary key, recreate/migrate with composite key.
2. **Repository Updates**:
   - Update `IModelRepository` and `ModelRepository`:
     - `save(model: Model) -> None` (uses `INSERT OR REPLACE INTO models ...`)
     - `get_by_model_id_and_version(model_id: str, model_version: str) -> Model`
     - `get_all() -> List[Model]` returning all model versions.
     - Retain `get_by_model_id(model_id: str) -> Model` returning the latest version for backwards compatibility.

---

## 5. Client Application Queries & Presentation Interfaces

### Context
Following Clean Architecture principles, presentation layers (GUI and CLI) must not query database tables directly. They should invoke dedicated Query and QueryHandler use cases in `Client/application/queries/`.

### Decision
1. **`GetTrainingShardsQuery`**:
   - File: `Client/application/queries/get_training_shards/`
   - Input: `GetTrainingShardsQuery(model_id: Optional[str] = None)`
   - Output: `List[TrainingShardViewDto]` (`model_id`, `model_version`, `dataset_id`, `shard_id`, `status`, `trainer_node_id`)
   - Handler: `GetTrainingShardsQueryHandler(shard_repository)`
2. **`GetTrainedModelsQuery`**:
   - File: `Client/application/queries/get_trained_models/`
   - Input: `GetTrainedModelsQuery()`
   - Output: `List[TrainedModelViewDto]` (`model_id`, `model_version`, `model_type`, `artifact_path`, `dataset_id`)
   - Handler: `GetTrainedModelsQueryHandler(model_repository)`
3. **GUI Tabs**:
   - **Tab: Training Shards**: Displays a `QTableWidget` (Model ID, Version, Shard ID, Status, Trainer) with a "Refresh" button executing `GetTrainingShardsQuery`.
   - **Tab: Trained Versions**: Displays a `QTableWidget` of completed models with an "Export / Save" button opening `QFileDialog.getSaveFileName` and copying the checkpoint to user-specified path.
4. **Console UI**:
   - Subcommand `watch-shards`: executes `GetTrainingShardsQuery`, renders formatted ASCII table, prompts user to press Enter to refresh or 'q' to quit.

---

## 6. End-to-End Test Verification, Loss Comparison & Teardown

### Context
`samples/full_distributed_training_test` validates the complete cluster without Docker. It must be enhanced to:
1. Verify both trainers return to `IDLE` status on the Coordinator via REST API.
2. Verify new version artifact (`v2` `.pt2`) is generated.
3. Compare training loss between base and fine-tuned models on test data.
4. Provide a standalone `clean.py` script to kill lingering processes and wipe test directories.

### Decision
1. **Coordinator Status Verification**:
   - Query `http://127.0.0.1:8080/api/trainers`.
   - Assert both `trainer-1` and `trainer-2` have `status == "IDLE"`.
2. **Model Loss Evaluation**:
   - In `verify.py`:
     - Load base model `.pt2` and aggregated model `.pt2` using PyTorch.
     - Load test dataset (`test_dataset.pt` or partitioned evaluation samples).
     - Compute forward passes and evaluation loss with the model's loss criterion (MSE loss).
     - Assert `base_loss` and `aggregated_loss` are finite numbers.
     - Strictly assert `aggregated_loss < base_loss`, logging the loss reduction.
3. **`clean.py` Utility**:
   - Standalone script that kills processes on ports 4001, 8090, 8080, 8081, 50051-50053, 9001-9003.
   - Cleans `work/` and `artifacts/` directories in `samples/full_distributed_training_test/`.
