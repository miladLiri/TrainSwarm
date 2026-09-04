# Configuration, Dependency Injection, and Handler Contracts

**Feature Branch**: `014-client-config-smoke-test`  
**Date**: 2026-09-04  
**Author**: Antigravity  
**Status**: Completed  

---

## 1. Configuration Manager Contract (`src/Client/config/`)

### Environment Variable Bindings

| Environment Variable | Target Attribute | Target Type | Required | Default | Description |
|---|---|---|---|---|---|
| `COORDINATOR_ADDRESS` | `coordinator_address` | `str` | Yes | N/A | Base HTTP URL for Coordinator API. Trailing slashes stripped. |
| `COORDINATOR_URL` | `coordinator_address` | `str` | Secondary | N/A | Legacy fallback if `COORDINATOR_ADDRESS` is unset. |
| `CLIENT_NODE_ID` | `client_node_id` | `str` | No | `"client-node-dev"` | Unique identifier of this client worker node. |
| `REQUEST_TIMEOUT_SECONDS` | `request_timeout_seconds` | `float` | No | `10.0` | Default timeout for HTTP requests and database locks. |
| `TRAINING_CLIENT_DB_PATH` | `db_path` | `Path` | No | `Path("./training.db")` | Filesystem path to the local SQLite database. |
| `SHARD_TRAINING_TIME_LIMIT` | `shard_training_time_limit_seconds` | `float` | No | `300.0` | Target time budget (seconds) per shard. |
| `SHARD_SAFETY_FACTOR` | `shard_safety_factor` | `float` | No | `1.0` | Multiplier ($0.0 < F \le 1.0$) applied to estimated shard size. |
| `TRAINING_WORKING_DIRECTORY` | `working_directory` | `Path` | No | `Path(".")` | Local working directory containing checkpoints & datasets. |

### Public Interface: `ConfigManager`

```python
class ConfigManager:
    """Sole authoritative reader and validator of environment configuration."""

    def __init__(self, env_file: Optional[Union[str, Path]] = None) -> None:
        """Loads environment variables and validates required entries."""
        ...

    def get_config(self) -> ClientConfig:
        """Returns the validated, immutable ClientConfig instance."""
        ...
```

---

## 2. Dependency Injection / Composition Root Contract (`src/Client/dependency_injection/`)

### Public Interface: `DIContainer`

```python
class DIContainer:
    """Composition root for explicit dependency construction and wiring."""

    def __init__(self, config: Optional[ClientConfig] = None) -> None:
        """Instantiates all client infrastructure, persistence, and command handlers."""
        ...

    @property
    def config(self) -> ClientConfig:
        """Access the validated configuration."""
        ...

    @property
    def database_manager(self) -> DatabaseManager:
        """Access the configured SQLite DatabaseManager."""
        ...

    @property
    def shard_repository(self) -> TrainingShardRepository:
        """Access the TrainingShardRepository wired to DatabaseManager."""
        ...

    @property
    def coordinator_adapter(self) -> Optional[CoordinatorAdapter]:
        """Access the CoordinatorAdapter wired with coordinator_address and timeout."""
        ...

    @property
    def training_orchestrator(self) -> TrainingOrchestrator:
        """Access the type-agnostic TrainingOrchestrator."""
        ...

    @property
    def smoke_test_handler(self) -> SmokeTestCommandHandler:
        """Access the SmokeTestCommandHandler wired with orchestrator and time limit."""
        ...
```

---

## 3. Refactored Infrastructure Constructor Contracts

### `CoordinatorAdapter` (`src/Client/infrastructure/adapters/coordinator_adapter.py`)

```python
class CoordinatorAdapter:
    def __init__(
        self,
        coordinator_address: str,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        """
        Initialize CoordinatorAdapter.
        
        Args:
            coordinator_address: Explicit, non-empty Coordinator base URL.
            timeout_seconds: Request timeout in seconds.
            session: Optional reusable session.
            
        Raises:
            CoordinatorConfigurationError: If coordinator_address is empty or invalid.
        """
        ...
```
*Note: Direct `os.getenv` calls are strictly removed from `coordinator_adapter.py`.*

### `DatabaseManager` (`src/Client/infrastructure/persistence/database.py`)

```python
class DatabaseManager:
    def __init__(
        self,
        db_path: Union[str, Path] = Path("./training.db"),
        timeout: float = 10.0,
    ) -> None:
        """
        Initialize DatabaseManager.
        
        Args:
            db_path: Explicit filesystem path for SQLite database.
            timeout: Lock timeout in seconds.
            
        Raises:
            DatabaseConfigurationError: If db_path is empty or invalid.
        """
        ...
```
*Note: Direct `os.getenv` calls are strictly removed from `database.py`.*

---

## 4. Smoke Test Command Handler Contract (`src/Client/application/smoke_test/`)

### Public Interface: `SmokeTestCommandHandler`

```python
class SmokeTestCommandHandler:
    def __init__(
        self,
        training_orchestrator: TrainingOrchestrator,
        shard_training_time_limit: float = 300.0,
        working_directory: Union[str, Path] = Path("."),
        safety_factor: float = 1.0,
    ) -> None:
        """
        Initialize SmokeTestCommandHandler with explicit collaborator dependencies.
        
        Args:
            training_orchestrator: Type-agnostic engine orchestrator.
            shard_training_time_limit: Max time budget per shard in seconds.
            working_directory: Directory containing checkpoint and dataset artifacts.
            safety_factor: Shard sizing safety margin (0.0 < factor <= 1.0).
        """
        ...

    def handle(self, command: SmokeTestCommand) -> SmokeTestResult:
        """
        Execute smoke test training validation and calculate shard sizing.
        
        Args:
            command: Validated SmokeTestCommand containing task and sample count.
            
        Returns:
            SmokeTestResult with success status, throughput, sizing, or error.
        """
        ...
```
