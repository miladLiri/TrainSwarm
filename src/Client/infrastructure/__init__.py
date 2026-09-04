"""Infrastructure package for TrainSwarm Client."""

from .adapters import (
    CoordinatorAdapter,
    CoordinatorAdapterError,
    CoordinatorConfigurationError,
    CoordinatorApiError,
    CoordinatorNetworkError,
    CreateTrainingTaskDto,
)
from .persistence import (
    DatabaseManager,
    TrainingShardRepository,
    PersistenceError,
    DatabaseConfigurationError,
    DatabaseInitializationError,
    DuplicateShardError,
)

__all__ = [
    "CoordinatorAdapter",
    "CoordinatorAdapterError",
    "CoordinatorConfigurationError",
    "CoordinatorApiError",
    "CoordinatorNetworkError",
    "CreateTrainingTaskDto",
    "DatabaseManager",
    "TrainingShardRepository",
    "PersistenceError",
    "DatabaseConfigurationError",
    "DatabaseInitializationError",
    "DuplicateShardError",
]
