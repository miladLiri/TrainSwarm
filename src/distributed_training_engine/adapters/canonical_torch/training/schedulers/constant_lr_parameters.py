"""
Parameter model for ConstantLR scheduler.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidSchedulerParametersError


@dataclass
class ConstantLRParameters:
    """Strongly typed parameter DTO for torch.optim.lr_scheduler.ConstantLR."""
    factor: float = 1.0 / 3.0
    total_iters: int = 5

    def validate(self) -> None:
        """Validate ConstantLR parameter boundaries."""
        if not isinstance(self.factor, (int, float)) or self.factor <= 0:
            raise InvalidSchedulerParametersError(f"ConstantLR factor must be > 0, got {self.factor}")
        if not isinstance(self.total_iters, int) or self.total_iters < 1:
            raise InvalidSchedulerParametersError(f"ConstantLR total_iters must be an integer >= 1, got {self.total_iters}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConstantLRParameters:
        params = cls(
            factor=float(data.get("factor", 1.0 / 3.0)),
            total_iters=int(data.get("total_iters", 5))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "total_iters": self.total_iters,
        }
