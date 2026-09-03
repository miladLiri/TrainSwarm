"""
Parameter model for SmoothL1Loss criterion.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidCriterionParametersError


@dataclass
class SmoothL1LossParameters:
    """Strongly typed parameter DTO for torch.nn.SmoothL1Loss."""
    beta: float = 1.0
    reduction: str = "mean"

    def validate(self) -> None:
        """Validate SmoothL1Loss parameter boundaries."""
        if not isinstance(self.beta, (int, float)) or self.beta < 0:
            raise InvalidCriterionParametersError(f"SmoothL1Loss beta must be >= 0, got {self.beta}")
        if self.reduction not in ("mean", "sum", "none"):
            raise InvalidCriterionParametersError(
                f"SmoothL1Loss reduction must be one of ('mean', 'sum', 'none'), got '{self.reduction}'"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SmoothL1LossParameters:
        params = cls(
            beta=float(data.get("beta", 1.0)),
            reduction=str(data.get("reduction", "mean"))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "beta": self.beta,
            "reduction": self.reduction,
        }
