"""Trainer infrastructure adapters."""

from .coordinator_adapter import (
    CoordinatorAdapter,
    CoordinatorAdapterError,
    CoordinatorAdapterResult,
    CoordinatorConfigurationError,
)
from .trainer_p2p_node_adapter import (
    TrainerP2PNodeAdapter,
    ITrainerP2PNodeAdapter,
    P2PNodeConnectionError,
    P2PTransferError,
)

__all__ = [
    "CoordinatorAdapter",
    "CoordinatorAdapterError",
    "CoordinatorAdapterResult",
    "CoordinatorConfigurationError",
    "TrainerP2PNodeAdapter",
    "ITrainerP2PNodeAdapter",
    "P2PNodeConnectionError",
    "P2PTransferError",
]
