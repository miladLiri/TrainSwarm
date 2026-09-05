"""Command DTO for the Submit Training application use case."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Union

from distributed_training_engine.model_type import ModelType
from .exceptions import SubmitTrainingValidationError


@dataclass
class SubmitTrainingCommand:
    """Input parameters for submitting a new model training task."""

    model_path: Union[str, Path]
    dataset_path: Union[str, Path]
    model_version: str
    model_type: Union[str, ModelType]
    training_config: Dict[str, Any]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate all command fields and input files."""
        # 1. Validate model_path
        if not self.model_path:
            raise SubmitTrainingValidationError(
                field="model_path",
                value=self.model_path,
                reason="model_path cannot be empty.",
            )
        p_model = Path(self.model_path).resolve()
        if not p_model.is_file():
            raise SubmitTrainingValidationError(
                field="model_path",
                value=str(self.model_path),
                reason=f"Model checkpoint file not found at '{p_model}'.",
            )

        # 2. Validate dataset_path
        if not self.dataset_path:
            raise SubmitTrainingValidationError(
                field="dataset_path",
                value=self.dataset_path,
                reason="dataset_path cannot be empty.",
            )
        p_dataset = Path(self.dataset_path).resolve()
        if not p_dataset.is_file():
            raise SubmitTrainingValidationError(
                field="dataset_path",
                value=str(self.dataset_path),
                reason=f"Dataset file not found at '{p_dataset}'.",
            )

        # 3. Validate model_version
        if not self.model_version or not str(self.model_version).strip():
            raise SubmitTrainingValidationError(
                field="model_version",
                value=self.model_version,
                reason="model_version must be a non-empty string.",
            )

        # 4. Validate model_type
        if isinstance(self.model_type, str):
            try:
                self.model_type = ModelType(self.model_type.strip().lower())
            except ValueError as e:
                valid_types = [e.value for e in ModelType]
                raise SubmitTrainingValidationError(
                    field="model_type",
                    value=self.model_type,
                    reason=f"Unsupported model_type '{self.model_type}'. Expected one of: {valid_types}",
                ) from e
        elif not isinstance(self.model_type, ModelType):
            raise SubmitTrainingValidationError(
                field="model_type",
                value=type(self.model_type),
                reason="model_type must be a ModelType enum or valid string.",
            )

        # 5. Validate training_config
        if not isinstance(self.training_config, dict):
            raise SubmitTrainingValidationError(
                field="training_config",
                value=type(self.training_config),
                reason="training_config must be a dictionary.",
            )

        required_keys = ("batch_size", "shuffle", "epochs", "gradient_accumulation_steps", "optimizer", "loss")
        for key in required_keys:
            if key not in self.training_config:
                raise SubmitTrainingValidationError(
                    field="training_config",
                    value=list(self.training_config.keys()),
                    reason=f"Missing required training config field '{key}'.",
                )
