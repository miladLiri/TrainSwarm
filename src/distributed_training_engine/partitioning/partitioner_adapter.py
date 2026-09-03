"""
Model-agnostic partitioner adapter abstract base class.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .partitioning_request import PartitioningRequest
    from .partitioning_result import PartitioningResult
    from .sampling_result import SamplingResult


class PartitionerAdapter(ABC):
    """
    Model-agnostic abstract base class for dataset partitioner adapters.
    Concrete adapters implement reading, slicing, and persisting model-specific datasets.
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
        to sampleOutputDirecotry with name <dataset_id>_sample.pt.

        Returns:
            SamplingResult instance with sample metadata.
        """
        pass

    @abstractmethod
    def CreateShards(self, shardSampleSize: int) -> "PartitioningResult":
        """
        Partition the dataset into shards containing at most shardSampleSize samples each.
        Persists all shards to shardsOutputDirectory following <datasetId>_<shardId>.pt naming.

        Args:
            shardSampleSize: Number of samples per shard.

        Returns:
            PartitioningResult containing metadata for all generated shards.
        """
        pass
