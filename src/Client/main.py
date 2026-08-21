"""Entry point for the TrainSwarm Client console application."""

import sys
from config import config
from application.state import ClientState
from application.session_service import SessionService
from infrastructure.coordinator_client import HttpCoordinatorClient
from presentation.console_ui import ConsoleUI


def main() -> int:
    # 1. Initialize State
    client_state = ClientState(
        node_id=config.client_node_id,
        coordinator_url=config.coordinator_url,
    )

    # 2. Initialize Infrastructure
    coordinator_client = HttpCoordinatorClient(
        base_url=config.coordinator_url,
        timeout=config.request_timeout_seconds,
    )

    # 3. Initialize Application Service
    session_service = SessionService(
        coordinator_client=coordinator_client,
        client_state=client_state,
    )

    # 4. Initialize Presentation UI & Run
    ui = ConsoleUI(session_service=session_service)
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())