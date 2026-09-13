"""Query and DTO models for retrieving trained models."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GetTrainedModelsQuery:
    """Request query to retrieve all persisted trained model versions."""
    model_id: Optional[str] = None


@dataclass(frozen=True)
class TrainedModelViewDto:
    """Read-only view model representing a trained model checkpoint."""
    model_id: str
    model_version: str
    model_type: str
    dataset_id: str
    model_artifact_path: str
    training_config_path: str
