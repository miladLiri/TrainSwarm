# Implementation Plan: Trainer Command Notification Infrastructure

**Branch**: `006-trainer-command-notification` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-trainer-command-notification/spec.md`

## Summary

Implement a reliable, one-way command and notification infrastructure from the .NET Coordinator to Python Trainers using long-lived server-streaming gRPC. The implementation introduces `ICommandCenter` / `TrainerConnectionManager` on the Coordinator and `CommandDispatcher` / `ICommandHandler` (`StartTrainingHandler`) on the Trainer. All commands utilize a common envelope with dynamic camelCase JSON data payloads, completely decoupling application business logic from the underlying gRPC transport.

## Technical Context

**Language/Version**: 
- **.NET 10** (`C# 13`) for Coordinator Control Plane
- **Python 3.10+** for Trainer Data Plane

**Primary Dependencies**:
- .NET: `Grpc.AspNetCore`, `Microsoft.EntityFrameworkCore.SqlServer`, `System.Text.Json`
- Python: `grpcio>=1.60.0`, `grpcio-tools>=1.60.0`, `requests>=2.31.0`, `python-dotenv>=1.0.0`

**Storage**:
- SQL Server for persistent session/trainer DB entities; in-memory thread-safe `ConcurrentDictionary` for active gRPC stream connections.

**Testing / Verification**:
- Build verification via `dotnet build` and `python -m py_compile`
- Executable verification via running Coordinator API and Trainer console application with end-to-end command dispatch.

**Target Platform**:
- Windows / Linux (cross-platform .NET 10 Kestrel web API and Python console applications).

**Project Type**:
- Distributed system: Web API control plane (.NET) + Console worker data plane (Python).

**Performance Goals**:
- Command delivery from Coordinator `ICommandCenter.SendAsync` to Trainer handler execution in <500ms on local/LAN network.

**Constraints**:
- Strictly one-way communication (Coordinator -> Trainer); zero trainer-to-coordinator application messages.
- Zero gRPC leakage into application or training logic.
- 5-second fixed interval reconnection retry on Python Trainer.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Separation of Concerns** | Coordinator manages control plane & command routing; Trainer manages training execution. No shared model weights in Coordinator. | **PASSED** |
| **II. Language & Runtime Strictness** | Coordinator in .NET 10 Web API; Trainer in Python Console Application. gRPC used for transport. | **PASSED** |
| **III. Explicit Contracts & Boundaries** | Protobuf contract (`coordinator_commands.proto`) and shared camelCase JSON payload schema (`start_training_command.json`). | **PASSED** |
| **IV. Engineering Standards (MVP)** | Simple, explicit abstractions (`ICommandCenter`, `TrainerConnectionManager`, `CommandDispatcher`, `ICommandHandler`). | **PASSED** |
| **V. Prohibitions & Zero Mocks** | Zero mock/stub implementations. No test files created (per Constitution V). Real gRPC connections. | **PASSED** |
| **VI. Real Functional Implementations** | Fully operational gRPC streaming, JSON serialization, and handler dispatch. | **PASSED** |
| **VII. Verification & Compilability** | Mandatory post-change build and run verification gate included. | **PASSED** |

## Project Structure

### Documentation (this feature)

```text
specs/006-trainer-command-notification/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 technical research & decisions
├── data-model.md        # Phase 1 data models & state lifecycles
├── quickstart.md        # Phase 1 validation guide & scenarios
├── contracts/           # Interface contracts
│   ├── coordinator_commands.proto
│   └── start_training_command.json
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 task decomposition (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/
├── Coordinator/
│   ├── TrainSwarm.Coordinator.Api/
│   │   ├── Grpc/
│   │   │   ├── CoordinatorCommandServiceImpl.cs   # gRPC service implementation (SubscribeCommands)
│   │   │   └── Protos/
│   │   │       └── coordinator_commands.proto     # Protobuf service & envelope definition
│   │   ├── Controllers/
│   │   │   └── CommandTestController.cs          # Optional dev/test dispatch endpoint
│   │   ├── Program.cs                             # Register gRPC services & connection manager
│   │   └── TrainSwarm.Coordinator.Api.csproj      # Reference Grpc.AspNetCore
│   └── TrainSwarm.Coordinator.Domain/
│       ├── Commands/
│       │   ├── ICommandCenter.cs                  # High-level command center interface
│       │   ├── CommandCenter.cs                   # CommandCenter implementation
│       │   ├── CommandType.cs                     # CommandType enum (StartTraining)
│       │   ├── CommandEnvelope.cs                 # Domain envelope model
│       │   ├── CommandDispatchResult.cs           # Result DTO
│       │   ├── ITrainerConnectionManager.cs       # Connection manager interface
│       │   ├── TrainerConnectionManager.cs        # In-memory stream manager
│       │   └── StartTrainingCommand.cs            # Typed payload DTO
│       └── TrainSwarm.Coordinator.Domain.csproj
│
└── Trainer/
    ├── domain/
    │   └── commands.py                            # CommandType, StartTrainingCommand models
    ├── application/
    │   ├── command_dispatcher.py                  # Generic command dispatcher & handler registry
    │   ├── command_handlers.py                    # ICommandHandler, StartTrainingHandler
    │   └── trainer_service.py                     # Integration with TrainerService
    ├── infrastructure/
    │   ├── coordinator_commands_pb2.py            # Generated Protobuf classes
    │   ├── coordinator_commands_pb2_grpc.py       # Generated gRPC stubs
    │   └── trainer_command_listener.py            # gRPC stream reader & 5s reconnect loop
    ├── config.py                                  # Config (COORDINATOR_GRPC_URL)
    ├── main.py                                    # Initialize listener & register handlers
    └── requirements.txt                           # grpcio, grpcio-tools
```

**Structure Decision**: Preserves the existing clean architecture in `src/Coordinator` (Domain/Api split) and `src/Trainer` (domain, application, infrastructure, presentation), adding focused command abstractions without modifying existing domain entities or leaking gRPC transport.

## Complexity Tracking

> *Constitution Check has zero violations. No special justifications required.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | N/A |
