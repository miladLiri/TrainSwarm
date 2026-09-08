"""Handler for SetNodeIdCommand in Client."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Client.application.state import ClientState
    from Client.infrastructure.adapters.client_p2p_node_adapter import IClientP2PNodeAdapter
except ImportError:
    from application.state import ClientState
    from infrastructure.adapters.client_p2p_node_adapter import IClientP2PNodeAdapter

from .set_node_id_command import SetNodeIdCommand

logger = logging.getLogger("trainswarm.client.set_node_id")


class SetNodeIdCommandHandler:
    """Queries local p2p-node via adapter and records its peer ID in ClientState and configuration."""

    def __init__(
        self,
        client_state: Optional[ClientState],
        p2p_node_adapter: IClientP2PNodeAdapter,
        client_config: Optional[object] = None,
    ) -> None:
        self.client_state = client_state
        self.p2p_node_adapter = p2p_node_adapter
        self.client_config = client_config

    def handle(self, command: Optional[SetNodeIdCommand] = None) -> str:
        """Query local p2p-node and update state and config."""
        logger.info("[SetNodeIdCommandHandler] Querying local p2p-node for peer identity...")
        node_id = self.p2p_node_adapter.get_p2p_node_id()

        if self.client_state is not None:
            self.client_state.set_node_id(node_id)

        if self.client_config is not None:
            try:
                object.__setattr__(self.client_config, "client_node_id", node_id)
            except Exception:
                pass

        logger.info("[SetNodeIdCommandHandler] Updated ClientState with P2P node ID: %s", node_id)
        return node_id
