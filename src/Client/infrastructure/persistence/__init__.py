"""Persistence package for TrainSwarm Client."""

from .database import DatabaseManager
from .training_shard_repository import (
    ITrainingShardRepository,
    TrainingShardRepository,
)
from .model_repository import (
    IModelRepository,
    ModelRepository,
)
from .exceptions import (
    PersistenceError,
    DatabaseConfigurationError,
    DatabaseInitializationError,
    DuplicateShardError,
    SerializationError,
    ModelNotFoundError,
    ModelPersistenceError,
)

__all__ = [
    "DatabaseManager",
    "ITrainingShardRepository",
    "TrainingShardRepository",
    "IModelRepository",
    "ModelRepository",
    "PersistenceError",
    "DatabaseConfigurationError",
    "DatabaseInitializationError",
    "DuplicateShardError",
    "SerializationError",
    "ModelNotFoundError",
    "ModelPersistenceError",
]

