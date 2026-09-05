"""Exceptions for the Submit Training application use case."""

from typing import Any, Optional


class SubmitTrainingError(Exception):
    """Base exception for all Submit Training use case failures."""
    pass


class SubmitTrainingValidationError(SubmitTrainingError):
    """Raised when command inputs, file paths, or parameters fail validation."""

    def __init__(self, field: str, value: Any, reason: str) -> None:
        super().__init__(f"Validation failed for field '{field}' (value: {value!r}): {reason}")
        self.field = field
        self.value = value
        self.reason = reason


class SubmitTrainingExecutionError(SubmitTrainingError):
    """Raised when an operation during the submit training workflow fails."""

    def __init__(self, phase: str, reason: str, cause: Optional[Exception] = None) -> None:
        super().__init__(f"Execution failed during phase '{phase}': {reason}")
        self.phase = phase
        self.reason = reason
        self.cause = cause
