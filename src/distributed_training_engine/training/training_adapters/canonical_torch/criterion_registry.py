"""
Criterion registry mapping loss types to parameter models and PyTorch loss modules.
"""

from __future__ import annotations
from typing import Any, Dict, Type
import torch.nn as nn
from .criteria import (
    MSELossParameters,
    L1LossParameters,
    SmoothL1LossParameters,
    CrossEntropyLossParameters,
    BCEWithLogitsLossParameters,
)
from ...exceptions import UnsupportedCriterionError, InvalidCriterionParametersError


class CriterionRegistry:
    """Registry managing loss criterion deserialization, validation, and instantiation."""

    _REGISTRY: Dict[str, tuple[Type[Any], Type[nn.Module]]] = {
        "mseloss": (MSELossParameters, nn.MSELoss),
        "l1loss": (L1LossParameters, nn.L1Loss),
        "smoothl1loss": (SmoothL1LossParameters, nn.SmoothL1Loss),
        "crossentropyloss": (CrossEntropyLossParameters, nn.CrossEntropyLoss),
        "bcewithlogitsloss": (BCEWithLogitsLossParameters, nn.BCEWithLogitsLoss),
    }

    @classmethod
    def register(cls, name: str, param_cls: Type[Any], loss_cls: Type[nn.Module]) -> None:
        """Register a new loss criterion type."""
        cls._REGISTRY[name.strip().lower()] = (param_cls, loss_cls)

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> None:
        """
        Validate loss criterion configuration block.
        """
        if not isinstance(config, dict):
            raise InvalidCriterionParametersError("Loss criterion configuration must be a dictionary.")
        loss_type = config.get("type")
        if not loss_type or not isinstance(loss_type, str):
            raise InvalidCriterionParametersError("Loss criterion configuration missing 'type' field.")
        key = loss_type.strip().lower()
        if key not in cls._REGISTRY:
            raise UnsupportedCriterionError(
                f"Unsupported loss criterion type '{loss_type}'. Supported: {list(cls._REGISTRY.keys())}"
            )
        params_dict = config.get("parameters", {})
        if not isinstance(params_dict, dict):
            raise InvalidCriterionParametersError("Loss criterion 'parameters' must be a dictionary.")
        param_cls, _ = cls._REGISTRY[key]
        param_cls.from_dict(params_dict)

    @classmethod
    def create(cls, config: Dict[str, Any]) -> nn.Module:
        """
        Instantiate PyTorch loss criterion module.
        """
        cls.validate(config)
        key = config["type"].strip().lower()
        param_cls, loss_cls = cls._REGISTRY[key]
        dto = param_cls.from_dict(config.get("parameters", {}))
        kwargs = dto.to_torch_kwargs()
        return loss_cls(**kwargs)
