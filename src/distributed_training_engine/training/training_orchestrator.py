"""
Training orchestrator controlling adapter selection and lifecycle execution.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Union
from .training_task_model import TrainingTask
from .training_result import TrainingResult
from .training_adapter_registry import TrainingAdapterRegistry

logger = logging.getLogger("distributed_training_engine.orchestrator")


class TrainingOrchestrator:
    """
    Type-agnostic orchestrator managing the training task lifecycle.
    """

    def __init__(self, adapter_registry: Optional[TrainingAdapterRegistry] = None) -> None:
        self.registry = adapter_registry or TrainingAdapterRegistry()

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

        logger.info(
            "Starting training task execution [task_id=%s, session_id=%s, type=%s, working_dir=%s]",
            task_obj.task_id, task_obj.session_id, task_obj.type, work_dir
        )

        # 1. Resolve adapter
        logger.debug("Resolving adapter for training type '%s'", task_obj.type)
        adapter_cls = self.registry.get(task_obj.type)
        adapter = adapter_cls(task=task_obj, working_directory=work_dir)

        # 2. Lifecycle: validate
        logger.info("Executing lifecycle phase: VALIDATE [task_id=%s]", task_obj.task_id)
        adapter.validate()
        logger.debug("Validation succeeded for task '%s'", task_obj.task_id)

        # 3. Lifecycle: prepare
        logger.info("Executing lifecycle phase: PREPARE [task_id=%s]", task_obj.task_id)
        adapter.prepare()
        logger.debug("Preparation succeeded for task '%s'", task_obj.task_id)

        # 4. Lifecycle: train
        logger.info("Executing lifecycle phase: TRAIN [task_id=%s]", task_obj.task_id)
        adapter.train()
        logger.debug("Training completed for task '%s'", task_obj.task_id)

        # 5. Lifecycle: save_result
        logger.info("Executing lifecycle phase: SAVE_RESULT [task_id=%s]", task_obj.task_id)
        result = adapter.save_result()
        logger.info(
            "Training task finished successfully [task_id=%s, steps=%d, epochs=%d, final_loss=%.6f, artifact=%s]",
            result.task_id, result.training_steps, result.epochs_completed, result.final_loss, result.output_checkpoint_path
        )

        return result
