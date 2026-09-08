"""Adapters infrastructure package."""

from .coordinator_adapter import (
    CoordinatorAdapter,
    CoordinatorAdapterError,
    CoordinatorConfigurationError,
    CoordinatorApiError,
    CoordinatorNetworkError,
)
from .create_training_task import CreateTrainingTaskDto
from .client_p2p_node_adapter import (
    ClientP2PNodeAdapter,
    IClientP2PNodeAdapter,
    P2PNodeConnectionError,
)

__all__ = [
    "CoordinatorAdapter",
    "CoordinatorAdapterError",
    "CoordinatorConfigurationError",
    "CoordinatorApiError",
    "CoordinatorNetworkError",
    "CreateTrainingTaskDto",
    "ClientP2PNodeAdapter",
    "IClientP2PNodeAdapter",
    "P2PNodeConnectionError",
]
