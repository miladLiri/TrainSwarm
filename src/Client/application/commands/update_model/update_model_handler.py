"""Handler for UpdateModelCommand in Client."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Client.domain.training_shard import TrainingShardStatus
    from Client.infrastructure.persistence.training_shard_repository import ITrainingShardRepository
except ImportError:
    from domain.training_shard import TrainingShardStatus
    from infrastructure.persistence.training_shard_repository import ITrainingShardRepository

try:
    from distributed_training_engine.training import TrainingResult
except ImportError:
    try:
        from distributed_training_engine import TrainingResult
    except ImportError:
        pass

from .update_model_command import UpdateModelCommand

logger = logging.getLogger("trainswarm.client.update_model")


class UpdateModelCommandHandler:
    """Handles UpdateModelCommand by recording the update artifact path, metrics, and transitioning shard to COMPLETED."""

    def __init__(self, shard_repository: ITrainingShardRepository) -> None:
        self.shard_repository = shard_repository

    def handle(
        self,
        command: Optional[UpdateModelCommand] = None,
        *,
        trainer_node_id: Optional[str] = None,
        training_result: Optional[TrainingResult] = None,
        saved_update_artifact_path: Optional[str] = None,
    ) -> None:
        """Process completed training update and update SQLite shard state."""
        if command is not None:
            t_node_id = command.trainer_node_id
            result = command.training_result
            update_path = command.saved_update_artifact_path
        else:
            t_node_id = trainer_node_id or ""
            result = training_result
            update_path = saved_update_artifact_path or ""

        if result is None:
            raise ValueError("training_result is required for UpdateModelCommand")

        m_id = result.base_model_id
        m_ver = str(result.base_model_version)
        d_id = result.dataset_id
        s_id = str(result.dataset_shard_id)

        logger.info(
            "[UpdateModelCommandHandler] Received update for shard (%s, %s, %s, %s) from trainer=%s, saved at %s",
            m_id, m_ver, d_id, s_id, t_node_id, update_path
        )

        shard = self.shard_repository.get_by_shard_key(m_id, m_ver, d_id, s_id)
        if not shard:
            raise ValueError(
                f"Training shard ({m_id}, {m_ver}, {d_id}, {s_id}) not found in repository"
            )

        # Update shard status to COMPLETED and set update artifact path and metrics
        self.shard_repository.update_shard_completed(
            model_id=m_id,
            model_version=m_ver,
            dataset_id=d_id,
            shard_id=s_id,
            update_artifact_path=update_path,
            metrics=result.metrics if hasattr(result, "metrics") else None,
            status=TrainingShardStatus.COMPLETED,
        )

        logger.info(
            "[UpdateModelCommandHandler] Successfully transitioned shard (%s, %s, %s, %s) to COMPLETED",
            m_id, m_ver, d_id, s_id
        )
