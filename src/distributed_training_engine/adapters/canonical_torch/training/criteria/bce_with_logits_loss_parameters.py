"""
Parameter model for BCEWithLogitsLoss criterion.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .....training.exceptions import InvalidCriterionParametersError


@dataclass
class BCEWithLogitsLossParameters:
    """Strongly typed parameter DTO for torch.nn.BCEWithLogitsLoss."""
    reduction: str = "mean"

    def validate(self) -> None:
        """Validate BCEWithLogitsLoss parameter boundaries."""
        if self.reduction not in ("mean", "sum", "none"):
            raise InvalidCriterionParametersError(
                f"BCEWithLogitsLoss reduction must be one of ('mean', 'sum', 'none'), got '{self.reduction}'"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BCEWithLogitsLossParameters:
        params = cls(reduction=str(data.get("reduction", "mean")))
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {"reduction": self.reduction}
