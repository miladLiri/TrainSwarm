"""Entry point for the TrainSwarm Client console and GUI application."""

import logging
import os
from pathlib import Path
import sys
from typing import List, Optional

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


def launch_gui(container: DIContainer) -> int:
    """Launch the PyQt6 desktop graphical user interface."""
    # Check for display server on Linux/macOS
    if sys.platform != "win32" and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        print(
            "[Client] [ERROR] No graphical display detected. "
            "Please run the client in CLI mode (e.g. python main.py submit-training --help).",
            file=sys.stderr,
        )
        return 1

    try:
        from presentation.gui.main_window import run_gui
        return run_gui(container)
    except ImportError as e:
        print(f"[Client] [ERROR] PyQt6 is required to run the desktop GUI: {e}", file=sys.stderr)
        print("[Client] [TIP] Install GUI dependencies via: pip install -r requirements-gui.txt", file=sys.stderr)
        return 1


def main(raw_args: Optional[List[str]] = None) -> int:
    args = raw_args if raw_args is not None else sys.argv[1:]

    # For help flag without boot
    if args and ("-h" in args or "--help" in args):
        parser = ConsoleUI.build_parser()
        parser.parse_args(args)
        return 0

    # 1. Initialize and validate centralized configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()
        if not args or args[0] not in ("submit-training", "gui"):
            print("========================================")
            print("       TrainSwarm Training Client       ")
            print("========================================")
            print(f"[Client] Configuration loaded successfully for node: {config.client_node_id}")
    except ClientConfigurationError as e:
        print(f"[Client] [ERROR] Configuration validation failed: {e}", file=sys.stderr)
        return 1

    # 2. Initialize Composition Root (Dependency Injection)
    container = DIContainer(config=config)

    # 3. Initialize Local SQLite Persistence
    try:
        container.database_manager.initialize()
        if not args or args[0] not in ("submit-training", "gui"):
            print(f"[Client] Local persistence initialized at: {container.database_manager.db_path}")
    except DatabaseInitializationError as e:
        print(f"[Client] [ERROR] Failed to initialize local persistence: {e}", file=sys.stderr)
        return 1

    # 4. Report Coordinator Adapter status
    if not args or args[0] not in ("submit-training", "gui"):
        if container.coordinator_adapter:
            print(f"[Client] Coordinator adapter initialized for: {container.coordinator_adapter.base_url}")
        else:
            print("[Client] [WARN] Coordinator adapter not configured at startup.")

    # 5. Route to GUI or Console UI
    if args and args[0] == "gui":
        return launch_gui(container)

    ui = ConsoleUI(submit_training_handler=container.submit_training_handler)
    return ui.run(args)


if __name__ == "__main__":
    sys.exit(main())
