"""Handler for GetTrainingTaskCommand in Client."""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
import uuid

try:
    from Client.domain.training_shard import TrainingShardStatus
    from Client.infrastructure.persistence.model_repository import IModelRepository
    from Client.infrastructure.persistence.training_shard_repository import ITrainingShardRepository
except ImportError:
    from domain.training_shard import TrainingShardStatus
    from infrastructure.persistence.model_repository import IModelRepository
    from infrastructure.persistence.training_shard_repository import ITrainingShardRepository

try:
    from distributed_training_engine.training import TrainingTask
except ImportError:
    try:
        from distributed_training_engine import TrainingTask
    except ImportError:
        pass

from .get_training_task_command import GetTrainingTaskCommand

logger = logging.getLogger("trainswarm.client.get_training_task")


class GetTrainingTaskCommandHandler:
    """Handles GetTrainingTaskCommand by querying model metadata, loading config, and updating shard."""

    def __init__(
        self,
        model_repository: IModelRepository,
        shard_repository: ITrainingShardRepository,
    ) -> None:
        self.model_repository = model_repository
        self.shard_repository = shard_repository

    def handle(
        self,
        command: Optional[GetTrainingTaskCommand] = None,
        *,
        trainer_node_id: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
        data_set_id: Optional[str] = None,
        shard_id: Optional[str] = None,
    ) -> TrainingTask:
        """Execute get training task workflow and return compiled TrainingTask."""
        if command is not None:
            t_node_id = command.trainer_node_id
            m_id = command.model_id
            m_ver = str(command.model_version)
            d_id = command.data_set_id
            s_id = str(command.shard_id)
        else:
            t_node_id = trainer_node_id or ""
            m_id = model_id or ""
            m_ver = str(model_version or "")
            d_id = data_set_id or ""
            s_id = str(shard_id or "")

        logger.info(
            "[GetTrainingTaskCommandHandler] Request for model=%s v%s, dataset=%s, shard=%s from trainer=%s",
            m_id, m_ver, d_id, s_id, t_node_id
        )

        # 1. Lookup model
        model = self.model_repository.get_by_model_id(m_id)
        if not model:
            raise ValueError(f"Model '{m_id}' not found in model repository")

        # 2. Load training config JSON
        config_path = Path(model.training_config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Training config file not found at: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            training_config = json.load(f)

        # 3. Lookup shard
        shard = self.shard_repository.get_by_shard_key(m_id, m_ver, d_id, s_id)
        if not shard:
            raise ValueError(f"Training shard ({m_id}, {m_ver}, {d_id}, {s_id}) not found")

        # 4. Update shard in SQLite: set trainer_node_id and transition to TRAINING
        self.shard_repository.update_shard_training_status(
            model_id=m_id,
            model_version=m_ver,
            dataset_id=d_id,
            shard_id=s_id,
            trainer_node_id=t_node_id,
            status=TrainingShardStatus.TRAINING,
        )

        # 5. Build TrainingTask
        task_id = shard.training_task_id or str(uuid.uuid4())
        task = TrainingTask(
            training_task_id=task_id,
            baseline_model_id=m_id,
            baseline_model_version=m_ver,
            data_set_id=d_id,
            data_set_shard_id=s_id,
            type=model.model_type,
            training=training_config,
        )

        logger.info(
            "[GetTrainingTaskCommandHandler] Successfully compiled task %s and marked shard training",
            task_id
        )
        return task
