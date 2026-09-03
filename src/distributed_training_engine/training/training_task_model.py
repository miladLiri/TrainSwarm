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
    training_task_id: str
    baseline_model_id: str
    baseline_model_version: str
    data_set_id: str
    data_set_shard_id: str
    type: str
    training: Dict[str, Any] = field(default_factory=dict)

    def validate_envelope(self) -> None:
        """
        Validate presence and non-emptiness of generic task envelope fields.
        """
        if not self.training_task_id or not isinstance(self.training_task_id, str) or not self.training_task_id.strip():
            raise InvalidTaskConfigurationError("training_task_id must be a non-empty string.")
        if not self.baseline_model_id or not isinstance(self.baseline_model_id, str) or not self.baseline_model_id.strip():
            raise InvalidTaskConfigurationError("baseline_model_id must be a non-empty string.")
        if not self.baseline_model_version or not isinstance(self.baseline_model_version, str) or not self.baseline_model_version.strip():
            raise InvalidTaskConfigurationError("baseline_model_version must be a non-empty string.")
        if not self.data_set_id or not isinstance(self.data_set_id, str) or not self.data_set_id.strip():
            raise InvalidTaskConfigurationError("data_set_id must be a non-empty string.")
        if not self.data_set_shard_id or not isinstance(self.data_set_shard_id, str) or not self.data_set_shard_id.strip():
            raise InvalidTaskConfigurationError("data_set_shard_id must be a non-empty string.")
        if not self.type or not isinstance(self.type, str) or not self.type.strip():
            raise InvalidTaskConfigurationError("type must be a non-empty string.")
        if not isinstance(self.training, dict):
            raise InvalidTaskConfigurationError("training section must be a dictionary.")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrainingTask:
        """Construct a TrainingTask from a dictionary and validate its envelope."""
        if not isinstance(data, dict):
            raise InvalidTaskConfigurationError("Task payload must be a JSON object / dictionary.")
        task = cls(
            training_task_id=str(data.get("training_task_id", "")),
            baseline_model_id=str(data.get("baseline_model_id", "")),
            baseline_model_version=str(data.get("baseline_model_version", "")),
            data_set_id=str(data.get("data_set_id", "")),
            data_set_shard_id=str(data.get("data_set_shard_id", "")),
            type=str(data.get("type", "")),
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
            "training_task_id": self.training_task_id,
            "baseline_model_id": self.baseline_model_id,
            "baseline_model_version": self.baseline_model_version,
            "data_set_id": self.data_set_id,
            "data_set_shard_id": self.data_set_shard_id,
            "type": self.type,
            "training": self.training,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the TrainingTask to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

