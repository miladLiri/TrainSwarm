"""Entry point for the TrainSwarm Client console application."""

import logging
from pathlib import Path
import sys

CLIENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CLIENT_DIR.parent
for p in [str(CLIENT_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from config import ConfigManager, ClientConfigurationError
from dependency_injection import DIContainer
from infrastructure.persistence import DatabaseInitializationError
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

    # 1. Initialize and validate centralized configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()
        print(f"[Client] Configuration loaded successfully for node: {config.client_node_id}")
    except ClientConfigurationError as e:
        print(f"[Client] [ERROR] Configuration validation failed: {e}")
        return 1

    # 2. Initialize Composition Root (Dependency Injection)
    container = DIContainer(config=config)

    # 3. Initialize Local SQLite Persistence
    try:
        container.database_manager.initialize()
        print(f"[Client] Local persistence initialized at: {container.database_manager.db_path}")
    except DatabaseInitializationError as e:
        print(f"[Client] [ERROR] Failed to initialize local persistence: {e}")
        return 1

    # 4. Report Coordinator Adapter status
    if container.coordinator_adapter:
        print(f"[Client] Coordinator adapter initialized for: {container.coordinator_adapter.base_url}")
    else:
        print("[Client] [WARN] Coordinator adapter not configured at startup.")

    # 5. Launch Console UI
    ui = ConsoleUI()
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
