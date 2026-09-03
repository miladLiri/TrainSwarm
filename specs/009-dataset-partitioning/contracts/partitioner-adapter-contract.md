# Contract: Partitioner Adapter & Registry Interface

**Feature**: `009-dataset-partitioning`  
**Date**: 2026-09-03  
**Status**: Active

---

## 1. `PartitionerAdapter` Abstract Interface

Located at: `src/distributed_training_engine/partitioning/partitioner_adapter.py`

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .partitioning_request import PartitioningRequest
    from .partitioning_result import PartitioningResult
    from .sampling_result import SamplingResult


class PartitionerAdapter(ABC):
    """
    Model-agnostic abstract base class for dataset partitioners.
    Concrete adapters implement reading and persisting model-specific dataset formats.
    """

    def __init__(self, request: "PartitioningRequest") -> None:
        """
        Initialize the partitioner adapter with the partitioning request.

        Args:
            request: Configuration containing model_type, datasetPath, shardsOutputDirectory,
                     sampleOutputDirecotry, and datasetId.
        """
        self.request = request

    @abstractmethod
    def CreateSample(self) -> "SamplingResult":
        """
        Extract a single representative sample from the dataset and persist it
        to sampleOutputDirecotry with naming <datasetId>_sample.pt.

        Returns:
            SamplingResult containing datasetId, samplePath, and sampleCount.

        Raises:
            DatasetAccessError: If datasetPath is missing or unreadable.
            DatasetFormatError: If dataset is empty or corrupted.
            OutputDirectoryError: If sampleOutputDirecotry cannot be created or accessed.
        """
        pass

    @abstractmethod
    def CreateShards(self, shardSampleSize: int) -> "PartitioningResult":
        """
        Partition the complete dataset into shards containing at most shardSampleSize samples each.
        Persists all shards to shardsOutputDirectory following <datasetId>_<shardId>.pt naming.

        Args:
            shardSampleSize: Target number of samples per shard (> 0).

        Returns:
            PartitioningResult containing datasetId, shardCount, and list of PartitionedShard descriptors.

        Raises:
            InvalidShardSampleSizeError: If shardSampleSize <= 0 or not an int.
            ExistingShardConflictError: If shardsOutputDirectory is non-empty.
            DatasetAccessError: If datasetPath is missing or unreadable.
            DatasetFormatError: If dataset format violates model contracts or contains corrupt samples.
            ShardSerializationError: If saving a shard artifact fails.
            OutputDirectoryError: If shardsOutputDirectory cannot be created.
        """
        pass
```

---

## 2. `PartitionerAdapterRegistry` Interface

Located at: `src/distributed_training_engine/partitioning/partitioner_adapter_registery.py`

```python
from typing import Dict, Type
from ..model_type import ModelType
from .exceptions import PartitionerAdapterNotFoundError
from .partitioner_adapter import PartitionerAdapter


class PartitionerAdapterRegistry:
    """Registry mapping ModelType to PartitionerAdapter implementations."""

    _registry: Dict[ModelType, Type[PartitionerAdapter]] = {}

    @classmethod
    def Register(cls, model_type: ModelType, partitioner_class: Type[PartitionerAdapter]) -> None:
        """
        Register a concrete PartitionerAdapter class for a given ModelType.

        Args:
            model_type: The ModelType key.
            partitioner_class: Subclass of PartitionerAdapter.
        """
        cls._registry[model_type] = partitioner_class

    @classmethod
    def Get(cls, model_type: ModelType) -> Type[PartitionerAdapter]:
        """
        Retrieve the registered PartitionerAdapter class for a given ModelType.

        Args:
            model_type: The ModelType to look up.

        Returns:
            The registered PartitionerAdapter subclass.

        Raises:
            PartitionerAdapterNotFoundError: If no adapter is registered for model_type.
        """
        if model_type not in cls._registry:
            raise PartitionerAdapterNotFoundError(
                f"No partitioner adapter registered for ModelType: '{model_type}'"
            )
        return cls._registry[model_type]
```

---

## 3. `PartitioningOrchestrator` Interface

Located at: `src/distributed_training_engine/partitioning/partitioning_orchecstrator.py`

```python
from .partitioner_adapter_registery import PartitionerAdapterRegistry
from .partitioning_request import PartitioningRequest
from .partitioning_result import PartitioningResult
from .sampling_result import SamplingResult


class PartitioningOrchestrator:
    """Coordinates the partitioning workflow lifecycle using registered adapters."""

    def __init__(self, request: PartitioningRequest) -> None:
        request.validate()
        self.request = request
        adapter_cls = PartitionerAdapterRegistry.Get(request.model_type)
        self.adapter = adapter_cls(request)

    def GetSample(self) -> SamplingResult:
        """Call model-specific sample creation and return SamplingResult."""
        return self.adapter.CreateSample()

    def CreateShards(self, shardSampleSize: int) -> PartitioningResult:
        """Validate sample size and delegate shard creation to the adapter."""
        if not isinstance(shardSampleSize, int) or shardSampleSize <= 0:
            from .exceptions import InvalidShardSampleSizeError
            raise InvalidShardSampleSizeError(
                f"shardSampleSize must be a positive integer, got: {shardSampleSize}"
            )
        return self.adapter.CreateShards(shardSampleSize)
```
