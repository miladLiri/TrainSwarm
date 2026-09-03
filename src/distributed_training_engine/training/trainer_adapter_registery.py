"""
Registry for mapping model/training types to their respective TrainerAdapter implementations.
"""

from typing import Dict, Type, Union
from ..model_type import ModelType
from .trainer_adapter import TrainerAdapter, TrainingAdapter
from .exceptions import UnsupportedTrainingTypeError


class TrainerAdapterRegistery:
    """
    Maintains mappings between ModelType and TrainerAdapter implementations.
    """

    def __init__(self, register_defaults: bool = True) -> None:
        self._adapters: Dict[str, Type[TrainerAdapter]] = {}
        if register_defaults:
            self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register default builtin adapters."""
        try:
            from ..adapters.canonical_torch.training.canonical_torch_trainer import CanonicalTorchTrainer
            self.register(ModelType.CANONICAL_TORCH, CanonicalTorchTrainer)
        except ImportError:
            pass

    def register(self, model_type: Union[ModelType, str], adapter_class: Type[TrainerAdapter]) -> None:
        """
        Register a new TrainerAdapter implementation for a given ModelType.
        """
        if not issubclass(adapter_class, TrainerAdapter):
            raise TypeError(f"Adapter class {adapter_class} must subclass TrainerAdapter.")
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        self._adapters[key] = adapter_class

    def get(self, model_type: Union[ModelType, str]) -> Type[TrainerAdapter]:
        """
        Retrieve the registered TrainerAdapter class for the given model_type.
        """
        key = str(model_type.value if isinstance(model_type, ModelType) else model_type).strip().lower()
        if key not in self._adapters:
            # Attempt lazy registration of canonical_torch if requested
            if key == ModelType.CANONICAL_TORCH.value:
                try:
                    from ..adapters.canonical_torch.training.canonical_torch_trainer import CanonicalTorchTrainer
                    self.register(ModelType.CANONICAL_TORCH, CanonicalTorchTrainer)
                    return self._adapters[key]
                except ImportError:
                    pass
            raise UnsupportedTrainingTypeError(
                f"Unsupported training type '{model_type}'. Registered types: {list(self._adapters.keys())}"
            )
        return self._adapters[key]


# Aliases for naming conventions and backward compatibility
TrainerAdapterRegistry = TrainerAdapterRegistery
TrainingAdapterRegistry = TrainerAdapterRegistery
