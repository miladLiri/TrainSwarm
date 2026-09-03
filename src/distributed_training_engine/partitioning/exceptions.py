"""
Exceptions for the dataset partitioning subsystem.
"""

from typing import Optional


class PartitioningError(Exception):
    """Base exception for all partitioning errors."""

    def __init__(self, message: str, dataset_id: Optional[str] = None, operation: Optional[str] = None) -> None:
        self.dataset_id = dataset_id
        self.operation = operation
        context_parts = []
        if dataset_id:
            context_parts.append(f"dataset='{dataset_id}'")
        if operation:
            context_parts.append(f"op='{operation}'")
        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        super().__init__(f"{message}{context_str}")


class InvalidPartitioningConfigurationError(PartitioningError):
    """Raised when partitioning request parameters or configuration are malformed."""
    pass


class InvalidShardSampleSizeError(PartitioningError):
    """Raised when shardSampleSize is non-positive or not an integer."""
    pass


class DatasetAccessError(PartitioningError):
    """Raised when the input dataset file does not exist or cannot be accessed."""
    pass


class DatasetFormatError(PartitioningError):
    """Raised when dataset format is corrupt, empty, or violates tensor contracts."""
    pass


class ShardSerializationError(PartitioningError):
    """Raised when serializing a partitioned shard to disk fails."""
    pass


class OutputDirectoryError(PartitioningError):
    """Raised when output directory cannot be created or accessed."""
    pass


class ExistingShardConflictError(PartitioningError):
    """Raised when the shards output directory is non-empty (conflict prevention)."""
    pass


class UnsupportedModelTypeError(PartitioningError):
    """Raised when an unsupported or unknown ModelType is requested."""
    pass


class PartitionerAdapterNotFoundError(PartitioningError):
    """Raised when no partitioner adapter is registered for a given ModelType."""
    pass


class PartitioningOperationError(PartitioningError):
    """General unrecoverable error during dataset partitioning workflow."""
    pass
