# Feature Specification: Trainer Connection — Coordinator Trainer Entity & Service, Trainer Architectural Parity, and Startup Lifecycle

**Feature Branch**: `016-trainer-connection`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "Coordinator: in coordinator i want a new Entity : Trainer (Id : guid auto increament, Trainer Node Id : string, Status : enum TrainerStatus: UNCLEAR, IDLE, BUSY) in Coordinator Domain / Entities; Trainer Service in application Services with method 'Connect Trainer' that gets a TrainerNodeId as input, removes previous record if trainer node id already exists, and inserts a trainer with idle status in db; and an api for this service. Trainer: exact command/command handler system + minimal dependency injection + config management system that implemented in Client with the same design; state.py for state management; infrastructure/coordinator_connection/ handling gRPC connection with coordinator (no logic change, only location change); infrastructure/adapters/coordinator_adapter.py implementing adapter for calling connect trainer api of coordinator, handling results, sending only success/fail/description model to caller, hiding HTTP requesting like Client coordinator adapter; coordinator HTTP address from ENV through config manager for adapter; coordinator gRPC address from ENV through config manager for coordinator_connection; application/coordinator_commands/ containing command dispatcher and command handlers in separate folders with commands beside them, clear domain directory; in state.py a state for ClientNodeId string (hardcoded string for now); application/trainer_commands/ folder with first command connect_trainer/ reading ClientNodeId from state and sending it to Coordinator via coordinator adapter; presentation/gui/ with system design like Client using PyQt6 as basic window shell; presentation/console_ui cleared for now; presentation/startup.py running on startup (gui or cli, executed once) calling connect trainer handler and halting application on error; Dockerfile updated with env variables, .env, .env.example, /artifacts volume mounted as working directory; consistency with Client design; verify projects build and run correctly; sample in samples/trainer_init_test with setup.py running coordinator then trainer and verifying record in trainer table."

## Clarifications

### Session 2026-09-06

- **Q: How should Trainer's entry point (`main.py`) determine whether to launch the PyQt6 GUI window or run in headless/console mode?** → **A: CLI by default, `gui` argument for window (Option A).** `python main.py` runs in headless CLI mode by default (executing `startup.py`, listening for commands, without requiring a display server), while `python main.py gui` launches the PyQt6 desktop window, mirroring Client's entry point design.
- **Q: How should `samples/trainer_init_test/setup.py` execute Coordinator and Trainer to verify database persistence?** → **A: Strictly containerized (Docker only) (Option B).** The setup script builds Docker images, creates a dedicated Docker bridge network, spins up Coordinator and Trainer containers with persistent volume mounts, and verifies the `Trainers` table in the Coordinator database via containerized execution.
- **Q: Should `TrainerState.client_node_id` strictly use a hardcoded string or allow initialization from the configured `TRAINER_NODE_ID` with a hardcoded default?** → **A: Strictly hardcoded string constant (not environment variable).** `TrainerState` internally sets `client_node_id` to a hardcoded string (e.g., `"trainer-node-01"`), without reading from environment variables for now.

### Architectural Alignment Decisions

- **Node Identity Representation in Trainer State**: `state.py` in the Trainer application maintains a state for `client_node_id` strictly initialized with a hardcoded string constant (e.g. `"trainer-node-01"`), which is read by the `connect_trainer` command handler and transmitted to the Coordinator as `TrainerNodeId`. It does not read from environment variables for now.
- **Coordinator HTTP Endpoint Route**: In accordance with REST conventions established in `TrainingTaskController` (`/api/training-tasks`), the Coordinator exposes the Connect Trainer endpoint at `POST /api/trainers/connect` accepting `{ "trainerNodeId": "string" }` and returning status `200 OK` (or `201 Created`) with the registered trainer record details (`id`, `trainerNodeId`, `status`).
- **Database Schema Migration**: EF Core manages the `Trainers` table within `CoordinatorDbContext`. An EF Core migration will be applied automatically on application startup via `db.Database.Migrate()`.
- **Command Dispatcher Organization**: Handlers previously located in `application/command_handlers.py` (such as `StartTrainingHandler`) and command envelopes from `domain/commands.py` are reorganized into subdirectories under `application/coordinator_commands/<command_name>/` (e.g., `application/coordinator_commands/start_training/` containing `command.py` and `handler.py`), alongside a centralized `dispatcher.py`. All leftover files in `domain/` are removed.
- **Coordinator Adapter Contract**: The adapter in `src/Trainer/infrastructure/adapters/coordinator_adapter.py` returns an immutable result object (`CoordinatorAdapterResult`) containing `success: bool`, `description: str`, and optional `trainer_id: Optional[str]`, abstracting all HTTP transport details.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coordinator Trainer Registration & Idempotent Connection (Priority: P1)

As a distributed training coordinator, I want to expose a durable registration endpoint and application service that registers incoming trainer nodes with status `IDLE`, automatically replacing any existing records for the same trainer node identifier, so that trainer availability is accurately tracked without duplicate or orphaned registrations.

**Why this priority**: Core control-plane capability. The Coordinator must reliably record connected trainers before training sessions can be scheduled or dispatched to them.

**Independent Test**: Send an HTTP POST request to `/api/trainers/connect` with `{ "trainerNodeId": "trainer-node-01" }`. Verify the response returns HTTP 200/201 with status `IDLE` and a valid GUID. Send a subsequent request with the same `trainerNodeId` and verify the previous record is replaced, resulting in exactly one row in the database for that node ID with a newly assigned GUID.

**Acceptance Scenarios**:

1. **Given** a valid `TrainerNodeId` string, **When** `TrainerService.ConnectTrainerAsync` is invoked, **Then** it persists a new `Trainer` entity with a newly generated `Guid`, the provided `TrainerNodeId`, and `TrainerStatus.IDLE`.
2. **Given** an existing `Trainer` record in the database with `TrainerNodeId = "trainer-01"`, **When** a new connect request arrives for `"trainer-01"`, **Then** the existing record is removed and a new record with `TrainerStatus.IDLE` is inserted within a single database transaction.
3. **Given** an invalid or empty `TrainerNodeId` (null, empty, or whitespace), **When** `POST /api/trainers/connect` is called, **Then** the API returns HTTP 400 Bad Request with descriptive validation errors, performing zero database modifications.

---

### User Story 2 - Trainer Architectural Standardization & State Management (Priority: P2)

As a software engineer maintaining TrainSwarm, I want the Trainer application to adopt the exact architectural patterns established in the Client (centralized configuration management, minimal composition-root dependency injection, and in-memory application state), so that both client and trainer services share a predictable, clean, and maintainable structure.

**Why this priority**: High structural value. Enforces constitutional principles of consistency, clean boundaries, configuration-driven behavior, and separation of concerns across Python services.

**Independent Test**: Initialize `ConfigManager` in Trainer with environment variables for HTTP and gRPC coordinator addresses. Initialize `DIContainer` and verify all adapters, handlers, and state objects are resolved without errors. Verify that `TrainerState` stores and exposes `client_node_id` with its configured or fallback default value.

**Acceptance Scenarios**:

1. **Given** environment variables `COORDINATOR_ADDRESS` and `COORDINATOR_GRPC_ADDRESS` (with respective fallbacks), **When** `ConfigManager` loads, **Then** it produces an immutable, validated `TrainerConfig` object.
2. **Given** missing mandatory configuration values, **When** `ConfigManager` loads, **Then** it raises a structured configuration exception explaining the missing variable.
3. **Given** `TrainerState`, **When** queried, **Then** it provides access to `client_node_id` (defaulting to a hardcoded string if unconfigured).
4. **Given** `DIContainer`, **When** instantiated with `TrainerConfig`, **Then** it composes the coordinator adapter, coordinator connection listener, state, and command handlers into an accessible composition root.

---

### User Story 3 - Trainer Connect Command & Infrastructure Adapter (Priority: P3)

As a trainer node, I want to execute a local `ConnectTrainerCommand` during startup that reads my node identifier from application state, transmits it to the Coordinator via an abstracted HTTP adapter, and returns a normalized result, so that connection logic is decoupled from UI and transport details.

**Why this priority**: Required to automate trainer registration upon node launch and isolate HTTP transport behind a reusable contract.

**Independent Test**: Instantiate `CoordinatorAdapter` pointing to a running Coordinator instance. Execute `ConnectTrainerCommandHandler.handle()`. Verify that the handler retrieves `client_node_id` from state, invokes the adapter, and returns a result indicating success and a descriptive message.

**Acceptance Scenarios**:

1. **Given** a running Coordinator, **When** `ConnectTrainerCommandHandler` executes, **Then** it reads `client_node_id` from `TrainerState`, calls `CoordinatorAdapter.connect_trainer()`, and returns a successful result model.
2. **Given** an unreachable Coordinator, **When** `ConnectTrainerCommandHandler` executes, **Then** `CoordinatorAdapter` catches transport errors and returns an unsuccessful result model containing a failure description, without raising unhandled exceptions to the caller.
3. **Given** the adapter implementation, **When** inspected, **Then** all HTTP request details (`requests.post`, status code checks, payload serialization) are completely encapsulated within `CoordinatorAdapter`.

---

### User Story 4 - Startup Lifecycle Guard, Presentation Shells, & Domain Cleanup (Priority: P4)

As a system operator or end-user, I want the Trainer application to execute a single startup routine that verifies Coordinator connectivity before launching either the GUI or CLI, aborting immediately if registration fails, while providing a clean PyQt6 window shell and removing obsolete domain files.

**Why this priority**: Prevents the trainer from entering an invalid operational state where it presents a UI to the user while disconnected from the control plane.

**Independent Test**: Launch Trainer with an invalid or unreachable Coordinator address and verify the process aborts immediately with a non-zero exit code and diagnostic error message from `startup.py`. Launch Trainer with a reachable Coordinator and verify `startup.py` executes once, connects successfully, and launches the PyQt6 desktop window.

**Acceptance Scenarios**:

1. **Given** Trainer launch (via GUI or CLI), **When** application boots, **Then** `presentation/startup.py` executes exactly once to run the connect trainer workflow.
2. **Given** a failed connection during startup, **When** `startup.py` receives a failure result, **Then** it logs a prominent error and terminates the process with exit code 1.
3. **Given** a successful connection, **When** GUI mode is requested via `python main.py gui`, **Then** a clean PyQt6 desktop window shell is instantiated and displayed; when invoked without arguments (`python main.py`), **Then** it proceeds in headless CLI mode.
4. **Given** `presentation/console_ui.py`, **When** inspected, **Then** it is cleared of legacy interactive menus and structured as a minimal headless CLI entry point.
5. **Given** `src/Trainer/domain/`, **When** inspected, **Then** it contains no remaining files, as commands are co-located in `application/coordinator_commands/<command>/`.
6. **Given** `src/Trainer/infrastructure/coordinator_connection/`, **When** inspected, **Then** all gRPC streaming listener and proto files reside inside this folder with preserved operational logic.

---

### User Story 5 - Containerized Packaging & Automated Initialization Verification (Priority: P5)

As a DevOps engineer and QA tester, I want an updated Dockerfile with `/artifacts` working directory volume mount and an automated verification script in `samples/trainer_init_test/setup.py` that spins up Coordinator and Trainer and verifies database persistence, so that containerized deployment and registration can be verified automatically.

**Why this priority**: Required by the TrainSwarm Constitution (Principle VII) and user specifications to guarantee build integrity, runnability, and functional correctness.

**Independent Test**: Execute `python samples/trainer_init_test/setup.py`. Verify that Coordinator builds and starts, Trainer builds and starts (or executes startup), and an SQL query against the Coordinator database confirms a row exists in `Trainers` table with status `IDLE`.

**Acceptance Scenarios**:

1. **Given** `src/Trainer/Dockerfile`, **When** built, **Then** it declares `/artifacts` as a volume and working directory, sets default environment variables, and copies project sources.
2. **Given** `.env` and `.env.example` in `src/Trainer/`, **When** inspected, **Then** they define `COORDINATOR_ADDRESS`, `COORDINATOR_GRPC_ADDRESS`, `TRAINER_NODE_ID`, and `REQUEST_TIMEOUT_SECONDS`.
3. **Given** `samples/trainer_init_test/setup.py`, **When** executed, **Then** it requires a running Docker daemon, builds and launches Coordinator and Trainer containers on `trainswarm-test-net`, queries the Coordinator database, verifies the trainer record exists with `status = 1` (`IDLE`), and outputs a pass confirmation.

---

### Edge Cases

- **Duplicate Connection Requests from Same Trainer**: When a trainer disconnects or restarts with the same `TrainerNodeId`, the Coordinator deletes the existing row and inserts a fresh row, guaranteeing no primary key collisions and resetting status to `IDLE`.
- **Coordinator HTTP Offline at Startup**: If the Coordinator web API is down, `startup.py` catches the adapter failure, prints a clear diagnostic to stderr, and halts execution before any UI windows open.
- **gRPC Connection Interruption**: When gRPC disconnection occurs in `coordinator_connection/`, existing automatic reconnection logic continues to attempt reconnection without crashing the application.
- **Concurrent Connect Requests for Identical Node ID**: Handled via database transaction locking to prevent race conditions during deletion and re-insertion.
- **Invalid Node Identifier**: Whitespace-only or empty strings for `TrainerNodeId` are rejected by Coordinator with HTTP 400 Bad Request.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Coordinator Service Requirements

- **FR-001**: Coordinator MUST define a `Trainer` entity in `TrainSwarm.Coordinator.Domain.Entities` with properties:
  - `Id`: `Guid` (Primary Key).
  - `TrainerNodeId`: `string` (Required, non-empty).
  - `Status`: `TrainerStatus` enum.
- **FR-002**: Coordinator MUST define a `TrainerStatus` enum in `TrainSwarm.Coordinator.Domain.Entities` with values:
  - `UNCLEAR = 0`
  - `IDLE = 1`
  - `BUSY = 2`
- **FR-003**: Coordinator Infrastructure MUST configure EF Core persistence for `Trainer` via `TrainerConfiguration` targeting table `Trainers`, and expose `DbSet<Trainer> Trainers` on `ICoordinatorDbContext` and `CoordinatorDbContext`.
- **FR-004**: Coordinator MUST generate and execute an EF Core migration ensuring the `Trainers` table is created in SQLite upon application boot.
- **FR-005**: Coordinator Application MUST implement `TrainerService` in `TrainSwarm.Coordinator.Application.Services` with method `ConnectTrainerAsync(ConnectTrainerDto request, CancellationToken ct)`.
- **FR-006**: When `ConnectTrainerAsync` executes:
  - If any existing `Trainer` record exists with matching `TrainerNodeId`, the service MUST remove the existing record(s).
  - The service MUST insert a new `Trainer` record with a newly generated `Guid` ID, matching `TrainerNodeId`, and `Status = TrainerStatus.IDLE`.
  - The deletion and insertion MUST occur within a single database transaction.
- **FR-007**: Coordinator API MUST expose an HTTP POST endpoint at `/api/trainers/connect` that delegates to `TrainerService.ConnectTrainerAsync` and returns HTTP 200 OK or 201 Created on success, or HTTP 400 Bad Request on invalid input.

#### Trainer Infrastructure & Configuration Requirements

- **FR-008**: Trainer MUST provide a centralized `ConfigManager` under `src/Trainer/config/` following the same architecture as Client (`config_manager.py`, `models.py`, `exceptions.py`).
- **FR-009**: Trainer configuration MUST resolve:
  - `COORDINATOR_ADDRESS` (with fallback to `COORDINATOR_URL`): HTTP base address for REST API calls.
  - `COORDINATOR_GRPC_ADDRESS` (with fallback to `COORDINATOR_GRPC_URL`): Address for gRPC command streaming.
  - `TRAINER_NODE_ID`: Identifier for the trainer node.
  - `REQUEST_TIMEOUT_SECONDS`: Request timeout in seconds.
- **FR-010**: Trainer MUST relocate all gRPC connection code (`TrainerCommandListener`, proto stubs, and channel lifecycle) into `src/Trainer/infrastructure/coordinator_connection/` without altering underlying connection or reconnection logic.
- **FR-011**: Trainer MUST implement `CoordinatorAdapter` in `src/Trainer/infrastructure/adapters/coordinator_adapter.py` that makes HTTP requests to Coordinator's Connect Trainer endpoint and returns an immutable `CoordinatorAdapterResult` containing `success: bool`, `description: str`, and optional `trainer_id: Optional[str]`, hiding all low-level HTTP transport from callers.

#### Trainer Application & Domain Requirements

- **FR-012**: Trainer MUST provide a minimal Dependency Injection container in `src/Trainer/dependency_injection/container.py` following the composition root pattern established in Client, wiring configuration, adapters, state, and command handlers.
- **FR-013**: Trainer MUST implement `TrainerState` in `src/Trainer/application/state.py` holding in-memory node state, including a state property for `client_node_id` initialized to a hardcoded string constant (e.g., `"trainer-node-01"`), without reading from environment variables for now.
- **FR-014**: Trainer MUST organize coordinator gRPC command dispatching into `src/Trainer/application/coordinator_commands/`, placing each handler in a dedicated subfolder alongside its command model (e.g. `start_training/command.py` and `start_training/handler.py`).
- **FR-015**: Trainer MUST implement local trainer command handling in `src/Trainer/application/trainer_commands/`, containing a `connect_trainer/` subfolder with `ConnectTrainerCommand` and `ConnectTrainerCommandHandler`.
- **FR-016**: `ConnectTrainerCommandHandler` MUST accept no input parameters, retrieve the node identifier from `TrainerState`, invoke `CoordinatorAdapter.connect_trainer()`, and return the result model.
- **FR-017**: All files in `src/Trainer/domain/` MUST be removed after relocating command models to their respective handler folders.

#### Trainer Presentation & Startup Requirements

- **FR-018**: Trainer MUST implement `presentation/startup.py` that executes on application launch, triggers `ConnectTrainerCommandHandler`, and if the result indicates failure, halts application execution with exit code 1 and prints an error message.
- **FR-019**: If both GUI and CLI entry points are initialized, `startup.py` MUST ensure the startup connection workflow executes exactly once.
- **FR-020**: Trainer MUST implement a minimalist PyQt6 window shell in `src/Trainer/presentation/gui/` matching the system design structure of Client GUI, launched when `python main.py gui` is executed.
- **FR-021**: `src/Trainer/presentation/console_ui.py` MUST be cleared of legacy interactive REPL logic and support headless operation when `python main.py` is invoked without GUI flags.

#### Packaging & Verification Requirements

- **FR-022**: `src/Trainer/Dockerfile` MUST be updated to configure environment variables, expose volume `/artifacts`, and set `/artifacts` as the working directory.
- **FR-023**: `src/Trainer/` MUST include `.env` and `.env.example` templates specifying required configuration keys.
- **FR-024**: An automated verification sample MUST be implemented in `samples/trainer_init_test/setup.py` that strictly utilizes Docker containers to launch Coordinator and Trainer, queries the Coordinator database, and verifies the existence of the registered `Trainer` record with `IDLE` status.

---

### Key Entities

- **Trainer (Coordinator Domain)**: Represents a registered distributed training compute node in the control plane.
  - `Id`: `Guid` unique primary key.
  - `TrainerNodeId`: Unique client-assigned or hardware node string.
  - `Status`: Current operational status (`UNCLEAR`, `IDLE`, `BUSY`).
- **TrainerStatus (Coordinator Domain Enum)**:
  - `UNCLEAR = 0`: Node status is unverified or unknown.
  - `IDLE = 1`: Node is registered, connected, and available for training tasks.
  - `BUSY = 2`: Node is actively performing a training workload.
- **TrainerConfig (Trainer Configuration)**: Immutable configuration model storing validated Coordinator HTTP and gRPC addresses, node identity, and timeout thresholds.
- **TrainerState (Trainer Application)**: In-memory state tracking local node identity (`client_node_id`), connection status, and operational flags.
- **CoordinatorAdapterResult (Trainer Infrastructure)**: Transport-agnostic result DTO returned by `CoordinatorAdapter` encapsulating `success: bool`, `description: str`, and optional `trainer_id: Optional[str]`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Single-Record Invariant**: Repeated connection requests for the same `TrainerNodeId` result in exactly 1 persisted row in the Coordinator database, with zero orphaned duplicate records.
- **SC-002**: **Registration Latency**: Connect Trainer requests complete within 500 milliseconds under nominal local network conditions.
- **SC-003**: **Fail-Fast Startup**: If Coordinator is unreachable, the Trainer application terminates cleanly within 5 seconds with exit code 1 and zero unhandled exceptions or crash dumps.
- **SC-004**: **Architectural Symmetry**: 100% of the core structural patterns present in Client (`config/`, `dependency_injection/`, `adapters/`, `state.py`) are replicated in Trainer with identical conventions.
- **SC-005**: **Zero Mock Implementations**: All tests and services execute against real SQLite persistence, real HTTP endpoints, and live subprocess/container executions with zero mocks.
- **SC-006**: **End-to-End Test Automation**: The automated verification script in `samples/trainer_init_test/setup.py` executes from clean state to verified database record and exits with code 0 in under 60 seconds.

---

## Assumptions

- **SQLite as Coordinator Persistence**: In accordance with Coordinator's existing setup, Coordinator uses SQLite via EF Core with automated migrations at boot.
- **Hardcoded Node ID**: In Trainer's `state.py`, `client_node_id` is strictly set to a hardcoded string constant (e.g., `"trainer-node-01"`) and is not populated from environment variables.
- **HTTP Endpoint Convention**: The Connect Trainer REST endpoint is mapped to `POST /api/trainers/connect`.
- **PyQt6 GUI Content**: In this specification, the PyQt6 GUI in Trainer provides a basic, functional window shell adhering to Client's GUI architecture; specific training controls, metrics displays, and canvas components are deferred to future specifications.
- **Console UI Simplification**: The existing interactive console menu in `console_ui.py` is cleared in preparation for standardized CLI command dispatching.
