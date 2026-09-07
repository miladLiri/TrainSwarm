"""Command handler for ConnectTrainerCommand."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Trainer.application.state import TrainerState
    from Trainer.infrastructure.adapters.coordinator_adapter import CoordinatorAdapter
    from .connect_trainer_command import ConnectTrainerCommand, ConnectTrainerResult
except ImportError:
    from application.state import TrainerState
    from infrastructure.adapters.coordinator_adapter import CoordinatorAdapter
    from .connect_trainer_command import ConnectTrainerCommand, ConnectTrainerResult

logger = logging.getLogger(__name__)


class ConnectTrainerCommandHandler:
    """Handles ConnectTrainerCommand by reading node ID from state and registering with Coordinator."""

    def __init__(
        self,
        trainer_state: TrainerState,
        coordinator_adapter: CoordinatorAdapter,
    ) -> None:
        self.trainer_state = trainer_state
        self.coordinator_adapter = coordinator_adapter

    def handle(
        self, command: Optional[ConnectTrainerCommand] = None
    ) -> ConnectTrainerResult:
        """Execute the connect trainer command.

        Reads the client_node_id from state and transmits it to Coordinator via coordinator_adapter.
        """
        node_id = self.trainer_state.client_node_id
        logger.info("[ConnectTrainerCommandHandler] Reading node identity from state: '%s'", node_id)

        adapter_result = self.coordinator_adapter.connect_trainer(node_id)

        if adapter_result.success:
            trainer_id = adapter_result.trainer_id or ""
            self.trainer_state.mark_connected(trainer_id)
            logger.info(
                "[ConnectTrainerCommandHandler] Connection confirmed by Coordinator. Assigned Trainer ID: %s",
                trainer_id,
            )
            return ConnectTrainerResult(
                success=True,
                description=adapter_result.description,
                trainer_id=trainer_id,
                status_code=adapter_result.status_code,
            )
        else:
            self.trainer_state.mark_disconnected()
            logger.warning(
                "[ConnectTrainerCommandHandler] Connection failed: %s",
                adapter_result.description,
            )
            return ConnectTrainerResult(
                success=False,
                description=adapter_result.description,
                trainer_id=None,
                status_code=adapter_result.status_code,
            )
