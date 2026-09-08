# Implementation Plan: Completing Submit Flow

**Branch**: `018-complete-submit-flow` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-complete-submit-flow/spec.md`

## Summary

Complete the end-to-end distributed training submission and task assignment flow across Client, Coordinator, and Trainer services:
1. **Client Model Persistence**: Define `Model` domain entity, create SQLite `models` table, implement `ModelRepository`, and integrate model persistence as a distinct observable step in `SubmitTrainingCommandHandler` immediately following shard persistence.
2. **Coordinator Command Dispatch & Safe Background Scheduling**: Update `StartTrainingCommand` to carry `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId`; push commands to assigned trainers via `ICommandCenter` in `SchedulerService` (with database rollback if dispatch fails); trigger thread-safe background scheduling in `TrainingTaskService` prior to returning HTTP responses.
3. **Trainer Modular Startup & Command Ingestion**: Consolidate registration, connection guard, and gRPC listener startup in `presentation/startup.py`; update `StartTrainingCommand` and `StartTrainingHandler` to parse and log the 5 command fields.
4. **Verification Test Sample**: Create a non-dockerized command-line test harness in `samples/task_assignment_test/` (`startup.py`, `submit.py`, `clean.py`) asserting end-to-end multi-service correctness.

## Technical Context

**Language/Version**: Python 3.10+ (Client & Trainer), .NET 10 (C# 14, Coordinator)

**Primary Dependencies**: 
- Client: PyTorch (`torch>=2.2.0`), `sqlite3`, standard library.
- Coordinator: ASP.NET Core, Microsoft.EntityFrameworkCore.Sqlite 10.0.10, ErrorOr 2.0.1, Grpc.AspNetCore 2.66.0.
- Trainer: `grpcio`, `protobuf`, PyTorch (`torch>=2.2.0`).

**Storage**: SQLite:
- Client: `training.db` (tables: `training_shards`, `models`).
- Coordinator: `coordinator.db` via EF Core (tables: `TrainingTasks`, `Trainers`).

**Testing / Verification**: Automated live command-line test harness in `samples/task_assignment_test/` using host processes (zero mocks per Constitution Principle V & VI).

**Target Platform**: Windows / Linux / macOS native host execution.

**Project Type**: Distributed System: Data-Plane Client (CLI/GUI), Control-Plane Coordinator (Web API + gRPC), Data-Plane Trainer (CLI/GUI), and Test Sample.

**Performance Goals**:
- Model persistence queryable via `get_by_model_id()` in < 50ms.
- Background scheduling triggered without adding latency to Client task creation HTTP response.
- Command dispatched to trainer within 1 second of task assignment.

**Constraints**:
- Zero mocks, zero unit tests; verification via real executables.
- Thread-safe background execution in Coordinator using `SemaphoreSlim(1, 1)` and `IServiceScopeFactory`.
- Strict separation of data plane (models, checkpoints, shards) from control plane.

**Scale/Scope**: 4 primary areas: Client persistence & handler, Coordinator command & services, Trainer presentation & command, and `samples/task_assignment_test/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control/data plane separation | **PASS** | Coordinator manages tasks and command routing; does not touch model weights or datasets. Client owns model metadata and shards. |
| **II. Language Strictness** | .NET for Coordinator, Python for Client/Trainer | **PASS** | Coordinator is .NET 10 Web API; Client and Trainer are Python console applications. |
| **III. Explicit Contracts** | Versioned contracts & DTOs | **PASS** | `StartTrainingCommand` contract unified across Coordinator (C#) and Trainer (Python) via JSON schema. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, clear | **PASS** | `SemaphoreSlim` synchronization for background scheduling without external queue broker; clean repository pattern. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero crypto | **PASS** | Strictly zero mocks/stubs; live command-line test harness in `samples/task_assignment_test/`. |
| **VI. Real Functional Implementations** | Real SQLite, real gRPC | **PASS** | Real SQLite database tables and queries, real gRPC streaming dispatch, real PyTorch artifacts. |
| **VII. Verification & Compilability** | Build & executable correctness | **PASS** | Mandatory validation via `dotnet build`, `python -m py_compile`, and execution of `startup.py` + `submit.py`. |

## Project Structure

### Documentation (this feature)

```text
specs/018-complete-submit-flow/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architecture research and decisions
├── data-model.md        # Phase 1 data model and entity definitions
├── quickstart.md        # Phase 1 verification and run guide
├── contracts/           # Phase 1 interface and command contracts
│   ├── start-training-command.json
│   └── client-model-repository.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Layout

```text
src/Client/
├── models/
│   ├── __init__.py                          # Re-export Model entity
│   └── model.py                             # Model dataclass definition
├── infrastructure/persistence/
│   ├── database.py                          # Add `models` table and index DDL
│   ├── exceptions.py                        # Add ModelNotFoundError, ModelPersistenceError
│   ├── model_repository.py                  # IModelRepository and SQLite ModelRepository
│   └── __init__.py                          # Re-export repository classes
├── application/submit_training/
│   └── submit_training_command_handler.py   # Persist Model entity in step 7, abort on failure
└── dependency_injection/container.py        # Register ModelRepository

src/Coordinator/
├── TrainSwarm.Coordinator.Application/
│   ├── Commands/
│   │   └── StartTrainingCommand.cs          # Update with 5 fields (ClientNodeId, ModelId, ...)
│   └── Services/
│       ├── SchedulerService.cs              # Push StartTrainingCommand via ICommandCenter, rollback on failure
│       └── TrainingTaskService.cs           # Thread-safe background scheduling via IServiceScopeFactory
└── TrainSwarm.Coordinator.Api/
    └── Controllers/
        └── CommandDispatchController.cs     # Align DTO with updated StartTrainingCommand

src/Trainer/
├── presentation/
│   ├── startup.py                           # Consolidate registration and listener setup
│   └── main.py                              # Delegate startup to startup.run_startup()
└── application/coordinator_commands/
    └── start_training/
        ├── command.py                       # Update StartTrainingCommand with 5 fields
        └── handler.py                       # Log all 5 received command fields

samples/task_assignment_test/
├── startup.py                               # Start Coordinator & Trainer background processes, synthesize artifacts
├── submit.py                                # Submit training task via Client CLI and assert end-to-end results
├── clean.py                                 # Terminate background processes via .test_pids.txt, clean DBs
└── README.md                                # Instructions and walkthrough
```

**Structure Decision**: Monorepo layout respecting service ownership. Clean separation of Client models and persistence, Coordinator application commands and services, Trainer presentation startup and coordinator commands, and `samples/task_assignment_test/`.

## Complexity Tracking

> Zero unjustified violations. All architectural decisions align directly with TrainSwarm Constitution principles.
