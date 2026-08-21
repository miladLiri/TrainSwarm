"""In-memory state management for the Client application."""

from typing import Optional
from domain.models import ClientNode, Session


class ClientState:
    """Manages the in-memory state of the running client node."""

    def __init__(self, node_id: str, coordinator_url: str, bootstrap_url: str = "http://localhost:6000"):
        self._node = ClientNode(
            node_id=node_id,
            coordinator_url=coordinator_url,
            bootstrap_url=bootstrap_url,
        )

    @property
    def node_id(self) -> str:
        return self._node.node_id

    @property
    def coordinator_url(self) -> str:
        return self._node.coordinator_url

    @property
    def bootstrap_url(self) -> str:
        return self._node.bootstrap_url

    @property
    def peer_id(self) -> Optional[str]:
        return self._node.peer_id

    def set_peer_id(self, peer_id: str) -> None:
        """Sets the assigned peer ID from Bootstrap relay."""
        self._node.peer_id = peer_id

    @property
    def active_session(self) -> Optional[Session]:
        return self._node.active_session

    def set_active_session(self, session: Session) -> None:
        """Sets or replaces the currently active training session."""
        self._node.active_session = session

    def clear_active_session(self) -> None:
        """Clears the currently active session."""
        self._node.active_session = None