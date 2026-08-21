"""Domain models for the TrainSwarm Trainer node."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class TrainerStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    REGISTERED = "REGISTERED"
    DISCONNECTED = "DISCONNECTED"
    TRAINING = "TRAINING"


@dataclass
class PeerSession:
    """Represents the peer identity registered with the Bootstrap relay."""
    peer_id: str
    node_id: str
    role: str
    relay_address: str
    registered_at: str


@dataclass
class TrainerNode:
    """Represents the local trainer node runtime state and configurations."""
    node_id: str
    bootstrap_url: str
    coordinator_url: str
    status: TrainerStatus = TrainerStatus.INITIALIZED
    peer_session: Optional[PeerSession] = None

