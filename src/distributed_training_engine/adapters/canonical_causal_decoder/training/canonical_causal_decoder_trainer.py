"""
Canonical Causal Decoder Model trainer adapter implementation.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
import random
import shutil
import tarfile
from typing import Any, Dict, List, Optional
import torch
from torch.utils.data import Dataset
from safetensors.torch import save_file

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )
except ImportError:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    Trainer = None
    TrainingArguments = None

from ....training.trainer_adapter import TrainerAdapter
from ....training.training_task_model import TrainingTask
from ....training.training_result import TrainingResult, DeltaArtifactInfo
from .canonical_causal_decoder_config import CanonicalCausalDecoderTrainingConfig
from ....training.exceptions import (
    MissingArtifactError,
    InvalidArtifactError,
    DatasetContractViolationError,
    ModelContractViolationError,
    TrainingExecutionError,
    ResultSaveError,
    TensorCompatibilityError,
    InvalidTaskConfigurationError,
)

logger = logging.getLogger("distributed_training_engine.adapters.canonical_causal_decoder.trainer")


class _CausalLMDataset(Dataset):
    """Internal PyTorch Dataset wrapping canonical causal decoder dictionary tensors."""

    def __init__(self, data: Dict[str, torch.Tensor]) -> None:
        self.input_ids = data["input_ids"]
        self.attention_mask = data["attention_mask"]
        self.labels = data["labels"]
        self.length = self.input_ids.shape[0]

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "labels": self.labels[idx],
        }


class CanonicalCausalDecoderTrainer(TrainerAdapter):
    """
    Executes local fine-tuning for Hugging Face causal language model transformer decoders
    using Hugging Face Trainer and dataset shards (.pt), producing .safetensors delta artifacts.
    """

    def __init__(self, task: TrainingTask, working_directory: Path) -> None:
        super().__init__(task=task, working_directory=working_directory)
        self.config: Optional[CanonicalCausalDecoderTrainingConfig] = None
        self.model_archive_path: Optional[Path] = None
        self.dataset_path: Optional[Path] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Runtime training components
        self.unpacked_dir: Optional[Path] = None
        self.model: Optional[Any] = None
        self.tokenizer: Optional[Any] = None
        self.baseline_parameters: Optional[Dict[str, torch.Tensor]] = None
        self.hf_trainer: Optional[Any] = None
        self.dataset_sample_count: int = 0

        # Metrics tracking
        self.global_steps: int = 0
        self.epochs_completed: int = 0
        self.samples_trained: int = 0
        self.last_loss: float = 0.0
        self.loss_history: List[float] = []

    def validate(self) -> None:
        """
        Phase 1: Inspect incoming TrainingTask envelope, configuration, and artifact existence.
        Must not hold files open or start computation.
        """
        logger.debug("Validating general task envelope for task '%s'", self.task.training_task_id)
        self.task.validate_envelope()

        logger.debug("Deserializing CanonicalCausalDecoderTrainingConfig for task '%s'", self.task.training_task_id)
        self.config = CanonicalCausalDecoderTrainingConfig.from_dict(self.task.training)

        # Resolve model archive path (accept .gz or .tar.gz)
        base_name = f"{self.task.baseline_model_id}_{self.task.baseline_model_version}"
        candidates = [
            self.working_directory / f"{base_name}.gz",
            self.working_directory / f"{base_name}.tar.gz",
        ]
        self.model_archive_path = next((p for p in candidates if p.is_file()), candidates[0])

        self.dataset_path = self.working_directory / f"{self.task.data_set_id}_{self.task.data_set_shard_id}.pt"

        logger.debug("Checking model archive artifact existence: %s", self.model_archive_path)
        if not self.model_archive_path.is_file():
            raise MissingArtifactError(
                f"Model archive file not found: '{self.model_archive_path}' for task '{self.task.training_task_id}'"
            )

        logger.debug("Checking dataset shard artifact existence: %s", self.dataset_path)
        if not self.dataset_path.is_file():
            raise MissingArtifactError(
                f"Dataset shard file not found: '{self.dataset_path}' for task '{self.task.training_task_id}'"
            )

        # Inspect archive layout without extracting everything
        try:
            with tarfile.open(str(self.model_archive_path), "r:*") as tar:
                names = tar.getnames()
                has_model = any(n == "model" or n.startswith("model/") or "/model/" in n or n.endswith("/model") for n in names)
                has_tokenizer = any(n == "tokenizer" or n.startswith("tokenizer/") or "/tokenizer/" in n or n.endswith("/tokenizer") for n in names)
                if not (has_model and has_tokenizer):
                    raise InvalidArtifactError(
                        f"Model archive '{self.model_archive_path.name}' must contain 'model/' and 'tokenizer/' directories."
                    )
        except tarfile.TarError as exc:
            raise InvalidArtifactError(
                f"Failed to inspect model archive '{self.model_archive_path}': {exc}"
            ) from exc

        logger.info(
            "Validation successful for causal decoder task '%s' [model=%s, shard=%s]",
            self.task.training_task_id, self.model_archive_path.name, self.dataset_path.name
        )

    def _apply_random_seed(self) -> None:
        """Apply random seed across Python, NumPy, and PyTorch if configured."""
        if self.config and self.config.seed is not None:
            seed = self.config.seed
            random.seed(seed)
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            try:
                import numpy as np
                np.random.seed(seed)
            except ImportError:
                pass

    def prepare(self) -> None:
        """
        Phase 2: Set up in-memory state, load model/tokenizer/dataset, capture baseline snapshot,
        and initialize Hugging Face Trainer. Must NOT execute optimization steps.
        """
        if AutoModelForCausalLM is None or Trainer is None:
            raise TrainingExecutionError(
                "transformers library is required for CanonicalCausalDecoderTrainer execution."
            )

        logger.info(
            "Preparing training state for task '%s' on device '%s'...",
            self.task.training_task_id, self.device
        )
        self._apply_random_seed()

        # 1. Unpack model archive into dedicated task subfolder
        self.unpacked_dir = self.working_directory / "model_unpacked"
        if self.unpacked_dir.exists():
            shutil.rmtree(self.unpacked_dir, ignore_errors=True)
        self.unpacked_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(str(self.model_archive_path), "r:*") as tar:
                tar.extractall(path=str(self.unpacked_dir))
        except Exception as exc:
            raise InvalidArtifactError(
                f"Failed to unpack model archive '{self.model_archive_path}': {exc}"
            ) from exc

        # Locate model and tokenizer directories inside unpacked folder
        model_dir = self.unpacked_dir / "model"
        tokenizer_dir = self.unpacked_dir / "tokenizer"

        # Handle archive structures where files are nested under a root directory
        if not model_dir.is_dir():
            nested_models = list(self.unpacked_dir.glob("**/model"))
            if nested_models and nested_models[0].is_dir():
                model_dir = nested_models[0]
        if not tokenizer_dir.is_dir():
            nested_tokenizers = list(self.unpacked_dir.glob("**/tokenizer"))
            if nested_tokenizers and nested_tokenizers[0].is_dir():
                tokenizer_dir = nested_tokenizers[0]

        if not model_dir.is_dir():
            raise InvalidArtifactError(f"Unpacked archive does not contain 'model/' directory at {model_dir}")
        if not tokenizer_dir.is_dir():
            raise InvalidArtifactError(f"Unpacked archive does not contain 'tokenizer/' directory at {tokenizer_dir}")

        # 2. Load model and tokenizer
        try:
            logger.info("Loading AutoTokenizer from: %s", tokenizer_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            logger.info("Loading AutoModelForCausalLM from: %s", model_dir)
            self.model = AutoModelForCausalLM.from_pretrained(str(model_dir))
        except Exception as exc:
            raise ModelContractViolationError(
                f"Failed to load Hugging Face model or tokenizer from unpacked archive: {exc}"
            ) from exc

        # 3. Load and validate dataset shard
        try:
            shard_data = torch.load(str(self.dataset_path), map_location="cpu", weights_only=False)
        except Exception as exc:
            raise DatasetContractViolationError(
                f"Failed to load dataset shard '{self.dataset_path}': {exc}"
            ) from exc

        if not isinstance(shard_data, dict):
            raise DatasetContractViolationError(
                f"Dataset shard '{self.dataset_path}' must be a dict, got {type(shard_data)}"
            )

        for req_key in ("input_ids", "attention_mask", "labels"):
            if req_key not in shard_data:
                raise DatasetContractViolationError(
                    f"Dataset shard missing required key '{req_key}'"
                )
            if not isinstance(shard_data[req_key], torch.Tensor):
                raise DatasetContractViolationError(
                    f"Dataset shard key '{req_key}' must be a torch.Tensor, got {type(shard_data[req_key])}"
                )

        input_ids = shard_data["input_ids"]
        attention_mask = shard_data["attention_mask"]
        labels = shard_data["labels"]

        if not (input_ids.ndim == 2 and attention_mask.ndim == 2 and labels.ndim == 2):
            raise DatasetContractViolationError(
                f"All tensors in dataset shard must be 2-dimensional (batch, seq_len)."
            )

        n_samples = input_ids.shape[0]
        if attention_mask.shape[0] != n_samples or labels.shape[0] != n_samples:
            raise DatasetContractViolationError(
                f"Mismatched sample counts across tensors: input_ids={n_samples}, "
                f"attention_mask={attention_mask.shape[0]}, labels={labels.shape[0]}"
            )

        if attention_mask.shape[1] != input_ids.shape[1] or labels.shape[1] != input_ids.shape[1]:
            raise DatasetContractViolationError(
                f"Mismatched sequence lengths across tensors in dataset shard."
            )

        self.dataset_sample_count = n_samples
        hf_dataset = _CausalLMDataset(shard_data)

        # 4. Snapshot immutable baseline parameters before training
        self.baseline_parameters = {
            name: param.detach().clone().cpu()
            for name, param in self.model.named_parameters()
            if param.requires_grad
        }
        logger.info(
            "Captured baseline parameter snapshot for %d trainable parameters.",
            len(self.baseline_parameters)
        )

        # 5. Construct Hugging Face TrainingArguments and Trainer
        output_dir = self.working_directory / "hf_trainer_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        use_cuda = torch.cuda.is_available() and self.device.type == "cuda"
        training_args_kwargs: Dict[str, Any] = {
            "output_dir": str(output_dir),
            "per_device_train_batch_size": self.config.batch_size,
            "num_train_epochs": self.config.epochs,
            "max_steps": self.config.max_steps if self.config.max_steps is not None else -1,
            "learning_rate": self.config.learning_rate,
            "weight_decay": self.config.weight_decay,
            "gradient_accumulation_steps": self.config.gradient_accumulation_steps,
            "max_grad_norm": self.config.max_grad_norm if self.config.max_grad_norm is not None else 0.0,
            "lr_scheduler_type": self.config.scheduler_type,
            "warmup_steps": self.config.warmup_steps,
            "fp16": self.config.fp16 and use_cuda,
            "bf16": self.config.bf16 and use_cuda,
            "logging_strategy": "steps",
            "logging_steps": 1,
            "save_strategy": "no",
            "report_to": [],
            "seed": self.config.seed,
        }

        import inspect
        sig_params = inspect.signature(TrainingArguments.__init__).parameters
        if "warmup_ratio" in sig_params:
            training_args_kwargs["warmup_ratio"] = self.config.warmup_ratio
        elif self.config.warmup_ratio > 0 and self.config.warmup_steps == 0:
            steps_per_epoch = max(1, n_samples // (self.config.batch_size * self.config.gradient_accumulation_steps))
            total_steps = self.config.max_steps if self.config.max_steps is not None and self.config.max_steps > 0 else steps_per_epoch * self.config.epochs
            training_args_kwargs["warmup_steps"] = max(1, int(total_steps * self.config.warmup_ratio))

        training_args = TrainingArguments(**training_args_kwargs)

        self.hf_trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=hf_dataset,
            processing_class=self.tokenizer,
        )
        logger.info("Hugging Face Trainer prepared successfully for task '%s'.", self.task.training_task_id)

    def train(self) -> None:
        """
        Phase 3: Execute fine-tuning using Hugging Face Trainer.
        """
        if self.hf_trainer is None:
            raise TrainingExecutionError("Cannot train: Hugging Face Trainer is not initialized.")

        logger.info("Starting local fine-tuning via Hugging Face Trainer...")
        try:
            train_output = self.hf_trainer.train()
            self.global_steps = int(train_output.global_step)
            self.epochs_completed = int(self.config.epochs)
            self.samples_trained = int(self.dataset_sample_count * self.epochs_completed)
            self.last_loss = float(train_output.training_loss) if train_output.training_loss is not None else 0.0

            # Extract loss history from trainer log history
            self.loss_history = [
                float(log["loss"])
                for log in self.hf_trainer.state.log_history
                if "loss" in log
            ]
            if not self.loss_history:
                self.loss_history = [self.last_loss]

            logger.info(
                "Fine-tuning complete: %d steps, %d epochs, %d samples, final loss: %.6f",
                self.global_steps, self.epochs_completed, self.samples_trained, self.last_loss
            )
        except Exception as exc:
            logger.error("Error during causal decoder training execution: %s", exc, exc_info=True)
            raise TrainingExecutionError(f"Causal decoder fine-tuning failed: {exc}") from exc

    def save_result(self) -> TrainingResult:
        """
        Phase 4: Calculate parameter deltas relative to baseline snapshot and serialize to .safetensors.
        """
        if self.model is None or self.baseline_parameters is None:
            raise ResultSaveError("Cannot save result: model has not been prepared/trained.")

        delta_filename = f"{self.task.baseline_model_id}_{self.task.baseline_model_version}_{self.task.data_set_id}_{self.task.data_set_shard_id}.safetensors"
        delta_path = self.working_directory / delta_filename

        logger.info("Computing parameter deltas (trained - base) for safetensors export...")
        try:
            trained_parameters = {
                name: param.detach().clone().cpu()
                for name, param in self.model.named_parameters()
                if param.requires_grad
            }

            # 1. Validate parameter key compatibility
            base_keys = set(self.baseline_parameters.keys())
            trained_keys = set(trained_parameters.keys())
            if base_keys != trained_keys:
                missing = base_keys - trained_keys
                unexpected = trained_keys - base_keys
                raise TensorCompatibilityError(
                    f"Parameter keys mismatch between baseline and trained model. Missing: {missing}, Unexpected: {unexpected}"
                )

            # 2. Calculate tensor differences: delta = trained - base
            delta_dict: Dict[str, torch.Tensor] = {}
            for name, base_tensor in self.baseline_parameters.items():
                trained_tensor = trained_parameters[name]

                if trained_tensor.shape != base_tensor.shape:
                    raise TensorCompatibilityError(
                        f"Shape mismatch for tensor '{name}': trained {trained_tensor.shape} vs base {base_tensor.shape}"
                    )

                delta_dict[name] = (trained_tensor - base_tensor).contiguous()

            # 3. Save delta artifact in safetensors format
            logger.info("Saving %d parameter deltas to %s", len(delta_dict), delta_path)
            save_file(delta_dict, str(delta_path))

            delta_info = DeltaArtifactInfo(
                filename=delta_filename,
                path=str(delta_path),
                format="safetensors",
                tensor_count=len(delta_dict),
                size_bytes=delta_path.stat().st_size,
            )

        except (TensorCompatibilityError, InvalidArtifactError):
            raise
        except Exception as exc:
            logger.error("Failed to calculate or save delta artifact: %s", exc, exc_info=True)
            raise ResultSaveError(f"Failed to save delta artifact to '{delta_path}': {exc}") from exc

        return TrainingResult(
            training_task_id=self.task.training_task_id,
            base_model_id=self.task.baseline_model_id,
            base_model_version=self.task.baseline_model_version,
            dataset_id=self.task.data_set_id,
            dataset_shard_id=self.task.data_set_shard_id,
            samples_trained=self.samples_trained,
            metrics={
                "loss_history": self.loss_history,
                "device": str(self.device),
                "total_steps": self.global_steps,
                "final_loss": self.last_loss,
            },
            delta=delta_info,
        )


__all__ = ["CanonicalCausalDecoderTrainer"]
