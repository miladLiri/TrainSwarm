"""
Strongly typed training configuration model for canonical_causal_decoder.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from ....training.exceptions import InvalidTaskConfigurationError


SUPPORTED_SCHEDULER_TYPES = {
    "linear",
    "cosine",
    "cosine_with_restarts",
    "polynomial",
    "constant",
    "constant_with_warmup",
}


@dataclass
class CanonicalCausalDecoderTrainingConfig:
    """Strongly typed configuration deserialized from the task 'training' dictionary."""
    seed: int = 42
    batch_size: int = 2
    epochs: int = 1
    max_steps: Optional[int] = None
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    gradient_accumulation_steps: int = 1
    max_grad_norm: Optional[float] = 1.0
    scheduler_type: str = "linear"
    warmup_steps: int = 0
    warmup_ratio: float = 0.0
    fp16: bool = False
    bf16: bool = False
    shuffle: bool = True

    def validate(self) -> None:
        """Validate all parameter constraints for Hugging Face TrainingArguments."""
        if not isinstance(self.seed, int) or self.seed < 0:
            raise InvalidTaskConfigurationError(
                f"seed must be a non-negative integer, got {self.seed}"
            )
        if not isinstance(self.batch_size, int) or self.batch_size < 1:
            raise InvalidTaskConfigurationError(
                f"batch_size must be a positive integer, got {self.batch_size}"
            )
        if not isinstance(self.epochs, int) or self.epochs < 1:
            raise InvalidTaskConfigurationError(
                f"epochs must be a positive integer, got {self.epochs}"
            )
        if self.max_steps is not None:
            if not isinstance(self.max_steps, int) or self.max_steps < 1:
                raise InvalidTaskConfigurationError(
                    f"max_steps must be null or an integer >= 1, got {self.max_steps}"
                )
        if not isinstance(self.learning_rate, (int, float)) or self.learning_rate <= 0.0:
            raise InvalidTaskConfigurationError(
                f"learning_rate must be a positive number, got {self.learning_rate}"
            )
        if not isinstance(self.weight_decay, (int, float)) or self.weight_decay < 0.0:
            raise InvalidTaskConfigurationError(
                f"weight_decay must be a non-negative number, got {self.weight_decay}"
            )
        if not isinstance(self.gradient_accumulation_steps, int) or self.gradient_accumulation_steps < 1:
            raise InvalidTaskConfigurationError(
                f"gradient_accumulation_steps must be an integer >= 1, got {self.gradient_accumulation_steps}"
            )
        if self.max_grad_norm is not None:
            if not isinstance(self.max_grad_norm, (int, float)) or self.max_grad_norm <= 0.0:
                raise InvalidTaskConfigurationError(
                    f"max_grad_norm must be null or a positive number, got {self.max_grad_norm}"
                )
        if not isinstance(self.scheduler_type, str) or self.scheduler_type.lower() not in SUPPORTED_SCHEDULER_TYPES:
            raise InvalidTaskConfigurationError(
                f"scheduler_type '{self.scheduler_type}' is not supported. Must be one of: {sorted(SUPPORTED_SCHEDULER_TYPES)}"
            )
        if not isinstance(self.warmup_steps, int) or self.warmup_steps < 0:
            raise InvalidTaskConfigurationError(
                f"warmup_steps must be a non-negative integer, got {self.warmup_steps}"
            )
        if not isinstance(self.warmup_ratio, (int, float)) or not (0.0 <= float(self.warmup_ratio) <= 1.0):
            raise InvalidTaskConfigurationError(
                f"warmup_ratio must be between 0.0 and 1.0, got {self.warmup_ratio}"
            )
        if not isinstance(self.fp16, bool):
            raise InvalidTaskConfigurationError(f"fp16 must be a boolean, got {self.fp16}")
        if not isinstance(self.bf16, bool):
            raise InvalidTaskConfigurationError(f"bf16 must be a boolean, got {self.bf16}")
        if not isinstance(self.shuffle, bool):
            raise InvalidTaskConfigurationError(f"shuffle must be a boolean, got {self.shuffle}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CanonicalCausalDecoderTrainingConfig:
        """Construct and validate from dictionary."""
        if not isinstance(data, dict):
            raise InvalidTaskConfigurationError("training configuration must be a dictionary.")

        max_steps_raw = data.get("max_steps")
        max_steps = int(max_steps_raw) if max_steps_raw is not None else None

        max_grad_norm_raw = data.get("max_grad_norm")
        max_grad_norm = float(max_grad_norm_raw) if max_grad_norm_raw is not None else None

        config = cls(
            seed=int(data.get("seed", 42)),
            batch_size=int(data.get("batch_size", 2)),
            epochs=int(data.get("epochs", 1)),
            max_steps=max_steps,
            learning_rate=float(data.get("learning_rate", 5e-5)),
            weight_decay=float(data.get("weight_decay", 0.01)),
            gradient_accumulation_steps=int(data.get("gradient_accumulation_steps", 1)),
            max_grad_norm=max_grad_norm,
            scheduler_type=str(data.get("scheduler_type", "linear")),
            warmup_steps=int(data.get("warmup_steps", 0)),
            warmup_ratio=float(data.get("warmup_ratio", 0.0)),
            fp16=bool(data.get("fp16", False)),
            bf16=bool(data.get("bf16", False)),
            shuffle=bool(data.get("shuffle", True)),
        )
        config.validate()
        return config
