"""
Aggregator adapter registry mapping ModelType to AggregatorAdapter implementations.
"""

from __future__ import annotations
from typing import Dict, Type, Union
from ..model_type import ModelType
from .exceptions import AggregatorAdapterNotFoundError, UnsupportedModelTypeError
from .aggregator_adapter import AggregatorAdapter


class AggregatorAdapterRegistery:
    """
    Registry maintaining mappings between ModelType and AggregatorAdapter classes.
    """

    _registry: Dict[str, Type[AggregatorAdapter]] = {}

    @classmethod
    def Register(cls, model_type: Union[ModelType, str], aggregator_class: Type[AggregatorAdapter]) -> None:
        """
        Register a concrete AggregatorAdapter subclass for a ModelType.

        Args:
            model_type: The ModelType enum or string key.
            aggregator_class: Subclass of AggregatorAdapter.
        """
        if not issubclass(aggregator_class, AggregatorAdapter):
            raise TypeError(f"aggregator_class '{aggregator_class}' must subclass AggregatorAdapter.")
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        cls._registry[key] = aggregator_class

    # Lowercase alias
    register = Register

    @classmethod
    def Get(cls, model_type: Union[ModelType, str]) -> Type[AggregatorAdapter]:
        """
        Retrieve the registered AggregatorAdapter class for a given ModelType.

        Args:
            model_type: The ModelType key.

        Returns:
            The registered AggregatorAdapter subclass.

        Raises:
            AggregatorAdapterNotFoundError: If no adapter is registered for model_type.
        """
        if model_type is None:
            raise UnsupportedModelTypeError("model_type cannot be None.")

        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        if key not in cls._registry:
            # Lazy import for canonical_torch if available
            if key == ModelType.CANONICAL_TORCH.value:
                try:
                    from ..adapters.canonical_torch.aggragation.canonical_torch_aggregator import (
                        CanonicalTorchAggregator,
                    )
                    cls.Register(ModelType.CANONICAL_TORCH, CanonicalTorchAggregator)
                    return cls._registry[key]
                except ImportError:
                    pass

            raise AggregatorAdapterNotFoundError(
                f"No aggregator adapter registered for ModelType: '{model_type}'"
            )
        return cls._registry[key]

    # Lowercase alias
    get = Get

    @classmethod
    def clear(cls) -> None:
        """Clear registry entries (for reset or isolation)."""
        cls._registry.clear()


# Aliases for naming conventions and compatibility
AggregatorAdapterRegistry = AggregatorAdapterRegistery
