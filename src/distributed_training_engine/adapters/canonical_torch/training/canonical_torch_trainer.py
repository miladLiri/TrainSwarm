"""
Canonical PyTorch training adapter implementation.
"""

from __future__ import annotations
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from safetensors.torch import save_file

from ....training.trainer_adapter import TrainerAdapter, TrainingAdapter
from ....training.training_task_model import TrainingTask
from ....training.training_result import TrainingResult, DeltaArtifactInfo
from .canonical_torch_config import CanonicalTorchTrainingConfig
from .optimizer_registry import OptimizerRegistry
from .scheduler_registry import SchedulerRegistry
from .criterion_registry import CriterionRegistry
from ....training.exceptions import (
    MissingArtifactError,
    InvalidArtifactError,
    DatasetContractViolationError,
    ModelContractViolationError,
    TrainingExecutionError,
    ResultSaveError,
    TensorCompatibilityError,
    DeltaCalculationError,
)

logger = logging.getLogger("distributed_training_engine.canonical_torch_trainer")


class CanonicalTorchTrainer(TrainerAdapter):
    """
    Executes local training for canonical PyTorch models (.pt2) and dataset shards (.pt),
    calculating parameter deltas and saving lightweight .safetensors artifacts.
    """

    def __init__(self, task: TrainingTask, working_directory: Path) -> None:
        super().__init__(task=task, working_directory=working_directory)
        self.config: Optional[CanonicalTorchTrainingConfig] = None
        self.checkpoint_path: Optional[Path] = None
        self.dataset_path: Optional[Path] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Runtime training components
        self.exported_program: Optional[torch.export.ExportedProgram] = None
        self.model: Optional[nn.Module] = None
        self.base_state_dict: Optional[Dict[str, torch.Tensor]] = None
        self.train_loader: Optional[DataLoader] = None
        self.criterion: Optional[nn.Module] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.scheduler: Optional[Any] = None
        self.sample_x: Optional[torch.Tensor] = None

        # Metrics tracking
        self.global_steps: int = 0
        self.epochs_completed: int = 0
        self.samples_trained: int = 0
        self.last_loss: float = 0.0
        self.loss_history: List[float] = []

    def validate(self) -> None:
        """
        Validate task configuration, deserialization, and artifact existence.
        """
        logger.debug("Validating general task envelope for task '%s'", self.task.training_task_id)
        self.task.validate_envelope()

        logger.debug("Deserializing CanonicalTorchTrainingConfig for task '%s'", self.task.training_task_id)
        self.config = CanonicalTorchTrainingConfig.from_dict(self.task.training)

        # Resolve artifact paths
        self.checkpoint_path = self.working_directory / f"{self.task.baseline_model_id}_{self.task.baseline_model_version}.pt2"
        self.dataset_path = self.working_directory / f"{self.task.data_set_id}_{self.task.data_set_shard_id}.pt"

        logger.debug("Checking checkpoint artifact existence: %s", self.checkpoint_path)
        if not self.checkpoint_path.is_file():
            raise MissingArtifactError(
                f"Checkpoint file not found: '{self.checkpoint_path}' for task '{self.task.training_task_id}'"
            )

        logger.debug("Checking dataset shard artifact existence: %s", self.dataset_path)
        if not self.dataset_path.is_file():
            raise MissingArtifactError(
                f"Dataset shard file not found: '{self.dataset_path}' for task '{self.task.training_task_id}'"
            )

        logger.info(
            "Validation successful for task '%s' [checkpoint=%s, shard=%s]",
            self.task.training_task_id, self.checkpoint_path.name, self.dataset_path.name
        )

    def _apply_random_seed(self) -> None:
        """Apply random seed across Python, NumPy, and PyTorch if configured."""
        if self.config and self.config.seed is not None:
            seed = self.config.seed
            logger.info("Applying random seed %d for reproducible training", seed)
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
        Load model program and dataset shards, prepare DataLoader, snapshot base model weights,
        device placement, and internal training state.
        """
        if self.config is None:
            self.validate()

        self._apply_random_seed()

        logger.info("Using device: %s for task '%s'", self.device, self.task.training_task_id)

        # 1. Load exported program (.pt2)
        logger.debug("Loading exported program from: %s", self.checkpoint_path)
        try:
            self.exported_program = torch.export.load(str(self.checkpoint_path))
        except Exception as exc:
            raise InvalidArtifactError(
                f"Failed to load PyTorch exported program from '{self.checkpoint_path}': {exc}"
            ) from exc

        try:
            self.model = self.exported_program.module()
        except Exception as exc:
            raise ModelContractViolationError(
                f"Exported program module extraction failed: {exc}"
            ) from exc

        if not isinstance(self.model, nn.Module):
            raise ModelContractViolationError(
                f"Extracted model is not an instance of torch.nn.Module (got {type(self.model)})"
            )

        # 2. Capture immutable baseline weights snapshot before any optimizer mutation
        self.base_state_dict = {
            name: tensor.detach().cpu().clone().contiguous()
            for name, tensor in self.model.state_dict().items()
        }
        logger.debug(
            "Captured baseline model state_dict snapshot (%d parameter/buffer tensors)",
            len(self.base_state_dict)
        )

        self.model.to(self.device)

        # 3. Load dataset shard (.pt)
        logger.debug("Loading dataset shard from: %s", self.dataset_path)
        try:
            shard_data = torch.load(str(self.dataset_path), weights_only=True)
        except Exception as exc:
            raise InvalidArtifactError(
                f"Failed to load dataset shard from '{self.dataset_path}': {exc}"
            ) from exc

        if not isinstance(shard_data, dict):
            raise DatasetContractViolationError(
                f"Dataset shard must be a dictionary containing 'x' and 'y', got {type(shard_data)}"
            )

        if "x" not in shard_data or "y" not in shard_data:
            raise DatasetContractViolationError(
                f"Dataset shard dictionary missing required 'x' or 'y' keys: {list(shard_data.keys())}"
            )

        x_tensor = shard_data["x"]
        y_tensor = shard_data["y"]

        if not isinstance(x_tensor, torch.Tensor) or not isinstance(y_tensor, torch.Tensor):
            raise DatasetContractViolationError("Dataset shard 'x' and 'y' must be torch.Tensor instances.")

        if x_tensor.dtype != torch.float32 or y_tensor.dtype != torch.float32:
            raise DatasetContractViolationError(
                f"Dataset shard tensors must have dtype torch.float32, got x={x_tensor.dtype}, y={y_tensor.dtype}"
            )

        if x_tensor.shape[0] != y_tensor.shape[0]:
            raise DatasetContractViolationError(
                f"Sample count mismatch in dataset shard: x has {x_tensor.shape[0]} samples, y has {y_tensor.shape[0]} samples"
            )

        # Save sample input for reference
        sample_len = min(2, x_tensor.shape[0])
        self.sample_x = x_tensor[:sample_len].clone()

        # 4. Create TensorDataset and DataLoader
        dataset = TensorDataset(x_tensor, y_tensor)
        self.train_loader = DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=self.config.shuffle
        )

        # 5. Construct registries
        self.criterion = CriterionRegistry.create(self.config.loss).to(self.device)
        self.optimizer = OptimizerRegistry.create(self.config.optimizer, self.model.parameters())
        self.scheduler = SchedulerRegistry.create(self.config.scheduler, self.optimizer)

        logger.info(
            "Preparation complete [samples=%d, batch_size=%d, batches_per_epoch=%d]",
            len(dataset), self.config.batch_size, len(self.train_loader)
        )

    def train(self) -> None:
        """
        Execute the autograd training loop according to the validated configuration.
        """
        if self.model is None or self.train_loader is None or self.optimizer is None or self.criterion is None:
            raise TrainingExecutionError("Adapter prepare() must be called before train().")

        logger.info(
            "Starting training loop [epochs=%d, max_steps=%s, grad_accum_steps=%d, max_grad_norm=%s]",
            self.config.epochs, self.config.max_steps, self.config.gradient_accumulation_steps, self.config.max_grad_norm
        )

        try:
            self.model.train()
        except (NotImplementedError, AttributeError):
            # PyTorch GraphModule from export might not implement mode toggling
            pass

        self.global_steps = 0
        self.epochs_completed = 0
        self.samples_trained = 0
        self.loss_history = []
        accumulated_batches = 0

        try:
            for epoch in range(self.config.epochs):
                logger.debug("Starting epoch %d/%d", epoch + 1, self.config.epochs)

                for batch_idx, (x_batch, y_batch) in enumerate(self.train_loader):
                    x_batch = x_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    outputs = self.model(x_batch)
                    loss = self.criterion(outputs, y_batch)

                    scaled_loss = loss / self.config.gradient_accumulation_steps
                    scaled_loss.backward()

                    accumulated_batches += 1
                    self.samples_trained += int(x_batch.shape[0])
                    self.last_loss = float(loss.item())

                    # Check gradient accumulation boundary
                    if accumulated_batches % self.config.gradient_accumulation_steps == 0:
                        if self.config.max_grad_norm is not None:
                            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)

                        self.optimizer.step()
                        if self.scheduler is not None:
                            self.scheduler.step()

                        self.optimizer.zero_grad()
                        self.global_steps += 1
                        accumulated_batches = 0
                        self.loss_history.append(self.last_loss)

                        logger.debug(
                            "Optimizer step %d [epoch=%d, batch=%d, loss=%.6f]",
                            self.global_steps, epoch + 1, batch_idx + 1, self.last_loss
                        )

                        if self.config.max_steps is not None and self.global_steps >= self.config.max_steps:
                            logger.info("Reached maximum configured steps (%d). Stopping training.", self.config.max_steps)
                            break

                # Handle incomplete accumulation group at the end of epoch
                if accumulated_batches > 0:
                    if self.config.max_grad_norm is not None:
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)

                    self.optimizer.step()
                    if self.scheduler is not None:
                        self.scheduler.step()

                    self.optimizer.zero_grad()
                    self.global_steps += 1
                    accumulated_batches = 0
                    self.loss_history.append(self.last_loss)

                    logger.debug("Flushed partial accumulation group at epoch %d [step=%d, loss=%.6f]", epoch + 1, self.global_steps, self.last_loss)

                    if self.config.max_steps is not None and self.global_steps >= self.config.max_steps:
                        logger.info("Reached maximum configured steps (%d). Stopping training.", self.config.max_steps)
                        self.epochs_completed = epoch + 1
                        break

                self.epochs_completed = epoch + 1
                logger.info(
                    "Epoch %d/%d completed [last_loss=%.6f, total_steps=%d, samples_trained=%d]",
                    self.epochs_completed, self.config.epochs, self.last_loss, self.global_steps, self.samples_trained
                )

                if self.config.max_steps is not None and self.global_steps >= self.config.max_steps:
                    break

        except Exception as exc:
            logger.error("Error during training loop execution: %s", exc, exc_info=True)
            raise TrainingExecutionError(f"Training loop failed: {exc}") from exc

    def save_result(self) -> TrainingResult:
        """
        Calculate model delta against the baseline weights snapshot and save as .safetensors artifact.
        """
        if self.model is None or self.base_state_dict is None:
            raise ResultSaveError("Cannot save result: model has not been prepared/trained.")

        delta_filename = f"{self.task.baseline_model_id}_{self.task.baseline_model_version}_{self.task.data_set_id}_{self.task.data_set_shard_id}.safetensors"
        delta_path = self.working_directory / delta_filename

        logger.info("Computing model delta and saving safetensors artifact to: %s", delta_path)

        try:
            try:
                self.model.eval()
            except (NotImplementedError, AttributeError):
                pass

            self.model.to("cpu")
            trained_state_dict = {
                name: tensor.detach().cpu().contiguous()
                for name, tensor in self.model.state_dict().items()
            }

            # 1. Validate parameter key compatibility
            base_keys = set(self.base_state_dict.keys())
            trained_keys = set(trained_state_dict.keys())
            if base_keys != trained_keys:
                missing = base_keys - trained_keys
                unexpected = trained_keys - base_keys
                raise TensorCompatibilityError(
                    f"Parameter keys mismatch between baseline and trained model. Missing: {missing}, Unexpected: {unexpected}"
                )

            # 2. Calculate tensor differences: delta = trained - base
            delta_dict: Dict[str, torch.Tensor] = {}
            for name, trained_tensor in trained_state_dict.items():
                base_tensor = self.base_state_dict[name]

                if trained_tensor.shape != base_tensor.shape:
                    raise TensorCompatibilityError(
                        f"Shape mismatch for tensor '{name}': trained {trained_tensor.shape} vs base {base_tensor.shape}"
                    )

                delta_dict[name] = (trained_tensor - base_tensor).contiguous()

            # 3. Save delta artifact in safetensors format
            save_file(delta_dict, str(delta_path))

            delta_info = DeltaArtifactInfo(
                filename=delta_filename,
                path=str(delta_path),
                format="safetensors",
                tensor_count=len(delta_dict),
                size_bytes=delta_path.stat().st_size,
            )

        except (TensorCompatibilityError, DeltaCalculationError):
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


# Backward compatibility alias
CanonicalTorchAdapter = CanonicalTorchTrainer

__all__ = ["CanonicalTorchTrainer", "CanonicalTorchAdapter"]

