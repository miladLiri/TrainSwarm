"""SQLite repository implementation for Model entity persistence."""

from __future__ import annotations
from abc import ABC, abstractmethod
import logging
import sqlite3
from typing import List, Optional

try:
    from Client.domain.model import Model
    from Client.infrastructure.persistence.database import DatabaseManager
    from Client.infrastructure.persistence.exceptions import (
        ModelNotFoundError,
        ModelPersistenceError,
    )
except ImportError:
    from domain.model import Model
    from infrastructure.persistence.database import DatabaseManager
    from infrastructure.persistence.exceptions import (
        ModelNotFoundError,
        ModelPersistenceError,
    )

logger = logging.getLogger(__name__)


class IModelRepository(ABC):
    """Abstract interface defining operations for Model entity persistence."""

    @abstractmethod
    def save(self, model: Model) -> None:
        """Persist or update a Model entity.

        Args:
            model: Validated Model entity instance.

        Raises:
            ModelPersistenceError: If persistence fails.
        """
        pass

    @abstractmethod
    def get_by_model_id(self, model_id: str) -> Model:
        """Retrieve the latest Model entity by its unique identifier.

        Args:
            model_id: UUID string of the model.

        Returns:
            The matching Model entity.

        Raises:
            ModelNotFoundError: If no record exists with the provided ID.
            ModelPersistenceError: If database query fails.
        """
        pass

    @abstractmethod
    def get_by_model_id_and_version(self, model_id: str, model_version: str) -> Model:
        """Retrieve a specific version of a Model entity.

        Args:
            model_id: UUID string of the model.
            model_version: Version string (e.g. "1", "2").

        Returns:
            The matching Model entity.

        Raises:
            ModelNotFoundError: If no record exists with the provided ID and version.
            ModelPersistenceError: If database query fails.
        """
        pass

    @abstractmethod
    def get_all(self) -> List[Model]:
        """Retrieve all persisted Model entities across all versions.

        Returns:
            List of all Model entities.

        Raises:
            ModelPersistenceError: If database query fails.
        """
        pass


class ModelRepository(IModelRepository):
    """SQLite implementation of IModelRepository."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def save(self, model: Model) -> None:
        """Save a Model entity to the models table."""
        model.validate()
        sql = """
        INSERT OR REPLACE INTO models (
            model_id,
            model_type,
            model_version,
            dataset_id,
            model_artifact_path,
            training_config_path
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    sql,
                    (
                        model.model_id,
                        model.model_type,
                        model.model_version,
                        model.dataset_id,
                        model.model_artifact_path,
                        model.training_config_path,
                    ),
                )
                conn.commit()
            logger.info("Successfully persisted model metadata for model_id='%s'", model.model_id)
        except sqlite3.Error as e:
            err = f"Failed to persist model '{model.model_id}': {e}"
            logger.error(err)
            raise ModelPersistenceError(err) from e

    def get_by_model_id(self, model_id: str) -> Model:
        """Query the latest version of a Model entity by model_id."""
        if not model_id or not isinstance(model_id, str):
            raise ModelNotFoundError(str(model_id), "Model ID must be a non-empty string.")

        sql = """
        SELECT
            model_id,
            model_type,
            model_version,
            dataset_id,
            model_artifact_path,
            training_config_path
        FROM models
        WHERE model_id = ?
        ORDER BY CAST(model_version AS INTEGER) DESC, model_version DESC
        LIMIT 1;
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (model_id,))
                row = cursor.fetchone()
                if row is None:
                    raise ModelNotFoundError(model_id)

                return Model(
                    model_id=row["model_id"],
                    model_type=row["model_type"],
                    model_version=row["model_version"],
                    dataset_id=row["dataset_id"],
                    model_artifact_path=row["model_artifact_path"],
                    training_config_path=row["training_config_path"],
                )
        except ModelNotFoundError:
            raise
        except sqlite3.Error as e:
            err = f"Failed to query model by id '{model_id}': {e}"
            logger.error(err)
            raise ModelPersistenceError(err) from e

    def get_by_model_id_and_version(self, model_id: str, model_version: str) -> Model:
        """Query a Model entity by composite key (model_id, model_version)."""
        if not model_id or not isinstance(model_id, str):
            raise ModelNotFoundError(str(model_id), "Model ID must be a non-empty string.")

        sql = """
        SELECT
            model_id,
            model_type,
            model_version,
            dataset_id,
            model_artifact_path,
            training_config_path
        FROM models
        WHERE model_id = ? AND model_version = ?;
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (model_id, str(model_version)))
                row = cursor.fetchone()
                if row is None:
                    raise ModelNotFoundError(f"{model_id} (version {model_version})")

                return Model(
                    model_id=row["model_id"],
                    model_type=row["model_type"],
                    model_version=row["model_version"],
                    dataset_id=row["dataset_id"],
                    model_artifact_path=row["model_artifact_path"],
                    training_config_path=row["training_config_path"],
                )
        except ModelNotFoundError:
            raise
        except sqlite3.Error as e:
            err = f"Failed to query model by id '{model_id}' and version '{model_version}': {e}"
            logger.error(err)
            raise ModelPersistenceError(err) from e

    def get_all(self) -> List[Model]:
        """Retrieve all persisted Model entities ordered by model_id and version."""
        sql = """
        SELECT
            model_id,
            model_type,
            model_version,
            dataset_id,
            model_artifact_path,
            training_config_path
        FROM models
        ORDER BY model_id ASC, CAST(model_version AS INTEGER) ASC, model_version ASC;
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                return [
                    Model(
                        model_id=row["model_id"],
                        model_type=row["model_type"],
                        model_version=row["model_version"],
                        dataset_id=row["dataset_id"],
                        model_artifact_path=row["model_artifact_path"],
                        training_config_path=row["training_config_path"],
                    )
                    for row in rows
                ]
        except sqlite3.Error as e:
            err = f"Failed to query all models: {e}"
            logger.error(err)
            raise ModelPersistenceError(err) from e
