"""Composition root dependency injection container for TrainSwarm Client."""

from __future__ import annotations
import logging
from typing import Optional

try:
    from Client.config import ClientConfig, ConfigManager
    from Client.infrastructure.adapters import CoordinatorAdapter
    from Client.infrastructure.persistence import DatabaseManager, TrainingShardRepository
    from Client.application.smoke_test import SmokeTestCommandHandler
    from Client.application.submit_training import SubmitTrainingCommandHandler
except ImportError:
    from config import ClientConfig, ConfigManager
    from infrastructure.adapters import CoordinatorAdapter
    from infrastructure.persistence import DatabaseManager, TrainingShardRepository
    from application.smoke_test import SmokeTestCommandHandler
    from application.submit_training import SubmitTrainingCommandHandler

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

        self._submit_training_handler = SubmitTrainingCommandHandler(
            working_directory=self._config.working_directory,
            smoke_test_handler=self._smoke_test_handler,
            shard_repository=self._shard_repository,
            coordinator_adapter=self._coordinator_adapter,
            client_node_id=self._config.client_node_id,
        )

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
        return self._submit_training_handler
