"""
Strongly typed training configuration model for canonical_torch.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from .optimizer_registry import OptimizerRegistry
from .scheduler_registry import SchedulerRegistry
from .criterion_registry import CriterionRegistry
from ...exceptions import InvalidCanonicalTrainingConfigError


@dataclass
class CanonicalTorchTrainingConfig:
    """Strongly typed configuration deserialized from the task 'training' dictionary."""
    batch_size: int
    shuffle: bool
    epochs: int
    gradient_accumulation_steps: int
    optimizer: Dict[str, Any]
    loss: Dict[str, Any]
    max_steps: Optional[int] = None
    max_grad_norm: Optional[float] = None
    seed: Optional[int] = None
    scheduler: Optional[Dict[str, Any]] = None

    def validate(self) -> None:
        """Validate all parameter constraints and embedded registry configurations."""
        if not isinstance(self.batch_size, int) or self.batch_size <= 0:
            raise InvalidCanonicalTrainingConfigError(
                f"batch_size must be a positive integer, got {self.batch_size}"
            )
        if not isinstance(self.shuffle, bool):
            raise InvalidCanonicalTrainingConfigError(
                f"shuffle must be a boolean, got {self.shuffle}"
            )
        if not isinstance(self.epochs, int) or self.epochs <= 0:
            raise InvalidCanonicalTrainingConfigError(
                f"epochs must be a positive integer, got {self.epochs}"
            )
        if not isinstance(self.gradient_accumulation_steps, int) or self.gradient_accumulation_steps < 1:
            raise InvalidCanonicalTrainingConfigError(
                f"gradient_accumulation_steps must be an integer >= 1, got {self.gradient_accumulation_steps}"
            )
        if self.max_steps is not None:
            if not isinstance(self.max_steps, int) or self.max_steps <= 0:
                raise InvalidCanonicalTrainingConfigError(
                    f"max_steps must be null or a positive integer, got {self.max_steps}"
                )
        if self.max_grad_norm is not None:
            if not isinstance(self.max_grad_norm, (int, float)) or self.max_grad_norm <= 0:
                raise InvalidCanonicalTrainingConfigError(
                    f"max_grad_norm must be null or a positive number, got {self.max_grad_norm}"
                )
        if self.seed is not None:
            if not isinstance(self.seed, int):
                raise InvalidCanonicalTrainingConfigError(
                    f"seed must be null or an integer, got {self.seed}"
                )

        # Validate registries
        try:
            OptimizerRegistry.validate(self.optimizer)
        except Exception as exc:
            raise InvalidCanonicalTrainingConfigError(f"Invalid optimizer configuration: {exc}") from exc

        try:
            CriterionRegistry.validate(self.loss)
        except Exception as exc:
            raise InvalidCanonicalTrainingConfigError(f"Invalid loss configuration: {exc}") from exc

        if self.scheduler is not None:
            try:
                SchedulerRegistry.validate(self.scheduler)
            except Exception as exc:
                raise InvalidCanonicalTrainingConfigError(f"Invalid scheduler configuration: {exc}") from exc

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CanonicalTorchTrainingConfig:
        """Construct and validate from dictionary."""
        if not isinstance(data, dict):
            raise InvalidCanonicalTrainingConfigError("training configuration must be a dictionary.")

        for required_key in ("batch_size", "shuffle", "epochs", "gradient_accumulation_steps", "optimizer", "loss"):
            if required_key not in data:
                raise InvalidCanonicalTrainingConfigError(f"Missing required training config field: '{required_key}'")

        max_grad_norm_raw = data.get("max_grad_norm")
        max_grad_norm = float(max_grad_norm_raw) if max_grad_norm_raw is not None else None

        max_steps_raw = data.get("max_steps")
        max_steps = int(max_steps_raw) if max_steps_raw is not None else None

        seed_raw = data.get("seed")
        seed = int(seed_raw) if seed_raw is not None else None

        config = cls(
            batch_size=int(data["batch_size"]),
            shuffle=bool(data["shuffle"]),
            epochs=int(data["epochs"]),
            gradient_accumulation_steps=int(data["gradient_accumulation_steps"]),
            optimizer=data["optimizer"],
            loss=data["loss"],
            max_steps=max_steps,
            max_grad_norm=max_grad_norm,
            seed=seed,
            scheduler=data.get("scheduler")
        )
        config.validate()
        return config
