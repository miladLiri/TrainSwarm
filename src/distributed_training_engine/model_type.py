"""
Model type enumeration for the distributed training engine.
"""

from enum import Enum


class ModelType(str, Enum):
    """Supported training and model types."""
    CANONICAL_TORCH = "canonical_torch"

    def __str__(self) -> str:
        return self.value
