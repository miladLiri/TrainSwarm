# Interface Contract: Client Model Repository

**Contract**: `IModelRepository` | **Location**: `Client.infrastructure.persistence`

## Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Optional
from Client.models.model import Model


class IModelRepository(ABC):
    """Abstract persistence interface for Model entity management in Client."""

    @abstractmethod
    def save(self, model: Model) -> None:
        """Persist a Model entity into the local database.

        Args:
            model: Validated Model entity instance.

        Raises:
            ModelPersistenceError: If a database error or constraint violation occurs.
        """
        pass

    @abstractmethod
    def get_by_model_id(self, model_id: str) -> Model:
        """Retrieve a Model entity by its unique identifier.

        Args:
            model_id: UUID string of the model.

        Returns:
            The matching Model entity instance.

        Raises:
            ModelNotFoundError: If no record matches the provided model_id.
            ModelPersistenceError: If a database connection error occurs.
        """
        pass
```

## Exception Hierarchy

```python
class ModelRepositoryError(Exception):
    """Base exception for model repository operations."""
    pass


class ModelNotFoundError(ModelRepositoryError):
    """Raised when a requested model_id does not exist in persistence."""
    def __init__(self, model_id: str) -> None:
        super().__init__(f"Model with id '{model_id}' was not found in local database.")
        self.model_id = model_id


class ModelPersistenceError(ModelRepositoryError):
    """Raised when a database lock, I/O, or SQLite execution error occurs."""
    pass
```
