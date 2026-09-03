"""Entry point for the TrainSwarm Client console application."""

import sys
from config import config
from application.state import ClientState
from application.session_service import SessionService
from infrastructure.coordinator_client import HttpCoordinatorClient
from infrastructure.bootstrap_client import BootstrapClient, BootstrapError
from infrastructure.persistence import (
    DatabaseManager,
    TrainingShardRepository,
    DatabaseInitializationError,
)
from presentation.console_ui import ConsoleUI


def main() -> int:
    # 1. Initialize State
    client_state = ClientState(
        node_id=config.client_node_id,
        coordinator_url=config.coordinator_url,
        bootstrap_url=config.bootstrap_url,
    )

    # 2. Initialize Infrastructure Clients & Persistence
    coordinator_client = HttpCoordinatorClient(
        base_url=config.coordinator_url,
        timeout=config.request_timeout_seconds,
    )
    bootstrap_client = BootstrapClient(
        base_url=config.bootstrap_url,
        timeout=config.request_timeout_seconds,
    )
    db_manager = DatabaseManager()
    try:
        db_manager.initialize()
        shard_repository = TrainingShardRepository(db_manager)
        print(f"[Client] Local persistence initialized at: {db_manager.db_path}")
    except DatabaseInitializationError as e:
        print(f"[Client] [ERROR] Failed to initialize local persistence: {e}")
        shard_repository = None

    # 3. Initialize Application Service
    session_service = SessionService(
        coordinator_client=coordinator_client,
        bootstrap_client=bootstrap_client,
        client_state=client_state,
    )

    # 4. Attempt automatic startup registration with Bootstrap relay
    try:
        data = session_service.register_with_bootstrap()
        print(f"[Client] Auto-registered with Bootstrap Relay! Assigned Peer ID: {data.get('peerId')}")
    except BootstrapError as e:
        print(f"[Client] [WARN] Could not connect to Bootstrap Relay at startup: {str(e)}")
        print("[Client] [INFO] You can retry connection at any time using menu option 3.")

    # 5. Initialize Presentation UI & Run REPL loop
    ui = ConsoleUI(session_service=session_service)
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())