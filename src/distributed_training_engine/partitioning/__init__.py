"""
Dataset partitioning subsystem for the distributed training engine.
"""

from .exceptions import (
    PartitioningError,
    InvalidPartitioningConfigurationError,
    InvalidShardSampleSizeError,
    DatasetAccessError,
    DatasetFormatError,
    ShardSerializationError,
    OutputDirectoryError,
    ExistingShardConflictError,
    UnsupportedModelTypeError,
    PartitionerAdapterNotFoundError,
    PartitioningOperationError,
)
from .partitioning_request import PartitioningRequest
from .sampling_result import SamplingResult
from .partitioning_result import PartitionedShard, PartitioningResult
from .partitioner_adapter import PartitionerAdapter
from .partitioner_adapter_registery import (
    PartitionerAdapterRegistery,
    PartitionerAdapterRegistry,
)
from .partitioning_orchestrator import (
    PartitioningOrchestrator,
    PartitioningOrchecstrator,
)

# Auto-register canonical_torch adapter
try:
    from ..adapters.canonical_torch.partitioning.canonical_torch_partitioner import (
        CanonicalTorchPartitioner,
    )
    from ..model_type import ModelType
    PartitionerAdapterRegistery.Register(ModelType.CANONICAL_TORCH, CanonicalTorchPartitioner)
except ImportError:
    pass

__all__ = [
    "PartitioningError",
    "InvalidPartitioningConfigurationError",
    "InvalidShardSampleSizeError",
    "DatasetAccessError",
    "DatasetFormatError",
    "ShardSerializationError",
    "OutputDirectoryError",
    "ExistingShardConflictError",
    "UnsupportedModelTypeError",
    "PartitionerAdapterNotFoundError",
    "PartitioningOperationError",
    "PartitioningRequest",
    "SamplingResult",
    "PartitionedShard",
    "PartitioningResult",
    "PartitionerAdapter",
    "PartitionerAdapterRegistery",
    "PartitionerAdapterRegistry",
    "PartitioningOrchestrator",
    "PartitioningOrchecstrator",
]
