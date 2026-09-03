"""
Aggregation request and model update DTOs.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union
from .exceptions import InvalidAggregationRequestError, InvalidUpdateError


@dataclass(frozen=True)
class ModelUpdate:
    """
    Metadata for an individual trainer update included in an aggregation round.
    """
    samplesTrained: int
    deltaPath: Union[str, Path]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def samples_trained(self) -> int:
        return self.samplesTrained

    @property
    def delta_path(self) -> Path:
        return Path(self.deltaPath).resolve()

    def validate(self) -> None:
        if not isinstance(self.samplesTrained, int) or self.samplesTrained <= 0:
            raise InvalidUpdateError(
                f"samplesTrained must be an integer > 0, got: {self.samplesTrained}",
                artifact_path=str(self.deltaPath) if self.deltaPath else None,
                operation="validate_update",
            )
        if not self.deltaPath or not str(self.deltaPath).strip():
            raise InvalidUpdateError(
                "deltaPath must be a non-empty file path.",
                operation="validate_update",
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelUpdate:
        return cls(
            samplesTrained=int(data.get("samplesTrained") if "samplesTrained" in data else data.get("samples_trained", 0)),
            deltaPath=data.get("deltaPath") or data.get("delta_path", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "samplesTrained": self.samplesTrained,
            "deltaPath": str(self.deltaPath),
        }


@dataclass(frozen=True)
class AggregationRequest:
    """
    Immutable request payload for initializing and executing a model aggregation round.
    """
    modelId: str
    baseModelVersion: int
    baseModelPath: Union[str, Path]
    newVersion: int
    newVersionOutputDirectory: Union[str, Path]
    updates: List[ModelUpdate]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def model_id(self) -> str:
        return self.modelId

    @property
    def base_model_version(self) -> int:
        return self.baseModelVersion

    @property
    def base_model_path(self) -> Path:
        return Path(self.baseModelPath).resolve()

    @property
    def new_version(self) -> int:
        return self.newVersion

    @property
    def new_version_output_directory(self) -> Path:
        return Path(self.newVersionOutputDirectory).resolve()

    def validate(self) -> None:
        if not self.modelId or not str(self.modelId).strip():
            raise InvalidAggregationRequestError(
                "modelId must be a non-empty string.",
                operation="validate_request",
            )

        if not isinstance(self.baseModelVersion, int) or self.baseModelVersion < 0:
            raise InvalidAggregationRequestError(
                f"baseModelVersion must be an integer >= 0, got: {self.baseModelVersion}",
                model_id=self.modelId,
                operation="validate_request",
            )

        if not self.baseModelPath or not str(self.baseModelPath).strip():
            raise InvalidAggregationRequestError(
                "baseModelPath must be a non-empty file path.",
                model_id=self.modelId,
                base_version=self.baseModelVersion,
                operation="validate_request",
            )

        if not isinstance(self.newVersion, int) or self.newVersion <= self.baseModelVersion:
            raise InvalidAggregationRequestError(
                f"newVersion ({self.newVersion}) must be an integer strictly greater than baseModelVersion ({self.baseModelVersion}).",
                model_id=self.modelId,
                base_version=self.baseModelVersion,
                new_version=self.newVersion,
                operation="validate_request",
            )

        if not self.newVersionOutputDirectory or not str(self.newVersionOutputDirectory).strip():
            raise InvalidAggregationRequestError(
                "newVersionOutputDirectory must be a non-empty directory path.",
                model_id=self.modelId,
                new_version=self.newVersion,
                operation="validate_request",
            )

        if not self.updates or not isinstance(self.updates, (list, tuple)) or len(self.updates) == 0:
            raise InvalidAggregationRequestError(
                "updates must be a non-empty list of ModelUpdate records.",
                model_id=self.modelId,
                base_version=self.baseModelVersion,
                new_version=self.newVersion,
                operation="validate_request",
            )

        for idx, u in enumerate(self.updates):
            if not isinstance(u, ModelUpdate):
                raise InvalidAggregationRequestError(
                    f"Item at updates[{idx}] is not a ModelUpdate instance (got {type(u)}).",
                    model_id=self.modelId,
                    base_version=self.baseModelVersion,
                    operation="validate_request",
                )
            u.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AggregationRequest:
        raw_updates = data.get("updates", [])
        updates = [
            u if isinstance(u, ModelUpdate) else ModelUpdate.from_dict(u)
            for u in raw_updates
        ]
        return cls(
            modelId=data.get("modelId") or data.get("model_id", ""),
            baseModelVersion=int(data.get("baseModelVersion") if "baseModelVersion" in data else data.get("base_model_version", 0)),
            baseModelPath=data.get("baseModelPath") or data.get("base_model_path", ""),
            newVersion=int(data.get("newVersion") if "newVersion" in data else data.get("new_version", 0)),
            newVersionOutputDirectory=data.get("newVersionOutputDirectory") or data.get("new_version_output_directory", ""),
            updates=updates,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modelId": self.modelId,
            "baseModelVersion": self.baseModelVersion,
            "baseModelPath": str(self.baseModelPath),
            "newVersion": self.newVersion,
            "newVersionOutputDirectory": str(self.newVersionOutputDirectory),
            "updates": [u.to_dict() for u in self.updates],
        }
