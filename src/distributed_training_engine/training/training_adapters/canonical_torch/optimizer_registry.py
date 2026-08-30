"""
Optimizer registry mapping optimizer types to parameter models and PyTorch optimizers.
"""

from __future__ import annotations
from typing import Any, Dict, Type
import torch
from .optimizers import AdamWParameters, SGDParameters
from ...exceptions import UnsupportedOptimizerError, InvalidOptimizerParametersError


class OptimizerRegistry:
    """Registry managing optimizer deserialization, validation, and instantiation."""

    _REGISTRY: Dict[str, tuple[Type[Any], Type[torch.optim.Optimizer]]] = {
        "adamw": (AdamWParameters, torch.optim.AdamW),
        "sgd": (SGDParameters, torch.optim.SGD),
    }

    @classmethod
    def register(
        cls,
        name: str,
        param_cls: Type[Any],
        optim_cls: Type[torch.optim.Optimizer]
    ) -> None:
        """Register a new optimizer type."""
        cls._REGISTRY[name.strip().lower()] = (param_cls, optim_cls)

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> None:
        """
        Validate optimizer configuration block without creating an optimizer.
        """
        if not isinstance(config, dict):
            raise InvalidOptimizerParametersError("Optimizer configuration must be a dictionary.")
        optim_type = config.get("type")
        if not optim_type or not isinstance(optim_type, str):
            raise InvalidOptimizerParametersError("Optimizer configuration missing 'type' field.")
        key = optim_type.strip().lower()
        if key not in cls._REGISTRY:
            raise UnsupportedOptimizerError(
                f"Unsupported optimizer type '{optim_type}'. Supported: {list(cls._REGISTRY.keys())}"
            )
        params_dict = config.get("parameters", {})
        if not isinstance(params_dict, dict):
            raise InvalidOptimizerParametersError("Optimizer 'parameters' must be a dictionary.")
        param_cls, _ = cls._REGISTRY[key]
        param_cls.from_dict(params_dict)

    @classmethod
    def create(cls, config: Dict[str, Any], model_parameters: Any) -> torch.optim.Optimizer:
        """
        Instantiate PyTorch optimizer bound to the supplied model parameters.
        """
        cls.validate(config)
        key = config["type"].strip().lower()
        param_cls, optim_cls = cls._REGISTRY[key]
        dto = param_cls.from_dict(config.get("parameters", {}))
        kwargs = dto.to_torch_kwargs()
        return optim_cls(model_parameters, **kwargs)
