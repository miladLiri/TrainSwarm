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
            "[StartTrainingHandler] Received StartTrainingCommand - ClientNodeId: %s, ModelId: %s, ModelVersion: %s, DataSetId: %s, ShardId: %s",
            command.client_node_id,
            command.model_id,
            command.model_version,
            command.data_set_id,
            command.shard_id,
        )
        print(
            f"\n[Trainer] [COMMAND RECEIVED] StartTraining -> ClientNodeId: {command.client_node_id}, "
            f"ModelId: {command.model_id}, ModelVersion: {command.model_version}, "
            f"DataSetId: {command.data_set_id}, ShardId: {command.shard_id}"
        )
        self.trainer_state.set_status("TRAINING")
        self.trainer_state.add_assigned_task(command.shard_id)
