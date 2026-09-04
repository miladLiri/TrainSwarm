"""Configuration module for the TrainSwarm Client."""

from .config_manager import ConfigManager
from .exceptions import (
    ClientConfigurationError,
    InvalidConfigurationValueError,
    MissingConfigurationError,
)
from .models import ClientConfig


def load_config() -> ClientConfig:
    """Convenience function to load and validate ClientConfig."""
    return ConfigManager().get_config()


__all__ = [
    "ConfigManager",
    "ClientConfig",
    "ClientConfigurationError",
    "MissingConfigurationError",
    "InvalidConfigurationValueError",
    "load_config",
]
