"""
Canonical PyTorch dataset partitioner adapter implementation.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import torch

from ....partitioning.partitioner_adapter import PartitionerAdapter
from ....partitioning.partitioning_request import PartitioningRequest
from ....partitioning.partitioning_result import PartitionedShard, PartitioningResult
from ....partitioning.sampling_result import SamplingResult
from ....partitioning.exceptions import (
    DatasetAccessError,
    DatasetFormatError,
    ExistingShardConflictError,
    InvalidShardSampleSizeError,
    OutputDirectoryError,
    ShardSerializationError,
)

logger = logging.getLogger("distributed_training_engine.canonical_torch_partitioner")


class CanonicalTorchPartitioner(PartitionerAdapter):
    """
    Partitioner adapter for canonical PyTorch datasets (.pt).
    Handles extracting representative samples and slicing datasets into fixed-size shards.
    """

    def __init__(self, request: PartitioningRequest) -> None:
        super().__init__(request)
        self.dataset_path = self.request.dataset_path
        self.shards_output_dir = self.request.shards_output_directory
        self.sample_output_dir = self.request.sample_output_directory
        self.dataset_id = self.request.dataset_id

    def _load_and_validate_dataset(self, operation: str) -> Dict[str, torch.Tensor]:
        """
        Load input PyTorch dataset file and validate tensor dictionary contracts.
        """
        logger.debug("Checking dataset file existence: %s for operation '%s'", self.dataset_path, operation)
        if not self.dataset_path.is_file():
            raise DatasetAccessError(
                f"Input dataset file not found: '{self.dataset_path}'",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        logger.info("Loading PyTorch dataset from '%s' [dataset_id=%s]", self.dataset_path, self.dataset_id)
        try:
            raw_data = torch.load(str(self.dataset_path), weights_only=True)
        except Exception as exc:
            raise DatasetFormatError(
                f"Failed to load PyTorch dataset from '{self.dataset_path}': {exc}",
                dataset_id=self.dataset_id,
                operation=operation,
            ) from exc

        if not isinstance(raw_data, dict):
            raise DatasetFormatError(
                f"Dataset must be a dictionary of tensors, got: {type(raw_data)}",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        if not raw_data:
            raise DatasetFormatError(
                "Dataset dictionary is empty (contains no tensor keys).",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        # Validate that all values are torch.Tensor and have matching sample count along dimension 0
        sample_count: Optional[int] = None
        for key, value in raw_data.items():
            if not isinstance(value, torch.Tensor):
                raise DatasetFormatError(
                    f"Dataset key '{key}' contains invalid non-tensor object of type {type(value)}",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )
            if value.ndim == 0:
                raise DatasetFormatError(
                    f"Dataset tensor '{key}' is a 0-dimensional scalar (expected batch dimension).",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )
            num_samples = value.shape[0]
            if sample_count is None:
                sample_count = num_samples
            elif num_samples != sample_count:
                raise DatasetFormatError(
                    f"Sample count mismatch: key '{key}' has {num_samples} samples, but previous keys had {sample_count}",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )

        if sample_count is None or sample_count == 0:
            raise DatasetFormatError(
                "Dataset contains 0 samples; cannot partition or extract sample from an empty dataset.",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        logger.debug(
            "Dataset validated successfully [dataset_id=%s, total_samples=%d, keys=%s]",
            self.dataset_id, sample_count, list(raw_data.keys())
        )
        return raw_data

    def CreateSample(self) -> SamplingResult:
        """
        Extract the first sample from the dataset and persist it as <dataset_id>_sample.pt.
        Atomically replaces any pre-existing sample artifact.
        """
        logger.info("Executing CreateSample() for dataset '%s'", self.dataset_id)
        raw_data = self._load_and_validate_dataset(operation="CreateSample")

        try:
            self.sample_output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise OutputDirectoryError(
                f"Failed to create sample output directory '{self.sample_output_dir}': {exc}",
                dataset_id=self.dataset_id,
                operation="CreateSample",
            ) from exc

        sample_filename = f"{self.dataset_id}_sample.pt"
        sample_path = self.sample_output_dir / sample_filename

        # Slice index 0:1 to retain batch dimension 1
        sample_dict = {
            k: v[0:1].detach().clone() if isinstance(v, torch.Tensor) else v
            for k, v in raw_data.items()
        }

        logger.info(
            "Saving representative sample to '%s' [dataset_id=%s, sample_count=1]",
            sample_path, self.dataset_id
        )

        try:
            torch.save(sample_dict, str(sample_path))
        except Exception as exc:
            raise ShardSerializationError(
                f"Failed to serialize representative sample to '{sample_path}': {exc}",
                dataset_id=self.dataset_id,
                operation="CreateSample",
            ) from exc

        return SamplingResult(
            datasetId=self.dataset_id,
            samplePath=str(sample_path),
            sampleCount=1,
        )

    def CreateShards(self, shardSampleSize: int) -> PartitioningResult:
        """
        Partition the complete dataset into shards of target sample size.
        Enforces strict empty-directory collision prevention.
        """
        if not isinstance(shardSampleSize, int) or isinstance(shardSampleSize, bool) or shardSampleSize <= 0:
            raise InvalidShardSampleSizeError(
                f"shardSampleSize must be a positive integer, got: {shardSampleSize}",
                dataset_id=self.dataset_id,
                operation="CreateShards",
            )

        logger.info(
            "Executing CreateShards(shardSampleSize=%d) for dataset '%s'",
            shardSampleSize, self.dataset_id
        )

        # 1. Output directory collision check
        if self.shards_output_dir.exists():
            try:
                contents = list(self.shards_output_dir.iterdir())
                if contents:
                    raise ExistingShardConflictError(
                        f"shardsOutputDirectory '{self.shards_output_dir}' is not empty. "
                        f"Found {len(contents)} existing file(s) or folder(s). "
                        "Partitioning requires a clean, empty output directory to avoid artifact collisions.",
                        dataset_id=self.dataset_id,
                        operation="CreateShards",
                    )
            except ExistingShardConflictError:
                raise
            except Exception as exc:
                raise OutputDirectoryError(
                    f"Failed to inspect shardsOutputDirectory '{self.shards_output_dir}': {exc}",
                    dataset_id=self.dataset_id,
                    operation="CreateShards",
                ) from exc
        else:
            try:
                self.shards_output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                raise OutputDirectoryError(
                    f"Failed to create shardsOutputDirectory '{self.shards_output_dir}': {exc}",
                    dataset_id=self.dataset_id,
                    operation="CreateShards",
                ) from exc

        # 2. Load and validate raw dataset
        raw_data = self._load_and_validate_dataset(operation="CreateShards")
        first_tensor = next(iter(raw_data.values()))
        total_samples = first_tensor.shape[0]

        logger.info(
            "Beginning dataset partitioning [dataset_id=%s, total_samples=%d, shard_sample_size=%d]",
            self.dataset_id, total_samples, shardSampleSize
        )

        shards: List[PartitionedShard] = []
        shard_index = 0

        # 3. Deterministic chunk slicing loop
        for start in range(0, total_samples, shardSampleSize):
            end = min(start + shardSampleSize, total_samples)
            chunk_samples = end - start

            # Slice tensor views
            shard_dict = {
                k: v[start:end].detach().clone() if isinstance(v, torch.Tensor) else v
                for k, v in raw_data.items()
            }

            shard_id = str(uuid.uuid4())
            shard_filename = f"{self.dataset_id}_{shard_id}.pt"
            shard_path = self.shards_output_dir / shard_filename

            logger.debug(
                "Serializing shard %d [shard_id=%s, samples=%d, range=%d..%d, path=%s]",
                shard_index, shard_id, chunk_samples, start, end, shard_filename
            )

            try:
                torch.save(shard_dict, str(shard_path))
            except Exception as exc:
                raise ShardSerializationError(
                    f"Failed to serialize shard '{shard_filename}' to '{shard_path}': {exc}",
                    dataset_id=self.dataset_id,
                    operation="CreateShards",
                ) from exc

            shards.append(
                PartitionedShard(
                    shardId=shard_id,
                    sampleCount=chunk_samples,
                    artifactPath=str(shard_path),
                )
            )
            shard_index += 1

        logger.info(
            "Dataset partitioning successfully produced %d shards for dataset '%s'",
            len(shards), self.dataset_id
        )

        return PartitioningResult(
            datasetId=self.dataset_id,
            shardCount=len(shards),
            shards=shards,
        )
