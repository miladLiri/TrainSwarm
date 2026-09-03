"""Domain models for local training shard state and lifecycle.

This module is strictly isolated from persistence frameworks and SQLite.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class TrainingShardStatus(str, Enum):
    """Lifecycle status of a local dataset shard."""
    READY = "ready"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingShard:
    """Represents the local persistent training state of one dataset shard for one model version."""

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
        """Validate domain invariants for the TrainingShard.

        Raises:
            ValueError: If any attribute fails validation rules.
        """
        if not self.id or not isinstance(self.id, str):
            raise ValueError("TrainingShard.id must be a non-empty string UUID")
        try:
            uuid.UUID(self.id)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"TrainingShard.id must be a valid UUID string: {self.id}") from e

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

        if not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool) or self.sample_count <= 0:
            raise ValueError(
                f"TrainingShard.sample_count must be an integer strictly greater than 0, got {self.sample_count}"
            )

        if not isinstance(self.status, TrainingShardStatus):
            if isinstance(self.status, str):
                try:
                    self.status = TrainingShardStatus(self.status.lower())
                except ValueError as e:
                    raise ValueError(f"Invalid TrainingShardStatus: {self.status}") from e
            else:
                raise ValueError(
                    f"TrainingShard.status must be a TrainingShardStatus instance, got {type(self.status)}"
                )

        if self.metrics is not None and not isinstance(self.metrics, dict):
            raise ValueError("TrainingShard.metrics must be a dictionary or None")

        if self.training_metadata is not None and not isinstance(self.training_metadata, dict):
            raise ValueError("TrainingShard.training_metadata must be a dictionary or None")

        if self.update_artifact_path is not None and not isinstance(self.update_artifact_path, str):
            raise ValueError("TrainingShard.update_artifact_path must be a string or None")

        if self.training_task_id is not None and not isinstance(self.training_task_id, str):
            raise ValueError("TrainingShard.training_task_id must be a string or None")
