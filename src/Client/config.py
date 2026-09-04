"""Configuration management for the TrainSwarm Client application."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


@dataclass(frozen=True)
class ClientConfig:
    coordinator_address: Optional[str]
    client_node_id: str
    request_timeout_seconds: float
    coordinator_url: Optional[str] = None


def load_config() -> ClientConfig:
    coord_addr = os.getenv("COORDINATOR_ADDRESS") or os.getenv("COORDINATOR_URL")
    if coord_addr:
        coord_addr = coord_addr.strip().rstrip("/")
        if not coord_addr:
            coord_addr = None
    
    client_node_id = os.getenv("CLIENT_NODE_ID", "client-node-dev").strip()
    
    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 10.0

    return ClientConfig(
        coordinator_address=coord_addr,
        client_node_id=client_node_id,
        request_timeout_seconds=timeout,
        coordinator_url=coord_addr,
    )


# Default singleton instance
config = load_config()