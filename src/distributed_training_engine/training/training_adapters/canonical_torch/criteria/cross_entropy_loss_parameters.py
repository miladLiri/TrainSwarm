"""
Parameter model for CrossEntropyLoss criterion.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from ....exceptions import InvalidCriterionParametersError


@dataclass
class CrossEntropyLossParameters:
    """Strongly typed parameter DTO for torch.nn.CrossEntropyLoss."""
    reduction: str = "mean"
    label_smoothing: float = 0.0

    def validate(self) -> None:
        """Validate CrossEntropyLoss parameter boundaries."""
        if self.reduction not in ("mean", "sum", "none"):
            raise InvalidCriterionParametersError(
                f"CrossEntropyLoss reduction must be one of ('mean', 'sum', 'none'), got '{self.reduction}'"
            )
        if not isinstance(self.label_smoothing, (int, float)) or not (0.0 <= self.label_smoothing <= 1.0):
            raise InvalidCriterionParametersError(
                f"CrossEntropyLoss label_smoothing must be in range [0.0, 1.0], got {self.label_smoothing}"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CrossEntropyLossParameters:
        params = cls(
            reduction=str(data.get("reduction", "mean")),
            label_smoothing=float(data.get("label_smoothing", 0.0))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        return {
            "reduction": self.reduction,
            "label_smoothing": self.label_smoothing,
        }
