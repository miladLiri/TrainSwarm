"""
Parameter model for ExponentialLR scheduler.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from ....exceptions import InvalidSchedulerParametersError


@dataclass
class ExponentialLRParameters:
    """Strongly typed parameter DTO for torch.optim.lr_scheduler.ExponentialLR."""
    gamma: float = 0.9

    def validate(self) -> None:
        """Validate ExponentialLR parameter boundaries."""
        if not isinstance(self.gamma, (int, float)) or not (0.0 < self.gamma <= 1.0):
            raise InvalidSchedulerParametersError(f"ExponentialLR gamma must be in range (0, 1], got {self.gamma}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExponentialLRParameters:
        params = cls(
            gamma=float(data.get("gamma", 0.9))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "gamma": self.gamma,
        }
