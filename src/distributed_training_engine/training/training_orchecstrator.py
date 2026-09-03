"""
Training orchestrator controlling adapter selection and lifecycle execution.
"""

from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from .training_task_model import TrainingTask
from .training_result import TrainingResult, ExecutionInfo
from .trainer_adapter_registery import TrainerAdapterRegistery, TrainingAdapterRegistry

logger = logging.getLogger("distributed_training_engine.orchestrator")


class TrainingOrchecstrator:
    """
    Type-agnostic orchestrator managing the training task lifecycle.
    """

    def __init__(self, adapter_registry: Optional[TrainerAdapterRegistery] = None) -> None:
        self.registry = adapter_registry or TrainerAdapterRegistery()

    def run(self, task: Union[TrainingTask, dict], working_directory: Union[str, Path]) -> TrainingResult:
        """
        Execute the complete local training task workflow.
        """
        work_dir = Path(working_directory).resolve()

        if isinstance(task, dict):
            task_obj = TrainingTask.from_dict(task)
        elif isinstance(task, TrainingTask):
            task_obj = task
            task_obj.validate_envelope()
        else:
            raise TypeError("task must be a TrainingTask instance or a dict payload.")

        started_at = datetime.now(timezone.utc).isoformat()
        start_perf = time.perf_counter()

        logger.info(
            "Starting training task execution [task_id=%s, model=%s_%s, dataset=%s_%s, type=%s, working_dir=%s]",
            task_obj.training_task_id, task_obj.baseline_model_id, task_obj.baseline_model_version,
            task_obj.data_set_id, task_obj.data_set_shard_id, task_obj.type, work_dir
        )

        # 1. Resolve adapter
        logger.debug("Resolving adapter for training type '%s'", task_obj.type)
        adapter_cls = self.registry.get(task_obj.type)
        adapter = adapter_cls(task=task_obj, working_directory=work_dir)

        # 2. Lifecycle: validate
        logger.info("Executing lifecycle phase: VALIDATE [task_id=%s]", task_obj.training_task_id)
        adapter.validate()
        logger.debug("Validation succeeded for task '%s'", task_obj.training_task_id)

        # 3. Lifecycle: prepare
        logger.info("Executing lifecycle phase: PREPARE [task_id=%s]", task_obj.training_task_id)
        adapter.prepare()
        logger.debug("Preparation succeeded for task '%s'", task_obj.training_task_id)

        # 4. Lifecycle: train
        logger.info("Executing lifecycle phase: TRAIN [task_id=%s]", task_obj.training_task_id)
        adapter.train()
        logger.debug("Training completed for task '%s'", task_obj.training_task_id)

        # 5. Lifecycle: save_result
        logger.info("Executing lifecycle phase: SAVE_RESULT [task_id=%s]", task_obj.training_task_id)
        result = adapter.save_result()

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = int((time.perf_counter() - start_perf) * 1000)

        result.execution = ExecutionInfo(
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

        logger.info(
            "Training task finished successfully [task_id=%s, samples=%d, duration=%dms, final_loss=%.6f, delta_artifact=%s]",
            result.training_task_id, result.samples_trained, duration_ms,
            result.metrics.get("final_loss", 0.0), result.delta.filename
        )

        return result


# Backward compatibility alias
TrainingOrchestrator = TrainingOrchecstrator
