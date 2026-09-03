"""
Parameter model for CosineAnnealingLR scheduler.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidSchedulerParametersError


@dataclass
class CosineAnnealingLRParameters:
    """Strongly typed parameter DTO for torch.optim.lr_scheduler.CosineAnnealingLR."""
    T_max: int = 10
    eta_min: float = 0.0

    def validate(self) -> None:
        """Validate CosineAnnealingLR parameter boundaries."""
        if not isinstance(self.T_max, int) or self.T_max < 1:
            raise InvalidSchedulerParametersError(f"CosineAnnealingLR T_max must be an integer >= 1, got {self.T_max}")
        if not isinstance(self.eta_min, (int, float)) or self.eta_min < 0:
            raise InvalidSchedulerParametersError(f"CosineAnnealingLR eta_min must be >= 0, got {self.eta_min}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CosineAnnealingLRParameters:
        params = cls(
            T_max=int(data.get("T_max", 10)),
            eta_min=float(data.get("eta_min", 0.0))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "T_max": self.T_max,
            "eta_min": self.eta_min,
        }
