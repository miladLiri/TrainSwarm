"""
Parameter model for LinearLR scheduler.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from ....exceptions import InvalidSchedulerParametersError


@dataclass
class LinearLRParameters:
    """Strongly typed parameter DTO for torch.optim.lr_scheduler.LinearLR."""
    start_factor: float = 1.0 / 3.0
    end_factor: float = 1.0
    total_iters: int = 5

    def validate(self) -> None:
        """Validate LinearLR parameter boundaries."""
        if not isinstance(self.start_factor, (int, float)) or self.start_factor <= 0:
            raise InvalidSchedulerParametersError(f"LinearLR start_factor must be > 0, got {self.start_factor}")
        if not isinstance(self.end_factor, (int, float)) or self.end_factor <= 0:
            raise InvalidSchedulerParametersError(f"LinearLR end_factor must be > 0, got {self.end_factor}")
        if not isinstance(self.total_iters, int) or self.total_iters < 1:
            raise InvalidSchedulerParametersError(f"LinearLR total_iters must be an integer >= 1, got {self.total_iters}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LinearLRParameters:
        params = cls(
            start_factor=float(data.get("start_factor", 1.0 / 3.0)),
            end_factor=float(data.get("end_factor", 1.0)),
            total_iters=int(data.get("total_iters", 5))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "start_factor": self.start_factor,
            "end_factor": self.end_factor,
            "total_iters": self.total_iters,
        }
