# TrainSwarm Coordinator

The **Coordinator** is a control-plane service responsible for distributed training task provisioning, lifecycle coordination, and trainer node command dispatching across the TrainSwarm cluster.

---

## Architecture

The Coordinator follows **Clean Architecture** with strict unidirectional dependencies and dependency inversion:

```text
┌─────────────────────────────────────────────────────────┐
│              TrainSwarm.Coordinator.Api                 │
│  (HTTP / gRPC presentation, DI composition, OpenAPI)    │
└────────────┬───────────────────────────────┬────────────┘
             │                               │
             ▼                               ▼
┌──────────────────────────────┐ ┌───────────────────────────────┐
│ TrainSwarm.Coordinator.      │ │ TrainSwarm.Coordinator.       │
│ Application                  │ │ Infrastructure                │
│ (Use cases, DTOs, contracts, │ │ (EF Core DbContext, SQLite,   │
│  relocated Commands)         │ │  migrations, configurations)  │
└────────────┬─────────────────┘ └───────────┬───────────────────┘
             │                               │
             ▼                               ▼
┌─────────────────────────────────────────────────────────┐
│            TrainSwarm.Coordinator.Domain                │
│       (Pure core business entity: TrainingTask)         │
└─────────────────────────────────────────────────────────┘
```

### Projects

1. **`TrainSwarm.Coordinator.Domain`**: Contains core business entities (`TrainingTask`). Zero external framework dependencies.
2. **`TrainSwarm.Coordinator.Application`**: Contains application use cases (`TrainingTaskService`), DTO contracts (`CreateTrainingTaskDto`, `CreateTrainingTaskResult`), persistence abstractions (`ICoordinatorDbContext`), and relocated trainer command dispatching (`Commands/`).
3. **`TrainSwarm.Coordinator.Infrastructure`**: Contains persistence implementation (`CoordinatorDbContext`), SQLite database configurations via EF Core Fluent API, and automated migrations.
4. **`TrainSwarm.Coordinator.Api`**: ASP.NET Core Web API project hosting REST endpoints (`TrainingTaskController`, `CommandDispatchController`), gRPC server (`CoordinatorCommandServiceImpl`), and host configuration.

---

## TrainingTask Feature

The `TrainingTask` capability provisions training partition workloads. When an API client submits a request with multiple dataset shard IDs, the Coordinator validates the payload and atomically persists **one independent `TrainingTask` entity per requested shard**, each with:
- A unique primary key `Guid` (`TrainingTaskId`).
- The shared `ClientNodeId`, `ModelId`, `ModelVersion`, and `DataSetId`.
- The specific `ShardId`.
- `TrainerNodeId` initialized to `string.Empty` (unassigned).

All shard tasks within a request are committed atomically within a single SQLite transaction: either all requested shard tasks are persisted or none are.

---

## API Specification

### Create Training Tasks

- **Method**: `POST`
- **Route**: `/api/training-tasks`
- **Content-Type**: `application/json`

#### Request Body (`CreateTrainingTaskDto`)

| Field | Type | Required | Constraints |
|---|---|---|---|
| `clientNodeId` | `string` | Yes | Non-null, non-empty, not only whitespace |
| `modelId` | `string` | Yes | Non-null, non-empty, not only whitespace |
| `modelVersion` | `string` | Yes | Non-null, non-empty, not only whitespace |
| `dataSetId` | `string` | Yes | Non-null, non-empty, not only whitespace |
| `shardIdList` | `string[]` | Yes | Must contain at least one shard; all elements non-empty and unique |

#### Example Request

```json
{
  "clientNodeId": "client-001",
  "modelId": "gpt2",
  "modelVersion": "12",
  "dataSetId": "dataset-001",
  "shardIdList": [
    "shard-001",
    "shard-002",
    "shard-003"
  ]
}
```

#### Successful Response (`201 Created`)

Returns the list of generated task IDs corresponding to the requested shards:

```json
{
  "trainingTaskIds": [
    "c8a514d2-28c9-4a94-b52b-7e6df8f74e62",
    "85dbd3ea-b19b-44ec-b873-ea5c6be2be71",
    "9f8a37e5-c2cf-4b72-8818-80b62e49c719"
  ]
}
```

#### Validation Failure (`400 Bad Request`)

If validation fails (missing fields, whitespace, empty shard list, or duplicate shard IDs), the API returns standard RFC 7807 `ValidationProblemDetails` with zero database writes:

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "errors": {
    "Invalid.DuplicateShardId": [
      "ShardIdList cannot contain duplicate shard IDs."
    ]
  }
}
```

---

## Configuration

The Coordinator database configuration is strictly externalized and read from the environment variable:

```bash
COORDINATOR_DB_CONNECTION_STRING="Data Source=/data/coordinator.db"
```

- **No Hard-Coded Fallback**: If `COORDINATOR_DB_CONNECTION_STRING` is missing or empty, the application fails fast during startup with an informative configuration exception.
- **Automated Migrations**: Upon valid startup, EF Core automatically applies all pending migrations to ensure the schema is up-to-date before handling traffic.

---

## Local Development

### 1. Build Solution

Restore dependencies and build all projects:

```powershell
dotnet build src/Coordinator/TrainSwarm.Coordinator.slnx
```

### 2. Run API

Set the environment variable and start the application:

```powershell
$env:COORDINATOR_DB_CONNECTION_STRING = "Data Source=coordinator_local.db"
dotnet run --project src/Coordinator/TrainSwarm.Coordinator.Api
```

Alternatively, execute the local runner script:

```powershell
.\src\Coordinator\Run-Coordinator-Dev.ps1
```

### 3. Access API & OpenAPI

Once running, the API listens on `http://localhost:8080`.
- OpenAPI schema endpoint: `http://localhost:8080/openapi/v1.json`

---

## Docker Deployment

### 1. Build Container Image

Build the multi-stage Docker image from the Coordinator directory:

```bash
docker build -f src/Coordinator/TrainSwarm.Coordinator.Api/Dockerfile -t trainswarm-coordinator src/Coordinator/
```

### 2. Run with Persistent Storage Volume

Mount a host or Docker named volume to `/data` so SQLite storage persists across container restarts:

```bash
docker run --rm -d \
  -p 8080:8080 \
  -v coordinator_data:/data \
  -e COORDINATOR_DB_CONNECTION_STRING="Data Source=/data/coordinator.db" \
  --name coordinator \
  trainswarm-coordinator
```
