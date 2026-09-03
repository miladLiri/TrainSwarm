# Architecture and Technology Research: Coordinator Clean Architecture & TrainingTask

**Branch**: `012-coordinator-training-task` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

## 1. Project Partitioning and Clean Architecture

- **Decision**: Restructure the Coordinator into four distinct projects with strictly unidirectional dependencies:
  - `TrainSwarm.Coordinator.Domain` (Core business entities, zero external dependencies)
  - `TrainSwarm.Coordinator.Application` (Use cases, DTOs, interfaces, commands, depends on Domain + EF Core abstractions)
  - `TrainSwarm.Coordinator.Infrastructure` (DbContext, EF Core SQLite implementation, migrations, depends on Application + Domain)
  - `TrainSwarm.Coordinator.Api` (ASP.NET Core Web API, controllers, gRPC, DI composition, depends on Application + Infrastructure)
  All projects set `<Nullable>disable</Nullable>` and `<TargetFramework>net10.0</TargetFramework>`.
- **Rationale**: Isolates business models from database technologies and HTTP/gRPC transport frameworks. Inverts dependencies so use cases dictate persistence contracts rather than database models dictating business rules.
- **Alternatives Considered**:
  - *Keep monolithic Domain project containing DbContext, Services, and Commands*: Rejected because it violated separation of concerns, coupled domain entities to EF Core and SQL Server, and prevented independent reuse.
  - *Create separate Persistence project*: Rejected to keep architecture lean (MVP focus); `Infrastructure` cleanly accommodates EF Core persistence, configuration, and migrations without unnecessary project proliferation.

## 2. Result and Error Handling Pattern

- **Decision**: Integrate the `ErrorOr` NuGet package (v2.0.1+) in `TrainSwarm.Coordinator.Application` for domain/application service returns.
- **Rationale**: Normal validation rejections (such as missing IDs or empty shard lists) are expected operational results rather than exceptional runtime crashes. Returning `Task<ErrorOr<CreateTrainingTaskResult>>` eliminates control-flow exceptions, standardizes error codes (`Invalid.ClientNodeId`, `Invalid.DuplicateShardId`, etc.), and enables clean HTTP status mapping.
- **Alternatives Considered**:
  - *Custom Result<T> record*: Rejected because `ErrorOr` is an industry-standard, lightweight discriminated union with rich error categorization (`Error.Validation`) and zero runtime baggage.
  - *Exception throwing (e.g. ValidationException)*: Explicitly forbidden by specification and best practices; exceptions degrade performance and obscure failure pathways.

## 3. Persistence Provider and Configuration

- **Decision**: Use `Microsoft.EntityFrameworkCore.Sqlite` (v10.0.10) managed via EF Core migrations, reading the database connection string strictly from the environment variable `COORDINATOR_DB_CONNECTION_STRING`.
- **Rationale**: SQLite provides lightweight, self-contained, and file-based relational storage that requires no dedicated database server process, making it ideal for distributed control plane nodes. Externalizing the connection string via an environment variable ensures compliance with 12-factor application guidelines and container runtime portability.
- **Alternatives Considered**:
  - *Microsoft.EntityFrameworkCore.SqlServer*: Previously configured in legacy Coordinator; rejected by specification in favor of embedded SQLite persistence.
  - *Fallback default connection string*: Explicitly rejected to ensure fail-fast behavior if operational configuration is missing.

## 4. Application Persistence Contract Abstraction

- **Decision**: Define `ICoordinatorDbContext` in `TrainSwarm.Coordinator.Application.Contracts` exposing `DbSet<TrainingTask> TrainingTasks { get; }` and `Task<int> SaveChangesAsync(CancellationToken ct = default)`.
- **Rationale**: Enables `TrainingTaskService` to query and persist entities through dependency inversion without referencing concrete Infrastructure classes (`CoordinatorDbContext`) or provider-specific SQLite extensions.
- **Alternatives Considered**:
  - *Generic Repository (`ITrainingTaskRepository`)*: Rejected as premature abstraction over EF Core. EF Core's `DbSet<T>` already implements the repository pattern and `DbContext` implements unit of work. Adding an extra repository layer adds boilerplate without practical benefit for this MVP slice.

## 5. Multi-Shard Task Generation and Atomicity

- **Decision**: For every valid shard identifier in `CreateTrainingTaskDto.ShardIdList`, generate a new `Guid` primary key, initialize `TrainerNodeId = string.Empty`, and persist all tasks within a single atomic EF Core operation (`AddRangeAsync` followed by `SaveChangesAsync`).
- **Rationale**: Guarantees all-or-nothing consistency. If database constraint errors or disk I/O failures occur during insertion, EF Core's internal transaction ensures zero partial tasks remain in SQLite.
- **Alternatives Considered**:
  - *Per-shard insert loops with individual SaveChanges*: Rejected because a failure midway through the batch would commit partial tasks, violating requirement AC-09.
  - *Bulk insert third-party libraries (e.g. EFCore.BulkExtensions)*: Rejected because standard EF Core batching easily handles typical shard batches (hundreds of rows) without external dependencies.

## 6. Command Relocation and gRPC Preservation

- **Decision**: Relocate `/Commands` from `TrainSwarm.Coordinator.Domain` to `TrainSwarm.Coordinator.Application.Commands`. Update Api namespaces (`CommandDispatchController`, `CoordinatorCommandServiceImpl`, `Program.cs`) accordingly.
- **Rationale**: Commands (`StartTrainingCommand`, `CommandCenter`, `TrainerConnectionManager`) represent application-level orchestration and trainer connection state rather than pure enterprise domain models. Relocating them to `Application` aligns with Clean Architecture while preserving existing REST and gRPC endpoints without logical changes.
- **Alternatives Considered**:
  - *Keep Commands in Domain*: Rejected by specification requirement Section 7.
  - *Move Commands to Infrastructure*: Rejected because command definitions and dispatch logic are application use cases.

## 7. API Error Mapping to RFC 7807 ValidationProblemDetails

- **Decision**: When `TrainingTaskService` returns validation errors, `TrainingTaskController` populates an ASP.NET Core `ModelStateDictionary` and returns `ValidationProblem(modelState)` yielding standard RFC 7807 `ValidationProblemDetails`.
- **Rationale**: Aligns with ASP.NET Core standard conventions, integrates cleanly with OpenAPI/Swagger schemas, and provides structured error dictionaries mapping field/code keys to descriptive messages.
- **Alternatives Considered**:
  - *Custom JSON envelope `{ "errors": [...] }`*: Rejected during clarification in favor of standard RFC 7807.
