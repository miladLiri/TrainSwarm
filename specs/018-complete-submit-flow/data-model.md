# Data Model Specification: Completing Submit Flow

**Feature**: `018-complete-submit-flow` | **Date**: 2026-09-08

## Overview

This document specifies the domain entities, database schemas, message contracts, and state lifecycle transitions across the Client, Coordinator, and Trainer services for the end-to-end model submission and task assignment flow.

---

## 1. Client Domain & Persistence Models

### 1.1 Model Entity (`Client.models.Model`)

Represents top-level metadata for a model submitted for distributed training.

```python
@dataclass
class Model:
    model_id: str             # Generated UUID string
    model_type: str           # Distributed training engine enum string (e.g. "canonical_torch")
    model_version: str        # Semantic or incremental version string (e.g. "1.0.0")
    dataset_id: str           # Generated UUID string for the associated dataset
    model_artifact_path: str  # Absolute path to staged model checkpoint (e.g. ".../uuid_v1.0.0.pt2")
    training_config_path: str # Absolute path to staged training config JSON (e.g. ".../uuid_v1.0.0_config.json")
```

#### Validation Invariants:
- `model_id`: Non-empty string, valid UUID format.
- `model_type`: Non-empty string matching supported training engine types (`canonical_torch`).
- `model_version`: Non-empty string.
- `dataset_id`: Non-empty string, valid UUID format.
- `model_artifact_path`: Non-empty string pointing to existing staged checkpoint file.
- `training_config_path`: Non-empty string pointing to existing staged configuration file.

### 1.2 SQLite Schema: `models` Table

Created idempotently in `Client.infrastructure.persistence.DatabaseManager`:

```sql
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY NOT NULL,
    model_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    model_artifact_path TEXT NOT NULL,
    training_config_path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_models_dataset_id ON models (dataset_id);
```

### 1.3 Entity Relationships in Client

```text
+-------------------------------------------------------+
|                        Model                          |
+-------------------------------------------------------+
| PK model_id: str                                      |
|    model_type: str                                    |
|    model_version: str                                 |
|    dataset_id: str                                    |
|    model_artifact_path: str                           |
|    training_config_path: str                          |
+-------------------------------------------------------+
                           | 1
                           |
                           | 1..*
                           v
+-------------------------------------------------------+
|                    TrainingShard                      |
+-------------------------------------------------------+
| PK id: str (UUID)                                     |
| FK model_id: str                                      |
|    model_version: str                                 |
| FK dataset_id: str                                    |
|    shard_id: str                                      |
|    artifact_path: str                                 |
|    sample_count: int                                  |
|    status: TrainingShardStatus                        |
|    training_task_id: Optional[str]                    |
+-------------------------------------------------------+
```

---

## 2. Coordinator Control Plane Models

### 2.1 TrainingTask Entity (`TrainSwarm.Coordinator.Domain.Entities.TrainingTask`)

```csharp
public class TrainingTask
{
    public Guid TrainingTaskId { get; set; }
    public string ClientNodeId { get; set; } = string.Empty;
    public string ModelId { get; set; } = string.Empty;
    public string ModelVersion { get; set; } = string.Empty;
    public string DataSetId { get; set; } = string.Empty;
    public string ShardId { get; set; } = string.Empty;
    public string TrainerNodeId { get; set; } = string.Empty;
    public DateTime SubmitTime { get; set; }
}
```

### 2.2 Trainer Entity (`TrainSwarm.Coordinator.Domain.Entities.Trainer`)

```csharp
public class Trainer
{
    public Guid Id { get; set; }
    public string TrainerNodeId { get; set; } = string.Empty;
    public string Address { get; set; } = string.Empty;
    public int Port { get; set; }
    public TrainerStatus Status { get; set; } = TrainerStatus.IDLE;
    public DateTime RegisteredAt { get; set; }
    public DateTime LastHeartbeat { get; set; }
}

public enum TrainerStatus
{
    IDLE = 1,
    BUSY = 2,
    UNCLEAR = 3
}
```

### 2.3 StartTrainingCommand DTO (`TrainSwarm.Coordinator.Application.Commands.StartTrainingCommand`)

```csharp
public class StartTrainingCommand
{
    [JsonPropertyName("clientNodeId")]
    public string ClientNodeId { get; set; } = string.Empty;

    [JsonPropertyName("modelId")]
    public string ModelId { get; set; } = string.Empty;

    [JsonPropertyName("modelVersion")]
    public string ModelVersion { get; set; } = string.Empty;

    [JsonPropertyName("dataSetId")]
    public string DataSetId { get; set; } = string.Empty;

    [JsonPropertyName("shardId")]
    public string ShardId { get; set; } = string.Empty;
}
```

---

## 3. Trainer Application Command Models

### 3.1 StartTrainingCommand (`Trainer.application.coordinator_commands.start_training.command.StartTrainingCommand`)

```python
@dataclass(frozen=True)
class StartTrainingCommand:
    client_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartTrainingCommand":
        client_node_id = data.get("clientNodeId") or data.get("client_node_id")
        model_id = data.get("modelId") or data.get("model_id")
        model_version = data.get("modelVersion") or data.get("model_version")
        data_set_id = data.get("dataSetId") or data.get("data_set_id")
        shard_id = data.get("shardId") or data.get("shard_id")

        if not all([client_node_id, model_id, model_version, data_set_id, shard_id]):
            raise ValueError(f"Missing required fields for StartTrainingCommand: {data}")

        return cls(
            client_node_id=str(client_node_id),
            model_id=str(model_id),
            model_version=str(model_version),
            data_set_id=str(data_set_id),
            shard_id=str(shard_id),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clientNodeId": self.client_node_id,
            "modelId": self.model_id,
            "modelVersion": self.model_version,
            "dataSetId": self.data_set_id,
            "shardId": self.shard_id,
        }
```

---

## 4. State Lifecycle Transitions

### 4.1 Client Submission Lifecycle

```text
[Input Files: .pt2, .pt, config.json]
                 |
                 v
        1. Validate & Stage
    (Staged into {working_dir}/{model_id}/)
                 |
                 v
      2. Sample & Smoke Test
   (Calculate recommended_samples_per_shard)
                 |
                 v
       3. Partition Dataset
     (Shards written to shards/{dataset_id}/)
                 |
                 v
     4. Persist Shards Locally
     (SQLite status: CREATED)
                 |
                 v
     5. Persist Model Locally
       (SQLite `models` table)
      [If fails -> Abort, leave CREATED]
                 |
                 v
    6. Register with Coordinator
    (POST /api/training-tasks)
                 |
                 v
    7. Update Shards to READY
     (SQLite status: READY)
```

### 4.2 Coordinator Task & Trainer Lifecycle

```text
Task Submitted -> Stored in SQLite (TrainerNodeId: "")
                      |
                      v
          Background Safe Scheduler
          (Guarded by SemaphoreSlim)
                      |
                      +---> Check Idle Trainers (Status == IDLE)
                      |
                      +---> Fair Model Round-Robin Selection
                      |
                      v
        Commit DB Assignment Transaction:
          - task.TrainerNodeId = trainer.TrainerNodeId
          - trainer.Status = TrainerStatus.BUSY
                      |
                      v
         Push StartTrainingCommand (gRPC)
                      |
             +--------+--------+
             |                 |
         [Success]          [Failure]
             |                 |
             v                 v
      Trainer receives    Rollback Assignment:
      and logs command    - task.TrainerNodeId = ""
                          - trainer.Status = UNCLEAR
                          - SaveChangesAsync()
```
