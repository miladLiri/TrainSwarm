"""
Partitioner adapter registry mapping ModelType to PartitionerAdapter implementations.
"""

from __future__ import annotations
from typing import Dict, Type, Union
from ..model_type import ModelType
from .exceptions import PartitionerAdapterNotFoundError, UnsupportedModelTypeError
from .partitioner_adapter import PartitionerAdapter


class PartitionerAdapterRegistery:
    """
    Registry maintaining mappings between ModelType and PartitionerAdapter classes.
    """

    _registry: Dict[str, Type[PartitionerAdapter]] = {}

    @classmethod
    def Register(cls, model_type: Union[ModelType, str], partitioner_class: Type[PartitionerAdapter]) -> None:
        """
        Register a concrete PartitionerAdapter subclass for a ModelType.

        Args:
            model_type: The ModelType enum or string key.
            partitioner_class: Subclass of PartitionerAdapter.
        """
        if not issubclass(partitioner_class, PartitionerAdapter):
            raise TypeError(f"partitioner_class '{partitioner_class}' must subclass PartitionerAdapter.")
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        cls._registry[key] = partitioner_class

    # Lowercase alias
    register = Register

    @classmethod
    def Get(cls, model_type: Union[ModelType, str]) -> Type[PartitionerAdapter]:
        """
        Retrieve the registered PartitionerAdapter class for a given ModelType.

        Args:
            model_type: The ModelType key.

        Returns:
            The registered PartitionerAdapter subclass.

        Raises:
            PartitionerAdapterNotFoundError: If no adapter is registered for model_type.
        """
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        if key not in cls._registry:
            # Check if canonical_torch can be registered lazily
            if key == ModelType.CANONICAL_TORCH.value:
                try:
                    from ..adapters.canonical_torch.partitioning.canonical_torch_partitioner import (
                        CanonicalTorchPartitioner,
                    )
                    cls.Register(ModelType.CANONICAL_TORCH, CanonicalTorchPartitioner)
                    return cls._registry[key]
                except ImportError:
                    pass

            raise PartitionerAdapterNotFoundError(
                f"No partitioner adapter registered for ModelType: '{model_type}'"
            )
        return cls._registry[key]

    # Lowercase alias
    get = Get

    @classmethod
    def clear(cls) -> None:
        """Clear registry entries (for testing/reset)."""
        cls._registry.clear()


# Aliases for naming conventions and compatibility
PartitionerAdapterRegistry = PartitionerAdapterRegistery
