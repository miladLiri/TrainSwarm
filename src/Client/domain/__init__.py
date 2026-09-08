"""Domain package for TrainSwarm Client."""

from .model import Model
from .training_shard import TrainingShard, TrainingShardStatus

__all__ = [
    "Model",
    "TrainingShard",
    "TrainingShardStatus",
]
