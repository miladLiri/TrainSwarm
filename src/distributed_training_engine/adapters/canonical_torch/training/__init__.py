"""
Canonical PyTorch training adapter package.
"""

from .canonical_torch_trainer import CanonicalTorchTrainer, CanonicalTorchAdapter
from .canonical_torch_config import CanonicalTorchTrainingConfig
from .optimizer_registry import OptimizerRegistry
from .scheduler_registry import SchedulerRegistry
from .criterion_registry import CriterionRegistry

__all__ = [
    "CanonicalTorchTrainer",
    "CanonicalTorchAdapter",
    "CanonicalTorchTrainingConfig",
    "OptimizerRegistry",
    "SchedulerRegistry",
    "CriterionRegistry",
]
