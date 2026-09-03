"""Persistence package for TrainSwarm Client."""

from .database import DatabaseManager
from .training_shard_repository import (
    ITrainingShardRepository,
    TrainingShardRepository,
)
from .exceptions import (
    PersistenceError,
    DatabaseConfigurationError,
    DatabaseInitializationError,
    DuplicateShardError,
    SerializationError,
)

__all__ = [
    "DatabaseManager",
    "ITrainingShardRepository",
    "TrainingShardRepository",
    "PersistenceError",
    "DatabaseConfigurationError",
    "DatabaseInitializationError",
    "DuplicateShardError",
    "SerializationError",
]
