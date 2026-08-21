"""Configuration management for the TrainSwarm Trainer application."""

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


@dataclass(frozen=True)
class TrainerConfig:
    trainer_node_id: str
    bootstrap_url: str
    coordinator_url: str
    request_timeout_seconds: float


def load_config() -> TrainerConfig:
    trainer_node_id = os.getenv("TRAINER_NODE_ID", "trainer-node-01")
    bootstrap_url = os.getenv("BOOTSTRAP_URL", "http://localhost:6000").rstrip("/")
    coordinator_url = os.getenv("COORDINATOR_URL", "http://localhost:5000").rstrip("/")
    
    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "5.0")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 5.0

    return TrainerConfig(
        trainer_node_id=trainer_node_id,
        bootstrap_url=bootstrap_url,
        coordinator_url=coordinator_url,
        request_timeout_seconds=timeout,
    )


# Default singleton instance
config = load_config()

