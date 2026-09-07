# Implementation Plan: Trainer Connection — Coordinator Trainer Entity & Service, Trainer Architectural Parity, and Startup Lifecycle

**Branch**: `016-trainer-connection` | **Date**: 2026-09-06 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/016-trainer-connection/spec.md)

**Input**: Feature specification from `/specs/016-trainer-connection/spec.md`

## Summary

Implement end-to-end Trainer registration, architectural parity between Trainer and Client, and startup lifecycle enforcement:
1. **Coordinator Control Plane**:
   - Add `Trainer` domain entity (`Id: Guid`, `TrainerNodeId: string`, `Status: TrainerStatus` enum `UNCLEAR=0`, `IDLE=1`, `BUSY=2`).
   - Configure EF Core persistence mapping (`TrainerConfiguration`), register `DbSet<Trainer> Trainers` in `CoordinatorDbContext` and `ICoordinatorDbContext`, and generate an EF Core migration.
   - Implement `TrainerService.ConnectTrainerAsync` with idempotent replacement semantics (removes previous record matching `TrainerNodeId` before inserting a new record with `IDLE` status).
   - Expose REST endpoint `POST /api/trainers/connect` returning HTTP 200/201 on success or 400 Bad Request on validation failure.
2. **Trainer Architectural Standardization (Client Parity)**:
   - Centralized configuration system in `src/Trainer/config/` (`config_manager.py`, `models.py`, `exceptions.py`) reading `COORDINATOR_ADDRESS`, `COORDINATOR_GRPC_ADDRESS`, `TRAINER_NODE_ID`, and timeouts.
   - Minimal dependency injection container in `src/Trainer/dependency_injection/container.py`.
   - In-memory state management in `src/Trainer/application/state.py` holding `client_node_id` as a hardcoded string constant.
   - Relocate gRPC streaming files into `src/Trainer/infrastructure/coordinator_connection/` without logic changes.
   - Implement `CoordinatorAdapter` in `src/Trainer/infrastructure/adapters/coordinator_adapter.py` encapsulating HTTP requests to `/api/trainers/connect` and returning an immutable `CoordinatorAdapterResult`.
   - Split commands: `coordinator_commands/` (with each handler in a subfolder with its command beside it) and `trainer_commands/` (with `connect_trainer/` command and handler).
   - Clear `src/Trainer/domain/`.
3. **Presentation Startup Guard & Desktop Shell**:
   - `presentation/startup.py` executing once at boot to run `ConnectTrainerCommandHandler`, halting the process on failure.
   - Entrypoint `main.py` routing: headless CLI by default (`python main.py`), PyQt6 desktop window shell when invoked with `gui` (`python main.py gui`).
   - Clear `presentation/console_ui.py`.
4. **Packaging & Verification Sample**:
   - Update `src/Trainer/Dockerfile` with `/artifacts` working directory volume, plus `.env` and `.env.example`.
   - Implement containerized verification sample in `samples/trainer_init_test/setup.py` running Coordinator and Trainer containers and asserting database persistence.

---

## Technical Context

**Language/Version**: 
- Coordinator (Control Plane): C# / .NET 9.0 Web API.
- Trainer (Data Plane): Python 3.11+.

**Primary Dependencies**:
- Coordinator: `Microsoft.EntityFrameworkCore.Sqlite`, `ErrorOr`, `Grpc.AspNetCore`.
- Trainer: `requests>=2.31.0`, `grpcio>=1.62.0`, `protobuf>=4.25.0`, `python-dotenv>=1.0.0`, `PyQt6>=6.6.0` (GUI shell).

**Storage**:
- SQLite database (`coordinator.db`) managed via EF Core with automated startup migrations (`db.Database.Migrate()`).

**Testing**:
- Zero-mock active execution per Constitution Principle V (NO MOCKS) and Principle VII (Mandatory Post-Change Quality Gate):
  - `dotnet build` verification for Coordinator.
  - `python -m py_compile` syntax checks for Trainer modules.
  - Containerized end-to-end verification script in `samples/trainer_init_test/setup.py`.

**Target Platform**:
- Linux (Docker container `python:3.11-slim` and `mcr.microsoft.com/dotnet/aspnet:9.0`), Windows, macOS.

**Project Type**:
- Distributed Machine Learning Swarm: Control Plane Web API (.NET) + Data Plane Compute Node (Python Console / PyQt6 Desktop App).

**Performance Goals**:
- Connect Trainer HTTP request latency < 500ms.
- Startup fail-fast abort on coordinator failure < 5s.

**Constraints**:
- Control plane never owns model data or session execution (Constitution Principle I).
- Pure-Python constructor injection via `DIContainer` without third-party DI frameworks.
- Zero mocks, zero stubs, zero test frameworks (no pytest/unittest).
- Verification test strictly utilizes Docker containers.

**Scale/Scope**:
- 5 files modified/added in Coordinator (`Trainer.cs`, `TrainerStatus.cs`, `TrainerConfiguration.cs`, `TrainerService.cs`, `TrainerController.cs`, migrations).
- 12 files refactored/added in Trainer (`config/`, `dependency_injection/`, `application/`, `infrastructure/`, `presentation/`, `Dockerfile`).
- 1 new sample test script in `samples/trainer_init_test/setup.py`.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. Coordinator registers Trainer availability without owning model checkpoints or dataset shards. Trainer receives commands via gRPC.
- **II. Language, Runtime, and Application Strictness**: PASS. Coordinator is built in .NET 9.0; Trainer is built in Python 3.11+. Communication occurs via REST (HTTP) for registration and gRPC for streaming.
- **III. Explicit Contracts & Boundaries**: PASS. `ConnectTrainerRequest`, `ConnectTrainerResponse`, `CoordinatorAdapterResult`, and command models define explicit typed contracts.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Clear vertical slices, explicit constructor injection, small modules, and configuration-driven execution.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero stubs, zero test frameworks, zero crypto, zero RCE.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Real SQLite persistence, real HTTP requests via `requests`, real gRPC streaming, real PyQt6 window shell.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. `dotnet build` succeeds, `py_compile` succeeds, and `samples/trainer_init_test/setup.py` provides automated containerized verification.

---

## Project Structure

### Documentation (this feature)

```text
specs/016-trainer-connection/
├── spec.md              # Feature specification with recorded clarifications
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 technical research & design decisions
├── data-model.md        # Phase 1 domain, DTO, state, and config models
├── quickstart.md        # Phase 1 build, execution & verification guide
├── contracts/           # Phase 1 interface contracts & schemas
│   ├── connect-trainer.schema.json
│   └── coordinator-adapter-contract.md
└── checklists/
    └── requirements.md  # Requirements quality checklist (16/16 passing)
```

### Source Code (repository root)

```text
src/
├── Coordinator/
│   ├── TrainSwarm.Coordinator.Domain/
│   │   └── Entities/
│   │       ├── Trainer.cs                          # New: Trainer domain entity (Id, TrainerNodeId, Status)
│   │       └── TrainerStatus.cs                    # New: Enum (UNCLEAR, IDLE, BUSY)
│   ├── TrainSwarm.Coordinator.Application/
│   │   ├── Contracts/
│   │   │   └── ICoordinatorDbContext.cs            # Updated: Adds DbSet<Trainer> Trainers
│   │   └── Services/
│   │       ├── ConnectTrainerDto.cs                # New: Request DTO
│   │       ├── ConnectTrainerResult.cs             # New: Application result DTO
│   │       └── TrainerService.cs                   # New: ConnectTrainerAsync with replacement logic
│   ├── TrainSwarm.Coordinator.Infrastructure/
│   │   └── Persistence/
│   │       ├── Configurations/
│   │       │   └── TrainerConfiguration.cs         # New: EF Core configuration for Trainers table
│   │       ├── CoordinatorDbContext.cs             # Updated: Adds DbSet<Trainer> Trainers
│   │       └── Migrations/                         # New: EF Core migration for Trainers table
│   └── TrainSwarm.Coordinator.Api/
│       ├── Controllers/
│       │   ├── ConnectTrainerResponseDto.cs        # New: API response DTO
│       │   └── TrainerController.cs                # New: POST /api/trainers/connect endpoint
│       └── Program.cs                              # Updated: Registers TrainerService in DI
│
├── Trainer/
│   ├── Dockerfile                                  # Updated: /artifacts volume & WORKDIR
│   ├── .env                                        # New: Environment configuration
│   ├── .env.example                                # New: Configuration template
│   ├── main.py                                     # Refactored: Routes to headless CLI or PyQt6 GUI
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config_manager.py                       # New: Centralized configuration manager
│   │   ├── models.py                               # New: TrainerConfig dataclass
│   │   └── exceptions.py                           # New: Typed configuration exceptions
│   ├── dependency_injection/
│   │   ├── __init__.py
│   │   └── container.py                            # New: DIContainer composition root
│   ├── domain/                                     # Cleared: All files removed
│   ├── application/
│   │   ├── __init__.py
│   │   ├── state.py                                # Refactored: Holds hardcoded client_node_id
│   │   ├── coordinator_commands/
│   │   │   ├── __init__.py
│   │   │   ├── dispatcher.py                       # Relocated: Routes gRPC envelopes
│   │   │   └── start_training/
│   │   │       ├── __init__.py
│   │   │       ├── command.py                      # Relocated: StartTrainingCommand & Envelope
│   │   │       └── handler.py                      # Relocated: StartTrainingHandler
│   │   └── trainer_commands/
│   │       ├── __init__.py
│   │       └── connect_trainer/
│   │           ├── __init__.py
│   │           ├── connect_trainer_command.py      # New: ConnectTrainerCommand
│   │           └── connect_trainer_handler.py      # New: ConnectTrainerCommandHandler
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── coordinator_connection/
│   │   │   ├── __init__.py
│   │   │   ├── coordinator_client.py               # Relocated: gRPC client
│   │   │   ├── coordinator_commands_pb2.py         # Relocated: Proto generated stub
│   │   │   ├── coordinator_commands_pb2_grpc.py    # Relocated: Proto gRPC service
│   │   │   └── trainer_command_listener.py         # Relocated: Background streaming listener
│   │   └── adapters/
│   │       ├── __init__.py
│   │       └── coordinator_adapter.py              # New: HTTP adapter for POST /api/trainers/connect
│   └── presentation/
│       ├── __init__.py
│       ├── console_ui.py                           # Refactored: Cleared for headless CLI execution
│       ├── startup.py                              # New: Startup connection guard
│       └── gui/
│           ├── __init__.py
│           └── main_window.py                      # New: Standalone PyQt6 window shell
│
└── samples/
    └── trainer_init_test/
        ├── setup.py                                # New: Containerized E2E test runner
        └── README.md                               # New: Sample documentation
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| **Command Co-location in Application** | Co-locates command DTOs beside their handlers in subfolders. | Placing all commands in a global domain module couples independent handlers and requires cross-folder navigation. |
| **Separate `coordinator_commands` vs `trainer_commands`** | Distinguishes remote Coordinator gRPC commands from local Trainer lifecycle commands. | Merging all commands into a single flat dispatcher would create confusing handler signatures and registration mechanics. |
| **Strictly Docker Containerized E2E Test** | Verifies multi-service networking and database persistence under production-like container boundaries. | Host-only subprocess tests cannot verify container networking, port mapping, or Docker volume mount integrity. |
