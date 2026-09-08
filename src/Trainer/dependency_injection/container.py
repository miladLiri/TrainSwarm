"""Composition root dependency injection container for TrainSwarm Trainer."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Trainer.config import ConfigManager, TrainerConfig
    from Trainer.application.state import TrainerState
    from Trainer.infrastructure.adapters import CoordinatorAdapter, TrainerP2PNodeAdapter
    from Trainer.application.trainer_commands.connect_trainer import ConnectTrainerCommandHandler
    from Trainer.application.trainer_commands.set_node_id import SetNodeIdCommandHandler
except ImportError:
    from config import ConfigManager, TrainerConfig
    from application.state import TrainerState
    from infrastructure.adapters import CoordinatorAdapter, TrainerP2PNodeAdapter
    from application.trainer_commands.connect_trainer import ConnectTrainerCommandHandler
    from application.trainer_commands.set_node_id import SetNodeIdCommandHandler

logger = logging.getLogger("trainswarm.trainer.di")


class DIContainer:
    """Composition Root responsible for assembling configuration, state, adapters, and handlers."""

    def __init__(self, config: Optional[TrainerConfig] = None) -> None:
        self._config: TrainerConfig = config or ConfigManager().get_config()
        logger.info(
            "Initializing Composition Root with TrainerConfig [node_id=%s, coordinator=%s]",
            self._config.trainer_node_id,
            self._config.coordinator_address,
        )

        # 1. State Management
        self._state = TrainerState()

        # 2. Infrastructure Adapters
        self._coordinator_adapter: Optional[CoordinatorAdapter] = None
        if self._config.coordinator_address:
            try:
                self._coordinator_adapter = CoordinatorAdapter(
                    coordinator_address=self._config.coordinator_address,
                    timeout_seconds=self._config.request_timeout_seconds,
                )
            except Exception as e:
                logger.warning("CoordinatorAdapter initialization failed: %s", e)
                self._coordinator_adapter = None

        self._p2p_node_adapter: TrainerP2PNodeAdapter = TrainerP2PNodeAdapter()

        # 3. Application Command Handlers
        self._connect_trainer_handler: Optional[ConnectTrainerCommandHandler] = None
        if self._coordinator_adapter:
            self._connect_trainer_handler = ConnectTrainerCommandHandler(
                trainer_state=self._state,
                coordinator_adapter=self._coordinator_adapter,
            )

        self._set_node_id_handler: SetNodeIdCommandHandler = SetNodeIdCommandHandler(
            trainer_state=self._state,
            p2p_node_adapter=self._p2p_node_adapter,
        )

        # 4. Background Command Listener and Dispatcher
        self._command_listener = None
        self._command_dispatcher = None

    @property
    def p2p_node_adapter(self) -> TrainerP2PNodeAdapter:
        """Access the TrainerP2PNodeAdapter."""
        return self._p2p_node_adapter

    @property
    def set_node_id_handler(self) -> SetNodeIdCommandHandler:
        """Access the SetNodeIdCommandHandler."""
        return self._set_node_id_handler

    @property
    def config(self) -> TrainerConfig:
        """Access the validated configuration."""
        return self._config

    @property
    def state(self) -> TrainerState:
        """Access in-memory application state."""
        return self._state

    @property
    def coordinator_adapter(self) -> Optional[CoordinatorAdapter]:
        """Access the Coordinator HTTP adapter."""
        return self._coordinator_adapter

    @property
    def connect_trainer_handler(self) -> Optional[ConnectTrainerCommandHandler]:
        """Access the ConnectTrainerCommandHandler."""
        return self._connect_trainer_handler

    @property
    def command_dispatcher(self):
        """Access the command dispatcher."""
        return self._command_dispatcher

    @command_dispatcher.setter
    def command_dispatcher(self, dispatcher) -> None:
        self._command_dispatcher = dispatcher

    @property
    def command_listener(self):
        """Access the gRPC command listener."""
        return self._command_listener

    @command_listener.setter
    def command_listener(self, listener) -> None:
        self._command_listener = listener
