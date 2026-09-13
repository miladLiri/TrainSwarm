"""Query and DTO models for retrieving training shards."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GetTrainingShardsQuery:
    """Request query to retrieve active and completed training shards."""
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    dataset_id: Optional[str] = None


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
