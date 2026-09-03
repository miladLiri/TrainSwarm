"""Custom exception hierarchy for local persistence infrastructure."""

class PersistenceError(Exception):
    """Base exception for all persistence-related failures."""
    pass


class DatabaseConfigurationError(PersistenceError):
    """Raised when database configuration resolution fails."""
    pass


class DatabaseInitializationError(PersistenceError):
    """Raised when database directory creation or schema initialization fails."""
    pass


class DuplicateShardError(PersistenceError):
    """Raised when attempting to persist a shard whose composite logical key already exists."""

    def __init__(self, model_id: str, model_version: str, dataset_id: str, shard_id: str, message: str = ""):
        self.model_id = model_id
        self.model_version = model_version
        self.dataset_id = dataset_id
        self.shard_id = shard_id
        full_message = (
            message or
            f"Training shard already exists for model '{model_id}' v{model_version}, "
            f"dataset '{dataset_id}', shard '{shard_id}'"
        )
        super().__init__(full_message)


class SerializationError(PersistenceError):
    """Raised when JSON serialization or deserialization of metrics or metadata fails."""
    pass
