"""Application use cases and services for session and peer management."""

from typing import Optional, List, Dict, Any
from domain.models import Session
from application.state import ClientState
from infrastructure.coordinator_client import HttpCoordinatorClient
from infrastructure.bootstrap_client import BootstrapClient, BootstrapError


class SessionService:
    """Coordinates session creation, Bootstrap relay connectivity, and local state management."""

    def __init__(
        self,
        coordinator_client: HttpCoordinatorClient,
        bootstrap_client: BootstrapClient,
        client_state: ClientState,
    ):
        self.coordinator_client = coordinator_client
        self.bootstrap_client = bootstrap_client
        self.client_state = client_state

    def register_with_bootstrap(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Registers client node with Bootstrap relay and stores peer ID."""
        data = self.bootstrap_client.register_peer(
            node_id=self.client_state.node_id,
            role="client",
            endpoint=endpoint,
        )
        peer_id = str(data.get("peerId", ""))
        if peer_id:
            self.client_state.set_peer_id(peer_id)
        return data

    def list_peers(self) -> List[Dict[str, Any]]:
        """Queries Bootstrap relay for active swarm peers."""
        return self.bootstrap_client.list_peers()

    def create_session(self, name: Optional[str] = None) -> Session:
        """Executes the create session use case and updates active state."""
        session = self.coordinator_client.create_session(
            client_node_id=self.client_state.node_id,
            name=name,
        )
        self.client_state.set_active_session(session)
        return session

    def get_active_session(self) -> Optional[Session]:
        """Retrieves the currently active session from local state."""
        return self.client_state.active_session