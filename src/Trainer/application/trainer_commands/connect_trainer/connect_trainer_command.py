"""Command and result models for connecting trainer to Coordinator."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConnectTrainerCommand:
    """Command to initiate trainer connection with Coordinator.

    Contains no input parameters; the handler reads the node identity from state.
    """
    pass


@dataclass(frozen=True)
class ConnectTrainerResult:
    """Outcome of ConnectTrainerCommand execution."""

    success: bool
    description: str
    trainer_id: Optional[str] = None
    status_code: Optional[int] = None
