"""
Canonical Causal Decoder aggregator implementation for weighted Federated Averaging.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import torch
from safetensors.torch import load_file

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    AutoModelForCausalLM = None
    AutoTokenizer = None

from ....aggregation.aggregator_adapter import AggregatorAdapter
from ....aggregation.aggregation_request import AggregationRequest, ModelUpdate
from ....aggregation.aggregation_result import AggregationResult
from ....aggregation.exceptions import (
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

logger = logging.getLogger("distributed_training_engine.adapters.canonical_causal_decoder.aggregator")


class CanonicalCausalDecoderAggregator(AggregatorAdapter):
    """
    Concrete aggregator adapter for Hugging Face causal language model transformer decoders.
    Validates SafeTensors parameter deltas, computes architecture-agnostic sample-weighted
    Federated Averaging, and atomically serializes new .gz model version archives.
    """

    def __init__(self, request: AggregationRequest) -> None:
        super().__init__(request)
        self.loaded_deltas: List[Tuple[ModelUpdate, Dict[str, torch.Tensor]]] = []
        self.base_state_dict: Optional[Dict[str, torch.Tensor]] = None
        self.base_unpacked_dir: Optional[Path] = None
        self.aggregated_delta: Optional[Dict[str, torch.Tensor]] = None

        self._is_deltas_loaded = False
        self._is_deltas_validated = False
        self._is_aggregated = False

    def LoadDelta(self) -> None:
        """
        Open and load all delta artifacts specified in request.updates using SafeTensors.
        """
        logger.info(
            "Loading %d delta artifacts for causal decoder model '%s' (base v%s)...",
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
                raise DeltaFormatError(
                    f"Failed to load SafeTensors delta artifact '{delta_path}': {exc}",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="LoadDelta",
                ) from exc

            if not isinstance(delta_dict, dict) or len(delta_dict) == 0:
                raise DeltaFormatError(
                    f"Delta artifact '{delta_path}' contains no tensors or is not a dictionary.",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    artifact_path=str(delta_path),
                    operation="LoadDelta",
                )

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
        and ensure the target output version archive does not already exist.
        """
        if not self._is_deltas_loaded:
            self.LoadDelta()

        # 1. Target Version Collision Check (.gz)
        target_file = self.request.new_version_output_directory / f"{self.request.model_id}_{self.request.new_version}.gz"
        if target_file.exists():
            raise ExistingModelVersionConflictError(
                f"Target model version file already exists: '{target_file}'. Overwriting published versions is prohibited.",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="ValidateDelta",
            )

        # 2. Check update samples validity
        for update, _ in self.loaded_deltas:
            if update.samples_trained <= 0:
                raise InvalidUpdateError(
                    f"Invalid samples_trained ({update.samples_trained}) for update '{update.shard_id}'. Must be > 0.",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    operation="ValidateDelta",
                )

        # 3. Verify base model archive existence
        base_path = self.request.base_model_path
        if not base_path.is_file():
            raise BaseModelAccessError(
                f"Base model archive file not found: '{base_path}'",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            )

        # 4. Unpack base model to temporary directory to read parameters
        temp_unpack_dir = Path(tempfile.mkdtemp(prefix="agg_base_unpacked_"))
        self.base_unpacked_dir = temp_unpack_dir

        try:
            with tarfile.open(str(base_path), "r:*") as tar:
                tar.extractall(path=str(temp_unpack_dir))
        except Exception as exc:
            shutil.rmtree(temp_unpack_dir, ignore_errors=True)
            raise BaseModelLoadError(
                f"Failed to unpack base model archive '{base_path}': {exc}",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            ) from exc

        model_dir = temp_unpack_dir / "model"
        tokenizer_dir = temp_unpack_dir / "tokenizer"
        if not model_dir.is_dir():
            nested_models = list(temp_unpack_dir.glob("**/model"))
            if nested_models and nested_models[0].is_dir():
                model_dir = nested_models[0]
        if not tokenizer_dir.is_dir():
            nested_tokenizers = list(temp_unpack_dir.glob("**/tokenizer"))
            if nested_tokenizers and nested_tokenizers[0].is_dir():
                tokenizer_dir = nested_tokenizers[0]

        if not model_dir.is_dir():
            shutil.rmtree(temp_unpack_dir, ignore_errors=True)
            raise BaseModelLoadError(
                f"Base model archive does not contain 'model/' directory.",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            )

        # Load base model state dict
        try:
            if AutoModelForCausalLM is not None:
                base_model = AutoModelForCausalLM.from_pretrained(str(model_dir))
                self.base_state_dict = {
                    name: tensor.detach().cpu().clone()
                    for name, tensor in base_model.state_dict().items()
                }
            else:
                # Fallback: load directly from safetensors or bin files
                safetensors_file = model_dir / "model.safetensors"
                if safetensors_file.is_file():
                    self.base_state_dict = load_file(str(safetensors_file), device="cpu")
                else:
                    bin_file = model_dir / "pytorch_model.bin"
                    if bin_file.is_file():
                        self.base_state_dict = torch.load(str(bin_file), map_location="cpu", weights_only=True)
                    else:
                        raise BaseModelLoadError(
                            "No model.safetensors or pytorch_model.bin found in base model directory.",
                            model_id=self.request.model_id,
                            base_version=self.request.base_model_version,
                            artifact_path=str(model_dir),
                        )
        except Exception as exc:
            shutil.rmtree(temp_unpack_dir, ignore_errors=True)
            raise BaseModelLoadError(
                f"Failed to load base model weights from '{model_dir}': {exc}",
                model_id=self.request.model_id,
                base_version=self.request.base_model_version,
                artifact_path=str(base_path),
                operation="ValidateDelta",
            ) from exc

        # 5. Validate tensor schemas across all deltas
        base_param_names = set(self.base_state_dict.keys())
        first_delta_keys = set(self.loaded_deltas[0][1].keys())

        # Check all deltas share identical key schema
        for idx, (update, delta_dict) in enumerate(self.loaded_deltas):
            delta_keys = set(delta_dict.keys())
            if delta_keys != first_delta_keys:
                missing = first_delta_keys - delta_keys
                unexpected = delta_keys - first_delta_keys
                raise TensorCompatibilityError(
                    f"Delta {idx} ('{update.shard_id}') has inconsistent keys compared to delta 0. "
                    f"Missing: {missing}, Unexpected: {unexpected}",
                    model_id=self.request.model_id,
                    base_version=self.request.base_model_version,
                    operation="ValidateDelta",
                )

            # Check delta keys exist in base model and shapes match
            for name, delta_tensor in delta_dict.items():
                if name not in base_param_names:
                    raise TensorCompatibilityError(
                        f"Delta contains parameter '{name}' which does not exist in base model.",
                        model_id=self.request.model_id,
                        base_version=self.request.base_model_version,
                        operation="ValidateDelta",
                    )
                base_tensor = self.base_state_dict[name]
                if delta_tensor.shape != base_tensor.shape:
                    raise TensorCompatibilityError(
                        f"Shape mismatch for parameter '{name}': delta {delta_tensor.shape} vs base {base_tensor.shape}",
                        model_id=self.request.model_id,
                        base_version=self.request.base_model_version,
                        operation="ValidateDelta",
                    )

        self._is_deltas_validated = True
        logger.info("All %d deltas successfully validated against base model schema.", len(self.loaded_deltas))

    # Lowercase alias
    validate_delta = ValidateDelta

    def Aggregate(self) -> None:
        """
        Compute sample-weighted Federated Averaging across all valid loaded deltas:
        delta_avg = sum( (n_i / N) * delta_i )
        """
        if not self._is_deltas_validated:
            self.ValidateDelta()

        total_samples = sum(u.samples_trained for u, _ in self.loaded_deltas)
        if total_samples <= 0:
            raise AggregationOperationError(
                f"Total samples trained across all updates must be > 0, got {total_samples}",
                model_id=self.request.model_id,
                operation="Aggregate",
            )

        logger.info(
            "Computing Federated Averaging across %d deltas (total_samples=%d)...",
            len(self.loaded_deltas), total_samples
        )

        try:
            # Initialize accumulator with zeros matching the first delta's tensors
            first_delta = self.loaded_deltas[0][1]
            aggregated: Dict[str, torch.Tensor] = {
                name: torch.zeros_like(tensor, dtype=torch.float32)
                for name, tensor in first_delta.items()
            }

            for update, delta_dict in self.loaded_deltas:
                weight = float(update.samples_trained) / float(total_samples)
                for name, delta_tensor in delta_dict.items():
                    aggregated[name].add_(delta_tensor.to(torch.float32), alpha=weight)

            # Convert back to original parameter dtypes
            self.aggregated_delta = {
                name: tensor.to(first_delta[name].dtype).contiguous()
                for name, tensor in aggregated.items()
            }

            self._is_aggregated = True
            logger.info("Sample-weighted Federated Averaging computed successfully.")
        except Exception as exc:
            raise AggregationOperationError(
                f"Failed to compute sample-weighted Federated Averaging: {exc}",
                model_id=self.request.model_id,
                operation="Aggregate",
            ) from exc

    # Lowercase alias
    aggregate = Aggregate

    def CreateNewVersion(self) -> AggregationResult:
        """
        Apply the aggregated delta to base model weights, preserve tokenizer unchanged,
        and atomically serialize into a new .gz model archive.
        """
        if not self._is_aggregated:
            self.Aggregate()

        target_file = self.request.new_version_output_directory / f"{self.request.model_id}_{self.request.new_version}.gz"
        self.request.new_version_output_directory.mkdir(parents=True, exist_ok=True)

        if target_file.exists():
            raise ExistingModelVersionConflictError(
                f"Target model version file already exists: '{target_file}'",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="CreateNewVersion",
            )

        logger.info(
            "Applying aggregated deltas to base model weights (W_new = W_base + delta_avg)..."
        )

        # 1. Calculate updated weights
        new_state_dict: Dict[str, torch.Tensor] = {}
        for name, base_tensor in self.base_state_dict.items():
            if name in self.aggregated_delta:
                delta_tensor = self.aggregated_delta[name]
                new_state_dict[name] = (base_tensor + delta_tensor).contiguous()
            else:
                new_state_dict[name] = base_tensor.contiguous()

        # 2. Prepare temporary directory structure for publishing
        temp_publish_dir = Path(tempfile.mkdtemp(prefix="agg_publish_"))
        temp_model_dir = temp_publish_dir / "model"
        temp_tokenizer_dir = temp_publish_dir / "tokenizer"
        temp_model_dir.mkdir(parents=True, exist_ok=True)
        temp_tokenizer_dir.mkdir(parents=True, exist_ok=True)

        temp_archive = self.request.new_version_output_directory / f"{self.request.model_id}_{self.request.new_version}_{uuid4().hex}.tmp.gz"

        try:
            # Locate base model and tokenizer paths in unpacked dir
            base_model_dir = self.base_unpacked_dir / "model"
            base_tokenizer_dir = self.base_unpacked_dir / "tokenizer"
            if not base_model_dir.is_dir():
                nested = list(self.base_unpacked_dir.glob("**/model"))
                if nested:
                    base_model_dir = nested[0]
            if not base_tokenizer_dir.is_dir():
                nested_tok = list(self.base_unpacked_dir.glob("**/tokenizer"))
                if nested_tok:
                    base_tokenizer_dir = nested_tok[0]

            # Save updated model
            if AutoModelForCausalLM is not None:
                model = AutoModelForCausalLM.from_pretrained(str(base_model_dir))
                model.load_state_dict(new_state_dict)
                model.save_pretrained(str(temp_model_dir))
            else:
                # Direct SafeTensors export
                save_file(new_state_dict, str(temp_model_dir / "model.safetensors"))
                # Copy config files
                for item in base_model_dir.iterdir():
                    if item.is_file() and not (item.name.endswith(".safetensors") or item.name.endswith(".bin")):
                        shutil.copy2(str(item), str(temp_model_dir / item.name))

            # Copy tokenizer directory unchanged
            if base_tokenizer_dir.is_dir():
                for item in base_tokenizer_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(str(item), str(temp_tokenizer_dir / item.name))
                    elif item.is_dir():
                        shutil.copytree(str(item), str(temp_tokenizer_dir / item.name))

            # Package into temporary .tar.gz archive
            logger.info("Packaging new model version archive into: %s", temp_archive)
            with tarfile.open(str(temp_archive), "w:gz") as tar:
                tar.add(str(temp_model_dir), arcname="model")
                tar.add(str(temp_tokenizer_dir), arcname="tokenizer")

            # Atomic rename to destination
            logger.info("Atomically renaming temporary archive to final destination: %s", target_file)
            os.replace(str(temp_archive), str(target_file))

        except Exception as exc:
            if temp_archive.exists():
                try:
                    temp_archive.unlink()
                except Exception:
                    pass
            raise ModelSerializationError(
                f"Failed to publish new model version to '{target_file}': {exc}",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="CreateNewVersion",
            ) from exc
        finally:
            # Clean up temporary folders
            shutil.rmtree(temp_publish_dir, ignore_errors=True)
            if self.base_unpacked_dir and self.base_unpacked_dir.exists():
                shutil.rmtree(self.base_unpacked_dir, ignore_errors=True)

        if not target_file.is_file() or target_file.stat().st_size == 0:
            raise ModelSerializationError(
                f"Published model archive not found or empty at '{target_file}'",
                model_id=self.request.model_id,
                new_version=self.request.new_version,
                artifact_path=str(target_file),
                operation="CreateNewVersion",
            )

        logger.info(
            "Successfully published model version '%s' to '%s' (size=%d bytes).",
            self.request.new_version, target_file, target_file.stat().st_size
        )

        return AggregationResult(
            modelId=self.request.model_id,
            baseModelVersion=int(self.request.base_model_version),
            newModelVersion=int(self.request.new_version),
            updatesCount=len(self.loaded_deltas),
            modelPath=str(target_file.resolve()),
        )

    # Lowercase alias
    create_new_version = CreateNewVersion


__all__ = ["CanonicalCausalDecoderAggregator"]
