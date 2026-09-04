"""Centralized configuration manager for TrainSwarm Client."""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional, Union

from .exceptions import (
    ClientConfigurationError,
    InvalidConfigurationValueError,
    MissingConfigurationError,
)
from .models import ClientConfig

logger = logging.getLogger("trainswarm.client.config")


class ConfigManager:
    """Sole authoritative component responsible for reading and validating Client environment variables."""

    ENV_COORDINATOR_ADDRESS = "COORDINATOR_ADDRESS"
    FALLBACK_ENV_COORDINATOR_URL = "COORDINATOR_URL"
    ENV_CLIENT_NODE_ID = "CLIENT_NODE_ID"
    ENV_REQUEST_TIMEOUT = "REQUEST_TIMEOUT_SECONDS"
    ENV_DB_PATH = "TRAINING_CLIENT_DB_PATH"
    ENV_SHARD_TRAINING_TIME_LIMIT = "SHARD_TRAINING_TIME_LIMIT"
    ENV_SHARD_SAFETY_FACTOR = "SHARD_SAFETY_FACTOR"
    ENV_WORKING_DIR = "TRAINING_WORKING_DIRECTORY"

    DEFAULT_CLIENT_NODE_ID = "client-node-dev"
    DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
    DEFAULT_DB_PATH = "./training.db"
    DEFAULT_SHARD_TRAINING_TIME_LIMIT = 300.0
    DEFAULT_SHARD_SAFETY_FACTOR = 1.0
    DEFAULT_WORKING_DIR = "."

    def __init__(self, env_file: Optional[Union[str, Path]] = None) -> None:
        self._load_dotenv(env_file)
        self._config: ClientConfig = self._build_config()

    def _load_dotenv(self, env_file: Optional[Union[str, Path]] = None) -> None:
        """Attempt to load .env file if python-dotenv is present."""
        try:
            from dotenv import load_dotenv

            if env_file is not None:
                resolved_env = Path(env_file).resolve()
                if resolved_env.is_file():
                    load_dotenv(dotenv_path=resolved_env)
            else:
                # Default search: alongside config or client root
                client_root = Path(__file__).resolve().parent.parent
                default_env = client_root / ".env"
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

    def _resolve_client_node_id(self) -> str:
        raw = os.getenv(self.ENV_CLIENT_NODE_ID, "").strip()
        return raw if raw else self.DEFAULT_CLIENT_NODE_ID

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

    def _resolve_db_path(self) -> Path:
        raw = os.getenv(self.ENV_DB_PATH, "").strip()
        if not raw:
            return Path(self.DEFAULT_DB_PATH).resolve()
        return Path(raw).resolve()

    def _resolve_shard_training_time_limit(self) -> float:
        raw = os.getenv(self.ENV_SHARD_TRAINING_TIME_LIMIT, "").strip()
        if not raw:
            return self.DEFAULT_SHARD_TRAINING_TIME_LIMIT
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError("Must be strictly positive")
            return val
        except ValueError as e:
            raise InvalidConfigurationValueError(
                variable_name=self.ENV_SHARD_TRAINING_TIME_LIMIT,
                raw_value=raw,
                reason="Must be a positive numeric value in seconds.",
            ) from e

    def _resolve_shard_safety_factor(self) -> float:
        raw = os.getenv(self.ENV_SHARD_SAFETY_FACTOR, "").strip()
        if not raw:
            return self.DEFAULT_SHARD_SAFETY_FACTOR
        try:
            val = float(raw)
            if val <= 0.0 or val > 1.0:
                raise ValueError("Must be between 0.0 (exclusive) and 1.0 (inclusive)")
            return val
        except ValueError as e:
            raise InvalidConfigurationValueError(
                variable_name=self.ENV_SHARD_SAFETY_FACTOR,
                raw_value=raw,
                reason="Must be a numeric value between 0.0 (exclusive) and 1.0 (inclusive).",
            ) from e

    def _resolve_working_directory(self) -> Path:
        raw = os.getenv(self.ENV_WORKING_DIR, "").strip()
        if not raw:
            return Path(self.DEFAULT_WORKING_DIR).resolve()
        return Path(raw).resolve()

    def _build_config(self) -> ClientConfig:
        """Parse, validate, and construct the ClientConfig instance."""
        coord_addr = self._resolve_coordinator_address()
        node_id = self._resolve_client_node_id()
        timeout = self._resolve_request_timeout()
        db_path = self._resolve_db_path()
        time_limit = self._resolve_shard_training_time_limit()
        safety_factor = self._resolve_shard_safety_factor()
        work_dir = self._resolve_working_directory()

        return ClientConfig(
            coordinator_address=coord_addr,
            client_node_id=node_id,
            request_timeout_seconds=timeout,
            db_path=db_path,
            shard_training_time_limit_seconds=time_limit,
            shard_safety_factor=safety_factor,
            working_directory=work_dir,
        )

    def get_config(self) -> ClientConfig:
        """Return the validated immutable ClientConfig."""
        return self._config
