"""
Parameter model for L1Loss criterion.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidCriterionParametersError


@dataclass
class L1LossParameters:
    """Strongly typed parameter DTO for torch.nn.L1Loss."""
    reduction: str = "mean"

    def validate(self) -> None:
        """Validate L1Loss parameter boundaries."""
        if self.reduction not in ("mean", "sum", "none"):
            raise InvalidCriterionParametersError(
                f"L1Loss reduction must be one of ('mean', 'sum', 'none'), got '{self.reduction}'"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> L1LossParameters:
        params = cls(reduction=str(data.get("reduction", "mean")))
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {"reduction": self.reduction}
