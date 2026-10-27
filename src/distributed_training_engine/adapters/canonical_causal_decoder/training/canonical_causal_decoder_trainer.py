"""
Canonical Causal Decoder Model trainer adapter implementation.
"""

from __future__ import annotations
import json
import logging
import math
import os
from pathlib import Path
import random
import shutil
import sys
import tarfile
import time
from typing import Any, Dict, List, Optional
import torch
from torch.utils.data import Dataset
from safetensors.torch import save_file

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        TrainerCallback,
    )
except ImportError:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    Trainer = None
    TrainingArguments = None
    TrainerCallback = object

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


def save_metrics_to_disk(metrics_data: Dict[str, Any], path: Path | str) -> None:
    """Save metrics dictionary atomically to JSON file on disk."""
    target_path = Path(path)
    temp_path = target_path.with_name(f"{target_path.name}.tmp")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    os.replace(temp_path, target_path)


class _CanonicalCausalDecoderTrainer(Trainer):
    """
    Subclasses Hugging Face Trainer to collect token-level accuracy
    and count processed tokens during training forward passes.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.loss_window: List[float] = []
        self.acc_window: List[float] = []
        self.total_tokens_processed: int = 0

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        outputs = model(**inputs)
        loss = outputs["loss"] if isinstance(outputs, dict) else outputs.loss

        if model.training:
            with torch.no_grad():
                shift_logits = outputs.logits[..., :-1, :].contiguous()
                shift_labels = inputs["labels"][..., 1:].contiguous()
                mask = shift_labels != -100
                if mask.sum() > 0:
                    preds = shift_logits.argmax(dim=-1)
                    batch_acc = (preds[mask] == shift_labels[mask]).float().mean().item() * 100.0
                else:
                    batch_acc = 0.0

                batch_tokens = (inputs["attention_mask"] == 1).sum().item()
                self.total_tokens_processed += batch_tokens
                self.loss_window.append(loss.item())
                self.acc_window.append(batch_acc)

        return (loss, outputs) if return_outputs else loss


class _MetricsTrackingCallback(TrainerCallback):
    """
    Callback for Hugging Face Trainer:
    1. Tracks loss, perplexity, token accuracy, speed, and time every log_every_steps.
    2. Saves metrics on-the-go atomically to training_metrics.json.
    3. Prints progress logs matching train_single_node.py formatting.
    """

    def __init__(
        self,
        metrics_data: Dict[str, Any],
        metrics_file: Path,
        start_time: float,
        total_steps: int,
        num_epochs: int,
        log_every_steps: int,
        device_type: str,
    ) -> None:
        self.metrics_data = metrics_data
        self.metrics_file = Path(metrics_file)
        self.start_time = start_time
        self.total_steps = total_steps
        self.num_epochs = num_epochs
        self.log_every_steps = max(1, log_every_steps)
        self.device_type = device_type

        self.last_logged_step = 0
        self.best_loss = float("inf")
        self.best_step = 0
        self.best_epoch = 0.0
        self.best_acc = 0.0
        self.trainer: Optional[Any] = None

    def on_step_end(self, args, state, control, model=None, tokenizer=None, **kwargs):
        trainer = self.trainer or kwargs.get("trainer")
        is_interval = (state.global_step % self.log_every_steps == 0 and state.global_step > self.last_logged_step)
        is_final = (state.global_step >= self.total_steps and state.global_step > self.last_logged_step)

        if is_interval or is_final:
            cur_time = time.time()
            elapsed = cur_time - self.start_time

            loss_window = trainer.loss_window if trainer else []
            acc_window = trainer.acc_window if trainer else []
            total_tokens = trainer.total_tokens_processed if trainer else 0

            avg_loss = sum(loss_window) / len(loss_window) if loss_window else 0.0
            avg_acc = sum(acc_window) / len(acc_window) if acc_window else 0.0
            if loss_window:
                loss_window.clear()
            if acc_window:
                acc_window.clear()

            perplexity = math.exp(min(avg_loss, 20.0))

            current_lr = 0.0
            if trainer and getattr(trainer, "lr_scheduler", None):
                current_lr = trainer.lr_scheduler.get_last_lr()[0]
            elif trainer and getattr(trainer, "optimizer", None) and trainer.optimizer.param_groups:
                current_lr = trainer.optimizer.param_groups[0]["lr"]
            elif state.log_history:
                current_lr = state.log_history[-1].get("learning_rate", 0.0)

            tokens_per_sec = total_tokens / elapsed if elapsed > 0 else 0.0

            vram_mb = 0.0
            if self.device_type == "cuda" and torch.cuda.is_available():
                vram_mb = torch.cuda.memory_allocated(0) / (1024 * 1024)

            cur_epoch = round(state.epoch, 3) if state.epoch is not None else 0.0

            step_metric = {
                "step": state.global_step,
                "epoch": cur_epoch,
                "loss": round(avg_loss, 4),
                "perplexity": round(perplexity, 2),
                "accuracy": round(avg_acc, 2),
                "learning_rate": float(f"{current_lr:.6e}"),
                "tokens_per_sec": round(tokens_per_sec, 1),
                "total_tokens": total_tokens,
                "elapsed_sec": round(elapsed, 2),
                "vram_allocated_mb": round(vram_mb, 1),
            }
            self.metrics_data["steps"].append(step_metric)

            is_best = avg_loss < self.best_loss
            if is_best:
                self.best_loss = avg_loss
                self.best_acc = avg_acc
                self.best_step = state.global_step
                self.best_epoch = cur_epoch

            best_flag = " [*BEST*]" if is_best else ""
            print(
                f"Step {state.global_step:4d}/{self.total_steps} (Ep {cur_epoch:.2f}/{self.num_epochs}) | "
                f"Loss: {avg_loss:.4f} | "
                f"PPL: {perplexity:6.2f} | "
                f"Acc: {avg_acc:5.2f}% | "
                f"Speed: {tokens_per_sec:5.0f} tok/s | "
                f"Time: {elapsed:5.1f}s{best_flag}",
                flush=True,
            )

            save_metrics_to_disk(self.metrics_data, self.metrics_file)
            self.last_logged_step = state.global_step


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

        # JSON metrics file and tracking
        self.metrics_file = self.working_directory / "training_metrics.json"
        self.metrics_data: Dict[str, Any] = {}
        self.metrics_callback: Optional[_MetricsTrackingCallback] = None
        self.training_start_time: float = 0.0
        self.total_planned_steps: int = 0

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

        steps_per_epoch = max(1, (n_samples // self.config.batch_size) // self.config.gradient_accumulation_steps)
        total_steps = self.config.max_steps if self.config.max_steps is not None and self.config.max_steps > 0 else steps_per_epoch * self.config.epochs
        self.total_planned_steps = total_steps
        log_every_steps = 5 if total_steps > 10 else 1

        import inspect
        sig_params = inspect.signature(TrainingArguments.__init__).parameters
        if "warmup_ratio" in sig_params:
            training_args_kwargs["warmup_ratio"] = self.config.warmup_ratio
        elif self.config.warmup_ratio > 0 and self.config.warmup_steps == 0:
            training_args_kwargs["warmup_steps"] = max(1, int(total_steps * self.config.warmup_ratio))

        training_args = TrainingArguments(**training_args_kwargs)

        total_params = sum(p.numel() for p in self.model.parameters())
        self.metrics_data = {
            "metadata": {
                "model_name": f"{self.task.baseline_model_id}:{self.task.baseline_model_version}",
                "device": self.device.type,
                "device_name": torch.cuda.get_device_name(0) if self.device.type == "cuda" else "CPU",
                "total_parameters": total_params,
                "batch_size": self.config.batch_size,
                "grad_accum_steps": self.config.gradient_accumulation_steps,
                "effective_batch_size": self.config.batch_size * self.config.gradient_accumulation_steps,
                "learning_rate": self.config.learning_rate,
                "max_seq_length": int(input_ids.shape[1]),
                "total_planned_steps": total_steps,
                "num_epochs": self.config.epochs,
                "steps_per_epoch": steps_per_epoch,
                "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "steps": [],
            "summary": {},
        }
        self.training_start_time = time.time()

        self.metrics_callback = _MetricsTrackingCallback(
            metrics_data=self.metrics_data,
            metrics_file=self.metrics_file,
            start_time=self.training_start_time,
            total_steps=total_steps,
            num_epochs=self.config.epochs,
            log_every_steps=log_every_steps,
            device_type=self.device.type,
        )

        self.hf_trainer = _CanonicalCausalDecoderTrainer(
            model=self.model,
            args=training_args,
            train_dataset=hf_dataset,
            processing_class=self.tokenizer,
            callbacks=[self.metrics_callback],
        )
        self.metrics_callback.trainer = self.hf_trainer
        try:
            from transformers.trainer_callback import PrinterCallback
            self.hf_trainer.remove_callback(PrinterCallback)
        except Exception:
            pass
        logger.info("Hugging Face Trainer prepared successfully for task '%s'.", self.task.training_task_id)

    def train(self) -> None:
        """
        Phase 3: Execute fine-tuning using Hugging Face Trainer.
        """
        if self.hf_trainer is None:
            raise TrainingExecutionError("Cannot train: Hugging Face Trainer is not initialized.")

        logger.info("Starting local fine-tuning via Hugging Face Trainer...")
        start_time = self.training_start_time or time.time()
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

            total_elapsed = time.time() - start_time
            steps_list = self.metrics_data.get("steps", [])
            final_epoch = steps_list[-1]["epoch"] if steps_list else float(self.epochs_completed)
            final_step = steps_list[-1]["step"] if steps_list else self.global_steps
            first_loss = steps_list[0]["loss"] if steps_list else self.last_loss
            last_loss = steps_list[-1]["loss"] if steps_list else self.last_loss
            first_ppl = steps_list[0]["perplexity"] if steps_list else math.exp(min(last_loss, 20.0))
            last_ppl = steps_list[-1]["perplexity"] if steps_list else math.exp(min(last_loss, 20.0))
            first_acc = steps_list[0]["accuracy"] if steps_list else 0.0
            last_acc = steps_list[-1]["accuracy"] if steps_list else 0.0

            best_loss = self.metrics_callback.best_loss if (self.metrics_callback and self.metrics_callback.best_loss != float("inf")) else last_loss
            best_acc = self.metrics_callback.best_acc if self.metrics_callback else last_acc
            best_step = self.metrics_callback.best_step if self.metrics_callback else final_step
            best_epoch = self.metrics_callback.best_epoch if self.metrics_callback else final_epoch

            total_tokens = self.hf_trainer.total_tokens_processed if hasattr(self.hf_trainer, "total_tokens_processed") else 0

            self.metrics_data["summary"] = {
                "status": "completed" if (self.config.max_steps and final_step >= self.config.max_steps) else "finished",
                "total_steps": final_step,
                "total_epochs_trained": final_epoch,
                "total_elapsed_sec": round(total_elapsed, 2),
                "total_tokens_processed": total_tokens,
                "average_tokens_per_sec": round(total_tokens / total_elapsed, 1) if total_elapsed > 0 else 0.0,
                "initial_loss": first_loss,
                "final_loss": last_loss,
                "initial_perplexity": first_ppl,
                "final_perplexity": last_ppl,
                "initial_accuracy": first_acc,
                "final_accuracy": last_acc,
                "best_loss": best_loss,
                "best_accuracy": best_acc,
                "best_step": best_step,
                "best_epoch": best_epoch,
            }
            save_metrics_to_disk(self.metrics_data, self.metrics_file)

            logger.info(
                "Fine-tuning complete: %d steps, %d epochs, %d samples, final loss: %.6f",
                self.global_steps, self.epochs_completed, self.samples_trained, self.last_loss
            )
        except Exception as exc:
            total_elapsed = time.time() - start_time
            steps_list = self.metrics_data.get("steps", [])
            final_epoch = steps_list[-1]["epoch"] if steps_list else 0.0
            final_step = steps_list[-1]["step"] if steps_list else 0
            total_tokens = getattr(self.hf_trainer, "total_tokens_processed", 0) if self.hf_trainer else 0
            self.metrics_data["summary"] = {
                "status": "failed",
                "total_steps": final_step,
                "total_epochs_trained": final_epoch,
                "total_elapsed_sec": round(total_elapsed, 2),
                "total_tokens_processed": total_tokens,
                "average_tokens_per_sec": round(total_tokens / total_elapsed, 1) if total_elapsed > 0 else 0.0,
                "initial_loss": steps_list[0]["loss"] if steps_list else None,
                "final_loss": steps_list[-1]["loss"] if steps_list else None,
                "initial_perplexity": steps_list[0]["perplexity"] if steps_list else None,
                "final_perplexity": steps_list[-1]["perplexity"] if steps_list else None,
                "initial_accuracy": steps_list[0]["accuracy"] if steps_list else None,
                "final_accuracy": steps_list[-1]["accuracy"] if steps_list else None,
                "best_loss": self.metrics_callback.best_loss if (self.metrics_callback and self.metrics_callback.best_loss != float("inf")) else None,
                "best_accuracy": self.metrics_callback.best_acc if self.metrics_callback else None,
                "best_step": self.metrics_callback.best_step if self.metrics_callback else None,
                "best_epoch": self.metrics_callback.best_epoch if self.metrics_callback else None,
            }
            try:
                save_metrics_to_disk(self.metrics_data, self.metrics_file)
            except Exception:
                pass
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
                "metrics_file": str(self.metrics_file),
            },
            delta=delta_info,
        )


__all__ = ["CanonicalCausalDecoderTrainer"]
