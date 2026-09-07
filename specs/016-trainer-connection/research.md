# Technical Research & Decisions: Trainer Connection

**Feature**: Trainer Connection (`016-trainer-connection`)  
**Status**: Completed  
**Date**: 2026-09-06  

This document records the architectural investigations, trade-offs, and technical design decisions made for implementing the Trainer Connection feature across the Coordinator (.NET) and Trainer (Python) subsystems.

---

## 1. Coordinator: Trainer Entity Persistence & Replacement Semantics

### Decision
Implement `Trainer` in `TrainSwarm.Coordinator.Domain.Entities` and configure it in EF Core (`CoordinatorDbContext`) targeting the `Trainers` table. In `TrainerService.ConnectTrainerAsync`, execute the replacement logic within an atomic database transaction:
1. Validate incoming `TrainerNodeId` (non-null, non-empty, non-whitespace).
2. Query `_dbContext.Trainers` for existing records matching `TrainerNodeId`.
3. If matching records exist, remove them via `_dbContext.Trainers.RemoveRange()`.
4. Instantiate a new `Trainer` entity with `Id = Guid.NewGuid()`, `TrainerNodeId = request.TrainerNodeId`, and `Status = TrainerStatus.IDLE`.
5. Add the entity via `_dbContext.Trainers.AddAsync()` and commit with `_dbContext.SaveChangesAsync()`.
6. Return `ErrorOr<ConnectTrainerResult>`.

### Rationale
- The user prompt explicitly stated: *"in connect trainer if the trainer node id already exists remove the previous record"*.
- Deleting existing records rather than performing an in-place property update ensures that a reconnecting or restarted trainer is provisioned with a fresh identity (`Guid`), cleanly resetting any stale operational state or associations.
- Performing removal and insertion within the same EF Core context transaction guarantees that unexpected database failures will not leave the system in an inconsistent or orphaned state.

### Alternatives Considered
- **In-place Status Update (Upsert)**: Update existing row status to `IDLE` while keeping the same `Id`. Rejected because user requirements explicitly mandated removing the previous record, and regenerating `Id` signals a discrete connection session.
- **Soft Delete**: Adding an `IsDeleted` flag. Rejected as unnecessary complexity for an MVP control plane tracking node availability.

---

## 2. Trainer: Command Organization & Co-location Pattern

### Decision
Split Trainer commands into two distinct namespaces within `src/Trainer/application/`:
1. `src/Trainer/application/coordinator_commands/`: Contains the dispatcher and handlers for remote commands received over the Coordinator gRPC stream.
   - Each command handler resides in its own folder (e.g. `start_training/handler.py`), with its command definition placed beside it (`start_training/command.py`).
   - A centralized `dispatcher.py` routes incoming gRPC envelopes to the registered handler.
2. `src/Trainer/application/trainer_commands/`: Contains local commands initiated by the Trainer process itself (mirroring Client's application commands).
   - Dedicated folder `connect_trainer/` containing `connect_trainer_command.py` and `connect_trainer_handler.py`.
3. Clear `src/Trainer/domain/`: Remove all obsolete models/commands in `domain/` to complete the co-location architecture as requested.

### Rationale
- Enforces modularity and high cohesion. A developer inspecting a command handler can immediately see its input command model without navigating to an external domain folder.
- Clear separation between remote control-plane commands (`coordinator_commands`) and local node-level operations (`trainer_commands`).

### Alternatives Considered
- **Keeping Commands in `domain/`**: Rejected because the prompt explicitly mandated: *"after moving command to each handler folder in application\coordinator_commands clear the domain directory. no files needed there"*.

---

## 3. Trainer: Composition Root & Centralized Configuration Parity with Client

### Decision
Replicate Client's dependency injection and configuration management patterns:
1. `src/Trainer/config/`:
   - `config_manager.py`: Authoritative reader of environment variables (`COORDINATOR_ADDRESS`, `COORDINATOR_GRPC_ADDRESS`, `TRAINER_NODE_ID`, `REQUEST_TIMEOUT_SECONDS`) with `.env` auto-loading via `python-dotenv`.
   - `models.py`: Immutable dataclass `TrainerConfig`.
   - `exceptions.py`: Typed hierarchy (`TrainerConfigurationError`, `MissingConfigurationError`, `InvalidConfigurationValueError`).
2. `src/Trainer/dependency_injection/`:
   - `container.py`: `DIContainer` class that constructs and wires `TrainerConfig`, `CoordinatorAdapter`, `TrainerCommandListener`, `TrainerState`, and command handlers.
3. `src/Trainer/application/state.py`:
   - Holds runtime state with a state attribute `client_node_id` strictly initialized to a hardcoded string constant (e.g., `"trainer-node-01"`), adhering to the user's explicit clarification.

### Rationale
- Directly addresses the user request: *"in trainer first we want exact command/command handler system + minimal dependency injection + config management system that implemented in Client with the same design"*.
- Eliminates scattered `os.getenv` calls and provides a single composition root for application wiring.

---

## 4. Trainer: Coordinator HTTP Adapter Abstraction

### Decision
Implement `CoordinatorAdapter` in `src/Trainer/infrastructure/adapters/coordinator_adapter.py`:
- Accepts `coordinator_address` and `timeout_seconds`.
- Provides `connect_trainer(trainer_node_id: str) -> CoordinatorAdapterResult`.
- Encapsulates `requests.Session`, timeout handling, JSON serialization/deserialization, and HTTP error handling (`requests.exceptions.Timeout`, `ConnectionError`, non-2xx status codes).
- Returns an immutable `CoordinatorAdapterResult` containing `success: bool`, `description: str`, and optional `trainer_id: Optional[str]`.

### Rationale
- Prevents HTTP transport and network exceptions from leaking into application command handlers.
- Matches Client's `CoordinatorAdapter` design where callers receive domain-friendly result objects or exceptions.

---

## 5. Trainer: Presentation Startup Guard & Entry Point Routing

### Decision
1. `src/Trainer/presentation/startup.py`:
   - Exposes a `StartupRunner` (or `run_startup(container: DIContainer) -> bool`) that executes the `ConnectTrainerCommandHandler`.
   - Maintains an internal flag to ensure idempotent single execution if multiple presentation layers are touched.
   - If the connect command fails, logs a prominent diagnostic error to `sys.stderr` and calls `sys.exit(1)`.
2. Entry Point Routing (`main.py`):
   - By default (`python main.py`), runs in headless CLI mode: executes `run_startup()`, starts the gRPC command listener, and keeps the process active.
   - When invoked with `gui` (`python main.py gui`), executes `run_startup()`, and if successful, launches the PyQt6 desktop window.
3. `console_ui.py`:
   - Cleared of interactive REPL menus, serving as a lightweight runner for CLI execution.

### Rationale
- Fulfills the user requirement: *"there should be an startup.py file in presentation that runs when application is started (gui or command line but if both is run it should be executed once) and it should call the connect trainer handler and if it does not work stop application from working with an error"*.
- Conforms to the user's clarified choice (Option A: CLI default, `gui` argument for window).

---

## 6. End-to-End Verification Sample Architecture (`samples/trainer_init_test/`)

### Decision
Create `samples/trainer_init_test/setup.py` that strictly utilizes Docker containers:
1. Creates a Docker bridge network `trainswarm-test-net` (reusing or creating if absent).
2. Builds the Coordinator Docker image from `src/Coordinator/TrainSwarm.Coordinator.Api/Dockerfile`.
3. Runs the Coordinator container with port `8080` published and a SQLite database volume mounted.
4. Polls Coordinator health until responsive (`http://127.0.0.1:8080/health`).
5. Builds the Trainer Docker image from `src/Trainer/Dockerfile`.
6. Runs the Trainer container on the same network with `COORDINATOR_ADDRESS=http://coordinator:8080` and `COORDINATOR_GRPC_ADDRESS=coordinator:8080`.
7. Inspects the SQLite database on the host/container volume using `sqlite3` or Python `sqlite3` to verify that a row exists in `Trainers` table with `TrainerNodeId = 'trainer-node-01'` and `Status = 1` (`IDLE`).
8. Provides clean teardown via `--down` flag or embedded cleanup.

### Rationale
- Satisfies user requirement: *"for test in samples/ create a trainer_init_test and inside it in setup.py run coordinator and then run trainer and there must be record in trainer table"*.
- Adheres to the user's explicit clarification: *"only docker"*.
- Complies with Constitution Principle V (NO MOCKS) and Principle VII (active executable verification).
