# Implementation Research: Fair Model-Level Round-Robin Coordinator Scheduler

## Decision 1: Model-Level Round-Robin Scheduling Algorithm & Cursor Mechanics

- **Decision**: Logical model queues with an in-memory round-robin cursor.
  - Retrieve all unassigned tasks (`TrainerNodeId == null || TrainerNodeId == ""`).
  - Group tasks by `ModelId`. Within each model queue, order tasks by `SubmitTime ASC`, then `TrainingTaskId ASC`.
  - Retrieve all idle trainers (`Status == TrainerStatus.IDLE`), ordered deterministically by `TrainerNodeId ASC`.
  - Maintain an in-memory cursor storing the next `ModelId` eligible for a scheduling turn.
  - Active rotation cycle:
    1. Identify models with pending tasks. Order them deterministically (e.g., sorted distinct `ModelId` list).
    2. Start searching from the stored cursor. If cursor is null or points to a non-existent model, start from the first available model.
    3. Select that model's oldest task (`SubmitTime ASC`, `TrainingTaskId ASC`).
    4. Pop the task and assign it to the next available idle trainer (`TrainerNodeId ASC`).
    5. Set cursor to the next model in active rotation.
    6. If the selected model has no remaining tasks, remove it from the active rotation for this cycle.
    7. Repeat until either all idle trainers are assigned or all tasks are assigned.
    8. If all models have zero remaining unassigned tasks, reset the stored cursor to null.
- **Rationale**:
  - Guarantees strict model-level fairness: a model with 1,000 tasks cannot starve a model with 1 task.
  - Maximizes trainer utilization: idle trainers are never left unused if tasks remain.
  - Preserves intra-model FIFO order.
  - Cursor persistence across calls ensures subsequent calls (e.g., Test 4) resume at the next model rather than restarting from the beginning.
- **Alternatives Considered**:
  - *Strict cycle limit (1 task per model per batch)*: Rejected because it leaves idle trainers unused when the number of idle trainers exceeds the number of active models (violating user requirement & Test 3).
  - *Database-persisted cursor*: Rejected as over-engineering for single-coordinator MVP; constitution dictates simplicity and minimal schema footprint.

---

## Decision 2: In-Memory Cursor State Management Across Scoped HTTP Requests

- **Decision**: Introduce a thread-safe singleton state service `ISchedulerCursorState` / `SchedulerCursorState`.
  - In ASP.NET Core, `SchedulerService` and `CoordinatorDbContext` are registered with `Scoped` lifetime (per HTTP request).
  - An in-memory cursor stored as an instance variable inside `SchedulerService` would be destroyed after each HTTP request, failing multi-request continuity tests (such as Test 4).
  - `SchedulerCursorState` is registered as a `Singleton` in `Program.cs` (`AddSingleton<ISchedulerCursorState, SchedulerCursorState>()`).
  - Thread-safe access is guarded using a lightweight lock (`lock (_lock)`).
  - Exposes `string? GetCurrentCursor()`, `void SetCurrentCursor(string? modelId)`, and `void Reset()`.
  - Calling `ClearTasksAsync` calls `_cursorState.Reset()`, ensuring subsequent isolated tests start fresh.
- **Rationale**:
  - Clean separation of concerns between stateless business logic (`SchedulerService`) and in-memory process-lifetime state (`SchedulerCursorState`).
  - Allows `TrainingTaskService.ClearTasksAsync` to reset cursor state cleanly without circular dependencies.
- **Alternatives Considered**:
  - *Static field inside `SchedulerService`*: Rejected because static fields complicate dependency injection, unit testing, and mock-free integration validation.
  - *Singleton `SchedulerService`*: Rejected because EF Core `DbContext` cannot be injected into a Singleton without factory scopes, creating anti-patterns.

---

## Decision 3: Atomic Assignment & Concurrency Safety

- **Decision**: Persist task and trainer mutations in a single `DbContext.SaveChangesAsync()` transaction with collision handling.
  - In `SchedulerService.AssignTasksAsync()`, updating `TrainingTask.TrainerNodeId = trainer.TrainerNodeId` and `Trainer.Status = TrainerStatus.BUSY` occurs on entities tracked by the same `CoordinatorDbContext`.
  - A single call to `await _dbContext.SaveChangesAsync(ct)` is executed within an implicit database transaction in EF Core.
  - Before assignment, the service verifies that the trainer is still `IDLE` and the task is still unassigned.
  - If a `DbUpdateConcurrencyException` occurs, the scheduler logs a warning, discards the contested assignment, and returns successful assignments.
- **Rationale**:
  - Satisfies requirement that task-to-trainer assignments are atomic.
  - Prevents race conditions where two simultaneous scheduling calls assign different tasks to the same trainer.
- **Alternatives Considered**:
  - *Raw SQL lock statements*: Rejected because SQLite in file/WAL mode handles file-level locking, and EF Core change tracking handles transactions natively.

---

## Decision 4: Domain SubmitTime Property & EF Core Migration

- **Decision**: Add `DateTime SubmitTime { get; set; }` to `TrainingTask` in `TrainSwarm.Coordinator.Domain.Entities`, configure it in `TrainingTaskConfiguration`, set it to `DateTime.Now` on task creation in `TrainingTaskService`, and add EF Core migration.
  - Configured in EF Core:
    ```csharp
    builder.Property(t => t.SubmitTime)
        .IsRequired();
    ```
  - `TrainingTaskService.CreateTrainingTaskAsync`:
    `tasks.Add(new TrainingTask { ..., SubmitTime = DateTime.Now });`
  - EF Core migration generated in `TrainSwarm.Coordinator.Infrastructure/Persistence/Migrations/` and applied on startup via `db.Database.Migrate()`.
- **Rationale**:
  - Strictly implements domain requirements.
  - Preserves FIFO ordering within each model queue based on `SubmitTime ASC`, with secondary tie-breaker `TrainingTaskId ASC`.
- **Alternatives Considered**:
  - *UTC Timestamp (`DateTime.UtcNow`)*: Evaluated and rejected in clarification session in favor of user specification for `DateTime.Now`.

---

## Decision 5: Administrative Reset APIs & Test Suite Harness

- **Decision**: Expose `POST /api/trainers/clear` and `POST /api/training-tasks/clear` returning HTTP 200 OK.
  - `TrainerService.ClearTrainersAsync`:
    Removes all rows from `Trainers` table via EF Core.
  - `TrainingTaskService.ClearTasksAsync`:
    Removes all rows from `TrainingTasks` table via EF Core and calls `_cursorState.Reset()`.
  - Test harness `samples/scheduling_test/`:
    - `setup.py`: Starts Coordinator via `dotnet run` (with clean temporary SQLite DB) and awaits `/health`.
    - `test.py`: Implements 12 distinct test functions against `http://localhost:5000`, using `POST /api/training-tasks`, `POST /api/trainers/connect`, `POST /api/scheduler/assign`, and clear endpoints.
    - `README.md`: Explains architecture, test coverage, and execution instructions.
- **Rationale**:
  - Adheres to TrainSwarm Constitution Principle VII (compilability, executability, correctness).
  - Eliminates test inter-dependencies by providing reliable, fast reset capabilities.
- **Alternatives Considered**:
  - *Direct SQLite file deletion between tests*: Rejected because locking issues occur on Windows while the Coordinator web API process is running. HTTP clear endpoints are clean and portable.
