"""
Partitioning orchestrator workflow coordinator.
"""

from __future__ import annotations
import logging
from typing import Optional
from .partitioner_adapter import PartitionerAdapter
from .partitioner_adapter_registery import PartitionerAdapterRegistery
from .partitioning_request import PartitioningRequest
from .partitioning_result import PartitioningResult
from .sampling_result import SamplingResult
from .exceptions import InvalidShardSampleSizeError

logger = logging.getLogger("distributed_training_engine.partitioning.orchestrator")


class PartitioningOrchecstrator:
    """
    Coordinates the dataset partitioning and sampling workflow.
    Resolves model-specific PartitionerAdapter instances through the registry.
    """

    def __init__(self, request: PartitioningRequest) -> None:
        """
        Initialize the orchestrator with the partitioning request.

        Args:
            request: The validated PartitioningRequest.
        """
        request.validate()
        self.request = request

        logger.info(
            "Initializing PartitioningOrchestrator [dataset_id=%s, model_type=%s, dataset_path=%s, shards_dir=%s, sample_dir=%s]",
            request.dataset_id, request.model_type, request.dataset_path,
            request.shards_output_directory, request.sample_output_directory
        )

        logger.debug("Resolving partitioner adapter for model type '%s'", request.model_type)
        adapter_cls = PartitionerAdapterRegistery.Get(request.model_type)
        self.adapter: PartitionerAdapter = adapter_cls(request)
        logger.info("Resolved partitioner adapter '%s'", adapter_cls.__name__)

    def GetSample(self) -> SamplingResult:
        """
        Extract a representative dataset sample and return SamplingResult.
        """
        logger.info("Executing GetSample() for dataset '%s'", self.request.dataset_id)
        result = self.adapter.CreateSample()
        logger.info("GetSample() completed [sample_path=%s, count=%d]", result.sample_path, result.sample_count)
        return result

    # Lowercase alias
    get_sample = GetSample

    def CreateShards(self, shardSampleSize: int) -> PartitioningResult:
        """
        Partition the complete dataset into shards of target sample size.

        Args:
            shardSampleSize: Number of samples per shard.

        Returns:
            PartitioningResult detailing all generated shards.
        """
        logger.info(
            "Executing CreateShards(shardSampleSize=%s) for dataset '%s'",
            shardSampleSize, self.request.dataset_id
        )

        if not isinstance(shardSampleSize, int) or isinstance(shardSampleSize, bool) or shardSampleSize <= 0:
            raise InvalidShardSampleSizeError(
                f"shardSampleSize must be a positive integer, got: {shardSampleSize}",
                dataset_id=self.request.dataset_id,
                operation="CreateShards"
            )

        result = self.adapter.CreateShards(shardSampleSize)
        logger.info(
            "CreateShards() completed [total_shards=%d, dataset_id=%s]",
            result.shard_count, result.dataset_id
        )
        return result

    # Lowercase alias
    create_shards = CreateShards


# Aliases for naming conventions and compatibility
PartitioningOrchestrator = PartitioningOrchecstrator
