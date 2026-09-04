# Phase 1 Data Model: Training Client Configuration, Dependency Injection, and Smoke Test

**Feature Branch**: `014-client-config-smoke-test`  
**Date**: 2026-09-04  
**Author**: Antigravity  
**Status**: Completed  

---

## 1. Entity Overview

```mermaid
classDiagram
    class ClientConfig {
        +str coordinator_address
        +str client_node_id
        +float request_timeout_seconds
        +Path db_path
        +float shard_training_time_limit_seconds
        +float shard_safety_factor
        +Path working_directory
    }

    class DIContainer {
        +ClientConfig config
        +DatabaseManager db_manager
        +TrainingShardRepository shard_repository
        +CoordinatorAdapter coordinator_adapter
        +TrainingOrchestrator training_orchestrator
        +SmokeTestCommandHandler smoke_test_handler
    }

    class SmokeTestCommand {
        +TrainingTask training_task_model
        +int sample_count
        +validate() void
    }

    class SmokeTestResult {
        +bool success
        +int sample_count
        +Optional~float~ training_time_seconds
        +Optional~float~ samples_per_second
        +Optional~float~ shard_training_time_limit_seconds
        +Optional~int~ estimated_samples_per_shard
        +Optional~int~ recommended_samples_per_shard
        +Optional~str~ error
        +to_dict() dict
        +from_dict(data) SmokeTestResult
    }

    class SmokeTestCommandHandler {
        -TrainingOrchestrator training_orchestrator
        -float shard_training_time_limit
        -Path working_directory
        -float safety_factor
        +handle(SmokeTestCommand) SmokeTestResult
    }

    DIContainer --> ClientConfig : wires
    DIContainer --> SmokeTestCommandHandler : constructs
    SmokeTestCommandHandler ..> SmokeTestCommand : consumes
    SmokeTestCommandHandler ..> SmokeTestResult : produces
```

---

## 2. Model Specifications

### 2.1 `ClientConfig` (`src/Client/config/config_manager.py`)

Represents the strongly typed, validated client configuration loaded from environment variables and `.env` files.

| Attribute | Type | Required | Default | Validation / Constraints |
|---|---|---|---|---|
| `coordinator_address` | `str` | Yes | N/A | Non-empty string; stripped of trailing slashes; valid URI scheme. |
| `client_node_id` | `str` | No | `"client-node-dev"` | Non-empty string identifier for client instance. |
| `request_timeout_seconds` | `float` | No | `10.0` | Strictly positive (`> 0.0`). |
| `db_path` | `Path` | No | `Path("./training.db")` | Resolved absolute or local filesystem path. |
| `shard_training_time_limit_seconds` | `float` | No | `300.0` | Strictly positive (`> 0.0`). |
| `shard_safety_factor` | `float` | No | `1.0` | Must be $0.0 < \text{factor} \le 1.0$. |
| `working_directory` | `Path` | No | `Path(".")` | Resolved filesystem directory for training task artifacts. |

---

### 2.2 `SmokeTestCommand` (`src/Client/application/smoke_test/smoke_test_command.py`)

Application command DTO requesting training validation and shard sizing calculation.

| Attribute | Type | Required | Description | Validation / Constraints |
|---|---|---|---|---|
| `training_task_model` | `TrainingTask` | Yes | Target training task definition. | Must be an instance of `TrainingTask`; `validate_envelope()` must succeed. |
| `sample_count` | `int` | Yes | Number of samples to train on. | Must be an integer strictly greater than zero (`sample_count > 0`). |

**Validation Method**:
- `validate()`: Raises `SmokeTestValidationError` if `sample_count <= 0` or if `training_task_model` is invalid.

---

### 2.3 `SmokeTestResult` (`src/Client/application/smoke_test/smoke_test_result.py`)

Application result DTO capturing the outcome of the smoke test, timing measurements, throughput, and shard recommendations.

| Attribute | Type | Nullable | Description |
|---|---|---|---|
| `success` | `bool` | No | True if training completed without errors; False on any failure. |
| `sample_count` | `int` | No | Number of samples benchmarked. |
| `training_time_seconds` | `Optional[float]` | Yes | Monotonic elapsed training duration in seconds (`None` on failure). |
| `samples_per_second` | `Optional[float]` | Yes | Calculated throughput: $\text{sample\_count} / \text{training\_time\_seconds}$ (`None` on failure). |
| `shard_training_time_limit_seconds` | `Optional[float]` | Yes | Time budget used for shard sizing calculation. |
| `estimated_samples_per_shard` | `Optional[int]` | Yes | Theoretical samples capacity: $\text{int}(\text{throughput} \times \text{limit})$ (`None` on failure). |
| `recommended_samples_per_shard` | `Optional[int]` | Yes | Recommended partition size: $\text{int}(\text{estimated} \times \text{safety\_factor})$ (`None` on failure). |
| `error` | `Optional[str]` | Yes | Error message or diagnostic details if training failed (`None` on success). |

**Methods**:
- `to_dict() -> dict`: Serializes result for logging and JSON communication.
- `from_dict(data: dict) -> SmokeTestResult`: Deserializes JSON payload into typed result object.

---

### 2.4 `DIContainer` (`src/Client/dependency_injection/container.py`)

Lightweight composition root assembling the Client application graph at startup.

| Property / Factory | Returned Type | Construction Mechanism |
|---|---|---|
| `config` | `ClientConfig` | Resolved from `ConfigManager`. |
| `db_manager` | `DatabaseManager` | `DatabaseManager(db_path=config.db_path, timeout=config.request_timeout_seconds)` |
| `shard_repository` | `TrainingShardRepository` | `TrainingShardRepository(db_manager=self.db_manager)` |
| `coordinator_adapter` | `CoordinatorAdapter` | `CoordinatorAdapter(coordinator_address=config.coordinator_address, timeout_seconds=config.request_timeout_seconds)` |
| `training_orchestrator`| `TrainingOrchestrator` | `TrainingOrchestrator()` from `distributed_training_engine.training` |
| `smoke_test_handler` | `SmokeTestCommandHandler`| `SmokeTestCommandHandler(training_orchestrator=self.training_orchestrator, shard_training_time_limit=config.shard_training_time_limit_seconds, working_directory=config.working_directory, safety_factor=config.shard_safety_factor)` |

---

## 3. Exception Hierarchy

```mermaid
classDiagram
    class Exception
    class ClientConfigurationError {
        +str message
    }
    class MissingConfigurationError {
        +str variable_name
    }
    class InvalidConfigurationValueError {
        +str variable_name
        +str raw_value
        +str reason
    }
    class SmokeTestError {
        +str message
    }
    class SmokeTestValidationError {
        +str field
        +Any value
    }
    class SmokeTestExecutionError {
        +str task_id
        +Exception cause
    }

    Exception <|-- ClientConfigurationError
    ClientConfigurationError <|-- MissingConfigurationError
    ClientConfigurationError <|-- InvalidConfigurationValueError
    Exception <|-- SmokeTestError
    SmokeTestError <|-- SmokeTestValidationError
    SmokeTestError <|-- SmokeTestExecutionError
```

---

## 4. Lifecycle & State Transitions

### Smoke Test Execution Lifecycle

```mermaid
stateDiagram-v2
    [*] --> CommandValidation: SmokeTestCommand received
    CommandValidation --> InvalidCommand: sample_count <= 0 or invalid task
    InvalidCommand --> [*]: Raise SmokeTestValidationError

    CommandValidation --> TrainingExecution: Command valid
    TrainingExecution --> TimeMeasurement: time.perf_counter() start

    state TrainingExecution {
        [*] --> Validate
        Validate --> Prepare
        Prepare --> Train
        Train --> SaveResult
        SaveResult --> [*]
    }

    TrainingExecution --> ExecutionFailed: Exception during training
    ExecutionFailed --> ErrorLogging: Log full traceback
    ErrorLogging --> FailedResult: SmokeTestResult(success=False, error=str(e))
    FailedResult --> [*]

    TrainingExecution --> SizingCalculation: Training succeeded
    TimeMeasurement --> SizingCalculation: Duration recorded
    SizingCalculation --> DeltaCleanup: Calculate throughput & shard sizes
    DeltaCleanup --> SuccessfulResult: Delete .safetensors delta
    SuccessfulResult --> [*]: Return SmokeTestResult(success=True)
```
