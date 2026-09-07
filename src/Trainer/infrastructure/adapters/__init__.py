"""Trainer infrastructure adapters."""

from .coordinator_adapter import (
    CoordinatorAdapter,
    CoordinatorAdapterError,
    CoordinatorAdapterResult,
    CoordinatorConfigurationError,
)

__all__ = [
    "CoordinatorAdapter",
    "CoordinatorAdapterError",
    "CoordinatorAdapterResult",
    "CoordinatorConfigurationError",
]
