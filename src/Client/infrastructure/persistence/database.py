"""SQLite persistence infrastructure and connection manager for TrainSwarm Client."""

from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Generator, Optional, Union

from .exceptions import (
    DatabaseConfigurationError,
    DatabaseInitializationError,
)

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS training_shards (
    id TEXT PRIMARY KEY NOT NULL,
    model_id TEXT NOT NULL,
    model_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    shard_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count > 0),
    status TEXT NOT NULL,
    metrics TEXT NULL,
    training_metadata TEXT NULL,
    update_artifact_path TEXT NULL,
    training_task_id TEXT NULL
);
"""

CREATE_UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_training_shards_logical_shard
ON training_shards (model_id, model_version, dataset_id, shard_id);
"""


class DatabaseManager:
    """Manages SQLite database configuration, connection lifecycle, and idempotent schema initialization."""

    def __init__(self, db_path: Union[str, Path] = Path("./training.db"), timeout: float = 5.0) -> None:
        """Initialize DatabaseManager.

        Args:
            db_path: Explicit filesystem path for SQLite database.
            timeout: Timeout in seconds for acquiring database locks.
        """
        self.timeout = timeout
        self.db_path = self._resolve_db_path(db_path)

    @staticmethod
    def _resolve_db_path(db_path: Union[str, Path]) -> Path:
        """Resolve and validate database path."""
        if db_path is None:
            raise DatabaseConfigurationError("Missing required db_path parameter.")
        raw_path = str(db_path).strip()
        if not raw_path:
            raise DatabaseConfigurationError("Database path cannot be an empty string.")
        return Path(raw_path).resolve()

    def initialize(self) -> None:
        """Ensure parent directories exist and create tables and indexes idempotently.

        Raises:
            DatabaseInitializationError: If directory creation or schema execution fails.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise DatabaseInitializationError(
                f"Failed to create parent directory for SQLite database at '{self.db_path.parent}': {e}"
            ) from e

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(CREATE_TABLE_SQL)
                cursor.execute(CREATE_UNIQUE_INDEX_SQL)
                conn.commit()
            logger.info("SQLite database schema initialized successfully at '%s'", self.db_path)
        except sqlite3.Error as e:
            raise DatabaseInitializationError(
                f"Failed to initialize SQLite database schema at '{self.db_path}': {e}"
            ) from e

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing a thread-safe, scoped SQLite connection.

        Yields:
            sqlite3.Connection configured with row_factory and busy_timeout.

        Raises:
            DatabaseInitializationError: If connection cannot be established.
        """
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=self.timeout)
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {int(self.timeout * 1000)};")
            conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        except sqlite3.Error as e:
            if conn:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        finally:
            if conn:
                conn.close()
