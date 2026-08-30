"""Entry point for the TrainSwarm Trainer console application."""

import sys
from config import config
from domain.commands import CommandType, StartTrainingCommand
from application.state import TrainerState
from application.trainer_service import TrainerService
from application.command_dispatcher import CommandDispatcher
from application.command_handlers import StartTrainingHandler
from infrastructure.bootstrap_client import BootstrapClient, BootstrapError
from infrastructure.coordinator_client import CoordinatorClient
from infrastructure.trainer_command_listener import TrainerCommandListener
from presentation.console_ui import ConsoleUI


def main() -> int:
    # 1. Initialize State
    trainer_state = TrainerState(
        node_id=config.trainer_node_id,
        bootstrap_url=config.bootstrap_url,
        coordinator_url=config.coordinator_url,
    )

    # 2. Initialize Infrastructure Clients
    bootstrap_client = BootstrapClient(
        base_url=config.bootstrap_url,
        timeout=config.request_timeout_seconds,
    )
    coordinator_client = CoordinatorClient(
        base_url=config.coordinator_url,
        timeout=config.request_timeout_seconds,
    )

    # 3. Initialize Command Dispatcher & Register Handlers
    command_dispatcher = CommandDispatcher()
    start_training_handler = StartTrainingHandler(trainer_state=trainer_state)
    command_dispatcher.register_handler(
        command_type=CommandType.StartTraining,
        model_class=StartTrainingCommand,
        handler=start_training_handler,
    )

    # 4. Start Background gRPC Command Stream Listener
    command_listener = TrainerCommandListener(
        trainer_node_id=config.trainer_node_id,
        coordinator_grpc_url=config.coordinator_grpc_url,
        command_dispatcher=command_dispatcher,
        reconnect_interval_seconds=5.0,
    )
    command_listener.start()

    # 5. Initialize Application Service
    trainer_service = TrainerService(
        trainer_state=trainer_state,
        bootstrap_client=bootstrap_client,
        coordinator_client=coordinator_client,
    )

    # 6. Attempt automatic startup registration with Bootstrap relay
    try:
        peer_session = trainer_service.register_with_bootstrap()
        print(f"[Trainer] Auto-registered with Bootstrap Relay! Assigned Peer ID: {peer_session.peer_id}")
    except BootstrapError as e:
        print(f"[Trainer] [WARN] Could not connect to Bootstrap Relay at startup: {str(e)}")
        print("[Trainer] [INFO] You can retry connection at any time using menu option 2.")

    # 7. Initialize Presentation UI & Run REPL loop
    try:
        ui = ConsoleUI(trainer_service=trainer_service)
        ui.run()
    finally:
        command_listener.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
