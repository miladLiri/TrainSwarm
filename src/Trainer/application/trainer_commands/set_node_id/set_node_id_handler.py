"""Handler for SetNodeIdCommand in Trainer."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Trainer.application.state import TrainerState
    from Trainer.infrastructure.adapters.trainer_p2p_node_adapter import ITrainerP2PNodeAdapter
except ImportError:
    from application.state import TrainerState
    from infrastructure.adapters.trainer_p2p_node_adapter import ITrainerP2PNodeAdapter

from .set_node_id_command import SetNodeIdCommand

logger = logging.getLogger("trainswarm.trainer.set_node_id")


class SetNodeIdCommandHandler:
    """Queries local p2p-node via adapter and records its peer ID in TrainerState."""

    def __init__(
        self,
        trainer_state: TrainerState,
        p2p_node_adapter: ITrainerP2PNodeAdapter,
    ) -> None:
        self.trainer_state = trainer_state
        self.p2p_node_adapter = p2p_node_adapter

    def handle(self, command: Optional[SetNodeIdCommand] = None) -> str:
        """Query local p2p-node and update state."""
        logger.info("[SetNodeIdCommandHandler] Querying local p2p-node for peer identity...")
        node_id = self.p2p_node_adapter.get_p2p_node_id()
        self.trainer_state.set_node_id(node_id)
        logger.info("[SetNodeIdCommandHandler] Updated TrainerState with P2P node ID: %s", node_id)
        return node_id
