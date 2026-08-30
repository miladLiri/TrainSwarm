"""
Parameter model for AdamW optimizer.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Tuple
from ....exceptions import InvalidOptimizerParametersError


@dataclass
class AdamWParameters:
    """Strongly typed parameter DTO for PyTorch torch.optim.AdamW."""
    learning_rate: float
    betas: Tuple[float, float] = (0.9, 0.999)
    eps: float = 1e-8
    weight_decay: float = 0.01
    amsgrad: bool = False

    def validate(self) -> None:
        """Validate AdamW parameter boundaries."""
        if not isinstance(self.learning_rate, (int, float)) or self.learning_rate <= 0:
            raise InvalidOptimizerParametersError(f"AdamW learning_rate must be > 0, got {self.learning_rate}")
        if not (isinstance(self.betas, (list, tuple)) and len(self.betas) == 2):
            raise InvalidOptimizerParametersError(f"AdamW betas must be a pair (beta1, beta2), got {self.betas}")
        b1, b2 = self.betas
        if not (0.0 <= b1 < 1.0) or not (0.0 <= b2 < 1.0):
            raise InvalidOptimizerParametersError(f"AdamW betas must be in range [0, 1), got ({b1}, {b2})")
        if not isinstance(self.eps, (int, float)) or self.eps <= 0:
            raise InvalidOptimizerParametersError(f"AdamW eps must be > 0, got {self.eps}")
        if not isinstance(self.weight_decay, (int, float)) or self.weight_decay < 0:
            raise InvalidOptimizerParametersError(f"AdamW weight_decay must be >= 0, got {self.weight_decay}")
        if not isinstance(self.amsgrad, bool):
            raise InvalidOptimizerParametersError(f"AdamW amsgrad must be a boolean, got {self.amsgrad}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AdamWParameters:
        """Deserialize and validate parameters from a dictionary."""
        if "learning_rate" not in data:
            raise InvalidOptimizerParametersError("Missing required optimizer parameter 'learning_rate'")
        betas = data.get("betas", (0.9, 0.999))
        if isinstance(betas, list):
            betas = tuple(betas)
        params = cls(
            learning_rate=float(data["learning_rate"]),
            betas=betas,
            eps=float(data.get("eps", 1e-8)),
            weight_decay=float(data.get("weight_decay", 0.01)),
            amsgrad=bool(data.get("amsgrad", False))
        )
        params.validate()
        return params

    def to_torch_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments expected by torch.optim.AdamW."""
        return {
            "lr": self.learning_rate,
            "betas": self.betas,
            "eps": self.eps,
            "weight_decay": self.weight_decay,
            "amsgrad": self.amsgrad,
        }
