"""Handler for TransferModelCommand in Client."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

try:
    from Client.infrastructure.persistence.model_repository import IModelRepository
except ImportError:
    from infrastructure.persistence.model_repository import IModelRepository

from .transfer_model_command import TransferModelCommand

logger = logging.getLogger("trainswarm.client.transfer_model")


class TransferModelCommandHandler:
    """Handles TransferModelCommand by resolving base model artifact path from ModelRepository."""

    def __init__(self, model_repository: IModelRepository) -> None:
        self.model_repository = model_repository

    def handle(
        self,
        command: Optional[TransferModelCommand] = None,
        *,
        trainer_node_id: Optional[str] = None,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> str:
        """Resolve model artifact path and return absolute filesystem path."""
        if command is not None:
            t_node_id = command.trainer_node_id
            m_id = command.model_id
            m_ver = str(command.model_version)
        else:
            t_node_id = trainer_node_id or ""
            m_id = model_id or ""
            m_ver = str(model_version or "")

        logger.info(
            "[TransferModelCommandHandler] Requested model=%s v%s by trainer=%s",
            m_id, m_ver, t_node_id
        )

        model = self.model_repository.get_by_model_id(m_id)
        if not model:
            raise ValueError(f"Model '{m_id}' not found in repository")

        if str(model.model_version) != m_ver:
            raise ValueError(
                f"Model version mismatch for '{m_id}': expected {m_ver}, found {model.model_version}"
            )

        model_path = Path(model.model_artifact_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model checkpoint artifact not found at: {model_path}")

        logger.info(
            "[TransferModelCommandHandler] Resolved model artifact path: %s",
            str(model_path.resolve())
        )
        return str(model_path.resolve())
