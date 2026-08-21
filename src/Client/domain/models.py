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
    """Represents the local client node identity, network session, and active training session."""
    node_id: str
    coordinator_url: str
    bootstrap_url: str = "http://localhost:6000"
    peer_id: Optional[str] = None
    active_session: Optional[Session] = None