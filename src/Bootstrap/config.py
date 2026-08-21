"""Configuration management for the TrainSwarm Bootstrap Relay service."""

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
class BootstrapConfig:
    host: str
    port: int
    relay_message_ttl_seconds: int


def load_config() -> BootstrapConfig:
    host = os.getenv("HOST", "0.0.0.0")
    try:
        port = int(os.getenv("PORT", "6000"))
    except ValueError:
        port = 6000

    try:
        ttl = int(os.getenv("RELAY_MESSAGE_TTL_SECONDS", "3600"))
    except ValueError:
        ttl = 3600

    return BootstrapConfig(
        host=host,
        port=port,
        relay_message_ttl_seconds=ttl,
    )


# Default singleton instance
config = load_config()

