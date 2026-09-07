"""Handler for StartTrainingCommand received from Coordinator."""

from __future__ import annotations
import logging

try:
    from Trainer.application.state import TrainerState
    from Trainer.application.coordinator_commands.dispatcher import ICommandHandler
    from .command import StartTrainingCommand
except ImportError:
    from application.state import TrainerState
    from application.coordinator_commands.dispatcher import ICommandHandler
    from .command import StartTrainingCommand

logger = logging.getLogger(__name__)


class StartTrainingHandler(ICommandHandler):
    """Handler for StartTrainingCommand."""

    def __init__(self, trainer_state: TrainerState) -> None:
        self.trainer_state = trainer_state

    def handle(self, command: StartTrainingCommand) -> None:
        logger.info(
            "[StartTrainingHandler] Received StartTrainingCommand - Session: %s, Client: %s",
            command.session_id,
            command.training_client_node_id,
        )
        print(
            f"\n[Trainer] [COMMAND RECEIVED] StartTraining -> SessionId: {command.session_id}, ClientNodeId: {command.training_client_node_id}"
        )
        self.trainer_state.set_status("TRAINING")
        self.trainer_state.add_assigned_task(command.session_id)
