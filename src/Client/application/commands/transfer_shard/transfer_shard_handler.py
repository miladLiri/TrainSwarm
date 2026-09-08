"""Handler for TransferShardCommand in Client."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

try:
    from Client.infrastructure.persistence.training_shard_repository import ITrainingShardRepository
except ImportError:
    from infrastructure.persistence.training_shard_repository import ITrainingShardRepository

from .transfer_shard_command import TransferShardCommand

logger = logging.getLogger("trainswarm.client.transfer_shard")


class TransferShardCommandHandler:
    """Handles TransferShardCommand by resolving dataset shard artifact path from TrainingShardRepository."""

    def __init__(self, shard_repository: ITrainingShardRepository) -> None:
        self.shard_repository = shard_repository

    def handle(
        self,
        command: Optional[TransferShardCommand] = None,
        *,
        trainer_node_id: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
        data_set_id: Optional[str] = None,
        shard_id: Optional[str] = None,
    ) -> str:
        """Resolve shard artifact path and return absolute filesystem path."""
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
            "[TransferShardCommandHandler] Requested shard (%s, %s, %s, %s) by trainer=%s",
            m_id, m_ver, d_id, s_id, t_node_id
        )

        shard = self.shard_repository.get_by_shard_key(m_id, m_ver, d_id, s_id)
        if not shard:
            raise ValueError(
                f"Training shard ({m_id}, {m_ver}, {d_id}, {s_id}) not found in repository"
            )

        shard_path = Path(shard.artifact_path)
        if not shard_path.exists():
            raise FileNotFoundError(f"Shard artifact file not found at: {shard_path}")

        logger.info(
            "[TransferShardCommandHandler] Resolved shard artifact path: %s",
            str(shard_path.resolve())
        )
        return str(shard_path.resolve())
