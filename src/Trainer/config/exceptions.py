"""Configuration exception hierarchy for TrainSwarm Trainer."""


class TrainerConfigurationError(Exception):
    """Base exception for all Trainer configuration-related errors."""
    pass


class MissingConfigurationError(TrainerConfigurationError):
    """Raised when a mandatory environment variable or configuration value is missing."""

    def __init__(self, variable_name: str, message: str = "") -> None:
        self.variable_name = variable_name
        super().__init__(
            message or f"Required environment variable '{variable_name}' is not set or empty."
        )


class InvalidConfigurationValueError(TrainerConfigurationError):
    """Raised when an environment variable value is malformed or out of permissible bounds."""

    def __init__(self, variable_name: str, raw_value: str, reason: str) -> None:
        self.variable_name = variable_name
        self.raw_value = raw_value
        self.reason = reason
        super().__init__(
            f"Invalid value '{raw_value}' for environment variable '{variable_name}': {reason}"
        )
