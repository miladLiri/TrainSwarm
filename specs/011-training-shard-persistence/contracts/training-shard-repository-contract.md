# Contract: TrainingShardRepository

**Feature Branch**: `011-training-shard-persistence`  
**Date**: 2026-09-03  
**Status**: Stable  

## 1. Purpose & Architectural Boundaries

`TrainingShardRepository` defines the public persistence interface consumed by the TrainSwarm Client application.

### Invariants & Boundaries
- All database objects (`sqlite3.Connection`, `sqlite3.Cursor`, SQL text, file paths) are completely encapsulated within the persistence infrastructure.
- Application code interacts solely via domain models (`TrainingShard`, `TrainingShardStatus`).
- Repository operations are synchronous, atomic, thread-safe, and insert-only for create methods.
- The repository does NOT execute network I/O, download artifacts, trigger training routines, or communicate with the Coordinator or P2P sidecar.

---

## 2. Python Interface Definition

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.training_shard import TrainingShard

class ITrainingShardRepository(ABC):
    """Abstract interface for local training shard persistence."""

    @abstractmethod
    def save(self, training_shard: TrainingShard) -> None:
        """
        Atomically persist a single TrainingShard into local storage.

        Args:
            training_shard: Domain entity containing valid shard details.

        Raises:
            DuplicateShardError: If a record with the same (model_id, model_version, dataset_id, shard_id)
                                 already exists in storage.
            PersistenceError: If a database connection, IO, or constraint error occurs.
            ValueError: If entity validation fails.
        """
        pass

    @abstractmethod
    def bulk_save(self, training_shards: List[TrainingShard]) -> None:
        """
        Atomically persist a collection of TrainingShard entities in a single database transaction.

        If any shard fails validation or violates unique constraints, the entire batch
        is rolled back, leaving no partially persisted records.

        Args:
            training_shards: List of domain entities to persist.

        Raises:
            DuplicateShardError: If duplicate composite keys exist within the batch or in storage.
            PersistenceError: If transaction or execution fails.
            ValueError: If any entity fails validation.
        """
        pass

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[TrainingShard]:
        """
        Retrieve a persisted TrainingShard by its unique UUID primary key.

        Args:
            id: UUID string primary key.

        Returns:
            The reconstructed TrainingShard domain entity with deserialized metrics and
            metadata, or None if no record matches the ID.

        Raises:
            PersistenceError: If read operation or JSON deserialization fails.
        """
        pass

    @abstractmethod
    def get_by_shard_key(
        self,
        model_id: str,
        model_version: str,
        dataset_id: str,
        shard_id: str
    ) -> Optional[TrainingShard]:
        """
        Retrieve a persisted TrainingShard by its logical composite unique key.

        Args:
            model_id: Model identifier.
            model_version: Model checkpoint version.
            dataset_id: Dataset identifier.
            shard_id: Shard identifier.

        Returns:
            The reconstructed TrainingShard domain entity, or None if no match is found.

        Raises:
            PersistenceError: If read operation or JSON deserialization fails.
        """
        pass
```

---

## 3. Exception Specification

All persistence exceptions are defined in `Client.infrastructure.persistence.exceptions`:

```python
class PersistenceError(Exception):
    """Base exception for all persistence-related failures."""
    pass

class DatabaseConfigurationError(PersistenceError):
    """Raised when database configuration (e.g. invalid path) fails."""
    pass

class DatabaseInitializationError(PersistenceError):
    """Raised when directory creation, connection establishment, or schema DDL fails."""
    pass

class DuplicateShardError(PersistenceError):
    """Raised when attempting to persist a shard whose composite key already exists."""
    def __init__(self, model_id: str, model_version: str, dataset_id: str, shard_id: str):
        super().__init__(
            f"Training shard already exists for model '{model_id}' v{model_version}, "
            f"dataset '{dataset_id}', shard '{shard_id}'"
        )
        self.model_id = model_id
        self.model_version = model_version
        self.dataset_id = dataset_id
        self.shard_id = shard_id

class SerializationError(PersistenceError):
    """Raised when JSON serialization or deserialization of metrics/metadata fails."""
    pass
```

---

## 4. Concurrency & Transaction Guarantees

1. **Transactional Atomicity**:
   - Every `save()` execution runs within an atomic transaction. A failure rolls back the insert.
   - Every `bulk_save()` execution runs within a single atomic batch transaction (`BEGIN IMMEDIATE` ... `COMMIT`). If any insert in the batch fails, the entire batch is rolled back (`ROLLBACK`).
2. **Thread Safety**:
   - Each operation acquires a dedicated, scoped SQLite connection via `DatabaseManager.get_connection()` with context-managed closure.
   - Connections configure `PRAGMA busy_timeout = 5000` (5-second lock wait).
   - Thread isolation prevents `sqlite3.ProgrammingError` regarding cross-thread connection sharing.
