# Application Query Contracts: Client Queries

**Feature**: `020-update-model-followup`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. `GetTrainingShardsQuery`

### Namespace / Location
`Client.application.queries.get_training_shards`

### Query Model
```python
@dataclass(frozen=True)
class GetTrainingShardsQuery:
    """Request query to retrieve active and completed training shards."""
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    dataset_id: Optional[str] = None
```

### Result DTO
```python
@dataclass(frozen=True)
class TrainingShardViewDto:
    """Read-only view model representing a training shard's state."""
    model_id: str
    model_version: str
    dataset_id: str
    shard_id: str
    status: str
    sample_count: int
    trainer_node_id: Optional[str] = None
    update_artifact_path: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
```

### Query Handler
```python
class GetTrainingShardsQueryHandler:
    def __init__(self, shard_repository: ITrainingShardRepository) -> None:
        self.shard_repository = shard_repository

    def handle(self, query: Optional[GetTrainingShardsQuery] = None) -> List[TrainingShardViewDto]:
        """Execute query returning a list of TrainingShardViewDto objects."""
        ...
```

---

## 2. `GetTrainedModelsQuery`

### Namespace / Location
`Client.application.queries.get_trained_models`

### Query Model
```python
@dataclass(frozen=True)
class GetTrainedModelsQuery:
    """Request query to retrieve all persisted trained model versions."""
    model_id: Optional[str] = None
```

### Result DTO
```python
@dataclass(frozen=True)
class TrainedModelViewDto:
    """Read-only view model representing a trained model checkpoint."""
    model_id: str
    model_version: str
    model_type: str
    dataset_id: str
    model_artifact_path: str
    training_config_path: str
```

### Query Handler
```python
class GetTrainedModelsQueryHandler:
    def __init__(self, model_repository: IModelRepository) -> None:
        self.model_repository = model_repository

    def handle(self, query: Optional[GetTrainedModelsQuery] = None) -> List[TrainedModelViewDto]:
        """Execute query returning all model versions recorded in persistence."""
        ...
```
