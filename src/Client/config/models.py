"""Configuration data models for TrainSwarm Client."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ClientConfig:
    """Strongly typed, immutable configuration for the TrainSwarm Client."""

    coordinator_address: str
    client_node_id: str = "client-node-dev"
    request_timeout_seconds: float = 10.0
    db_path: Path = Path("./training.db")
    shard_training_time_limit_seconds: float = 300.0
    shard_safety_factor: float = 1.0
    working_directory: Path = Path(".")

    @property
    def coordinator_url(self) -> str:
        """Backward-compatibility alias for coordinator_address."""
        return self.coordinator_address
