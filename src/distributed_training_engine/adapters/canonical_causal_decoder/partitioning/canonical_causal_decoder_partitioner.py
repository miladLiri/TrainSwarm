"""
Canonical Causal Decoder dataset partitioner adapter implementation.
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

logger = logging.getLogger("distributed_training_engine.adapters.canonical_causal_decoder.partitioner")

REQUIRED_KEYS = ("input_ids", "attention_mask", "labels")


class CanonicalCausalDecoderPartitioner(PartitionerAdapter):
    """
    Partitioner adapter for canonical causal decoder datasets (.pt).
    Validates tokenized causal LM dictionary contracts (input_ids, attention_mask, labels),
    extracts representative smoke-test samples, and slices datasets into balanced shards.
    """

    def __init__(self, request: PartitioningRequest) -> None:
        super().__init__(request)
        self.dataset_path = self.request.dataset_path
        self.shards_output_dir = self.request.shards_output_directory
        self.sample_output_dir = self.request.sample_output_directory
        self.dataset_id = self.request.dataset_id

    def _load_and_validate_dataset(self, operation: str) -> Dict[str, torch.Tensor]:
        """
        Load input PyTorch dataset file and validate the canonical causal decoder contract.
        """
        logger.debug("Checking dataset file existence: %s for operation '%s'", self.dataset_path, operation)
        if not self.dataset_path.is_file():
            raise DatasetAccessError(
                f"Input dataset file not found: '{self.dataset_path}'",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        logger.info("Loading causal decoder dataset from '%s' [dataset_id=%s]", self.dataset_path, self.dataset_id)
        try:
            raw_data = torch.load(str(self.dataset_path), map_location="cpu", weights_only=False)
        except Exception as exc:
            raise DatasetFormatError(
                f"Failed to load PyTorch dataset from '{self.dataset_path}': {exc}",
                dataset_id=self.dataset_id,
                operation=operation,
            ) from exc

        if not isinstance(raw_data, dict):
            raise DatasetFormatError(
                f"Dataset must be a dictionary of tensors with keys {REQUIRED_KEYS}, got: {type(raw_data)}",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        for req_key in REQUIRED_KEYS:
            if req_key not in raw_data:
                raise DatasetFormatError(
                    f"Dataset missing required canonical key '{req_key}'. Required keys: {REQUIRED_KEYS}",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )
            tensor = raw_data[req_key]
            if not isinstance(tensor, torch.Tensor):
                raise DatasetFormatError(
                    f"Dataset key '{req_key}' must be a torch.Tensor, got {type(tensor)}",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )
            if tensor.ndim != 2:
                raise DatasetFormatError(
                    f"Dataset tensor '{req_key}' must have 2 dimensions (batch, seq_len), got shape {tensor.shape}",
                    dataset_id=self.dataset_id,
                    operation=operation,
                )

        input_ids = raw_data["input_ids"]
        attention_mask = raw_data["attention_mask"]
        labels = raw_data["labels"]

        sample_count = input_ids.shape[0]
        if sample_count == 0:
            raise DatasetFormatError(
                "Dataset contains 0 samples; cannot partition or extract sample from an empty dataset.",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        if attention_mask.shape[0] != sample_count or labels.shape[0] != sample_count:
            raise DatasetFormatError(
                f"Mismatched sample count along dimension 0: input_ids={sample_count}, "
                f"attention_mask={attention_mask.shape[0]}, labels={labels.shape[0]}",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        seq_len = input_ids.shape[1]
        if attention_mask.shape[1] != seq_len or labels.shape[1] != seq_len:
            raise DatasetFormatError(
                f"Mismatched sequence length along dimension 1: input_ids={seq_len}, "
                f"attention_mask={attention_mask.shape[1]}, labels={labels.shape[1]}",
                dataset_id=self.dataset_id,
                operation=operation,
            )

        logger.debug(
            "Causal decoder dataset validated successfully [dataset_id=%s, total_samples=%d, seq_len=%d]",
            self.dataset_id, sample_count, seq_len
        )
        return raw_data

    def CreateSample(self) -> SamplingResult:
        """
        Extract representative samples (first 1-2 samples) and persist as <dataset_id>_sample.pt.
        """
        logger.info("Executing CreateSample() for causal decoder dataset '%s'", self.dataset_id)
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

        total_samples = raw_data["input_ids"].shape[0]
        sample_size = min(2, total_samples)

        sample_dict = {
            k: v[0:sample_size].detach().clone()
            for k, v in raw_data.items()
        }

        logger.info(
            "Saving representative causal decoder sample to '%s' [dataset_id=%s, sample_count=%d]",
            sample_path, self.dataset_id, sample_size
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
            sampleCount=sample_size,
        )

    def CreateShards(self, shardSampleSize: int) -> PartitioningResult:
        """
        Partition the complete causal decoder dataset into shards of target sample size.
        """
        if not isinstance(shardSampleSize, int) or isinstance(shardSampleSize, bool) or shardSampleSize <= 0:
            raise InvalidShardSampleSizeError(
                f"shardSampleSize must be a positive integer, got: {shardSampleSize}",
                dataset_id=self.dataset_id,
                operation="CreateShards",
            )

        logger.info(
            "Executing CreateShards(shardSampleSize=%d) for causal decoder dataset '%s'",
            shardSampleSize, self.dataset_id
        )

        # Output directory collision check
        if self.shards_output_dir.exists():
            try:
                contents = list(self.shards_output_dir.iterdir())
                if contents:
                    raise ExistingShardConflictError(
                        f"shardsOutputDirectory '{self.shards_output_dir}' is not empty. "
                        f"Found {len(contents)} existing file(s) or folder(s).",
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

        raw_data = self._load_and_validate_dataset(operation="CreateShards")
        total_samples = raw_data["input_ids"].shape[0]

        shards: List[PartitionedShard] = []
        start_idx = 0
        shard_seq = 0

        while start_idx < total_samples:
            end_idx = min(start_idx + shardSampleSize, total_samples)
            current_count = end_idx - start_idx
            shard_id = f"shard_{shard_seq}"
            shard_filename = f"{self.dataset_id}_{shard_id}.pt"
            shard_path = self.shards_output_dir / shard_filename

            shard_dict = {
                k: v[start_idx:end_idx].detach().clone()
                for k, v in raw_data.items()
            }

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
                    sampleCount=current_count,
                    artifactPath=str(shard_path),
                )
            )

            start_idx = end_idx
            shard_seq += 1

        logger.info(
            "Causal decoder partitioning complete [dataset_id=%s, total_samples=%d, shards_count=%d]",
            self.dataset_id, total_samples, len(shards)
        )

        return PartitioningResult(
            datasetId=self.dataset_id,
            shardCount=len(shards),
            shards=shards,
        )


__all__ = ["CanonicalCausalDecoderPartitioner"]
