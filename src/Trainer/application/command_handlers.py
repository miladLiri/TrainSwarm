"""Command handler contracts and implementations for the Trainer."""

import logging
from abc import ABC, abstractmethod
from typing import Any
from domain.commands import StartTrainingCommand
from application.state import TrainerState

logger = logging.getLogger(__name__)


class ICommandHandler(ABC):
    """Abstract base class for typed command handlers."""

    @abstractmethod
    def handle(self, command: Any) -> None:
        """Handle the strongly typed command."""
        pass


class StartTrainingHandler(ICommandHandler):
    """Handler for StartTrainingCommand."""

    def __init__(self, trainer_state: TrainerState):
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
