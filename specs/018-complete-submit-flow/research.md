# Architecture Research & Design Decisions: Completing Submit Flow

**Feature**: `018-complete-submit-flow` | **Date**: 2026-09-08 | **Status**: Complete

## Executive Summary

This feature closes the loop between the training Client submission pipeline, Coordinator scheduling & command dispatch, and Trainer command reception. It adds local model persistence in the Client SQLite database, updates the `StartTrainingCommand` contract across services, pushes commands from Coordinator to assigned trainers in a thread-safe background scheduling pass, consolidates Trainer startup, and establishes a non-dockerized command-line verification test sample.

---

## Research Topics & Decisions

### 1. Client Model Metadata Persistence Architecture

#### Context & Problem
Currently, the Client persists partitioned shards in the `training_shards` SQLite table during `SubmitTrainingCommandHandler`. However, top-level model metadata (model identifier, model engine type, model version, dataset identifier, staged model checkpoint path, and training configuration path) is not persisted in a dedicated model entity or table.

#### Decision
1. **Model Entity**: Create `Model` dataclass in `src/Client/models/model.py` (and re-export in `src/Client/models/__init__.py`).
   - Fields:
     - `model_id: str` (UUID string)
     - `model_type: str` (engine type enum string, e.g., `"canonical_torch"`)
     - `model_version: str` (e.g., `"1.0.0"`)
     - `dataset_id: str` (UUID string)
     - `model_artifact_path: str` (absolute filesystem path to staged `.pt2` file)
     - `training_config_path: str` (absolute filesystem path to staged `config.json` file)
2. **Persistence Schema**: Add a new table `models` to SQLite via `DatabaseManager.initialize()`:
   ```sql
   CREATE TABLE IF NOT EXISTS models (
       model_id TEXT PRIMARY KEY NOT NULL,
       model_type TEXT NOT NULL,
       model_version TEXT NOT NULL,
       dataset_id TEXT NOT NULL,
       model_artifact_path TEXT NOT NULL,
       training_config_path TEXT NOT NULL
   );
   ```
3. **Repository Contract**: Define `IModelRepository` interface and `ModelRepository` implementation in `src/Client/infrastructure/persistence/model_repository.py`:
   - `save(model: Model) -> None`: Inserts or replaces a model entity.
   - `get_by_model_id(model_id: str) -> Model`: Queries the table and returns a `Model` entity; raises `ModelNotFoundError` if not found.
4. **Handler Integration**:
   - In `SubmitTrainingCommandHandler.handle()`, after step 6 (shards persistence), add step 7:
     ```python
     report_progress("Persisting model metadata in local database", 85)
     model_entity = Model(
         model_id=model_id,
         model_type=model_type_str,
         model_version=command.model_version,
         dataset_id=dataset_id,
         model_artifact_path=str(model_dest),
         training_config_path=str(config_dest),
     )
     self.model_repository.save(model_entity)
     ```
   - If `save()` fails, abort the submission immediately, leave shards in `CREATED` status, and return failure (per Clarification Q1).

#### Alternatives Considered
- *Persisting model data inside `training_shards`*: Rejected because it duplicates model artifact paths across every shard row and violates domain normalization.
- *Saving model metadata as a JSON file only*: Rejected because SQLite provides atomic queries, indexing, and transactional consistency with the rest of the Client state.

---

### 2. Coordinator StartTrainingCommand Contract & Command Push

#### Context & Problem
`StartTrainingCommand` previously held `{ TrainingClientNodeId, SessionId }`. The updated specification requires 5 exact properties:
- `ClientNodeId`: ID of the submitting client node.
- `ModelId`: Identifier of the model.
- `ModelVersion`: Version string of the model.
- `DataSetId`: Identifier of the dataset.
- `ShardId`: Specific shard assigned to the trainer.

#### Decision
1. **Command Class**: Update `TrainSwarm.Coordinator.Application.Commands.StartTrainingCommand`:
   ```csharp
   public class StartTrainingCommand
   {
       [JsonPropertyName("clientNodeId")]
       public string ClientNodeId { get; set; } = string.Empty;

       [JsonPropertyName("modelId")]
       public string ModelId { get; set; } = string.Empty;

       [JsonPropertyName("modelVersion")]
       public string ModelVersion { get; set; } = string.Empty;

       [JsonPropertyName("dataSetId")]
       public string DataSetId { get; set; } = string.Empty;

       [JsonPropertyName("shardId")]
       public string ShardId { get; set; } = string.Empty;
   }
   ```
2. **Command Dispatch in SchedulerService**:
   - Inject `ICommandCenter` into `SchedulerService`.
   - In `AssignTasksAsync()`, after `SaveChangesAsync()` persists task and trainer status updates:
     - For each newly assigned task (`assignedResults`), retrieve the task entity or DTO and create `StartTrainingCommand`.
     - Dispatch via `await _commandCenter.SendAsync(trainer.TrainerNodeId, command);`
     - If dispatch fails: Catch error, revert assignment in DB (`task.TrainerNodeId = string.Empty; trainer.Status = TrainerStatus.UNCLEAR; await _dbContext.SaveChangesAsync();`), and log diagnostics (per Clarification Q2).

#### Alternatives Considered
- *Pushing commands before database commit*: Rejected because if the database commit fails, the trainer would have received a phantom instruction for an unpersisted assignment.
- *Fire-and-forget without checking dispatch result*: Rejected because the trainer could be silently offline, leaving the task stuck in `BUSY`. Reverting on dispatch failure makes the failure state observable and allows subsequent healthy trainers to pick up the task.

---

### 3. Asynchronous Safe Background Scheduling in TrainingTaskService

#### Context & Problem
When the Client submits a training task via `CreateTrainingTaskAsync()`, the coordinator saves the tasks in SQLite. The requirement is to run `SchedulerService.AssignTasksAsync()` in the background before returning the response to the client, while guaranteeing thread safety and avoiding lost logs or database context disposal errors.

#### Decision
1. **Thread-Safety Synchronization**: Use a singleton or static `SemaphoreSlim _schedulingLock = new(1, 1);` to serialize background scheduling runs, preventing race conditions and database collisions.
2. **Scope Isolation**: In ASP.NET Core, `ICoordinatorDbContext` is registered as `Scoped`. If `Task.Run()` accesses the scoped `SchedulerService` or `DbContext` of the active HTTP request, the context will be disposed when the HTTP request completes.
   - Solution: Inject `IServiceScopeFactory` into `TrainingTaskService`.
   - In `CreateTrainingTaskAsync()`:
     ```csharp
     // Fire-and-forget background safe execution
     _ = Task.Run(async () =>
     {
         try
         {
             await _schedulingLock.WaitAsync();
             try
             {
                 using var scope = _scopeFactory.CreateScope();
                 var scheduler = scope.ServiceProvider.GetRequiredService<SchedulerService>();
                 var logger = scope.ServiceProvider.GetRequiredService<ILogger<TrainingTaskService>>();
                 logger.LogInformation("[BackgroundScheduler] Triggering task assignment cycle...");
                 var result = await scheduler.AssignTasksAsync();
                 if (result.IsError)
                 {
                     logger.LogWarning("[BackgroundScheduler] Scheduling encountered error: {Error}", result.FirstError.Description);
                 }
                 else
                 {
                     logger.LogInformation("[BackgroundScheduler] Scheduling completed: {Count} tasks assigned.", result.Value.Count);
                 }
             }
             finally
             {
                 _schedulingLock.Release();
             }
         }
         catch (Exception ex)
         {
             _logger.LogError(ex, "[BackgroundScheduler] Unhandled exception in background scheduler pass.");
         }
     });
     ```
3. **Log Traceability**: Use structured logging with `[BackgroundScheduler]` prefix ensuring messages are streamed to the console logger and preserved in terminal output.

#### Alternatives Considered
- *Awaiting scheduler synchronously before returning*: Rejected because spec explicitly mandates non-blocking background execution (`Assign Task MUST be exesuted in background and does not block the current thread`).
- *BackgroundService Queue / Channel*: Viable, but `Task.Run` with `SemaphoreSlim` and `IServiceScopeFactory` is self-contained, minimal, and fully satisfies MVP standards without introducing external background queue infrastructure.

---

### 4. Trainer Startup Refactoring & Command Handler

#### Context & Problem
In `src/Trainer/main.py`, the registration of the trainer, connection guard, and `TrainerCommandListener` initialization are scattered across `main.py` and `presentation/startup.py`.
Furthermore, `StartTrainingCommand` in `src/Trainer/application/coordinator_commands/start_training/command.py` expects `{ training_client_node_id, session_id }`, which mismatches the updated Coordinator command.

#### Decision
1. **Startup Consolidation in `src/Trainer/presentation/startup.py`**:
   - Provide `run_startup(container: DIContainer) -> bool` that:
     1. Executes `ConnectTrainerCommandHandler` to register trainer with Coordinator.
     2. Instantiates and starts `TrainerCommandListener` in the background.
     3. Returns success (or exits with code 1 if connection fails).
   - In `main.py`, simplify the entry point:
     1. Load config & container.
     2. Register command handlers on dispatcher.
     3. Call `run_startup(container)`.
     4. Route to GUI or CLI.
2. **Trainer StartTrainingCommand Model**:
   - Update `StartTrainingCommand` with properties:
     `client_node_id`, `model_id`, `model_version`, `data_set_id`, `shard_id`.
   - Update `from_dict(data)` to handle camelCase and snake_case keys:
     `client_node_id = data.get("clientNodeId") or data.get("client_node_id")`, etc.
   - Update `StartTrainingHandler.handle()`:
     Log all 5 parameters clearly to the console and logger:
     ```python
     logger.info(
         "[StartTrainingHandler] Received StartTrainingCommand - ClientNodeId: %s, ModelId: %s, ModelVersion: %s, DataSetId: %s, ShardId: %s",
         command.client_node_id,
         command.model_id,
         command.model_version,
         command.data_set_id,
         command.shard_id,
     )
     ```

---

### 5. Non-Dockerized Verification Test Architecture (`samples/task_assignment_test/`)

#### Context & Problem
We need an automated verification sample validating the full end-to-end flow without Docker:
Coordinator (dotnet CLI) -> Trainer (python CLI) -> Client CLI submission -> Scheduling -> Command dispatch -> Command reception.

#### Decision
1. **Sample Structure**:
   ```text
   samples/task_assignment_test/
   ├── startup.py       # Starts Coordinator & Trainer as background processes, creates test artifacts (.pt2, .pt, config.json)
   ├── submit.py        # Submits training task via Client CLI, verifies DB states, scheduling, and trainer logs
   ├── clean.py         # Terminates processes via .test_pids.txt, removes temp databases and artifacts
   └── README.md        # Comprehensive instructions and documentation
   ```
2. **Lifecycle & Execution Flow**:
   - `startup.py`:
     - Checks availability of `dotnet` and `python`.
     - Cleans any previous stale processes or ports.
     - Spawns Coordinator (`dotnet run --project ...`) on dedicated port (e.g. 5050 / 8085).
     - Polls `/health` until HTTP 200 is returned.
     - Spawns Trainer (`python main.py`) pointing to Coordinator on dedicated port.
     - Polls Coordinator `/api/trainers` or checks logs until Trainer status is `1` (`IDLE`).
     - Saves PIDs to `.test_pids.txt`.
     - Generates synthetic PyTorch model (`Simple1DCNN` exported as `.pt2`), dataset (`.pt`), and `training_config.json`.
     - Prints success banner and exits 0, leaving services running in background (Clarification Q3).
   - `submit.py`:
     - Executes `python main.py submit-training` using the Client CLI pointing to Coordinator and local artifacts.
     - Validates Client SQLite database: queries `training_shards` and `models` tables.
     - Validates Coordinator SQLite database: verifies `TrainingTask` record created and assigned to trainer (`TrainerNodeId` not empty).
     - Validates Trainer log: asserts `StartTrainingCommand` received and logged with correct `ModelId`, `DataSetId`, `ShardId`.
     - Pretty-prints verification results and exits 0 on success.
   - `clean.py`:
     - Reads `.test_pids.txt`, kills process trees, frees ports, and cleans temporary directories.

---

## Constitution Compliance Confirmation

- **Principle I (Separation of Concerns)**: Coordinator only controls tasks and routes commands; Client owns local model metadata and checkpoints; Trainer executes training upon receiving commands.
- **Principle II (Language & Application Strictness)**: .NET Web API for Coordinator; Python console apps for Client and Trainer; canonical PyTorch for test model/dataset.
- **Principle III (Explicit Contracts)**: `StartTrainingCommand` schema matches exactly across C# and Python; DTOs used at boundaries.
- **Principle IV (MVP Focus)**: Clear, simple, robust code without unnecessary distributed middleware or over-engineered queuing frameworks.
- **Principle V & VI (Zero Mocks & Real Implementations)**: Zero mocks; real SQLite databases; real gRPC streams; real host processes in `task_assignment_test`.
- **Principle VII (Verification & Compilability)**: Verified via `dotnet build`, `python -m py_compile`, and execution of `startup.py` + `submit.py`.
