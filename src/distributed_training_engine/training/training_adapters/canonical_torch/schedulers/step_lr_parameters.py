"""
Parameter model for StepLR scheduler.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from ....exceptions import InvalidSchedulerParametersError


@dataclass
class StepLRParameters:
    """Strongly typed parameter DTO for torch.optim.lr_scheduler.StepLR."""
    step_size: int = 30
    gamma: float = 0.1

    def validate(self) -> None:
        """Validate StepLR parameter boundaries."""
        if not isinstance(self.step_size, int) or self.step_size < 1:
            raise InvalidSchedulerParametersError(f"StepLR step_size must be an integer >= 1, got {self.step_size}")
        if not isinstance(self.gamma, (int, float)) or not (0.0 < self.gamma <= 1.0):
            raise InvalidSchedulerParametersError(f"StepLR gamma must be in range (0, 1], got {self.gamma}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StepLRParameters:
        params = cls(
            step_size=int(data.get("step_size", 30)),
            gamma=float(data.get("gamma", 0.1))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "step_size": self.step_size,
            "gamma": self.gamma,
        }
