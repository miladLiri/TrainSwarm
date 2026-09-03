"""
Canonical PyTorch aggregator implementation for weighted Federated Averaging.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import torch
import torch.nn as nn
from safetensors.torch import load_file

from distributed_training_engine.aggregation.aggregator_adapter import AggregatorAdapter
from distributed_training_engine.aggregation.aggregation_request import (
    AggregationRequest,
    ModelUpdate,
)
from distributed_training_engine.aggregation.aggregation_result import AggregationResult
from distributed_training_engine.aggregation.exceptions import (
    AggregationOperationError,
    BaseModelAccessError,
    BaseModelLoadError,
    DeltaAccessError,
    DeltaFormatError,
    ExistingModelVersionConflictError,
    InvalidAggregationRequestError,
    InvalidUpdateError,
    ModelSerializationError,
    TensorCompatibilityError,
)

logger = logging.getLogger("distributed_training_engine.adapters.canonical_torch.aggregator")


class CanonicalTorchAggregator(AggregatorAdapter):
    """
    Concrete aggregator adapter for PyTorch 2 ExportedProgram models (.pt2)
    and SafeTensors parameter delta artifacts.
    """

    def __init__(self, request: AggregationRequest) -> None:
        super().__init__(request)
        self.loaded_deltas: List[Tuple[ModelUpdate, Dict[str, torch.Tensor]]] = []
        self.base_exported_program: Optional[torch.export.ExportedProgram] = None
        self.base_state_dict: Optional[Dict[str, torch.Tensor]] = None
        self.aggregated_delta: Optional[Dict[str, torch.Tensor]] = None

        self._is_deltas_loaded = False
        self._is_deltas_validated = False
        self._is_aggregated = False

    def LoadDelta(self) -> None:
        """
        Open and load all delta artifacts specified in request.updates using SafeTensors.
        """
        logger.info(
            "Loading %d delta artifacts for model '%s' (base v%d)...",
            len(self.request.updates),
            self.request.model_id,
            self.request.base_model_version,
        )

        loaded: List[Tuple[ModelUpdate, Dict[str, torch.Tensor]]] = []
        for idx, update in enumerate(self.request.updates):
            delta_path = update.delta_path
            logger.debug(
                "Loading delta %d/%d from: %s (samplesTrained=%d)",
                idx + 1,
                len(self.request.updates),
                delta_path,
                update.samples_trained,
            )

            if not delta_path.is_file():
                logger.error("Delta artifact not found on disk: %s", delta_path)
                raise DeltaAccessError(
                    f"Delta artifact file not found: '{delta_path}'",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="LoadDelta",
                )

            try:
                delta_dict = load_file(str(delta_path), device="cpu")
            except Exception as exc:
                logger.error("Failed to deserialize SafeTensors delta '%s': %s", delta_path, exc, exc_info=True)
                raise DeltaFormatError(
                    f"Failed to load SafeTensors delta artifact '{delta_path}': {exc}",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="LoadDelta",
                ) from exc

            if not isinstance(delta_dict, dict) or len(delta_dict) == 0:
                logger.error("Delta artifact '%s' is empty or not a valid dictionary.", delta_path)
                raise DeltaFormatError(
                    f"Delta artifact '{delta_path}' contains no tensors or is not a dictionary.",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="LoadDelta",
                )

            # Ensure all tensors are detached cpu tensors
            cpu_delta = {
                k: v.detach().cpu().contiguous()
                for k, v in delta_dict.items()
            }
            loaded.append((update, cpu_delta))

        self.loaded_deltas = loaded
        self._is_deltas_loaded = True
        logger.info("Successfully loaded all %d delta artifacts into memory.", len(self.loaded_deltas))

    # Lowercase alias
    load_delta = LoadDelta

    def ValidateDelta(self) -> None:
        """
        Validate all loaded deltas against the base model schema, check samplesTrained,
        and ensure the target output model file does not already exist.
        """
        if not self._is_deltas_loaded:
            self.LoadDelta()

        target_file = self.request.new_version_output_directory / f"{self.request.model_id}_{self.request.new_version}.pt2"
        logger.debug("Checking target version file collision at: %s", target_file)

        # 1. Existing Model Version Collision Check (Immutability Protection)
        if target_file.exists():
            logger.error("Target model version file already exists: %s", target_file)
            raise ExistingModelVersionConflictError(
                f"Target model version file already exists: '{target_file}'. Overwriting published versions is prohibited.",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="ValidateDelta",
            )

        # 2. Output directory preparation
        try:
            self.request.new_version_output_directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("Failed to create output directory '%s': %s", self.request.new_version_output_directory, exc)
            raise BaseModelAccessError(
                f"Failed to prepare target output directory '{self.request.new_version_output_directory}': {exc}",
                model_id=self.request.model_id,
                artifact_path=str(self.request.new_version_output_directory),
                operation="ValidateDelta",
            ) from exc

        # 3. Load immutable base model
        base_path = self.request.base_model_path
        logger.info("Loading baseline PyTorch exported program from: %s", base_path)
        if not base_path.is_file():
            logger.error("Base model file not found: %s", base_path)
            raise BaseModelAccessError(
                f"Base model artifact not found: '{base_path}'",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            )

        try:
            exported_program = torch.export.load(str(base_path))
        except Exception as exc:
            logger.error("Failed to load PyTorch ExportedProgram from '%s': %s", base_path, exc, exc_info=True)
            raise BaseModelLoadError(
                f"Failed to load base model ExportedProgram from '{base_path}': {exc}",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            ) from exc

        try:
            module = exported_program.module()
        except Exception as exc:
            raise BaseModelLoadError(
                f"Failed to extract module from exported program: {exc}",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                operation="ValidateDelta",
            ) from exc

        if not isinstance(module, nn.Module):
            raise BaseModelLoadError(
                f"Base model module is not a torch.nn.Module (got {type(module)})",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                operation="ValidateDelta",
            )

        # Snapshot base state dict
        self.base_exported_program = exported_program
        self.base_state_dict = {
            k: v.detach().cpu().clone().contiguous()
            for k, v in module.state_dict().items()
        }
        logger.info("Base model loaded with %d parameter/buffer tensors.", len(self.base_state_dict))

        # 4. Validate each delta against base state dict
        base_keys = set(self.base_state_dict.keys())
        for idx, (update, delta_dict) in enumerate(self.loaded_deltas):
            delta_path = update.delta_path

            # Validate samplesTrained > 0
            if update.samples_trained <= 0:
                raise InvalidUpdateError(
                    f"Update at index {idx} has invalid samplesTrained={update.samples_trained} (must be > 0).",
                    artifact_path=str(delta_path),
                    operation="ValidateDelta",
                )

            delta_keys = set(delta_dict.keys())
            if delta_keys != base_keys:
                missing = base_keys - delta_keys
                unexpected = delta_keys - base_keys
                error_msg = f"Tensor keys mismatch in delta '{delta_path}'. Missing: {sorted(missing)}, Unexpected: {sorted(unexpected)}"
                logger.error(error_msg)
                raise TensorCompatibilityError(
                    error_msg,
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="ValidateDelta",
                )

            # Validate tensor shapes and dtypes
            for name, delta_tensor in delta_dict.items():
                base_tensor = self.base_state_dict[name]

                if delta_tensor.shape != base_tensor.shape:
                    error_msg = (
                        f"Shape mismatch for tensor '{name}' in delta '{delta_path}': "
                        f"expected {base_tensor.shape}, got {delta_tensor.shape}"
                    )
                    logger.error(error_msg)
                    raise TensorCompatibilityError(
                        error_msg,
                        model_id=self.request.model_id,
                        base_version=self.request.base_model_version,
                        artifact_path=str(delta_path),
                        operation="ValidateDelta",
                    )

                if delta_tensor.dtype != base_tensor.dtype:
                    error_msg = (
                        f"Dtype mismatch for tensor '{name}' in delta '{delta_path}': "
                        f"expected {base_tensor.dtype}, got {delta_tensor.dtype}"
                    )
                    logger.error(error_msg)
                    raise TensorCompatibilityError(
                        error_msg,
                        model_id=self.request.model_id,
                        base_version=self.request.base_model_version,
                        artifact_path=str(delta_path),
                        operation="ValidateDelta",
                    )

        self._is_deltas_validated = True
        logger.info("All %d deltas successfully passed schema and shape compatibility validation.", len(self.loaded_deltas))

    # Lowercase alias
    validate_delta = ValidateDelta

    def Aggregate(self) -> None:
        """
        Perform sample-weighted Federated Averaging across all loaded deltas.
        Accumulates in float64 precision and rounds integer buffers to native integer dtype.
        """
        if not self._is_deltas_validated:
            self.ValidateDelta()

        if self.base_state_dict is None:
            raise AggregationOperationError("Base state dict is missing. ValidateDelta must succeed before Aggregate.")

        total_samples = sum(update.samples_trained for update, _ in self.loaded_deltas)
        if total_samples <= 0:
            raise AggregationOperationError(
                f"Total samples trained across updates is non-positive ({total_samples}).",
                model_id=self.request.model_id,
                operation="Aggregate",
            )

        logger.info(
            "Computing weighted Federated Averaging over %d updates (total_samples=%d)...",
            len(self.loaded_deltas),
            total_samples,
        )

        aggregated_delta: Dict[str, torch.Tensor] = {}

        try:
            for name, base_tensor in self.base_state_dict.items():
                is_float = base_tensor.is_floating_point()

                # Accumulate in float64 for numerical precision
                accumulator = torch.zeros(base_tensor.shape, dtype=torch.float64, device="cpu")

                for update, delta_dict in self.loaded_deltas:
                    weight = float(update.samples_trained)
                    delta_tensor = delta_dict[name]
                    accumulator.add_(delta_tensor.to(dtype=torch.float64, device="cpu"), alpha=weight)

                # Divide by total weight
                average = accumulator / float(total_samples)

                if is_float:
                    aggregated_delta[name] = average.to(dtype=base_tensor.dtype).contiguous()
                else:
                    # Non-floating point buffers (e.g. integer step counters): round and cast back
                    rounded = torch.round(average)
                    aggregated_delta[name] = rounded.to(dtype=base_tensor.dtype).contiguous()

                logger.debug(
                    "Aggregated tensor '%s' [shape=%s, dtype=%s, is_float=%s]",
                    name,
                    base_tensor.shape,
                    base_tensor.dtype,
                    is_float,
                )

        except Exception as exc:
            logger.error("Error occurred during Federated Averaging: %s", exc, exc_info=True)
            raise AggregationOperationError(
                f"Federated Averaging computation failed: {exc}",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                operation="Aggregate",
            ) from exc

        self.aggregated_delta = aggregated_delta
        self._is_aggregated = True
        logger.info("Weighted Federated Averaging completed successfully for all %d tensors.", len(aggregated_delta))

    # Lowercase alias
    aggregate = Aggregate

    def CreateNewVersion(self) -> AggregationResult:
        """
        Reconstruct new model weights from base model + aggregated delta,
        atomically serialize the new model version, and return AggregationResult.
        """
        if not self._is_aggregated or self.aggregated_delta is None:
            self.Aggregate()

        if self.base_exported_program is None or self.base_state_dict is None or self.aggregated_delta is None:
            raise ModelSerializationError("Internal state invalid for CreateNewVersion: missing base program or deltas.")

        target_file = self.request.new_version_output_directory / f"{self.request.model_id}_{self.request.new_version}.pt2"
        if target_file.exists():
            raise ExistingModelVersionConflictError(
                f"Target model version file already exists: '{target_file}'",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="CreateNewVersion",
            )

        logger.info(
            "Reconstructing new model version %d weights (newState = baseState + aggregatedDelta)...",
            self.request.new_version,
        )

        # 1. Reconstruct state dict
        new_state_dict: Dict[str, torch.Tensor] = {}
        for name, base_tensor in self.base_state_dict.items():
            delta_tensor = self.aggregated_delta[name]
            new_state_dict[name] = (base_tensor + delta_tensor).contiguous()

        # 2. Update exported program module
        try:
            module = self.base_exported_program.module()
            module.load_state_dict(new_state_dict, strict=True)
        except Exception as exc:
            logger.error("Failed to load reconstructed state dict into exported program module: %s", exc, exc_info=True)
            raise ModelSerializationError(
                f"Failed to apply reconstructed weights to base module: {exc}",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                operation="CreateNewVersion",
            ) from exc

        # 3. Atomic file serialization
        temp_filename = f"{self.request.model_id}_{self.request.new_version}_{uuid4().hex}.tmp.pt2"
        temp_path = self.request.new_version_output_directory / temp_filename

        logger.info("Writing new model version to temporary file: %s", temp_path)
        try:
            torch.export.save(self.base_exported_program, str(temp_path))

            if not temp_path.is_file() or temp_path.stat().st_size == 0:
                raise ModelSerializationError(
                    f"Temporary model file '{temp_path}' is missing or empty after serialization.",
                    model_id=self.request.model_id,
                    new_version=self.request.new_version,
                    artifact_path=str(temp_path),
                )

            logger.info("Atomically renaming temporary model '%s' to final destination: '%s'", temp_path.name, target_file.name)
            os.replace(str(temp_path), str(target_file))

        except Exception as exc:
            logger.error("Failed during model serialization or atomic rename: %s", exc, exc_info=True)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug("Cleaned up temporary file: %s", temp_path)
                except Exception:
                    pass
            raise ModelSerializationError(
                f"Failed to atomically persist new model version to '{target_file}': {exc}",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="CreateNewVersion",
            ) from exc

        if not target_file.is_file() or target_file.stat().st_size == 0:
            raise ModelSerializationError(
                f"Published model file not found or empty at '{target_file}'",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
            )

        resolved_path = str(target_file.resolve())
        logger.info(
            "New model version published successfully: %s (size: %d bytes)",
            resolved_path,
            target_file.stat().st_size,
        )

        return AggregationResult(
            modelId=self.request.model_id,
            baseModelVersion=self.request.base_model_version,
            newModelVersion=self.request.new_version,
            updatesCount=len(self.loaded_deltas),
            modelPath=resolved_path,
        )

    # Lowercase alias
    create_new_version = CreateNewVersion
