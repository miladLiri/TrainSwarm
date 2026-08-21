"""In-memory state management for the Trainer application."""

from typing import Optional
from domain.models import TrainerNode, PeerSession, TrainerStatus


class TrainerState:
    """Manages the in-memory state of the running trainer node."""

    def __init__(self, node_id: str, bootstrap_url: str, coordinator_url: str):
        self._node = TrainerNode(
            node_id=node_id,
            bootstrap_url=bootstrap_url,
            coordinator_url=coordinator_url,
        )

    @property
    def node_id(self) -> str:
        return self._node.node_id

    @property
    def bootstrap_url(self) -> str:
        return self._node.bootstrap_url

    @property
    def coordinator_url(self) -> str:
        return self._node.coordinator_url

    @property
    def status(self) -> TrainerStatus:
        return self._node.status

    @property
    def peer_session(self) -> Optional[PeerSession]:
        return self._node.peer_session

    @property
    def peer_id(self) -> Optional[str]:
        return self._node.peer_session.peer_id if self._node.peer_session else None

    def set_peer_session(self, peer_session: PeerSession) -> None:
        """Updates the registered peer session and status."""
        self._node.peer_session = peer_session
        self._node.status = TrainerStatus.REGISTERED

    def set_status(self, status: TrainerStatus) -> None:
        """Updates current node status."""
        self._node.status = status

    def clear_peer_session(self) -> None:
        """Clears the registered peer session and marks disconnected."""
        self._node.peer_session = None
        self._node.status = TrainerStatus.DISCONNECTED

