"""
Model aggregation subsystem for distributed training engine.
"""

from .aggregation_request import AggregationRequest, ModelUpdate
from .aggregation_result import AggregationResult
from .aggregator_adapter import AggregatorAdapter
from .aggregator_adapter_registery import (
    AggregatorAdapterRegistery,
    AggregatorAdapterRegistry,
)
from .aggregation_orchestrator import (
    AggregationOrchestrator,
)
from .exceptions import (
    AggregationError,
    UnsupportedModelTypeError,
    AggregatorAdapterNotFoundError,
    InvalidAggregationRequestError,
    DeltaAccessError,
    DeltaFormatError,
    TensorCompatibilityError,
    InvalidBaseModelVersionError,
    InconsistentModelIdError,
    InvalidUpdateError,
    BaseModelAccessError,
    BaseModelLoadError,
    AggregationOperationError,
    ExistingModelVersionConflictError,
    ModelSerializationError,
)

__all__ = [
    "AggregationRequest",
    "ModelUpdate",
    "AggregationResult",
    "AggregatorAdapter",
    "AggregatorAdapterRegistery",
    "AggregatorAdapterRegistry",
    "AggregationOrchestrator",
    "AggregationError",
    "UnsupportedModelTypeError",
    "AggregatorAdapterNotFoundError",
    "InvalidAggregationRequestError",
    "DeltaAccessError",
    "DeltaFormatError",
    "TensorCompatibilityError",
    "InvalidBaseModelVersionError",
    "InconsistentModelIdError",
    "InvalidUpdateError",
    "BaseModelAccessError",
    "BaseModelLoadError",
    "AggregationOperationError",
    "ExistingModelVersionConflictError",
    "ModelSerializationError",
]
