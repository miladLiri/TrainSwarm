# Coordinator Adapter Public Interface Contract

**Module**: `infrastructure.adapters`

## 1. Class: `CreateTrainingTaskDto`

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass(frozen=True)
class CreateTrainingTaskDto:
    client_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id_list: List[str]

    def __post_init__(self) -> None:
        """Validates all fields are non-empty and shard_id_list contains >= 1 valid item."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Serializes DTO to camelCase JSON payload expected by Coordinator API."""
        ...
```

---

## 2. Class: `CoordinatorAdapter`

```python
from typing import Optional, List
import requests

class CoordinatorAdapter:
    def __init__(
        self,
        coordinator_address: Optional[str] = None,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initializes adapter.
        
        Args:
            coordinator_address: Optional base URL. If None, reads from COORDINATOR_ADDRESS.
            timeout_seconds: Request timeout in seconds (default 10.0).
            session: Optional reusable requests.Session for connection pooling/testing.
            
        Raises:
            CoordinatorConfigurationError: If COORDINATOR_ADDRESS is missing or empty.
        """
        ...

    def create_training_task(self, request: CreateTrainingTaskDto) -> List[str]:
        """Sends POST /api/training-tasks to Coordinator and returns created task IDs.
        
        Args:
            request: Validated CreateTrainingTaskDto instance.
            
        Returns:
            List[str]: List of training task GUIDs created on Coordinator.
            
        Raises:
            CoordinatorApiError: If Coordinator returns non-success HTTP status (4xx, 5xx).
            CoordinatorNetworkError: If connection fails or times out.
            CoordinatorAdapterError: If response body is malformed or lacks trainingTaskIds.
        """
        ...
```

---

## 3. Exceptions

```python
class CoordinatorAdapterError(Exception):
    """Base exception for all Coordinator adapter failures."""
    pass

class CoordinatorConfigurationError(CoordinatorAdapterError):
    """Raised when COORDINATOR_ADDRESS is missing or empty."""
    pass

class CoordinatorApiError(CoordinatorAdapterError):
    """Raised when Coordinator returns a non-success HTTP status code."""
    def __init__(self, status_code: int, response_text: str):
        super().__init__(f"Coordinator API error ({status_code}): {response_text}")
        self.status_code = status_code
        self.response_text = response_text

class CoordinatorNetworkError(CoordinatorAdapterError):
    """Raised when network transport fails (connection refused, timeout, DNS failure)."""
    pass
```
