"""Exceptions for the Smoke Test application use case."""

from typing import Any, Optional


class SmokeTestError(Exception):
    """Base exception for smoke test operations."""
    pass


class SmokeTestValidationError(SmokeTestError):
    """Raised when a smoke test command or input validation fails."""

    def __init__(self, field: str, value: Any, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid smoke test command parameter '{field}' ({value}): {reason}")


class SmokeTestExecutionError(SmokeTestError):
    """Raised when a smoke test training execution fails."""

    def __init__(self, task_id: str, message: str, cause: Optional[Exception] = None) -> None:
        self.task_id = task_id
        self.cause = cause
        super().__init__(f"Smoke test execution failed for task '{task_id}': {message}")
