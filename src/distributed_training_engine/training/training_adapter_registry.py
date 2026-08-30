"""
Registry for mapping model/training types to their respective TrainingAdapter implementations.
"""

from typing import Dict, Type, Union
from .model_type import ModelType
from .training_adapter import TrainingAdapter
from .exceptions import UnsupportedTrainingTypeError


class TrainingAdapterRegistry:
    """
    Maintains mappings between ModelType and TrainingAdapter implementations.
    """

    def __init__(self, register_defaults: bool = True) -> None:
        self._adapters: Dict[str, Type[TrainingAdapter]] = {}
        if register_defaults:
            self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register default builtin adapters."""
        try:
            from .training_adapters.canonical_torch.canonical_torch_adapter import CanonicalTorchAdapter
            self.register(ModelType.CANONICAL_TORCH, CanonicalTorchAdapter)
        except ImportError:
            # Lazy import support if canonical adapter is being initialized
            pass

    def register(self, model_type: Union[ModelType, str], adapter_class: Type[TrainingAdapter]) -> None:
        """
        Register a new TrainingAdapter implementation for a given ModelType.
        """
        if not issubclass(adapter_class, TrainingAdapter):
            raise TypeError(f"Adapter class {adapter_class} must subclass TrainingAdapter.")
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        self._adapters[key] = adapter_class

    def get(self, model_type: Union[ModelType, str]) -> Type[TrainingAdapter]:
        """
        Retrieve the registered TrainingAdapter class for the given model_type.
        """
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        if key not in self._adapters:
            # Attempt lazy registration of canonical_torch if requested
            if key == ModelType.CANONICAL_TORCH.value:
                from .training_adapters.canonical_torch.canonical_torch_adapter import CanonicalTorchAdapter
                self.register(ModelType.CANONICAL_TORCH, CanonicalTorchAdapter)
                return self._adapters[key]
            raise UnsupportedTrainingTypeError(
                f"Unsupported training type '{model_type}'. Registered types: {list(self._adapters.keys())}"
            )
        return self._adapters[key]
