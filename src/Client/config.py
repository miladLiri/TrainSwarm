"""Configuration management for the TrainSwarm Client application."""

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
class ClientConfig:
    coordinator_url: str
    client_node_id: str
    request_timeout_seconds: float


def load_config() -> ClientConfig:
    coordinator_url = os.getenv("COORDINATOR_URL", "http://localhost:5000").rstrip("/")
    client_node_id = os.getenv("CLIENT_NODE_ID", "client-node-dev")
    
    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "5.0")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 5.0

    return ClientConfig(
        coordinator_url=coordinator_url,
        client_node_id=client_node_id,
        request_timeout_seconds=timeout,
    )


# Default singleton instance
config = load_config()