"""
Partitioning request DTO encapsulating parameters for dataset partitioning.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Union
from ..model_type import ModelType
from .exceptions import InvalidPartitioningConfigurationError


@dataclass
class PartitioningRequest:
    """
    Configuration payload for dataset sampling and partitioning operations.
    """
    model_type: ModelType
    datasetPath: Union[str, Path]
    shardsOutputDirectory: Union[str, Path]
    sampleOutputDirecotry: Union[str, Path]
    datasetId: str

    def __post_init__(self) -> None:
        self.validate()

    @property
    def dataset_path(self) -> Path:
        return Path(self.datasetPath).resolve()

    @property
    def shards_output_directory(self) -> Path:
        return Path(self.shardsOutputDirectory).resolve()

    @property
    def sample_output_directory(self) -> Path:
        return Path(self.sampleOutputDirecotry).resolve()

    @property
    def dataset_id(self) -> str:
        return self.datasetId

    def validate(self) -> None:
        """Validate request fields and paths."""
        if not self.datasetId or not str(self.datasetId).strip():
            raise InvalidPartitioningConfigurationError("datasetId must be a non-empty string.")

        if not self.datasetPath or not str(self.datasetPath).strip():
            raise InvalidPartitioningConfigurationError("datasetPath must be a non-empty path.", dataset_id=self.datasetId)

        if not self.shardsOutputDirectory or not str(self.shardsOutputDirectory).strip():
            raise InvalidPartitioningConfigurationError("shardsOutputDirectory must be a non-empty path.", dataset_id=self.datasetId)

        if not self.sampleOutputDirecotry or not str(self.sampleOutputDirecotry).strip():
            raise InvalidPartitioningConfigurationError("sampleOutputDirecotry must be a non-empty path.", dataset_id=self.datasetId)

        if isinstance(self.model_type, str):
            try:
                self.model_type = ModelType(self.model_type)
            except ValueError as exc:
                raise InvalidPartitioningConfigurationError(
                    f"Invalid model_type: '{self.model_type}'. Expected one of: {[e.value for e in ModelType]}",
                    dataset_id=self.datasetId
                ) from exc
        elif not isinstance(self.model_type, ModelType):
            raise InvalidPartitioningConfigurationError(
                f"model_type must be a ModelType instance or valid string, got: {type(self.model_type)}",
                dataset_id=self.datasetId
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PartitioningRequest:
        """Construct a PartitioningRequest from dictionary."""
        return cls(
            model_type=data.get("model_type") or data.get("modelType"),
            datasetPath=data.get("datasetPath") or data.get("dataset_path"),
            shardsOutputDirectory=data.get("shardsOutputDirectory") or data.get("shards_output_directory"),
            sampleOutputDirecotry=data.get("sampleOutputDirecotry") or data.get("sample_output_directory") or data.get("sampleOutputDirectory"),
            datasetId=data.get("datasetId") or data.get("dataset_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize PartitioningRequest to dictionary representation."""
        return {
            "model_type": str(self.model_type),
            "datasetPath": str(self.datasetPath),
            "shardsOutputDirectory": str(self.shardsOutputDirectory),
            "sampleOutputDirecotry": str(self.sampleOutputDirecotry),
            "datasetId": self.datasetId,
        }
