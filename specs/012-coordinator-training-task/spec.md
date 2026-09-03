# Feature Specification: Coordinator — TrainingTask Feature and Clean Architecture Restructure

**Feature Branch**: `012-coordinator-training-task`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Restructure the existing Coordinator module into a Clean Architecture structure and implement the new TrainingTask feature. Split Coordinator into TrainSwarm.Coordinator.Domain, Application, Infrastructure, and Api. Implement TrainingTask domain model, application service with ErrorOr, SQLite persistence via EF Core configured from COORDINATOR_DB_CONNECTION_STRING, atomic creation of one TrainingTask per shard via POST /api/training-tasks, structured logging, relocate Commands to Application, preserve gRPC API, remove obsolete services/controllers, update Dockerfile and README."

## Clarifications

### Session 2026-09-03

- **Q: How should the Coordinator handle a request when `ShardIdList` contains duplicate shard identifiers? (FR-012)** → **A: Reject the request with validation error `Invalid.DuplicateShardId` (HTTP 400 Bad Request) (Option A).**
- **Q: What JSON response structure should `TrainingTaskController` return when mapping `ErrorOr` validation errors to HTTP 400 Bad Request? (FR-026)** → **A: Standard RFC 7807 `ValidationProblemDetails` containing `title`, `status: 400`, and an `errors` dictionary (Option A).**
- **Q: How should the initial unassigned state of `TrainerNodeId` be represented in the entity and database schema? (FR-008)** → **A: Initialize `TrainerNodeId` as `string.Empty` and configure it as a non-nullable database column (`TEXT NOT NULL DEFAULT ''`) (Option A).**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and Persist Distributed Training Tasks per Shard (Priority: P1)

As a distributed training client or control-plane coordinator operator, I want to submit a training task creation request containing client identity, model identity, model version, dataset identity, and a list of dataset shard identifiers, so that the Coordinator atomically provisions and persists exactly one independent `TrainingTask` entity per requested shard with a unique identifier and an unassigned trainer state.

**Why this priority**: Foundational control-plane capability for distributed model training in TrainSwarm. Without durable, per-shard training task records, the Coordinator cannot track or assign partition workloads to distributed trainers.

**Independent Test**: Send an HTTP POST request to `/api/training-tasks` with a valid JSON payload containing 3 shard IDs. Verify that the response status is `201 Created` with a JSON payload containing exactly 3 distinct GUID strings. Verify in the SQLite database that 3 rows exist in the `TrainingTasks` table sharing identical client, model, model version, and dataset identifiers, with matching shard identifiers and empty `TrainerNodeId`.

**Acceptance Scenarios**:

1. **Given** a valid `CreateTrainingTaskDto` containing `ClientNodeId = "client-01"`, `ModelId = "model-01"`, `ModelVersion = "5"`, `DataSetId = "dataset-01"`, and `ShardIdList = ["shard-01", "shard-02", "shard-03"]`, **When** `POST /api/training-tasks` is invoked, **Then** the service returns `201 Created` with a JSON body containing `trainingTaskIds` containing exactly 3 GUIDs.
2. **Given** a persisted set of training tasks from a creation request, **When** inspecting the database records, **Then** each task has a newly generated `Guid` primary key (`TrainingTaskId`), matching `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, respective `ShardId`, and `TrainerNodeId = string.Empty`.
3. **Given** an existing populated database, **When** new tasks are created, **Then** previously persisted tasks remain unmodified and intact.

---

### User Story 2 - Request Validation and Atomic Transaction Guarantees (Priority: P2)

As a system operator, I want all input parameters strictly validated before database execution and all shard tasks persisted within an atomic transaction, so that invalid requests are rejected immediately without database writes, and unexpected persistence failures leave zero partial or orphaned records.

**Why this priority**: Guarantees database integrity and prevents corrupted, partial, or orphaned state in distributed training coordination.

**Independent Test**: Send invalid requests (missing `ClientNodeId`, empty `ModelId`, whitespace `ModelVersion`, null `DataSetId`, empty `ShardIdList`, or a list containing whitespace shard IDs). Verify that the API returns `400 Bad Request` with structured `ErrorOr` validation errors and that zero database rows are inserted. Simulate a database constraint or I/O failure during multi-task insertion and verify that 0 tasks are committed to the database.

**Acceptance Scenarios**:

1. **Given** a request where any of `ClientNodeId`, `ModelId`, `ModelVersion`, or `DataSetId` is null, empty, or whitespace, **When** `POST /api/training-tasks` is executed, **Then** the service returns `400 Bad Request` with an appropriate error code (e.g., `Invalid.ClientNodeId`, `Invalid.ModelId`, `Invalid.ModelVersion`, `Invalid.DataSetId`) and no database transaction occurs.
2. **Given** a request where `ShardIdList` is null, empty, or contains null/empty/whitespace shard items, **When** `POST /api/training-tasks` is executed, **Then** the service returns `400 Bad Request` with error `Invalid.ShardIdList` or `Invalid.ShardId` and no database transaction occurs.
3. **Given** a request specifying 10 shards where database persistence fails midway through insertion, **When** the transaction encounters an error, **Then** all pending inserts roll back atomically, leaving 0 tasks from that request persisted.

---

### User Story 3 - Clean Architecture Restructuring and Boundary Isolation (Priority: P3)

As a software engineer maintaining the TrainSwarm platform, I want the Coordinator solution restructured into four distinct projects (`Domain`, `Application`, `Infrastructure`, `Api`) with strict unidirectional dependency inversion and nullable disabled, so that business models and use cases are completely insulated from web frameworks and database providers, while preserving existing command dispatching and gRPC functionality.

**Why this priority**: Resolves legacy monolithic coupling in the Coordinator, standardizes solution architecture across TrainSwarm, cleanly isolates EF Core/SQLite persistence into Infrastructure, and enables independent testing and extensibility.

**Independent Test**: Build the entire Coordinator solution. Verify the dependency direction: `Domain` has no project references; `Application` references only `Domain` (and EF Core abstractions); `Infrastructure` references `Application` and `Domain`; `Api` references `Application` and `Infrastructure`. Verify that `Commands/` relocated to `Application` functions identically, and gRPC endpoints in `Api/Grpc` compile and execute without regression.

**Acceptance Scenarios**:

1. **Given** the restructured solution, **When** compiling `TrainSwarm.Coordinator.Domain`, **Then** it compiles with zero references to EF Core, ASP.NET Core, Infrastructure, or Api, containing only core domain entities (`TrainingTask`).
2. **Given** the relocated `Commands/` folder in `TrainSwarm.Coordinator.Application`, **When** `TrainSwarm.Coordinator.Api` runs gRPC command dispatching, **Then** the gRPC service `CoordinatorCommandServiceImpl` and REST controller `CommandDispatchController` dispatch commands without error.
3. **Given** obsolete Coordinator services (`SessionService`, `TrainerService`), entities, repositories, context, and controllers (`SessionsController`, `TrainersController`), **When** the restructure completes, **Then** all obsolete files are removed and the solution builds cleanly without dead references.

---

### User Story 4 - Environment-Driven Persistence Configuration, Migrations, and Docker Deployment (Priority: P4)

As a DevOps engineer deploying TrainSwarm in containerized environments, I want the Coordinator to configure SQLite persistence strictly via the `COORDINATOR_DB_CONNECTION_STRING` environment variable, apply EF Core migrations automatically during startup, and run within a multi-stage Docker container supporting persistent volume mounts, so that deployment is predictable, secure, and resilient across restarts.

**Why this priority**: Ensures seamless containerized execution, prevents hardcoded database paths, and guarantees durable persistence across container lifecycles.

**Independent Test**: Start the Coordinator API with `COORDINATOR_DB_CONNECTION_STRING` unset or empty, verifying immediate startup failure with a clear error message. Start with `COORDINATOR_DB_CONNECTION_STRING=Data Source=/data/coordinator.db` and verify automated migration and database creation. Build the multi-stage Dockerfile and run the container with a mounted `/data` volume, verifying functional API readiness and database persistence.

**Acceptance Scenarios**:

1. **Given** `COORDINATOR_DB_CONNECTION_STRING` is unset or empty at startup, **When** the application launches, **Then** the application aborts startup immediately with a descriptive configuration error message.
2. **Given** a valid SQLite connection string, **When** the application starts, **Then** EF Core migrations automatically execute to ensure the SQLite schema and `TrainingTasks` table exist before HTTP traffic is accepted.
3. **Given** the updated Dockerfile, **When** executing `docker build`, **Then** all 4 projects build and publish cleanly, producing a runnable image that exposes port 8080 and a `/data` volume for SQLite persistence.

---

### Edge Cases

- **Empty or Whitespace-Only Shard Identifiers**: A `ShardIdList` containing valid entries mixed with an empty or whitespace string (e.g., `["shard-1", "   ", "shard-2"]`) must fail validation completely; partial persistence is strictly disallowed.
- **Duplicate Shard IDs in Single Request**: If a client request contains duplicate shard identifiers within `ShardIdList` (e.g., `["shard-01", "shard-01"]`), `TrainingTaskService` rejects the entire request with validation error `Invalid.DuplicateShardId` (HTTP 400 Bad Request) and performs zero database writes.
- **Missing Environment Variable on Startup**: If `COORDINATOR_DB_CONNECTION_STRING` is not configured, the API must fail fast during host building, preventing unconfigured execution.
- **Database Lock Contention under High Concurrency**: SQLite file locks under concurrent write operations must be handled cleanly through scoped connection management and appropriate transaction timeouts.
- **Unwriteable Database Directory**: If the SQLite file path cannot be created or accessed due to permissions, startup migration must fail with an informative logged error.
- **Large Shard Batches**: A request with a large number of shards (e.g., 500 shards) must execute within a single transaction without exceeding transaction limits or leaking connections.

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Solution Structure & Clean Architecture Boundaries
- **FR-001**: The Coordinator solution MUST consist of exactly four .NET class/executable projects:
  - `TrainSwarm.Coordinator.Domain` (Class Library)
  - `TrainSwarm.Coordinator.Application` (Class Library)
  - `TrainSwarm.Coordinator.Infrastructure` (Class Library)
  - `TrainSwarm.Coordinator.Api` (ASP.NET Core Web API)
- **FR-002**: All projects MUST have nullable reference types disabled (`<Nullable>disable</Nullable>`).
- **FR-003**: Project references MUST strictly adhere to Clean Architecture dependency rules:
  - `Domain` MUST NOT depend on any other project, EF Core, or ASP.NET Core.
  - `Application` MUST depend only on `Domain` and `Microsoft.EntityFrameworkCore` (for `ICoordinatorDbContext` and `DbSet`).
  - `Infrastructure` MUST depend on `Application` and `Domain`.
  - `Api` MUST depend on `Application` and `Infrastructure`.
  - No reverse dependencies or bypass dependencies are permitted.
- **FR-004**: The existing `/Commands` directory from `TrainSwarm.Coordinator.Domain` MUST be relocated entirely to `TrainSwarm.Coordinator.Application` without changes to command logic.
- **FR-005**: All obsolete Coordinator services (`SessionService`, `TrainerService`), old entities (`Session`, `Trainer`), old context (`CoordinatorDbContext` in Domain), old migrations, old controllers (`SessionsController`, `TrainersController`), and obsolete references MUST be completely removed.
- **FR-006**: Existing gRPC API (`TrainSwarm.Coordinator.Api.Grpc.CoordinatorCommandServiceImpl`) and command REST endpoint (`CommandDispatchController`) MUST remain intact and operational.

#### 2. Domain Model (`TrainSwarm.Coordinator.Domain`)
- **FR-007**: System MUST provide the `TrainingTask` entity in namespace `TrainSwarm.Coordinator.Domain.Entities`.
- **FR-008**: `TrainingTask` MUST contain exactly the following business properties:
  - `TrainingTaskId` (`Guid`): Primary key.
  - `ClientNodeId` (`string`): Identifier of the client node (required).
  - `ModelId` (`string`): Identifier of the model being trained (required).
  - `ModelVersion` (`string`): Target model checkpoint version (required).
  - `DataSetId` (`string`): Identifier of the dataset (required).
  - `ShardId` (`string`): Identifier of the specific dataset shard (required).
  - `TrainerNodeId` (`string`): Identifier of assigned trainer; initialized to `string.Empty` upon task creation and stored as a non-nullable database column defaulting to empty string.
- **FR-009**: `TrainingTask` MUST NOT contain API DTO concerns or EF Core mapping attributes (prefer EF Core Fluent API configuration in Infrastructure).

#### 3. Application Layer (`TrainSwarm.Coordinator.Application`)
- **FR-010**: System MUST define `CreateTrainingTaskDto` in `TrainSwarm.Coordinator.Application.Services` containing:
  - `ClientNodeId` (`string`, required)
  - `ModelId` (`string`, required)
  - `ModelVersion` (`string`, required)
  - `DataSetId` (`string`, required)
  - `ShardIdList` (`List<string>`, required, non-empty)
- **FR-011**: System MUST provide `TrainingTaskService` in `TrainSwarm.Coordinator.Application.Services` exposing:
  `Task<ErrorOr<CreateTrainingTaskResult>> CreateTrainingTaskAsync(CreateTrainingTaskDto request, CancellationToken ct = default)`.
- **FR-012**: `TrainingTaskService` MUST validate the complete DTO prior to any persistence operation:
  - `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId` must not be null, empty, or whitespace.
  - `ShardIdList` must not be null or empty.
  - Each shard ID in `ShardIdList` must not be null, empty, or whitespace.
  - Shard IDs within `ShardIdList` must be distinct without duplicates.
- **FR-013**: Validation failures MUST return explicit `ErrorOr.Error` objects (e.g., `Invalid.ClientNodeId`, `Invalid.ModelId`, `Invalid.ModelVersion`, `Invalid.DataSetId`, `Invalid.ShardIdList`, `Invalid.ShardId`, `Invalid.DuplicateShardId`) without throwing exceptions.
- **FR-014**: For every valid shard ID in `ShardIdList`, `TrainingTaskService` MUST instantiate one `TrainingTask` entity with a newly generated `Guid`, copying `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, assigning the specific `ShardId`, and setting `TrainerNodeId = string.Empty`.
- **FR-015**: All generated `TrainingTask` entities for a request MUST be persisted within an atomic transaction via `ICoordinatorDbContext`. If any insertion fails, the entire transaction rolls back cleanly with zero committed records.
- **FR-016**: Application project MUST define the persistence abstraction `ICoordinatorDbContext` under `TrainSwarm.Coordinator.Application.Contracts` exposing:
  - `DbSet<TrainingTask> TrainingTasks { get; }`
  - `Task<int> SaveChangesAsync(CancellationToken ct = default)`

#### 4. Infrastructure & Persistence (`TrainSwarm.Coordinator.Infrastructure`)
- **FR-017**: Infrastructure project MUST implement `CoordinatorDbContext` in `TrainSwarm.Coordinator.Infrastructure.Persistence`, inheriting from `DbContext` and implementing `ICoordinatorDbContext`.
- **FR-018**: System MUST configure `TrainingTask` via `TrainingTaskConfiguration` implementing `IEntityTypeConfiguration<TrainingTask>`, configuring `TrainingTaskId` as primary key, and all string columns (including `TrainerNodeId`) as non-nullable database columns with `TrainerNodeId` defaulting to `string.Empty` (`TEXT NOT NULL DEFAULT ''`).
- **FR-019**: Infrastructure MUST use EF Core SQLite provider (`Microsoft.EntityFrameworkCore.Sqlite`).
- **FR-020**: The SQLite connection string MUST be loaded exclusively from the environment variable `COORDINATOR_DB_CONNECTION_STRING`. If missing or empty, application startup MUST fail immediately with an explicit configuration error; hardcoded connection strings and silent defaults are strictly prohibited.
- **FR-021**: Infrastructure MUST provide an extension method `AddCoordinatorPersistenceServices` on `IServiceCollection` to register `CoordinatorDbContext` as `ICoordinatorDbContext` via `AddDbContext`.
- **FR-022**: Infrastructure MUST provide an initial EF Core migration for `TrainingTask` creating the `TrainingTasks` table.
- **FR-023**: Application startup MUST execute `Database.Migrate()` on `CoordinatorDbContext` ensuring the database schema is up-to-date before handling HTTP/gRPC requests.

#### 5. Presentation / API Layer (`TrainSwarm.Coordinator.Api`)
- **FR-024**: System MUST expose `POST /api/training-tasks` via `TrainingTaskController`.
- **FR-025**: The endpoint MUST accept `CreateTrainingTaskDto` as JSON body and delegate execution to `TrainingTaskService`.
- **FR-026**: Validation failures returned by `TrainingTaskService` MUST be mapped to `400 Bad Request` using standard RFC 7807 `ValidationProblemDetails` containing `title`, `status = 400`, and an `errors` dictionary mapping invalidated property names or error codes to error descriptions.
- **FR-027**: Successful creation MUST return `201 Created` with a response payload containing the list of newly created task GUIDs: `{"trainingTaskIds": ["guid-1", "guid-2", ...]}`.
- **FR-028**: Controllers MUST NOT access `CoordinatorDbContext`, EF Core entities, or execute database operations directly.
- **FR-029**: Application logging MUST use `Microsoft.Extensions.Logging` structured logging for successful task creations (logging `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardCount`), validation rejections, and persistence failures. Primary logging MUST NOT use `Console.WriteLine`.
- **FR-030**: API project MUST configure OpenAPI / Swagger descriptions for request and response models.

#### 6. Docker & Documentation
- **FR-031**: Coordinator `Dockerfile` MUST be updated to build and publish all four projects (`Domain`, `Application`, `Infrastructure`, `Api`) in multi-stage builds.
- **FR-032**: Docker container MUST configure a `/data` directory suitable for mounting persistent host storage for the SQLite database.
- **FR-033**: Coordinator `README.md` MUST be updated to document Coordinator responsibilities, Clean Architecture layout, `TrainingTask` endpoint usage, environment variables, local development steps, and Docker deployment with persistent volumes.

### Key Entities

- **`TrainingTask`**: Core domain entity representing an atomic unit of distributed training assigned to a specific dataset shard for a model version.
  - Attributes: `TrainingTaskId` (Guid, PK), `ClientNodeId` (string), `ModelId` (string), `ModelVersion` (string), `DataSetId` (string), `ShardId` (string), `TrainerNodeId` (string, initially empty).
- **`CreateTrainingTaskDto`**: Application contract defining the payload required to create training tasks across a list of shards.
  - Attributes: `ClientNodeId` (string), `ModelId` (string), `ModelVersion` (string), `DataSetId` (string), `ShardIdList` (List<string>).
- **`CreateTrainingTaskResult`**: Application DTO representing the outcome of task creation.
  - Attributes: `TrainingTaskIds` (IReadOnlyList<Guid>).
- **`ICoordinatorDbContext`**: Application abstraction defining the persistence contract implemented by Infrastructure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the four Coordinator projects (`Domain`, `Application`, `Infrastructure`, `Api`) restore, compile, and build cleanly with zero errors.
- **SC-002**: 100% compliance with Clean Architecture dependency boundaries (zero references from `Domain` to other projects/EF Core/ASP.NET; zero references from `Application` to `Infrastructure` or `Api`).
- **SC-003**: 100% atomicity for training task persistence (a request for N shards persists either all N tasks or 0 tasks upon failure).
- **SC-004**: 100% of invalid creation requests (missing/empty fields, empty shard list, whitespace items) return HTTP `400 Bad Request` with structured error details and perform zero database writes.
- **SC-005**: 100% of valid creation requests return HTTP `201 Created` with exactly the set of generated GUIDs corresponding to the requested shards.
- **SC-006**: 100% configuration enforcement: Coordinator fails fast on launch when `COORDINATOR_DB_CONNECTION_STRING` is missing or empty.
- **SC-007**: 0 regression on relocated `Commands/` and existing gRPC API (`CoordinatorCommandServiceImpl` and `CommandDispatchController`).
- **SC-008**: Coordinator Docker image builds successfully and initializes the SQLite database within `/data`.

## Assumptions

- Target .NET SDK version is .NET 10.0 (aligned with existing Coordinator `.csproj` and `Dockerfile` configurations).
- SQLite is the sole persistence provider for Coordinator training tasks in this architecture.
- `TrainerNodeId` is unassigned (`string.Empty`) at creation time because trainer scheduling and discovery occur in downstream workflows.
- Shard IDs within `ShardIdList` in a single request must be unique non-empty strings.
- The SQLite connection string format follows standard ADO.NET syntax (e.g., `Data Source=/data/coordinator.db`).
- Application logging utilizes structured logger categories via `ILogger<T>`.
