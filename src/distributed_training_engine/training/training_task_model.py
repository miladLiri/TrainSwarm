"""
Top-level training task model for the distributed training engine.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict
from .exceptions import InvalidTaskConfigurationError


@dataclass
class TrainingTask:
    """
    Serialized description of one training operation assigned to a trainer.
    """
    task_id: str
    session_id: str
    type: str
    checkpoint_version: str
    dataset_shard_id: str
    training: Dict[str, Any] = field(default_factory=dict)

    def validate_envelope(self) -> None:
        """
        Validate presence and non-emptiness of generic task envelope fields.
        """
        if not self.task_id or not isinstance(self.task_id, str) or not self.task_id.strip():
            raise InvalidTaskConfigurationError("task_id must be a non-empty string.")
        if not self.session_id or not isinstance(self.session_id, str) or not self.session_id.strip():
            raise InvalidTaskConfigurationError("session_id must be a non-empty string.")
        if not self.type or not isinstance(self.type, str) or not self.type.strip():
            raise InvalidTaskConfigurationError("type must be a non-empty string.")
        if not self.checkpoint_version or not isinstance(self.checkpoint_version, str) or not self.checkpoint_version.strip():
            raise InvalidTaskConfigurationError("checkpoint_version must be a non-empty string.")
        if not self.dataset_shard_id or not isinstance(self.dataset_shard_id, str) or not self.dataset_shard_id.strip():
            raise InvalidTaskConfigurationError("dataset_shard_id must be a non-empty string.")
        if not isinstance(self.training, dict):
            raise InvalidTaskConfigurationError("training section must be a dictionary.")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrainingTask:
        """Construct a TrainingTask from a dictionary and validate its envelope."""
        if not isinstance(data, dict):
            raise InvalidTaskConfigurationError("Task payload must be a JSON object / dictionary.")
        task = cls(
            task_id=str(data.get("task_id", "")),
            session_id=str(data.get("session_id", "")),
            type=str(data.get("type", "")),
            checkpoint_version=str(data.get("checkpoint_version", "")),
            dataset_shard_id=str(data.get("dataset_shard_id", "")),
            training=data.get("training", {})
        )
        task.validate_envelope()
        return task

    @classmethod
    def from_json(cls, json_str: str) -> TrainingTask:
        """Construct a TrainingTask from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise InvalidTaskConfigurationError(f"Invalid JSON task payload: {exc}") from exc
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TrainingTask to a plain dictionary."""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "type": self.type,
            "checkpoint_version": self.checkpoint_version,
            "dataset_shard_id": self.dataset_shard_id,
            "training": self.training,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the TrainingTask to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
