# Interface Contract: Coordinator Adapter

**Subsystem**: Trainer Infrastructure  
**Module**: `src/Trainer/infrastructure/adapters/coordinator_adapter.py`  
**Purpose**: Encapsulate HTTP communication with the Coordinator REST API, abstracting networking, JSON serialization, and error recovery from application command handlers.

---

## 1. Class Signature

```python
class CoordinatorAdapter:
    def __init__(
        self,
        coordinator_address: str,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize adapter with Coordinator base URL and timeout.
        
        Args:
            coordinator_address: Base URL of the Coordinator REST API (e.g. http://localhost:8080).
            timeout_seconds: HTTP connect/read timeout in seconds.
            session: Optional pre-configured requests.Session (for connection pooling/testing).
        """
        ...

    def connect_trainer(self, trainer_node_id: str) -> CoordinatorAdapterResult:
        """Call Coordinator's POST /api/trainers/connect endpoint.
        
        Args:
            trainer_node_id: Logical string identifier of the trainer node.
            
        Returns:
            CoordinatorAdapterResult with success=True and trainer_id on success,
            or success=False and description detailing the failure reason.
            This method NEVER raises unhandled network exceptions to the caller.
        """
        ...

    def close(self) -> None:
        """Release underlying HTTP resources."""
        ...
```

---

## 2. Result Data Contract

```python
@dataclass(frozen=True)
class CoordinatorAdapterResult:
    success: bool
    description: str
    trainer_id: Optional[str] = None
    status_code: Optional[int] = None
```

---

## 3. Behavioral Guarantees

1. **Address Normalization**: Trailing slashes in `coordinator_address` are automatically stripped (e.g., `http://coordinator:8080/` -> `http://coordinator:8080`).
2. **Exception Encapsulation**: Low-level errors (`requests.exceptions.Timeout`, `requests.exceptions.ConnectionError`, `requests.exceptions.RequestException`) are caught internally and mapped to `CoordinatorAdapterResult(success=False, description=...)`.
3. **HTTP Status Mapping**:
   - Status `200` / `201`: Parses JSON body, extracts `id`, and returns `CoordinatorAdapterResult(success=True, description="Trainer registered successfully.", trainer_id=id, status_code=code)`.
   - Status `400`: Parses validation problem details and returns `CoordinatorAdapterResult(success=False, description="Validation failed: ...", status_code=400)`.
   - Status `500`+: Returns `CoordinatorAdapterResult(success=False, description="Coordinator server error: ...", status_code=500)`.
4. **Context Manager Support**: Supports `with CoordinatorAdapter(...) as adapter:` for deterministic session cleanup.
