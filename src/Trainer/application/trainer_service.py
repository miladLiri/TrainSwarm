"""Application use cases and services for the Trainer node."""

from typing import Optional, List, Dict, Any
from domain.models import PeerSession, TrainerStatus
from application.state import TrainerState
from infrastructure.bootstrap_client import BootstrapClient, BootstrapError
from infrastructure.coordinator_client import CoordinatorClient


class TrainerService:
    """Coordinates Trainer network lifecycle, Bootstrap registration, and peer queries."""

    def __init__(
        self,
        trainer_state: TrainerState,
        bootstrap_client: BootstrapClient,
        coordinator_client: CoordinatorClient,
    ):
        self.trainer_state = trainer_state
        self.bootstrap_client = bootstrap_client
        self.coordinator_client = coordinator_client

    def register_with_bootstrap(self, endpoint: Optional[str] = None) -> PeerSession:
        """Registers with Bootstrap relay and updates local node state."""
        try:
            peer_session = self.bootstrap_client.register_peer(
                node_id=self.trainer_state.node_id,
                role="trainer",
                endpoint=endpoint,
            )
            self.trainer_state.set_peer_session(peer_session)
            return peer_session
        except BootstrapError as e:
            self.trainer_state.clear_peer_session()
            raise e

    def list_peers(self) -> List[Dict[str, Any]]:
        """Queries Bootstrap relay for active swarm peers."""
        return self.bootstrap_client.list_peers()

    def check_coordinator_health(self) -> Dict[str, Any]:
        """Checks if the Coordinator is reachable."""
        return self.coordinator_client.check_health()

