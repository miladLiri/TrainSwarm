# Data Model: Coordinator Clean Architecture & TrainingTask

**Branch**: `012-coordinator-training-task` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

## 1. Domain Entities

### `TrainingTask`

Represents an atomic, durable unit of distributed training assigned to a specific dataset shard for a model version.

- **Namespace**: `TrainSwarm.Coordinator.Domain.Entities`
- **Class**: `TrainingTask`

| Property | C# Type | Required | Nullable | Default | Description |
|---|---|---|---|---|---|
| `TrainingTaskId` | `Guid` | Yes | No | `Guid.NewGuid()` | Primary key identity of the training task. |
| `ClientNodeId` | `string` | Yes | No | None | Identifier of the submitting Training Client node. |
| `ModelId` | `string` | Yes | No | None | Identifier of the neural model being trained (e.g. `gpt2`). |
| `ModelVersion` | `string` | Yes | No | None | Target model checkpoint version (e.g. `5`, `12`). |
| `DataSetId` | `string` | Yes | No | None | Identifier of the dataset being trained on. |
| `ShardId` | `string` | Yes | No | None | Identifier of the specific partition shard within the dataset. |
| `TrainerNodeId` | `string` | Yes | No | `string.Empty` | Identifier of the assigned trainer node; empty string when unassigned. |

#### Lifecycle / State Transitions

1. **Created (Unassigned)**: Created by `TrainingTaskService` upon receiving `CreateTrainingTaskDto`. `TrainerNodeId` is set to `string.Empty`.
2. **Assigned**: Downstream coordinator scheduling (future feature) assigns a registered trainer node ID to `TrainerNodeId`.
3. **Completed / Failed**: Monitored via task execution events (future features).

---

## 2. Application Contracts & DTOs

### `CreateTrainingTaskDto`

Input payload sent by clients to request training task creation across multiple shards.

- **Namespace**: `TrainSwarm.Coordinator.Application.Services`

| Field | Type | Required | Validation Rules |
|---|---|---|---|
| `ClientNodeId` | `string` | Yes | Non-null, non-empty, not only whitespace. |
| `ModelId` | `string` | Yes | Non-null, non-empty, not only whitespace. |
| `ModelVersion` | `string` | Yes | Non-null, non-empty, not only whitespace. |
| `DataSetId` | `string` | Yes | Non-null, non-empty, not only whitespace. |
| `ShardIdList` | `List<string>` | Yes | Non-null, count > 0, every element non-null/non-empty/not whitespace, all elements distinct. |

### `CreateTrainingTaskResult`

Application-level return payload indicating generated task identities.

- **Namespace**: `TrainSwarm.Coordinator.Application.Services`

| Field | Type | Description |
|---|---|---|
| `TrainingTaskIds` | `IReadOnlyList<Guid>` | The list of generated GUIDs corresponding to the requested shards. |

### `CreateTrainingTaskResponseDto`

HTTP presentation response body returned by `TrainingTaskController`.

- **Namespace**: `TrainSwarm.Coordinator.Api.Controllers`

```json
{
  "trainingTaskIds": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "7ba85f64-5717-4562-b3fc-2c963f66afa7"
  ]
}
```

---

## 3. Database Schema Mapping (SQLite)

### Table: `TrainingTasks`

Configured in `TrainSwarm.Coordinator.Infrastructure.Persistence.Configurations.TrainingTaskConfiguration` using EF Core Fluent API.

| Column Name | SQLite Data Type | Constraints | Default | Mapping |
|---|---|---|---|---|
| `TrainingTaskId` | `TEXT` | `PRIMARY KEY NOT NULL` | None | `Guid` stored as string representation |
| `ClientNodeId` | `TEXT` | `NOT NULL` | None | String property |
| `ModelId` | `TEXT` | `NOT NULL` | None | String property |
| `ModelVersion` | `TEXT` | `NOT NULL` | None | String property |
| `DataSetId` | `TEXT` | `NOT NULL` | None | String property |
| `ShardId` | `TEXT` | `NOT NULL` | None | String property |
| `TrainerNodeId` | `TEXT` | `NOT NULL` | `''` | String property defaulting to empty string |

#### SQLite DDL (Initial Migration)

```sql
CREATE TABLE "TrainingTasks" (
    "TrainingTaskId" TEXT NOT NULL CONSTRAINT "PK_TrainingTasks" PRIMARY KEY,
    "ClientNodeId" TEXT NOT NULL,
    "ModelId" TEXT NOT NULL,
    "ModelVersion" TEXT NOT NULL,
    "DataSetId" TEXT NOT NULL,
    "ShardId" TEXT NOT NULL,
    "TrainerNodeId" TEXT NOT NULL DEFAULT ''
);
```

---

## 4. Validation & Error Catalog

| Error Code | HTTP Status | Validation Condition | Message / Description |
|---|---|---|---|
| `Invalid.ClientNodeId` | 400 | `ClientNodeId` is null, empty, or whitespace | "ClientNodeId is required and cannot be empty or whitespace." |
| `Invalid.ModelId` | 400 | `ModelId` is null, empty, or whitespace | "ModelId is required and cannot be empty or whitespace." |
| `Invalid.ModelVersion` | 400 | `ModelVersion` is null, empty, or whitespace | "ModelVersion is required and cannot be empty or whitespace." |
| `Invalid.DataSetId` | 400 | `DataSetId` is null, empty, or whitespace | "DataSetId is required and cannot be empty or whitespace." |
| `Invalid.ShardIdList` | 400 | `ShardIdList` is null or empty | "ShardIdList is required and must contain at least one shard ID." |
| `Invalid.ShardId` | 400 | An element in `ShardIdList` is null, empty, or whitespace | "ShardId elements cannot be null, empty, or whitespace." |
| `Invalid.DuplicateShardId` | 400 | `ShardIdList` contains duplicate shard identifiers | "ShardIdList cannot contain duplicate shard IDs." |
