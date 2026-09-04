"""Command DTO for the Smoke Test application use case."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Union
from distributed_training_engine.training import TrainingTask
from .exceptions import SmokeTestValidationError


@dataclass
class SmokeTestCommand:
    """Request payload to execute a training smoke test for shard sizing and validation."""

    training_task_model: TrainingTask
    sample_count: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate command parameters."""
        if not isinstance(self.sample_count, int) or self.sample_count <= 0:
            raise SmokeTestValidationError(
                field="sample_count",
                value=self.sample_count,
                reason="sample_count must be an integer strictly greater than zero.",
            )

        if self.training_task_model is None:
            raise SmokeTestValidationError(
                field="training_task_model",
                value=None,
                reason="training_task_model cannot be None.",
            )

        if not isinstance(self.training_task_model, TrainingTask):
            raise SmokeTestValidationError(
                field="training_task_model",
                value=type(self.training_task_model),
                reason="training_task_model must be an instance of TrainingTask.",
            )

        # Validate task envelope
        try:
            self.training_task_model.validate_envelope()
        except Exception as e:
            raise SmokeTestValidationError(
                field="training_task_model",
                value=self.training_task_model,
                reason=f"Task envelope validation failed: {e}",
            ) from e
