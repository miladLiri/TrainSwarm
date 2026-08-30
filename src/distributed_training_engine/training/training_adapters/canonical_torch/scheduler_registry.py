"""
Scheduler registry mapping scheduler types to parameter models and PyTorch LR schedulers.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Type
import torch
from .schedulers import (
    ConstantLRParameters,
    LinearLRParameters,
    StepLRParameters,
    ExponentialLRParameters,
    CosineAnnealingLRParameters,
)
from ...exceptions import UnsupportedSchedulerError, InvalidSchedulerParametersError


class SchedulerRegistry:
    """Registry managing scheduler deserialization, validation, and instantiation."""

    _REGISTRY: Dict[str, tuple[Type[Any], Type[Any]]] = {
        "constantlr": (ConstantLRParameters, torch.optim.lr_scheduler.ConstantLR),
        "linearlr": (LinearLRParameters, torch.optim.lr_scheduler.LinearLR),
        "steplr": (StepLRParameters, torch.optim.lr_scheduler.StepLR),
        "exponentiallr": (ExponentialLRParameters, torch.optim.lr_scheduler.ExponentialLR),
        "cosineannealinglr": (CosineAnnealingLRParameters, torch.optim.lr_scheduler.CosineAnnealingLR),
    }

    @classmethod
    def register(cls, name: str, param_cls: Type[Any], scheduler_cls: Type[Any]) -> None:
        """Register a new scheduler type."""
        cls._REGISTRY[name.strip().lower()] = (param_cls, scheduler_cls)

    @classmethod
    def validate(cls, config: Optional[Dict[str, Any]]) -> None:
        """
        Validate scheduler configuration block.
        """
        if config is None:
            return
        if not isinstance(config, dict):
            raise InvalidSchedulerParametersError("Scheduler configuration must be a dictionary.")
        sched_type = config.get("type")
        if not sched_type or not isinstance(sched_type, str):
            raise InvalidSchedulerParametersError("Scheduler configuration missing 'type' field.")
        key = sched_type.strip().lower()
        if key not in cls._REGISTRY:
            raise UnsupportedSchedulerError(
                f"Unsupported scheduler type '{sched_type}'. Supported: {list(cls._REGISTRY.keys())}"
            )
        params_dict = config.get("parameters", {})
        if not isinstance(params_dict, dict):
            raise InvalidSchedulerParametersError("Scheduler 'parameters' must be a dictionary.")
        param_cls, _ = cls._REGISTRY[key]
        param_cls.from_dict(params_dict)

    @classmethod
    def create(cls, config: Optional[Dict[str, Any]], optimizer: torch.optim.Optimizer) -> Optional[Any]:
        """
        Instantiate PyTorch scheduler attached to the provided optimizer.
        """
        if config is None:
            return None
        cls.validate(config)
        key = config["type"].strip().lower()
        param_cls, sched_cls = cls._REGISTRY[key]
        dto = param_cls.from_dict(config.get("parameters", {}))
        kwargs = dto.to_torch_kwargs()
        return sched_cls(optimizer, **kwargs)
