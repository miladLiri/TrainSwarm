# Implementation Plan: Coordinator — TrainingTask Feature and Clean Architecture Restructure

**Branch**: `012-coordinator-training-task` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-coordinator-training-task/spec.md`

## Summary

Restructure the Coordinator module into a strict Clean Architecture solution consisting of four projects: `TrainSwarm.Coordinator.Domain`, `TrainSwarm.Coordinator.Application`, `TrainSwarm.Coordinator.Infrastructure`, and `TrainSwarm.Coordinator.Api`. Implement the `TrainingTask` feature enabling clients to atomically provision durable, per-shard training tasks via `POST /api/training-tasks`. Use EF Core with SQLite configured exclusively via `COORDINATOR_DB_CONNECTION_STRING`, leverage `ErrorOr` for result/error handling, preserve relocated commands and gRPC services, remove obsolete monolithic classes, and package the solution in Docker with volume mounts.

## Technical Context

**Language/Version**: C# / .NET 10.0 (`net10.0`, SDK 10.0.400), with `<Nullable>disable</Nullable>` across all projects.

**Primary Dependencies**:
- `Microsoft.EntityFrameworkCore` (v10.0.10) in Application & Infrastructure
- `Microsoft.EntityFrameworkCore.Sqlite` (v10.0.10) in Infrastructure
- `Microsoft.EntityFrameworkCore.Design` (v10.0.10) in Infrastructure
- `Microsoft.EntityFrameworkCore.Tools` (v10.0.10) in Api
- `ErrorOr` (v2.0.1) in Application
- `Grpc.AspNetCore` (v2.71.0) in Api
- `Microsoft.AspNetCore.OpenApi` (v10.0.10) in Api

**Storage**: SQLite relational database via EF Core migrations, stored at the path specified by `COORDINATOR_DB_CONNECTION_STRING`.

**Testing**: Active build and runtime verification via `dotnet build`, `dotnet run`, and HTTP API invocations (strictly NO unit/mock test files per Constitution Principle V).

**Target Platform**: Cross-platform .NET 10 (Windows dev, Linux Docker runtime image `mcr.microsoft.com/dotnet/aspnet:10.0`).

**Project Type**: Web API and gRPC control-plane service.

**Performance Goals**: Sub-50ms task creation response for typical batch sizes (1 to 50 shards) under local SQLite transactions.

**Constraints**:
- Strict unidirectional dependencies (Domain has 0 dependencies; Application depends on Domain; Infrastructure and Api depend downstream; zero reverse dependencies).
- Fail fast on startup if `COORDINATOR_DB_CONNECTION_STRING` is unset or empty.
- Atomicity: 100% all-or-nothing persistence per request batch.
- Structured logging with `Microsoft.Extensions.Logging` (zero `Console.WriteLine`).

**Scale/Scope**: Handles control-plane task provisioning for tens to hundreds of shards per distributed model training run.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evaluation & Compliance Notes |
|---|---|---|
| **I. Semi-Distributed Architecture** | **PASS** | Coordinator remains strictly in the control plane, tracking task metadata and trainer assignments without touching model weights, gradients, or dataset binaries. |
| **II. Language, Runtime & Application Strictness** | **PASS** | Coordinator is implemented in .NET 10 as an ASP.NET Core Web API / gRPC application. Uses EF Core SQLite persistence as specified. |
| **III. Explicit Contracts & Boundaries** | **PASS** | Explicit DTOs (`CreateTrainingTaskDto`, `CreateTrainingTaskResponseDto`) isolate external network boundaries from internal entities. gRPC and REST command interfaces preserved. |
| **IV. Engineering & Coding Standards (MVP Focus)** | **PASS** | Simple, explicit code without speculative frameworks or premature abstraction. Relies on EF Core DbContext as repository and unit of work. |
| **V. Explicit Prohibitions** | **PASS** | **NO MOCKS**: Real working SQLite persistence and EF Core migrations. **NO TESTS**: No test projects or unit test files created. **NO CRYPTO / NO RCE / NO ROLE MERGING**: Clean control-plane boundaries maintained. |
| **VI. Real Functional Implementations** | **PASS** | Zero dummy placeholders or fake implementations; fully operational SQLite persistence and REST API. |
| **VII. Verification & Compilability Quality Gate** | **PASS** | Mandatory active compilation (`dotnet build`) and executable verification (`dotnet run` + API calls) planned before concluding work. |

## Project Structure

### Documentation (this feature)

```text
specs/012-coordinator-training-task/
├── plan.md              # This implementation plan
├── research.md          # Architecture decisions, technology choices, and rationales
├── data-model.md        # Entities, DTOs, validation rules, and SQLite schema
├── quickstart.md        # Runnable verification guide and curl/PowerShell scenarios
├── contracts/           # Interface contracts
│   └── training-task-api.json # OpenAPI v3 specification for POST /api/training-tasks
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/Coordinator/
├── TrainSwarm.Coordinator.Domain/
│   ├── Entities/
│   │   └── TrainingTask.cs
│   └── TrainSwarm.Coordinator.Domain.csproj
│
├── TrainSwarm.Coordinator.Application/
│   ├── Commands/
│   │   ├── CommandCenter.cs
│   │   ├── CommandDispatchResult.cs
│   │   ├── CommandEnvelope.cs
│   │   ├── CommandType.cs
│   │   ├── ICommandCenter.cs
│   │   ├── ITrainerConnectionManager.cs
│   │   ├── StartTrainingCommand.cs
│   │   └── TrainerConnectionManager.cs
│   ├── Contracts/
│   │   └── ICoordinatorDbContext.cs
│   ├── Services/
│   │   ├── CreateTrainingTaskDto.cs
│   │   ├── CreateTrainingTaskResult.cs
│   │   └── TrainingTaskService.cs
│   └── TrainSwarm.Coordinator.Application.csproj
│
├── TrainSwarm.Coordinator.Infrastructure/
│   ├── Persistence/
│   │   ├── CoordinatorDbContext.cs
│   │   ├── Configurations/
│   │   │   └── TrainingTaskConfiguration.cs
│   │   └── Migrations/
│   │       └── [Timestamp]_InitialTrainingTask.cs
│   ├── ServiceCollectionExtensions.cs
│   └── TrainSwarm.Coordinator.Infrastructure.csproj
│
├── TrainSwarm.Coordinator.Api/
│   ├── Controllers/
│   │   ├── CommandDispatchController.cs
│   │   └── TrainingTaskController.cs
│   ├── Grpc/
│   │   └── CoordinatorCommandServiceImpl.cs
│   ├── Protos/
│   │   └── coordinator_commands.proto
│   ├── Dockerfile
│   ├── Program.cs
│   └── TrainSwarm.Coordinator.Api.csproj
│
├── TrainSwarm.Coordinator.slnx
└── README.md
```

**Structure Decision**: Clean Architecture with 4 distinct projects. `Domain` contains only the `TrainingTask` entity. `Application` contains use cases (`TrainingTaskService`), relocated `Commands/`, and `ICoordinatorDbContext`. `Infrastructure` contains `CoordinatorDbContext`, EF Core configurations, and SQLite migrations. `Api` hosts HTTP controllers, gRPC services, and dependency composition.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **SQLite instead of SQL Server (Constitution Principle II)** | User specification explicitly mandates SQLite persistence via `COORDINATOR_DB_CONNECTION_STRING` for lightweight, file-based embedded execution. | Hosting a full SQL Server instance is overly heavy for local node execution and containerized worker nodes in MVP. |
| **4 Projects instead of Single Project** | Required by Clean Architecture restructure to guarantee unidirectional dependency inversion and prevent framework leakage into domain/application logic. | Monolithic project allowed database contexts and web controllers to become tightly coupled to domain entities. |
