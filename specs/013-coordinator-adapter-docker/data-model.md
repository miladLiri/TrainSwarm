# Data Model: Coordinator Adapter & Training Client Infrastructure

**Feature**: `013-coordinator-adapter-docker` | **Date**: 2026-09-04

## 1. DTO Model (`CreateTrainingTaskDto`)

**File**: `src/Client/infrastructure/adapters/create_training_task.py`

### Class Definition

```python
@dataclass(frozen=True)
class CreateTrainingTaskDto:
    client_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id_list: list[str]
```

### Attributes & Validation Rules

| Attribute | Python Type | JSON Wire Key | Nullable | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `client_node_id` | `str` | `clientNodeId` | No | Required; non-empty string; stripped string cannot be empty. |
| `model_id` | `str` | `modelId` | No | Required; non-empty string; stripped string cannot be empty. |
| `model_version` | `str` | `modelVersion` | No | Required; non-empty string; stripped string cannot be empty. |
| `data_set_id` | `str` | `dataSetId` | No | Required; non-empty string; stripped string cannot be empty. |
| `shard_id_list` | `list[str]` | `shardIdList` | No | Required; non-empty list (`len >= 1`); every element must be a non-empty, non-whitespace string. |

### Wire Format Serialization (`to_dict()`)

The DTO serializes into a dictionary conforming to the Coordinator API schema:

```json
{
  "clientNodeId": "client-node-01",
  "modelId": "resnet50-v2",
  "modelVersion": "1.0.0",
  "dataSetId": "cifar10",
  "shardIdList": [
    "shard-001",
    "shard-002"
  ]
}
```

---

## 2. Adapter Component (`CoordinatorAdapter`)

**File**: `src/Client/infrastructure/adapters/coordinator_adapter.py`

### Component Specification

```python
class CoordinatorAdapter:
    def __init__(
        self,
        coordinator_address: Optional[str] = None,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        ...

    def create_training_task(self, request: CreateTrainingTaskDto) -> list[str]:
        ...
```

### Configuration & State

| Field | Type | Source / Resolution | Description |
| :--- | :--- | :--- | :--- |
| `coordinator_address` | `str` | `coordinator_address` param or `os.getenv("COORDINATOR_ADDRESS")` | Normalized URL without trailing slash. Fails fast if missing. |
| `timeout_seconds` | `float` | Parameter (default: 10.0) | Timeout in seconds for HTTP network calls. |
| `_session` | `requests.Session` | Injected parameter or internal instance | HTTP session for connection pooling and lifecycle safety. |

### API Endpoint Target

- **Method**: `POST`
- **URL**: `{COORDINATOR_ADDRESS}/api/training-tasks`
- **Headers**: `{"Content-Type": "application/json"}`
- **Response Format**:
  ```json
  {
    "trainingTaskIds": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "7ca85f64-5717-4562-b3fc-2c963f66bfa7"
    ]
  }
  ```
- **Return Value**: `list[str]` containing the created task GUIDs.

---

## 3. Exception Hierarchy

**Module**: `src/Client/infrastructure/adapters/coordinator_adapter.py`

```text
Exception
└── CoordinatorAdapterError
    ├── CoordinatorConfigurationError
    ├── CoordinatorApiError
    │   ├── status_code: int
    │   └── response_text: str
    └── CoordinatorNetworkError
```

### Exception Semantics

1. **`CoordinatorConfigurationError`**: Raised during initialization if `COORDINATOR_ADDRESS` is missing, empty, or whitespace.
2. **`CoordinatorApiError`**: Raised when the Coordinator returns an HTTP status code `< 200` or `>= 300`. Preserves `status_code` and raw or JSON error payload in `response_text`.
3. **`CoordinatorNetworkError`**: Raised on transport failures: DNS failure, connection refused, connection timeout, connection reset.
4. **`CoordinatorAdapterError`**: Raised when an HTTP 2xx response contains invalid/unparseable JSON or lacks the `trainingTaskIds` collection.

---

## 4. Architectural Boundaries

```text
+----------------------------------------------------------------+
|                        Client Application                      |
|                                                                |
|  +---------------------------+    +-------------------------+  |
|  |    CoordinatorAdapter     |    | TrainingShardRepository |  |
|  |                           |    |                         |  |
|  | - CreateTrainingTaskDto   |    | - TrainingShard         |  |
|  | - requests.Session        |    | - DatabaseManager       |  |
|  +-------------+-------------+    +------------+------------+  |
+----------------|-------------------------------|---------------+
                 | HTTP REST                     | SQLite Local I/O
                 v                               v
    +-------------------------+    +----------------------------+
    |       Coordinator       |    |       /data/training.db    |
    |  POST /api/training-    |    |   (Persistent Host Volume) |
    |  tasks                  |    +----------------------------+
    +-------------------------+
```

### Isolation Rules
- **No SQLite in Adapter**: `CoordinatorAdapter` has zero imports of `sqlite3`, `DatabaseManager`, or `TrainingShardRepository`.
- **No HTTP in Repository**: `TrainingShardRepository` has zero imports of `requests` or `CoordinatorAdapter`.
- **Caller Decoupling**: External callers interact solely with `CoordinatorAdapter.create_training_task(dto)` and never construct raw HTTP requests.
