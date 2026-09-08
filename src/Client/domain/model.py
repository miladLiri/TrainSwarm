"""Domain entity for Model metadata in TrainSwarm Client."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import uuid


@dataclass
class Model:
    """Represents top-level model metadata for a submitted training job."""

    model_id: str
    model_type: str
    model_version: str
    dataset_id: str
    model_artifact_path: str
    training_config_path: str

    def validate(self) -> None:
        """Validate domain invariants for Model entity.

        Raises:
            ValueError: If any attribute fails validation rules.
        """
        if not self.model_id or not isinstance(self.model_id, str):
            raise ValueError("Model.model_id must be a non-empty string UUID")
        try:
            uuid.UUID(self.model_id)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Model.model_id must be a valid UUID string: {self.model_id}") from e

        if not self.model_type or not isinstance(self.model_type, str):
            raise ValueError("Model.model_type must be a non-empty string")

        if not self.model_version or not isinstance(self.model_version, str):
            raise ValueError("Model.model_version must be a non-empty string")

        if not self.dataset_id or not isinstance(self.dataset_id, str):
            raise ValueError("Model.dataset_id must be a non-empty string UUID")
        try:
            uuid.UUID(self.dataset_id)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Model.dataset_id must be a valid UUID string: {self.dataset_id}") from e

        if not self.model_artifact_path or not isinstance(self.model_artifact_path, str):
            raise ValueError("Model.model_artifact_path must be a non-empty string")

        if not self.training_config_path or not isinstance(self.training_config_path, str):
            raise ValueError("Model.training_config_path must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        """Convert Model entity to dictionary representation."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "model_version": self.model_version,
            "dataset_id": self.dataset_id,
            "model_artifact_path": self.model_artifact_path,
            "training_config_path": self.training_config_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Model:
        """Create Model entity from dictionary."""
        return cls(
            model_id=str(data["model_id"]),
            model_type=str(data["model_type"]),
            model_version=str(data["model_version"]),
            dataset_id=str(data["dataset_id"]),
            model_artifact_path=str(data["model_artifact_path"]),
            training_config_path=str(data["training_config_path"]),
        )
