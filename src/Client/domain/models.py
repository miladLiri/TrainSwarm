"""Domain models for the TrainSwarm Client."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    """Represents a training session tracked by the Coordinator."""
    session_id: str
    name: str
    client_node_id: str
    status: str = "NONE"


@dataclass
class ClientNode:
    """Represents the local client node identity and active session."""
    node_id: str
    coordinator_url: str
    active_session: Optional[Session] = None