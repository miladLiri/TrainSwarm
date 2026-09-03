# Data Model: Training Client — Local Training Shard Persistence Infrastructure

**Feature Branch**: `011-training-shard-persistence`  
**Date**: 2026-09-03  
**Status**: Complete  

## Overview

This document specifies the domain entity model, enumeration types, validation rules, relational SQLite schema, and index design for local training shard persistence in the TrainSwarm Client.

---

## 1. Domain Entities

### 1.1 `TrainingShardStatus` (Enum)

Represents the lifecycle state of a dataset shard in the local training pipeline.

- **Storage Type**: Stable lowercase string (`TEXT`)
- **Values**:
  - `READY`: `"ready"` — Shard is prepared locally and available for training.
  - `TRAINING`: `"training"` — Shard is actively assigned to and being trained by an engine adapter.
  - `COMPLETED`: `"completed"` — Local training completed successfully; update delta artifact generated.
  - `FAILED`: `"failed"` — Training execution failed.

```python
from enum import Enum

class TrainingShardStatus(str, Enum):
    READY = "ready"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

### 1.2 `TrainingShard` (Entity Model)

Represents the local persistent training state of a single dataset shard partition for a specific global model checkpoint version.

| Field Name | Domain Type | SQLite Type | Nullable | Description | Validation Rule |
|---|---|---|---|---|---|
| `id` | `str` | `TEXT` | No | Unique local identifier (UUID4) | Primary key; must be valid UUID string |
| `model_id` | `str` | `TEXT` | No | Identifier of the model being trained | Required, non-empty string |
| `model_type` | `str` | `TEXT` | No | Architecture / distributed engine type | Required, non-empty opaque string |
| `model_version` | `str` | `TEXT` | No | Global model/checkpoint version | Required, non-empty string |
| `dataset_id` | `str` | `TEXT` | No | Identifier of the source dataset | Required, non-empty string |
| `shard_id` | `str` | `TEXT` | No | Identifier of the dataset shard | Required, non-empty string |
| `artifact_path` | `str` | `TEXT` | No | Full filesystem path to the shard artifact | Required, non-empty absolute or normalized path |
| `sample_count` | `int` | `INTEGER` | No | Number of training samples in the shard | Required integer strictly greater than 0 (`> 0`) |
| `status` | `TrainingShardStatus` | `TEXT` | No | Current training lifecycle status | Must be valid `TrainingShardStatus` member |
| `metrics` | `Optional[Dict[str, Any]]` | `TEXT` | Yes | Training execution metrics (loss, accuracy, etc.) | JSON-serializable dictionary or `None` |
| `training_metadata` | `Optional[Dict[str, Any]]` | `TEXT` | Yes | Arbitrary execution metadata (duration, device, etc.) | JSON-serializable dictionary or `None` |
| `update_artifact_path`| `Optional[str]` | `TEXT` | Yes | Full filesystem path to generated delta artifact | Non-empty string or `None`; populated post-training |
| `training_task_id` | `Optional[str]` | `TEXT` | Yes | Identifier of assigned training task | Non-empty string or `None`; populated on assignment |

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class TrainingShard:
    id: str
    model_id: str
    model_type: str
    model_version: str
    dataset_id: str
    shard_id: str
    artifact_path: str
    sample_count: int
    status: TrainingShardStatus = TrainingShardStatus.READY
    metrics: Optional[Dict[str, Any]] = None
    training_metadata: Optional[Dict[str, Any]] = None
    update_artifact_path: Optional[str] = None
    training_task_id: Optional[str] = None

    def validate(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise ValueError("TrainingShard.id must be a non-empty string UUID")
        if not self.model_id or not isinstance(self.model_id, str):
            raise ValueError("TrainingShard.model_id must be a non-empty string")
        if not self.model_type or not isinstance(self.model_type, str):
            raise ValueError("TrainingShard.model_type must be a non-empty string")
        if not self.model_version or not isinstance(self.model_version, str):
            raise ValueError("TrainingShard.model_version must be a non-empty string")
        if not self.dataset_id or not isinstance(self.dataset_id, str):
            raise ValueError("TrainingShard.dataset_id must be a non-empty string")
        if not self.shard_id or not isinstance(self.shard_id, str):
            raise ValueError("TrainingShard.shard_id must be a non-empty string")
        if not self.artifact_path or not isinstance(self.artifact_path, str):
            raise ValueError("TrainingShard.artifact_path must be a non-empty string")
        if not isinstance(self.sample_count, int) or self.sample_count <= 0:
            raise ValueError("TrainingShard.sample_count must be an integer strictly greater than 0")
        if not isinstance(self.status, TrainingShardStatus):
            raise ValueError(f"TrainingShard.status must be a TrainingShardStatus instance, got {type(self.status)}")
```

---

## 2. Relational Schema Design (SQLite)

### 2.1 Table Definition: `training_shards`

```sql
CREATE TABLE IF NOT EXISTS training_shards (
    id TEXT PRIMARY KEY NOT NULL,
    model_id TEXT NOT NULL,
    model_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    shard_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count > 0),
    status TEXT NOT NULL,
    metrics TEXT NULL,
    training_metadata TEXT NULL,
    update_artifact_path TEXT NULL,
    training_task_id TEXT NULL
);
```

### 2.2 Composite Unique Index

To enforce business rule FR-006 / User Story 3, the combination of `(model_id, model_version, dataset_id, shard_id)` must be globally unique across all records in the table:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_training_shards_logical_shard 
ON training_shards (model_id, model_version, dataset_id, shard_id);
```

---

## 3. Lifecycle State Machine

```text
       ┌──────────────┐
       │    READY     │ (Shard registered locally, sample_count > 0)
       └──────┬───────┘
              │
              │ Task Assigned / Training Started
              ▼
       ┌──────────────┐
       │   TRAINING   │ (Engine adapter executing local training)
       └──────┬───────┘
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
┌───────────┐    ┌───────────┐
│ COMPLETED │    │  FAILED   │
└───────────┘    └───────────┘
(Update delta    (Execution
 saved, metrics   error, metrics
 populated)       optional)
```

*Note*: In the current initial slice (Feature 011), `TrainingShardRepository` supports insert-only persistence (`save` / `bulk_save`) and point queries (`get_by_id` / `get_by_shard_key`). Shard lifecycle updates will be utilized in subsequent training task orchestration features.

---

## 4. Mapping & Serialization Rules

1. **`status`**:
   - Python: `TrainingShardStatus.READY`
   - SQLite: `'ready'` (value extracted via `.value`)
   - Reconstructed via `TrainingShardStatus(row['status'])`
2. **`metrics`**:
   - Python: `{"loss": 0.342, "accuracy": 0.87, "epochs": 3}` (or `None`)
   - SQLite: `'{"loss": 0.342, "accuracy": 0.87, "epochs": 3}'` (or `NULL`)
   - Serialized via `json.dumps(obj)` if not None else `None`
   - Deserialized via `json.loads(text)` if text is not None else `None`
3. **`training_metadata`**:
   - Python: `{"duration": 1000}` (or `None`)
   - SQLite: `'{"duration": 1000}'` (or `NULL`)
   - Serialized via `json.dumps(obj)` if not None else `None`
   - Deserialized via `json.loads(text)` if text is not None else `None`
4. **`update_artifact_path` & `training_task_id`**:
   - Direct string mapping (`None` <-> `NULL`)
