"""Startup routine and connection guard for TrainSwarm Trainer presentation."""

from __future__ import annotations
import logging
import sys
from typing import Any

try:
    from Trainer.infrastructure.coordinator_connection import TrainerCommandListener
    from Trainer.application.coordinator_commands import (
        CommandDispatcher,
        CommandType,
        StartTrainingCommand,
        StartTrainingHandler,
    )
except ImportError:
    from infrastructure.coordinator_connection import TrainerCommandListener
    from application.coordinator_commands import (
        CommandDispatcher,
        CommandType,
        StartTrainingCommand,
        StartTrainingHandler,
    )

logger = logging.getLogger(__name__)

_has_run = False


def run_startup(container: Any) -> bool:
    """Execute the startup connection routine and command listener.

    Guarantees single execution across presentation entry points.
    Invokes ConnectTrainerCommandHandler and aborts application execution with an
    error if the connection fails.
    Upon successful connection, initializes and starts TrainerCommandListener.
    """
    global _has_run
    if _has_run:
        return True

    print("========================================")
    print("        TrainSwarm Trainer Node         ")
    print("========================================")
    print("[Trainer] Running startup connection guard...")

    handler = getattr(container, "connect_trainer_handler", None)
    if not handler:
        print(
            "[Trainer] [FATAL ERROR] ConnectTrainerCommandHandler is not configured in DIContainer.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = handler.handle()
    if not result.success:
        print(
            f"[Trainer] [FATAL ERROR] Could not connect to Coordinator: {result.description}",
            file=sys.stderr,
        )
        logger.error("[TrainerStartup] Aborting startup due to connection failure: %s", result.description)
        sys.exit(1)

    print(f"[Trainer] Successfully connected to Coordinator! Registration ID: {result.trainer_id}")

    # Initialize and start TrainerCommandListener
    command_listener = getattr(container, "command_listener", None)
    if not command_listener:
        dispatcher = getattr(container, "command_dispatcher", None)
        if not dispatcher:
            dispatcher = CommandDispatcher()
            start_training_handler = StartTrainingHandler(trainer_state=container.state)
            dispatcher.register_handler(
                command_type=CommandType.StartTraining,
                model_class=StartTrainingCommand,
                handler=start_training_handler,
            )
            container.command_dispatcher = dispatcher

        config = container.config
        node_identity = getattr(container.state, "client_node_id", config.trainer_node_id)
        command_listener = TrainerCommandListener(
            trainer_node_id=node_identity,
            coordinator_grpc_url=config.coordinator_grpc_address,
            command_dispatcher=dispatcher,
            reconnect_interval_seconds=5.0,
        )
        container.command_listener = command_listener

    command_listener.start()
    print(f"[Trainer] Command listener started for trainer '{node_identity}'.")

    _has_run = True
    return True


def reset_startup_flag() -> None:
    """Reset the execution flag (primarily for testing)."""
    global _has_run
    _has_run = False
