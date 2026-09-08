"""Composition root dependency injection container for TrainSwarm Client."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Client.config import ClientConfig, ConfigManager
    from Client.application.state import ClientState
    from Client.infrastructure.adapters import CoordinatorAdapter, ClientP2PNodeAdapter
    from Client.infrastructure.persistence import DatabaseManager, TrainingShardRepository, ModelRepository
    from Client.application.smoke_test import SmokeTestCommandHandler
    from Client.application.submit_training import SubmitTrainingCommandHandler
    from Client.application.commands.set_node_id import SetNodeIdCommandHandler
    from Client.application.commands.get_training_task import GetTrainingTaskCommandHandler
    from Client.application.commands.transfer_model import TransferModelCommandHandler
    from Client.application.commands.transfer_shard import TransferShardCommandHandler
    from Client.application.commands.update_model import UpdateModelCommandHandler
except ImportError:
    from config import ClientConfig, ConfigManager
    from application.state import ClientState
    from infrastructure.adapters import CoordinatorAdapter, ClientP2PNodeAdapter
    from infrastructure.persistence import DatabaseManager, TrainingShardRepository, ModelRepository
    from application.smoke_test import SmokeTestCommandHandler
    from application.submit_training import SubmitTrainingCommandHandler
    from application.commands.set_node_id import SetNodeIdCommandHandler
    from application.commands.get_training_task import GetTrainingTaskCommandHandler
    from application.commands.transfer_model import TransferModelCommandHandler
    from application.commands.transfer_shard import TransferShardCommandHandler
    from application.commands.update_model import UpdateModelCommandHandler

from distributed_training_engine.training import TrainingOrchestrator

logger = logging.getLogger("trainswarm.client.di")


class DIContainer:
    """Composition Root responsible for assembling infrastructure, persistence, and application handlers."""

    def __init__(self, config: Optional[ClientConfig] = None) -> None:
        self._config: ClientConfig = config or ConfigManager().get_config()

        logger.info("Initializing Composition Root with ClientConfig [node_id=%s, db=%s]",
                    self._config.client_node_id, self._config.db_path)

        # 1. Construct persistence
        self._database_manager = DatabaseManager(
            db_path=self._config.db_path,
            timeout=self._config.request_timeout_seconds,
        )
        self._shard_repository = TrainingShardRepository(database_manager=self._database_manager)
        self._model_repository = ModelRepository(db_manager=self._database_manager)

        # 2. Construct adapters
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

        # 3. Construct distributed training orchestrator
        self._training_orchestrator = TrainingOrchestrator()

        # 4. Construct application command handlers
        self._smoke_test_handler = SmokeTestCommandHandler(
            training_orchestrator=self._training_orchestrator,
            shard_training_time_limit=self._config.shard_training_time_limit_seconds,
            working_directory=self._config.working_directory,
            safety_factor=self._config.shard_safety_factor,
        )

        # 5. State Management & P2P Infrastructure
        self._state = ClientState(
            node_id=self._config.client_node_id,
            coordinator_url=self._config.coordinator_address or "",
        )
        self._p2p_node_adapter = ClientP2PNodeAdapter()
        self._set_node_id_handler = SetNodeIdCommandHandler(
            client_state=self._state,
            p2p_node_adapter=self._p2p_node_adapter,
            client_config=self._config,
        )

        self._submit_training_handler = SubmitTrainingCommandHandler(
            working_directory=self._config.working_directory,
            smoke_test_handler=self._smoke_test_handler,
            shard_repository=self._shard_repository,
            coordinator_adapter=self._coordinator_adapter,
            client_node_id=self._config.client_node_id,
            model_repository=self._model_repository,
            client_state=self._state,
        )
        self._get_training_task_handler = GetTrainingTaskCommandHandler(
            model_repository=self._model_repository,
            shard_repository=self._shard_repository,
        )
        self._transfer_model_handler = TransferModelCommandHandler(
            model_repository=self._model_repository,
        )
        self._transfer_shard_handler = TransferShardCommandHandler(
            shard_repository=self._shard_repository,
        )
        self._update_model_handler = UpdateModelCommandHandler(
            shard_repository=self._shard_repository,
        )

        self._p2p_node_adapter.get_training_task_handler = self._get_training_task_handler
        self._p2p_node_adapter.transfer_model_handler = self._transfer_model_handler
        self._p2p_node_adapter.transfer_shard_handler = self._transfer_shard_handler
        self._p2p_node_adapter.update_model_handler = self._update_model_handler

    @property
    def state(self) -> ClientState:
        """Access in-memory application state."""
        return self._state

    @property
    def p2p_node_adapter(self) -> ClientP2PNodeAdapter:
        """Access ClientP2PNodeAdapter."""
        return self._p2p_node_adapter

    @property
    def set_node_id_handler(self) -> SetNodeIdCommandHandler:
        """Access SetNodeIdCommandHandler."""
        return self._set_node_id_handler

    @property
    def get_training_task_handler(self) -> GetTrainingTaskCommandHandler:
        """Access GetTrainingTaskCommandHandler."""
        return self._get_training_task_handler

    @property
    def transfer_model_handler(self) -> TransferModelCommandHandler:
        """Access TransferModelCommandHandler."""
        return self._transfer_model_handler

    @property
    def transfer_shard_handler(self) -> TransferShardCommandHandler:
        """Access TransferShardCommandHandler."""
        return self._transfer_shard_handler

    @property
    def update_model_handler(self) -> UpdateModelCommandHandler:
        """Access UpdateModelCommandHandler."""
        return self._update_model_handler

    @property
    def config(self) -> ClientConfig:
        """Access the validated configuration."""
        return self._config

    @property
    def database_manager(self) -> DatabaseManager:
        """Access the SQLite DatabaseManager."""
        return self._database_manager

    @property
    def shard_repository(self) -> TrainingShardRepository:
        """Access the TrainingShardRepository wired to DatabaseManager."""
        return self._shard_repository

    @property
    def model_repository(self) -> ModelRepository:
        """Access the ModelRepository wired to DatabaseManager."""
        return self._model_repository

    @property
    def coordinator_adapter(self) -> Optional[CoordinatorAdapter]:
        """Access the CoordinatorAdapter wired with coordinator_address and timeout."""
        return self._coordinator_adapter

    @property
    def training_orchestrator(self) -> TrainingOrchestrator:
        """Access the type-agnostic TrainingOrchestrator."""
        return self._training_orchestrator

    @property
    def smoke_test_handler(self) -> SmokeTestCommandHandler:
        """Access the SmokeTestCommandHandler wired with orchestrator and time limit."""
        return self._smoke_test_handler

    @property
    def submit_training_handler(self) -> SubmitTrainingCommandHandler:
        """Access the SubmitTrainingCommandHandler wired with orchestrator, persistence, and adapters."""
        if hasattr(self, "_state") and self._state and self._state.client_node_id:
            self._submit_training_handler.client_node_id = self._state.client_node_id
        return self._submit_training_handler
