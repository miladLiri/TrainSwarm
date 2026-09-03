"""
Parameter model for SGD optimizer.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidOptimizerParametersError


@dataclass
class SGDParameters:
    """Strongly typed parameter DTO for PyTorch torch.optim.SGD."""
    learning_rate: float
    momentum: float = 0.0
    dampening: float = 0.0
    weight_decay: float = 0.0
    nesterov: bool = False

    def validate(self) -> None:
        """Validate SGD parameter boundaries."""
        if not isinstance(self.learning_rate, (int, float)) or self.learning_rate <= 0:
            raise InvalidOptimizerParametersError(f"SGD learning_rate must be > 0, got {self.learning_rate}")
        if not isinstance(self.momentum, (int, float)) or self.momentum < 0:
            raise InvalidOptimizerParametersError(f"SGD momentum must be >= 0, got {self.momentum}")
        if not isinstance(self.dampening, (int, float)) or self.dampening < 0:
            raise InvalidOptimizerParametersError(f"SGD dampening must be >= 0, got {self.dampening}")
        if not isinstance(self.weight_decay, (int, float)) or self.weight_decay < 0:
            raise InvalidOptimizerParametersError(f"SGD weight_decay must be >= 0, got {self.weight_decay}")
        if not isinstance(self.nesterov, bool):
            raise InvalidOptimizerParametersError(f"SGD nesterov must be a boolean, got {self.nesterov}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SGDParameters:
        """Deserialize and validate parameters from a dictionary."""
        if "learning_rate" not in data:
            raise InvalidOptimizerParametersError("Missing required optimizer parameter 'learning_rate'")
        params = cls(
            learning_rate=float(data["learning_rate"]),
            momentum=float(data.get("momentum", 0.0)),
            dampening=float(data.get("dampening", 0.0)),
            weight_decay=float(data.get("weight_decay", 0.0)),
            nesterov=bool(data.get("nesterov", False))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments expected by torch.optim.SGD."""
        return {
            "lr": self.learning_rate,
            "momentum": self.momentum,
            "dampening": self.dampening,
            "weight_decay": self.weight_decay,
            "nesterov": self.nesterov,
        }
