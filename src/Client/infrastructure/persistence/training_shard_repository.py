"""Repository implementation for local dataset training shard persistence."""

from abc import ABC, abstractmethod
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from src.Client.domain.training_shard import TrainingShard, TrainingShardStatus
from .database import DatabaseManager
from .exceptions import (
    DuplicateShardError,
    PersistenceError,
    SerializationError,
)

logger = logging.getLogger(__name__)

INSERT_SHARD_SQL = """
INSERT INTO training_shards (
    id,
    model_id,
    model_type,
    model_version,
    dataset_id,
    shard_id,
    artifact_path,
    sample_count,
    status,
    metrics,
    training_metadata,
    update_artifact_path,
    training_task_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

SELECT_BY_ID_SQL = """
SELECT id, model_id, model_type, model_version, dataset_id, shard_id,
       artifact_path, sample_count, status, metrics, training_metadata,
       update_artifact_path, training_task_id
FROM training_shards
WHERE id = ?;
"""

SELECT_BY_SHARD_KEY_SQL = """
SELECT id, model_id, model_type, model_version, dataset_id, shard_id,
       artifact_path, sample_count, status, metrics, training_metadata,
       update_artifact_path, training_task_id
FROM training_shards
WHERE model_id = ? AND model_version = ? AND dataset_id = ? AND shard_id = ?;
"""


class ITrainingShardRepository(ABC):
    """Abstract interface for TrainingShard local persistence."""

    @abstractmethod
    def save(self, training_shard: TrainingShard) -> None:
        """Atomically persist a single TrainingShard.

        Args:
            training_shard: Domain model instance to persist.
        """
        pass

    @abstractmethod
    def bulk_save(self, training_shards: List[TrainingShard]) -> None:
        """Atomically persist a list of TrainingShard instances in a single transaction.

        Args:
            training_shards: List of domain models to persist.
        """
        pass

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[TrainingShard]:
        """Retrieve a TrainingShard by primary key id.

        Args:
            id: UUID string primary key.
        """
        pass

    @abstractmethod
    def get_by_shard_key(
        self,
        model_id: str,
        model_version: str,
        dataset_id: str,
        shard_id: str,
    ) -> Optional[TrainingShard]:
        """Retrieve a TrainingShard by composite key (model_id, model_version, dataset_id, shard_id)."""
        pass


class TrainingShardRepository(ITrainingShardRepository):
    """SQLite implementation of TrainingShardRepository."""

    def __init__(self, database_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize TrainingShardRepository.

        Args:
            database_manager: DatabaseManager instance managing SQLite connection and configuration.
        """
        self.db = database_manager if database_manager is not None else DatabaseManager()

    @staticmethod
    def _serialize_json(data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Serialize dictionary to JSON string."""
        if data is None:
            return None
        try:
            return json.dumps(data)
        except (TypeError, ValueError) as e:
            raise SerializationError(f"Failed to serialize dictionary to JSON: {e}") from e

    @staticmethod
    def _deserialize_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
        """Deserialize JSON string to dictionary."""
        if text is None:
            return None
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise SerializationError(f"Expected JSON object (dict), got {type(parsed)}")
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            raise SerializationError(f"Failed to deserialize JSON string '{text}': {e}") from e

    def _row_to_entity(self, row: sqlite3.Row) -> TrainingShard:
        """Map SQLite row to TrainingShard domain entity."""
        try:
            status = TrainingShardStatus(row["status"])
        except ValueError as e:
            raise PersistenceError(f"Invalid status '{row['status']}' stored in database: {e}") from e

        metrics = self._deserialize_json(row["metrics"])
        metadata = self._deserialize_json(row["training_metadata"])

        return TrainingShard(
            id=row["id"],
            model_id=row["model_id"],
            model_type=row["model_type"],
            model_version=row["model_version"],
            dataset_id=row["dataset_id"],
            shard_id=row["shard_id"],
            artifact_path=row["artifact_path"],
            sample_count=row["sample_count"],
            status=status,
            metrics=metrics,
            training_metadata=metadata,
            update_artifact_path=row["update_artifact_path"],
            training_task_id=row["training_task_id"],
        )

    def save(self, training_shard: TrainingShard) -> None:
        """Atomically persist a single TrainingShard into SQLite.

        Raises:
            ValueError: If entity validation fails.
            DuplicateShardError: If composite key already exists.
            PersistenceError: On database or serialization error.
        """
        training_shard.validate()

        params = (
            training_shard.id,
            training_shard.model_id,
            training_shard.model_type,
            training_shard.model_version,
            training_shard.dataset_id,
            training_shard.shard_id,
            training_shard.artifact_path,
            training_shard.sample_count,
            training_shard.status.value,
            self._serialize_json(training_shard.metrics),
            self._serialize_json(training_shard.training_metadata),
            training_shard.update_artifact_path,
            training_task_id := training_shard.training_task_id,
        )

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(INSERT_SHARD_SQL, params)
                conn.commit()
            logger.debug("Successfully persisted shard %s", training_shard.id)
        except sqlite3.IntegrityError as e:
            err_msg = str(e).lower()
            if "unique" in err_msg or "primary" in err_msg:
                raise DuplicateShardError(
                    model_id=training_shard.model_id,
                    model_version=training_shard.model_version,
                    dataset_id=training_shard.dataset_id,
                    shard_id=training_shard.shard_id,
                    message=f"Duplicate shard detected for ({training_shard.model_id}, {training_shard.model_version}, {training_shard.dataset_id}, {training_shard.shard_id}): {e}",
                ) from e
            if "check" in err_msg:
                raise ValueError(f"Database constraint violation on save: {e}") from e
            raise PersistenceError(f"Integrity constraint violation saving shard: {e}") from e
        except sqlite3.Error as e:
            raise PersistenceError(f"Database error while saving shard '{training_shard.id}': {e}") from e

    def bulk_save(self, training_shards: List[TrainingShard]) -> None:
        """Atomically persist a list of TrainingShard instances in a single transaction.

        Raises:
            ValueError: If any entity fails validation.
            DuplicateShardError: If duplicate composite keys exist in batch or database.
            PersistenceError: On database error.
        """
        if not training_shards:
            return

        seen_keys: Set[Tuple[str, str, str, str]] = set()
        seen_ids: Set[str] = set()
        rows_to_insert = []

        for shard in training_shards:
            shard.validate()

            if shard.id in seen_ids:
                raise DuplicateShardError(
                    model_id=shard.model_id,
                    model_version=shard.model_version,
                    dataset_id=shard.dataset_id,
                    shard_id=shard.shard_id,
                    message=f"Duplicate primary key ID '{shard.id}' found in bulk save batch",
                )
            seen_ids.add(shard.id)

            composite_key = (shard.model_id, shard.model_version, shard.dataset_id, shard.shard_id)
            if composite_key in seen_keys:
                raise DuplicateShardError(
                    model_id=shard.model_id,
                    model_version=shard.model_version,
                    dataset_id=shard.dataset_id,
                    shard_id=shard.shard_id,
                    message=f"Duplicate composite key {composite_key} found within bulk save batch",
                )
            seen_keys.add(composite_key)

            rows_to_insert.append((
                shard.id,
                shard.model_id,
                shard.model_type,
                shard.model_version,
                shard.dataset_id,
                shard.shard_id,
                shard.artifact_path,
                shard.sample_count,
                shard.status.value,
                self._serialize_json(shard.metrics),
                self._serialize_json(shard.training_metadata),
                shard.update_artifact_path,
                shard.training_task_id,
            ))

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                # Use immediate transaction for batch write
                cursor.execute("BEGIN IMMEDIATE;")
                for row_params in rows_to_insert:
                    cursor.execute(INSERT_SHARD_SQL, row_params)
                conn.commit()
            logger.debug("Successfully bulk-saved %d shards", len(training_shards))
        except sqlite3.IntegrityError as e:
            err_msg = str(e).lower()
            if "unique" in err_msg or "primary" in err_msg:
                raise DuplicateShardError(
                    model_id="",
                    model_version="",
                    dataset_id="",
                    shard_id="",
                    message=f"Duplicate shard detected during bulk save: {e}",
                ) from e
            if "check" in err_msg:
                raise ValueError(f"Database constraint violation during bulk save: {e}") from e
            raise PersistenceError(f"Integrity error during bulk save: {e}") from e
        except sqlite3.Error as e:
            raise PersistenceError(f"Database error during bulk save: {e}") from e

    def get_by_id(self, id: str) -> Optional[TrainingShard]:
        """Retrieve a TrainingShard by primary key UUID.

        Returns:
            TrainingShard if found, else None.
        """
        if not id or not isinstance(id, str):
            return None

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(SELECT_BY_ID_SQL, (id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_entity(row)
        except sqlite3.Error as e:
            raise PersistenceError(f"Database error querying shard by id '{id}': {e}") from e

    def get_by_shard_key(
        self,
        model_id: str,
        model_version: str,
        dataset_id: str,
        shard_id: str,
    ) -> Optional[TrainingShard]:
        """Retrieve a TrainingShard by composite logical key.

        Returns:
            TrainingShard if found, else None.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    SELECT_BY_SHARD_KEY_SQL,
                    (model_id, str(model_version), dataset_id, shard_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_entity(row)
        except sqlite3.Error as e:
            raise PersistenceError(
                f"Database error querying shard by composite key ({model_id}, {model_version}, {dataset_id}, {shard_id}): {e}"
            ) from e
