"""
Exceptions for the model aggregation subsystem.
"""

from typing import Optional


class AggregationError(Exception):
    """Base exception for all aggregation errors."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        base_version: Optional[int] = None,
        new_version: Optional[int] = None,
        artifact_path: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> None:
        self.model_id = model_id
        self.base_version = base_version
        self.new_version = new_version
        self.artifact_path = artifact_path
        self.operation = operation

        context_parts = []
        if model_id is not None:
            context_parts.append(f"model='{model_id}'")
        if base_version is not None:
            context_parts.append(f"base_v={base_version}")
        if new_version is not None:
            context_parts.append(f"new_v={new_version}")
        if artifact_path is not None:
            context_parts.append(f"path='{artifact_path}'")
        if operation is not None:
            context_parts.append(f"op='{operation}'")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        super().__init__(f"{message}{context_str}")


class UnsupportedModelTypeError(AggregationError):
    """Raised when an unsupported or unknown ModelType is requested for aggregation."""
    pass


class AggregatorAdapterNotFoundError(AggregationError):
    """Raised when no aggregator adapter is registered for a given ModelType."""
    pass


class InvalidAggregationRequestError(AggregationError):
    """Raised when aggregation request parameters or updates list are malformed."""
    pass


class DeltaAccessError(AggregationError):
    """Raised when a specified delta artifact file does not exist or cannot be accessed."""
    pass


class DeltaFormatError(AggregationError):
    """Raised when a delta artifact is corrupted or cannot be deserialized."""
    pass


class TensorCompatibilityError(AggregationError):
    """Raised when delta tensor keys, shapes, or dtypes do not match the base model."""
    pass


class InvalidBaseModelVersionError(AggregationError):
    """Raised when a delta or request references an invalid base model version."""
    pass


class InconsistentModelIdError(AggregationError):
    """Raised when a model update or artifact belongs to a different model ID."""
    pass


class InvalidUpdateError(AggregationError):
    """Raised when update metadata is invalid (e.g., samplesTrained <= 0)."""
    pass


class BaseModelAccessError(AggregationError):
    """Raised when the base model checkpoint cannot be found or accessed."""
    pass


class BaseModelLoadError(AggregationError):
    """Raised when the base model artifact fails to deserialize or load."""
    pass


class AggregationOperationError(AggregationError):
    """Raised when mathematical Federated Averaging computation fails."""
    pass


class ExistingModelVersionConflictError(AggregationError):
    """Raised when the target new model version artifact already exists (immutability protection)."""
    pass


class ModelSerializationError(AggregationError):
    """Raised when saving the new model version artifact fails."""
    pass
