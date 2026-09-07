"""Centralized configuration manager for TrainSwarm Trainer."""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional, Union

from .exceptions import (
    TrainerConfigurationError,
    InvalidConfigurationValueError,
    MissingConfigurationError,
)
from .models import TrainerConfig

logger = logging.getLogger("trainswarm.trainer.config")


class ConfigManager:
    """Sole authoritative component responsible for reading and validating Trainer environment variables."""

    ENV_COORDINATOR_ADDRESS = "COORDINATOR_ADDRESS"
    FALLBACK_ENV_COORDINATOR_URL = "COORDINATOR_URL"
    ENV_COORDINATOR_GRPC_ADDRESS = "COORDINATOR_GRPC_ADDRESS"
    FALLBACK_ENV_COORDINATOR_GRPC_URL = "COORDINATOR_GRPC_URL"
    ENV_TRAINER_NODE_ID = "TRAINER_NODE_ID"
    ENV_REQUEST_TIMEOUT = "REQUEST_TIMEOUT_SECONDS"
    ENV_WORKING_DIR = "TRAINER_WORKING_DIRECTORY"
    FALLBACK_ENV_WORKING_DIR = "TRAINING_WORKING_DIRECTORY"

    DEFAULT_TRAINER_NODE_ID = "trainer-node-01"
    DEFAULT_COORDINATOR_GRPC_ADDRESS = "localhost:5000"
    DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
    DEFAULT_WORKING_DIR = "/artifacts"

    def __init__(self, env_file: Optional[Union[str, Path]] = None) -> None:
        self._load_dotenv(env_file)
        self._config: TrainerConfig = self._build_config()

    def _load_dotenv(self, env_file: Optional[Union[str, Path]] = None) -> None:
        """Attempt to load .env file if python-dotenv is present."""
        try:
            from dotenv import load_dotenv

            if env_file is not None:
                resolved_env = Path(env_file).resolve()
                if resolved_env.is_file():
                    load_dotenv(dotenv_path=resolved_env)
            else:
                trainer_root = Path(__file__).resolve().parent.parent
                default_env = trainer_root / ".env"
                if default_env.is_file():
                    load_dotenv(dotenv_path=default_env)
        except ImportError:
            pass

    def _resolve_coordinator_address(self) -> str:
        raw = os.getenv(self.ENV_COORDINATOR_ADDRESS, "").strip()
        if not raw:
            raw = os.getenv(self.FALLBACK_ENV_COORDINATOR_URL, "").strip()

        if not raw:
            raise MissingConfigurationError(
                self.ENV_COORDINATOR_ADDRESS,
                f"Missing required environment variable '{self.ENV_COORDINATOR_ADDRESS}'.",
            )
        return raw.rstrip("/")

    def _resolve_coordinator_grpc_address(self) -> str:
        raw = os.getenv(self.ENV_COORDINATOR_GRPC_ADDRESS, "").strip()
        if not raw:
            raw = os.getenv(self.FALLBACK_ENV_COORDINATOR_GRPC_URL, "").strip()

        if not raw:
            raw = self.DEFAULT_COORDINATOR_GRPC_ADDRESS

        if "://" in raw:
            raw = raw.split("://", 1)[1]
        return raw.rstrip("/")

    def _resolve_trainer_node_id(self) -> str:
        raw = os.getenv(self.ENV_TRAINER_NODE_ID, "").strip()
        return raw if raw else self.DEFAULT_TRAINER_NODE_ID

    def _resolve_request_timeout(self) -> float:
        raw = os.getenv(self.ENV_REQUEST_TIMEOUT, "").strip()
        if not raw:
            return self.DEFAULT_REQUEST_TIMEOUT_SECONDS
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError("Must be strictly positive")
            return val
        except ValueError as e:
            raise InvalidConfigurationValueError(
                variable_name=self.ENV_REQUEST_TIMEOUT,
                raw_value=raw,
                reason="Must be a positive numeric value in seconds.",
            ) from e

    def _resolve_working_directory(self) -> Path:
        raw = os.getenv(self.ENV_WORKING_DIR, "").strip()
        if not raw:
            raw = os.getenv(self.FALLBACK_ENV_WORKING_DIR, "").strip()
        if not raw:
            default_path = Path(self.DEFAULT_WORKING_DIR)
            if default_path.is_dir():
                return default_path.resolve()
            return Path(".").resolve()
        return Path(raw).resolve()

    def _build_config(self) -> TrainerConfig:
        """Parse, validate, and construct the TrainerConfig instance."""
        coord_addr = self._resolve_coordinator_address()
        grpc_addr = self._resolve_coordinator_grpc_address()
        node_id = self._resolve_trainer_node_id()
        timeout = self._resolve_request_timeout()
        work_dir = self._resolve_working_directory()

        return TrainerConfig(
            coordinator_address=coord_addr,
            coordinator_grpc_address=grpc_addr,
            trainer_node_id=node_id,
            request_timeout_seconds=timeout,
            working_directory=work_dir,
        )

    def get_config(self) -> TrainerConfig:
        """Return the validated immutable TrainerConfig."""
        return self._config
