"""Entry point for the TrainSwarm Client console application."""

import logging
import sys
from config import config
from infrastructure.adapters import (
    CoordinatorAdapter,
    CoordinatorConfigurationError,
)
from infrastructure.persistence import (
    DatabaseManager,
    TrainingShardRepository,
    DatabaseInitializationError,
)
from presentation.console_ui import ConsoleUI

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("trainswarm.client")


def main() -> int:
    print("========================================")
    print("       TrainSwarm Training Client       ")
    print("========================================")

    # 1. Initialize Local SQLite Persistence
    db_manager = DatabaseManager()
    try:
        db_manager.initialize()
        shard_repository = TrainingShardRepository(db_manager)
        print(f"[Client] Local persistence initialized at: {db_manager.db_path}")
    except DatabaseInitializationError as e:
        print(f"[Client] [ERROR] Failed to initialize local persistence: {e}")
        return 1

    # 2. Initialize Coordinator Adapter
    try:
        coordinator_adapter = CoordinatorAdapter(
            coordinator_address=config.coordinator_address,
            timeout_seconds=config.request_timeout_seconds,
        )
        print(f"[Client] Coordinator adapter initialized for: {coordinator_adapter.base_url}")
    except CoordinatorConfigurationError as e:
        print(f"[Client] [WARN] Coordinator adapter not configured at startup: {e}")
        print("[Client] [INFO] Set COORDINATOR_ADDRESS to enable Coordinator task creation.")
        coordinator_adapter = None

    # 3. Launch Console UI
    ui = ConsoleUI()
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
