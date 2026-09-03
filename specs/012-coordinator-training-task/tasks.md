# Tasks: Coordinator — TrainingTask Feature and Clean Architecture Restructure

**Branch**: `012-coordinator-training-task` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Clean Architecture project definitions, dependencies, and solution structure.

- [x] T001 Update project dependencies and disable nullable in `src/Coordinator/TrainSwarm.Coordinator.Domain/TrainSwarm.Coordinator.Domain.csproj`
- [x] T002 [P] Create class library project with ErrorOr and EF Core abstractions in `src/Coordinator/TrainSwarm.Coordinator.Application/TrainSwarm.Coordinator.Application.csproj`
- [x] T003 [P] Create class library project with EF Core SQLite and Design dependencies in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/TrainSwarm.Coordinator.Infrastructure.csproj`
- [x] T004 Update project references and disable nullable in `src/Coordinator/TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj`
- [x] T005 Update solution file to register all four projects in `src/Coordinator/TrainSwarm.Coordinator.slnx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Relocate commands, remove obsolete legacy code, and establish core entity and persistence contracts.

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [x] T006 Relocate `/Commands` folder from Domain to Application and update namespaces in `src/Coordinator/TrainSwarm.Coordinator.Application/Commands/`
- [x] T007 Remove obsolete legacy entities, services, context, and migrations from `src/Coordinator/TrainSwarm.Coordinator.Domain/`
- [x] T008 Remove obsolete legacy controllers and DTOs from `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/`
- [x] T009 Implement `TrainingTask` domain entity with non-nullable properties in `src/Coordinator/TrainSwarm.Coordinator.Domain/Entities/TrainingTask.cs`
- [x] T010 Define `ICoordinatorDbContext` persistence abstraction in `src/Coordinator/TrainSwarm.Coordinator.Application/Contracts/ICoordinatorDbContext.cs`
- [x] T011 [P] Implement `TrainingTaskConfiguration` with EF Core Fluent API in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Configurations/TrainingTaskConfiguration.cs`
- [x] T012 Implement `CoordinatorDbContext` implementing `ICoordinatorDbContext` in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/CoordinatorDbContext.cs`
- [x] T013 Implement `AddCoordinatorPersistenceServices` DI extension method in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/ServiceCollectionExtensions.cs`

**Checkpoint**: Core domain entity, application persistence abstraction, and SQLite infrastructure configuration are ready.

---

## Phase 3: User Story 1 - Create and Persist Distributed Training Tasks per Shard (Priority: P1) 🎯 MVP

**Goal**: Enable clients to submit multi-shard requests and atomically persist one `TrainingTask` per shard with `TrainerNodeId = string.Empty` and return HTTP 201 Created with generated GUIDs.

**Independent Test**: Issue a `POST /api/training-tasks` request with 3 valid shard IDs; verify the API returns `201 Created` with 3 distinct GUIDs and exactly 3 corresponding records exist in the SQLite database with identical model metadata and empty trainer IDs.

### Implementation for User Story 1

- [x] T014 [P] [US1] Implement `CreateTrainingTaskDto` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/CreateTrainingTaskDto.cs`
- [x] T015 [P] [US1] Implement `CreateTrainingTaskResult` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/CreateTrainingTaskResult.cs`
- [x] T016 [US1] Implement task instantiation and atomic multi-shard persistence in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [x] T017 [P] [US1] Implement `CreateTrainingTaskResponseDto` in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/CreateTrainingTaskResponseDto.cs`
- [x] T018 [US1] Implement `POST /api/training-tasks` endpoint returning 201 Created in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainingTaskController.cs`
- [x] T019 [US1] Register `TrainingTaskService` in DI container in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`

**Checkpoint**: At this point, User Story 1 is fully functional and delivers the core MVP slice.

---

## Phase 4: User Story 2 - Request Validation and Atomic Transaction Guarantees (Priority: P2)

**Goal**: Validate all input fields before database operations, reject invalid requests and duplicate shards with explicit `ErrorOr` errors, and guarantee atomic rollback on persistence failure.

**Independent Test**: Issue requests with missing/whitespace fields and duplicate shard IDs; verify the API returns `400 Bad Request` with standard `ValidationProblemDetails` and leaves zero database records inserted.

### Implementation for User Story 2

- [x] T020 [US2] Implement input parameter validation and duplicate shard rejection returning `ErrorOr` in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`
- [x] T021 [US2] Map `ErrorOr` validation errors to RFC 7807 `ValidationProblemDetails` returning HTTP 400 in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainingTaskController.cs`
- [x] T022 [US2] Add structured logging for task creation metrics, validation rejections, and persistence errors in `src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainingTaskService.cs`

**Checkpoint**: Input validation, duplicate prevention, structured logging, and atomic rollback guarantees are fully operational.

---

## Phase 5: User Story 3 - Clean Architecture Restructuring and Boundary Isolation (Priority: P3)

**Goal**: Verify strict unidirectional dependencies across all 4 projects, confirm relocated commands and gRPC services function without regression, and ensure obsolete monolithic classes are eliminated.

**Independent Test**: Verify that `TrainSwarm.Coordinator.slnx` builds with zero errors, `Domain` has zero references, `CommandDispatchController` dispatches commands successfully, and `CoordinatorCommandServiceImpl` serves gRPC requests without regression.

### Implementation for User Story 3

- [x] T023 [P] [US3] Update namespace imports to `TrainSwarm.Coordinator.Application.Commands` in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/CommandDispatchController.cs`
- [x] T024 [P] [US3] Update namespace imports to `TrainSwarm.Coordinator.Application.Commands` in `src/Coordinator/TrainSwarm.Coordinator.Api/Grpc/CoordinatorCommandServiceImpl.cs`
- [x] T025 [US3] Configure command singletons, gRPC mapping, and OpenAPI schema metadata in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`
- [x] T026 [US3] Verify solution compilability and zero reverse-dependency violations by building `src/Coordinator/TrainSwarm.Coordinator.slnx`

**Checkpoint**: Clean Architecture boundary enforcement and gRPC/command compatibility verified.

---

## Phase 6: User Story 4 - Environment-Driven Persistence Configuration, Migrations, and Docker Deployment (Priority: P4)

**Goal**: Ensure SQLite persistence is configured strictly from `COORDINATOR_DB_CONNECTION_STRING`, apply EF Core migrations automatically during startup, update Dockerfile to multi-stage build of all 4 projects, and configure `/data` volume.

**Independent Test**: Launch the API without `COORDINATOR_DB_CONNECTION_STRING` and verify immediate fail-fast termination; launch with a valid connection string and verify automated migration creates the `TrainingTasks` table; build the Docker container image.

### Implementation for User Story 4

- [x] T027 [US4] Create initial EF Core SQLite migration for `TrainingTask` in `src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Migrations/`
- [x] T028 [US4] Implement startup fail-fast validation for `COORDINATOR_DB_CONNECTION_STRING` and automated migration execution in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`
- [x] T029 [US4] Update multi-stage build for all four projects and declare `/data` volume in `src/Coordinator/TrainSwarm.Coordinator.Api/Dockerfile`
- [x] T030 [US4] Update local developer startup script to configure `COORDINATOR_DB_CONNECTION_STRING` in `src/Coordinator/Run-Coordinator-Dev.ps1`

**Checkpoint**: Externalized environment configuration, automated startup migrations, and containerization verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, final code cleanup, and end-to-end verification.

- [x] T031 [P] Update module documentation with Clean Architecture, API contracts, configuration, Docker, and local run instructions in `src/Coordinator/README.md`
- [x] T032 Remove obsolete compiler directories, temporary files, and empty folders across `src/Coordinator/`
- [x] T033 Execute end-to-end runtime verification scenarios from `specs/012-coordinator-training-task/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion.
- **User Story 2 (Phase 4)**: Depends on User Story 1 completion.
- **User Story 3 (Phase 5)**: Depends on Foundational completion (can run concurrently with US1/US2).
- **User Story 4 (Phase 6)**: Depends on Foundational and User Story 1 completion.
- **Polish (Phase 7)**: Depends on all user story phases being complete.

### Parallel Opportunities

- Within Phase 1: `T002` and `T003` can be created in parallel.
- Within Phase 2: `T011` can be implemented in parallel with `T010`.
- Within Phase 3: `T014`, `T015`, and `T017` DTO definitions can be created in parallel.
- Within Phase 5: `T023` and `T024` namespace updates can run in parallel.
- Within Phase 7: `T031` documentation updates can run in parallel with cleanup tasks.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001 - T005).
2. Complete Phase 2: Foundational (T006 - T013).
3. Complete Phase 3: User Story 1 (T014 - T019).
4. **STOP and VALIDATE**: Verify basic task creation via `POST /api/training-tasks` and SQLite database records.

### Incremental Delivery

1. Setup + Foundational -> Foundation ready.
2. User Story 1 -> Multi-shard task creation endpoint working (MVP).
3. User Story 2 -> Validation, RFC 7807 ProblemDetails, and structured logging added.
4. User Story 3 -> Commands and gRPC endpoints verified with zero legacy remnants.
5. User Story 4 -> Environment-driven persistence, EF migrations, and Docker container verified.
6. Polish -> README and quickstart verification.
