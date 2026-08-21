"""Application use cases and services for session management."""

from typing import Optional
from domain.models import Session
from application.state import ClientState
from infrastructure.coordinator_client import HttpCoordinatorClient


class SessionService:
    """Coordinates session creation and local state management."""

    def __init__(self, coordinator_client: HttpCoordinatorClient, client_state: ClientState):
        self.coordinator_client = coordinator_client
        self.client_state = client_state

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