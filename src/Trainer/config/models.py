"""Configuration domain models for TrainSwarm Trainer."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainerConfig:
    """Strongly typed, immutable configuration for the Trainer service."""

    coordinator_address: str
    coordinator_grpc_address: str
    trainer_node_id: str
    request_timeout_seconds: float
    working_directory: Path
