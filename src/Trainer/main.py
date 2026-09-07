"""Entry point for the TrainSwarm Trainer console and GUI application."""

from __future__ import annotations
import logging
import os
from pathlib import Path
import sys
from typing import List, Optional

TRAINER_DIR = Path(__file__).resolve().parent
SRC_DIR = TRAINER_DIR.parent
for p in [str(TRAINER_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from config import ConfigManager, TrainerConfigurationError
from dependency_injection import DIContainer
from application.coordinator_commands import CommandDispatcher, CommandType, StartTrainingCommand, StartTrainingHandler
from infrastructure.coordinator_connection import TrainerCommandListener
from presentation.startup import run_startup
from presentation.console_ui import ConsoleUI

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("trainswarm.trainer")


def launch_gui(container: DIContainer) -> int:
    """Launch the PyQt6 desktop graphical user interface."""
    if sys.platform != "win32" and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        print(
            "[Trainer] [ERROR] No graphical display detected. "
            "Please run the trainer in headless CLI mode (python main.py).",
            file=sys.stderr,
        )
        return 1

    try:
        from presentation.gui.main_window import run_gui
        return run_gui(container)
    except ImportError as e:
        print(f"[Trainer] [ERROR] PyQt6 is required to run desktop GUI: {e}", file=sys.stderr)
        return 1


def main(raw_args: Optional[List[str]] = None) -> int:
    args = raw_args if raw_args is not None else sys.argv[1:]

    # 1. Initialize Configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()
    except TrainerConfigurationError as e:
        print(f"[Trainer] [ERROR] Configuration validation failed: {e}", file=sys.stderr)
        return 1

    # 2. Initialize Dependency Injection Container (Composition Root)
    container = DIContainer(config=config)

    # 3. Initialize Coordinator gRPC Command Dispatcher & Register Handlers
    dispatcher = CommandDispatcher()
    start_training_handler = StartTrainingHandler(trainer_state=container.state)
    dispatcher.register_handler(
        command_type=CommandType.StartTraining,
        model_class=StartTrainingCommand,
        handler=start_training_handler,
    )

    # 4. Start Background gRPC Command Stream Listener
    command_listener = TrainerCommandListener(
        trainer_node_id=config.trainer_node_id,
        coordinator_grpc_url=config.coordinator_grpc_address,
        command_dispatcher=dispatcher,
        reconnect_interval_seconds=5.0,
    )
    container.command_listener = command_listener
    command_listener.start()

    try:
        # 5. Execute Presentation Startup Guard (Halts with exit code 1 on failure)
        run_startup(container)

        # 6. Route to GUI or Headless CLI
        if args and args[0] == "gui":
            return launch_gui(container)

        ui = ConsoleUI(container=container)
        return ui.run(args)
    finally:
        command_listener.stop()


if __name__ == "__main__":
    sys.exit(main())
