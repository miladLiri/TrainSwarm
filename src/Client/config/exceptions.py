"""Exception hierarchy for Client configuration management."""

from typing import Optional


class ClientConfigurationError(Exception):
    """Base exception for all client configuration errors."""
    pass


class MissingConfigurationError(ClientConfigurationError):
    """Raised when a required configuration value or environment variable is missing."""

    def __init__(self, variable_name: str, message: Optional[str] = None) -> None:
        self.variable_name = variable_name
        msg = message or f"Missing required environment variable '{variable_name}'."
        super().__init__(msg)


class InvalidConfigurationValueError(ClientConfigurationError):
    """Raised when a configuration value cannot be parsed or violates constraints."""

    def __init__(self, variable_name: str, raw_value: str, reason: str) -> None:
        self.variable_name = variable_name
        self.raw_value = raw_value
        self.reason = reason
        super().__init__(
            f"Invalid configuration value for '{variable_name}' ('{raw_value}'): {reason}"
        )
