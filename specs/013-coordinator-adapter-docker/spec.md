# Feature Specification: Training Client — Coordinator Adapter and Docker Infrastructure

**Feature Branch**: `013-coordinator-adapter-docker`

**Created**: 2026-09-04

**Status**: Draft

**Input**: User description: "Extend the Python Training Client infrastructure with a Coordinator API adapter. The Training Client must be able to request creation of training tasks from the Coordinator through a dedicated adapter. The implementation must add infrastructure/adapters/, coordinator_adapter.py, CreateTrainingTaskDto contract/model beside adapter, read COORDINATOR_ADDRESS env var, expose create_training_task method, send POST /api/training-tasks, validate HTTP/API response, log errors, propagate errors, hide HTTP details, remove obsolete infrastructure files leaving only persistence/ and adapters/, create/update Dockerfile, and configure Docker SQLite persistence via volume."

## Clarifications

### Session 2026-09-04

- **Q: How should the Training Client console UI adapt its interactive menu to support training task creation once the legacy session and bootstrap infrastructure clients are removed?** → **A: Clear `console_ui` for now; strip out legacy session and bootstrap menu workflows, keeping console UI minimal/dormant and free of obsolete dependencies.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit Training Task Creation Request via Coordinator Adapter (Priority: P1)

As the Training Client application, I want to request the creation of training tasks by passing a structured DTO to a dedicated Coordinator adapter, so that training tasks are provisioned on the Coordinator control plane without coupling the client application to HTTP transport details or manual URL formatting.

**Why this priority**: Foundational communication bridge between Training Client and Coordinator. Without this adapter, the Training Client cannot submit distributed training tasks to the control plane.

**Independent Test**: Instantiate `CoordinatorAdapter` pointing to a running or simulated Coordinator API endpoint, supply a valid `CreateTrainingTaskDto` containing valid identifiers and a list of shard IDs, execute `create_training_task(dto)`, and verify that the adapter returns the list of created training task IDs provisioned by the Coordinator.

**Acceptance Scenarios**:

1. **Given** a valid `CreateTrainingTaskDto` (`client_node_id="client-1"`, `model_id="m1"`, `model_version="v1"`, `data_set_id="ds1"`, `shard_id_list=["s1", "s2"]`) and a responsive Coordinator at `COORDINATOR_ADDRESS`, **When** `CoordinatorAdapter.create_training_task(dto)` is executed, **Then** the adapter sends an HTTP POST request to `{COORDINATOR_ADDRESS}/api/training-tasks` with header `Content-Type: application/json` and a JSON body with camelCase keys (`clientNodeId`, `modelId`, `modelVersion`, `dataSetId`, `shardIdList`).
2. **Given** a successful Coordinator response with status HTTP 200 or 201 containing `{"trainingTaskIds": ["guid-1", "guid-2"]}`, **When** the adapter parses the response, **Then** it returns `["guid-1", "guid-2"]` as a native `list[str]`.
3. **Given** a request where any required field in `CreateTrainingTaskDto` is missing or empty, or where `shard_id_list` is empty, **When** constructing or validating the DTO, **Then** an explicit validation error is raised before any HTTP request is issued.

---

### User Story 2 - Resilient Error Handling, Logging, and Escalation (Priority: P2)

As a developer or system operator monitoring Training Client execution, I want the Coordinator adapter to log detailed diagnostic context (address, endpoint, method, HTTP status code, error message, model metadata, shard count) using the existing logging infrastructure and escalate meaningful exceptions to the caller whenever communication or validation fails, so that failures are immediately diagnosable and never fail silently.

**Why this priority**: In semi-distributed training swarms, silent failures, swallowed exceptions, or unlogged network issues make failure diagnosis impossible and can cause deadlocked workflows.

**Independent Test**: Simulate various Coordinator API failure conditions (HTTP 400 Bad Request, HTTP 500 Internal Server Error, malformed response JSON, missing `trainingTaskIds` field, connection timeout, and connection refused). Verify that appropriate error logs are emitted via `logging.getLogger` and that dedicated adapter exceptions (`CoordinatorApiError`, `CoordinatorNetworkError`, `CoordinatorAdapterError`) are raised to the caller with clear diagnostic messages.

**Acceptance Scenarios**:

1. **Given** the Coordinator responds with a non-success HTTP status code (such as 400, 404, 409, 500, or 503), **When** `create_training_task()` processes the response, **Then** it logs the failure context (HTTP status, error message, endpoint, request metadata), does not return a successful result, and raises `CoordinatorApiError` containing the status code and error details.
2. **Given** the Coordinator responds with HTTP 200 or 201 but the response body is invalid JSON or lacks the expected `trainingTaskIds` array, **When** the adapter parses the response, **Then** it treats the response as an operation failure, logs the issue, and raises `CoordinatorAdapterError`.
3. **Given** the Coordinator host cannot be reached (connection refused, network timeout, DNS resolution failure, connection reset), **When** `create_training_task()` attempts the HTTP call, **Then** it logs the network failure and raises `CoordinatorNetworkError`.
4. **Given** any communication failure, **When** handling the exception, **Then** the adapter never catches and swallows the error (e.g. returning an empty list `[]` on error is strictly forbidden).

---

### User Story 3 - Environment-Driven Configuration and Fast Failure (Priority: P3)

As a DevOps engineer configuring the Training Client in varied deployment environments, I want the Coordinator address to be loaded strictly from the `COORDINATOR_ADDRESS` environment variable without hardcoded fallback hosts, failing fast at startup if the variable is absent or empty, so that misconfigurations are detected immediately before invalid operations occur.

**Why this priority**: Eliminates hardcoded addresses (such as `localhost` or `coordinator`), prevents implicit traffic routing to wrong environments, and ensures zero-assumption container runtime configuration.

**Independent Test**: Attempt to instantiate `CoordinatorAdapter` without `COORDINATOR_ADDRESS` set in the environment or with an empty string. Verify that adapter initialization immediately raises `CoordinatorConfigurationError` identifying the missing variable. Set `COORDINATOR_ADDRESS="http://coordinator:8080/"` and verify the adapter normalizes the base URL by stripping trailing slashes.

**Acceptance Scenarios**:

1. **Given** `COORDINATOR_ADDRESS` is not set or contains only whitespace, **When** initializing `CoordinatorAdapter` without an explicit address, **Then** initialization immediately raises `CoordinatorConfigurationError` citing `COORDINATOR_ADDRESS`.
2. **Given** `COORDINATOR_ADDRESS="http://coordinator:8080"`, **When** `CoordinatorAdapter` initializes, **Then** the base URL is successfully resolved without silent fallbacks to default addresses.
3. **Given** an address provided with trailing slashes (e.g., `http://coordinator:8080///`), **When** initialized, **Then** the adapter normalizes the address cleanly to `http://coordinator:8080`.

---

### User Story 4 - Infrastructure Directory Restructuring and Architectural Isolation (Priority: P4)

As a software maintainer of the Training Client, I want the `infrastructure/` package cleanly reorganized so that it contains exclusively `adapters/` and `persistence/`, removing obsolete legacy clients while maintaining strict isolation between HTTP communication and SQLite persistence, so that the codebase reflects clean separation of concerns and contains no dead code.

**Why this priority**: Resolves legacy technical debt in the Training Client infrastructure layer, removes obsolete files, and prevents architectural bleed between persistence and networking.

**Independent Test**: Inspect `src/Client/infrastructure/` and verify that only `adapters/` and `persistence/` subdirectories exist. Verify that obsolete files (`bootstrap_client.py`, `coordinator_client.py`) are deleted. Confirm that `CoordinatorAdapter` has zero imports or dependencies on `TrainingShardRepository` or SQLite, and that the Training Client console application initializes and starts cleanly.

**Acceptance Scenarios**:

1. **Given** the Training Client infrastructure directory, **When** inspecting contents, **Then** only `adapters/` and `persistence/` packages exist; obsolete infrastructure files are completely removed.
2. **Given** `CoordinatorAdapter`, **When** inspecting code dependencies, **Then** it contains zero references to `sqlite3`, `DatabaseManager`, or `TrainingShardRepository`.
3. **Given** `TrainingShardRepository`, **When** inspecting code dependencies, **Then** it contains zero references to HTTP clients, `CoordinatorAdapter`, or network protocols.
4. **Given** external code calling the Coordinator API, **When** requesting task creation, **Then** it interacts solely through `CoordinatorAdapter` and does not construct raw HTTP requests.

---

### User Story 5 - Containerized Execution with Persistent SQLite Volume (Priority: P5)

As a deployment engineer, I want an updated Dockerfile for the Training Client that packages the application and dependencies, accepts runtime environment variables, and configures a dedicated `/data` volume for the local SQLite database, so that the container starts reliably and preserves all training shard state across container restarts and recreations.

**Why this priority**: Guarantees containerized portability and prevents data loss of locally tracked training shards when containers are restarted or redeployed.

**Independent Test**: Build the Docker image from `src/Client/Dockerfile`. Run a container mounting a host volume to `/data`, configuring `COORDINATOR_ADDRESS=http://coordinator:8080` and `TRAINING_CLIENT_DB_PATH=/data/training.db`. Verify that the Training Client starts cleanly, creates the database file in `/data`, and retains existing records when the container is stopped and restarted with the same volume.

**Acceptance Scenarios**:

1. **Given** the Training Client Dockerfile, **When** `docker build` is executed, **Then** the image builds successfully using a compatible Python base image without build errors.
2. **Given** a running container, **When** runtime environment variables `COORDINATOR_ADDRESS` and `TRAINING_CLIENT_DB_PATH` are supplied, **Then** the application reads these values without hardcoded image defaults.
3. **Given** a volume mounted at container path `/data`, **When** the Training Client initializes persistence at `/data/training.db` and persists shards, **Then** restarting or recreating the container with the same volume mount retains the database and all shard records.
4. **Given** the container entrypoint, **When** started, **Then** it launches the actual Training Client console application (`python main.py`).

---

### Edge Cases

- **Trailing Slashes in Coordinator Address**: When `COORDINATOR_ADDRESS` has trailing slashes (e.g., `http://coordinator:8080/`), the adapter normalizes it so the resulting URL is strictly `http://coordinator:8080/api/training-tasks` without double slashes.
- **Empty or Whitespace Fields in DTO**: If any field (`client_node_id`, `model_id`, `model_version`, `data_set_id`) is empty or whitespace-only, the DTO validation rejects the request before any HTTP connection is attempted.
- **Empty or Whitespace Shard Identifiers**: If `shard_id_list` is empty or contains empty/whitespace strings (e.g., `["shard-1", "  "]`), DTO validation rejects the request.
- **Non-JSON Error Responses**: When the Coordinator returns an HTTP 500/502/503 error with an HTML or plain text error page instead of JSON, the adapter safely extracts the raw text for logging without crashing in JSON deserialization.
- **Connection Leaks and Resource Cleanup**: The adapter manages its underlying HTTP client session safely (e.g. reusing sessions properly or using context managers) to prevent unclosed sockets or connection leaks across repeated requests.
- **Request Timeout**: All network operations against the Coordinator use an explicit timeout (defaulting to 10.0 seconds or configurable), preventing threads from hanging indefinitely on stalled connections.
- **Unwriteable Database Directory in Docker**: If `/data` lacks appropriate write permissions, `DatabaseManager` raises `DatabaseInitializationError` cleanly during application startup.

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Transfer Object (`infrastructure/adapters/create_training_task.py`)
- **FR-001**: System MUST provide a `CreateTrainingTaskDto` class in `infrastructure/adapters/create_training_task.py`.
- **FR-002**: `CreateTrainingTaskDto` MUST encapsulate exactly:
  - `client_node_id` (`str`): Client node identifier (required, non-empty, non-whitespace).
  - `model_id` (`str`): Target model identifier (required, non-empty, non-whitespace).
  - `model_version` (`str`): Target model version (required, non-empty, non-whitespace).
  - `data_set_id` (`str`): Target dataset identifier (required, non-empty, non-whitespace).
  - `shard_id_list` (`list[str]`): List of shard identifiers (required, non-empty list of non-empty, non-whitespace strings).
- **FR-003**: `CreateTrainingTaskDto` MUST validate its attributes upon construction or serialization, raising a `ValueError` or domain validation error if any constraint in FR-002 is violated.
- **FR-004**: `CreateTrainingTaskDto` MUST serialize to a JSON payload conforming to the Coordinator API contract with exact camelCase field names:
  ```json
  {
    "clientNodeId": "...",
    "modelId": "...",
    "modelVersion": "...",
    "dataSetId": "...",
    "shardIdList": ["...", "..."]
  }
  ```
- **FR-005**: `CreateTrainingTaskDto` serialization MUST NOT emit Python `snake_case` field names (`client_node_id`, `model_id`, etc.) in the network payload.

#### 2. Coordinator Adapter (`infrastructure/adapters/coordinator_adapter.py`)
- **FR-006**: System MUST provide a `CoordinatorAdapter` class in `infrastructure/adapters/coordinator_adapter.py`.
- **FR-007**: `CoordinatorAdapter` MUST read the Coordinator base address from the `COORDINATOR_ADDRESS` environment variable during initialization (with optional constructor parameter override for dependency injection / testability).
- **FR-008**: If `COORDINATOR_ADDRESS` is absent, empty, or whitespace-only, `CoordinatorAdapter` MUST raise `CoordinatorConfigurationError` clearly identifying the missing environment variable. Silent fallback to default hostnames (such as `localhost`, `127.0.0.1`, or `coordinator`) is strictly prohibited.
- **FR-009**: `CoordinatorAdapter` MUST normalize the Coordinator base address by stripping trailing slashes.
- **FR-010**: `CoordinatorAdapter` MUST expose method `create_training_task(request: CreateTrainingTaskDto) -> list[str]` accepting `CreateTrainingTaskDto` directly.
- **FR-011**: `CoordinatorAdapter` MUST hide all HTTP transport details (URL construction, headers, JSON serialization, HTTP status checks, response deserialization) from the caller.
- **FR-012**: `CoordinatorAdapter` MUST construct the full target URL by appending `/api/training-tasks` to the configured Coordinator base address.
- **FR-013**: `CoordinatorAdapter` MUST issue an HTTP POST request with header `Content-Type: application/json` and the serialized DTO as the request body.
- **FR-014**: `CoordinatorAdapter` MUST enforce an explicit network request timeout (configurable, default 10.0 seconds) for all HTTP operations.
- **FR-015**: `CoordinatorAdapter` MUST validate the HTTP response from the Coordinator:
  - HTTP status indicates success (`200 OK` or `201 Created`).
  - Response body is valid JSON.
  - Response JSON contains top-level property `trainingTaskIds`.
  - `trainingTaskIds` is a non-null collection/list of string GUIDs.
- **FR-016**: On successful response validation, `create_training_task()` MUST return the list of created training task IDs as `list[str]`.
- **FR-017**: If the Coordinator returns a non-success HTTP status code (e.g., 400, 401, 403, 404, 409, 500, 503), `CoordinatorAdapter` MUST:
  - Log an error via Python `logging.getLogger` containing diagnostic context: Coordinator address, HTTP method, endpoint, status code, response error message, model ID, model version, dataset ID, and shard count.
  - Raise a `CoordinatorApiError` specifying the HTTP status code and error details.
- **FR-018**: If the Coordinator returns an HTTP success status (2xx) but the response body is not valid JSON or lacks a valid `trainingTaskIds` collection, `CoordinatorAdapter` MUST log an error and raise `CoordinatorAdapterError`.
- **FR-019**: If network communication fails (connection refused, timeout, DNS resolution failure, connection reset), `CoordinatorAdapter` MUST log the error and raise `CoordinatorNetworkError`.
- **FR-020**: `CoordinatorAdapter` MUST NOT catch and swallow exceptions, and MUST NOT return an empty list or fake response upon failure.
- **FR-021**: System MUST define an exception hierarchy rooted at `CoordinatorAdapterError`, with specialized subclasses `CoordinatorConfigurationError`, `CoordinatorApiError`, and `CoordinatorNetworkError`.
- **FR-022**: `CoordinatorAdapter` MUST use an established Python HTTP client library (`requests`) and manage client sessions safely without leaking sockets or connections.
- **FR-023**: `CoordinatorAdapter` MUST support testability via dependency injection (such as injectable `requests.Session` or transport handler) to allow full behavioral verification without a live Coordinator service.

#### 3. Infrastructure Directory Restructuring & Application Cleanliness
- **FR-024**: After implementation, `src/Client/infrastructure/` MUST contain strictly two subpackages:
  - `infrastructure/persistence/` (containing existing SQLite persistence and repository)
  - `infrastructure/adapters/` (containing `__init__.py`, `coordinator_adapter.py`, and `create_training_task.py`)
- **FR-025**: All obsolete files in `src/Client/infrastructure/`—specifically `coordinator_client.py` and `bootstrap_client.py`—MUST be completely removed.
- **FR-026**: `src/Client/infrastructure/__init__.py` and `infrastructure/adapters/__init__.py` MUST export relevant classes cleanly.
- **FR-027**: `CoordinatorAdapter` MUST NOT access or import `TrainingShardRepository`, `DatabaseManager`, or `sqlite3`.
- **FR-028**: `TrainingShardRepository` MUST NOT access or import `CoordinatorAdapter` or network clients.
- **FR-029**: Application entry points (`src/Client/main.py`, application services, `console_ui.py`) MUST be updated to remove dependencies on deleted legacy clients, wiring `CoordinatorAdapter` and `TrainingShardRepository` cleanly so the application launches and runs without broken imports. `console_ui.py` MUST be cleared of legacy session and bootstrap menu workflows for now, keeping it minimal and dormant without obsolete dependencies.

#### 4. Docker Containerization & Volume Persistence
- **FR-030**: `src/Client/Dockerfile` MUST be created or updated using a compatible Python base image (`python:3.11-slim`).
- **FR-031**: Dockerfile MUST set working directory to `/app`, copy dependency files (`requirements.txt`), install dependencies, copy application source code, and set entrypoint to execute the Training Client application (`CMD ["python", "main.py"]`).
- **FR-032**: Dockerfile MUST NOT hardcode `COORDINATOR_ADDRESS` or `TRAINING_CLIENT_DB_PATH`.
- **FR-033**: Container MUST configure and document `/data` as a mountable persistent volume directory for SQLite storage.
- **FR-034**: Persistence path MUST be configurable at runtime via `TRAINING_CLIENT_DB_PATH` (e.g., `TRAINING_CLIENT_DB_PATH=/data/training.db`), ensuring SQLite database files and training shard records persist across container restarts.

### Key Entities

- **`CreateTrainingTaskDto`**: High-level data transfer object representing a training task creation request sent to the Coordinator.
  - Attributes: `client_node_id` (str), `model_id` (str), `model_version` (str), `data_set_id` (str), `shard_id_list` (list[str]).
- **`CoordinatorAdapter`**: Infrastructure adapter responsible for marshaling requests, invoking Coordinator REST endpoints, validating responses, and translating network outcomes into application results.
- **`CoordinatorAdapterError`**: Root exception class for all Coordinator adapter errors, with subclasses:
  - `CoordinatorConfigurationError`: Raised when required environment configuration (`COORDINATOR_ADDRESS`) is missing or invalid.
  - `CoordinatorApiError`: Raised when Coordinator returns non-success HTTP status codes (contains `status_code` and `response_text`).
  - `CoordinatorNetworkError`: Raised when network transport fails (connection refused, timeout, DNS failure).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of training task creation requests sent by `CoordinatorAdapter` conform to Coordinator REST contract (`POST /api/training-tasks`, `Content-Type: application/json`, camelCase payload).
- **SC-002**: 100% of successful Coordinator responses returning `{"trainingTaskIds": [...]}` are mapped to a Python `list[str]` of task IDs.
- **SC-003**: 100% of non-success HTTP responses (4xx, 5xx) and malformed 2xx responses trigger structured logging and raise explicit adapter exceptions with 0% silent swallowed errors.
- **SC-004**: 100% of network failures (connection refused, timeouts) trigger structured logging and raise `CoordinatorNetworkError`.
- **SC-005**: 100% fast failure: missing or empty `COORDINATOR_ADDRESS` immediately halts adapter initialization with `CoordinatorConfigurationError`.
- **SC-006**: 0 obsolete files remain in `infrastructure/`—only `persistence/` and `adapters/` exist.
- **SC-007**: 0 broken imports across the Training Client codebase after removing legacy infrastructure files; application compiles and launches cleanly.
- **SC-008**: Training Client Docker image builds successfully and retains SQLite state across container restarts when `/data` volume is mounted.

## Assumptions

- Target Python runtime is Python 3.11+ aligned with the existing project environment and Dockerfile.
- The `requests` library (version `>=2.31.0`, already present in `requirements.txt`) is used as the HTTP client library.
- The Coordinator API implements the endpoint `POST /api/training-tasks` according to specification `012-coordinator-training-task`, returning HTTP 201 Created with JSON body `{"trainingTaskIds": ["..."]}`.
- SQLite database path is resolved by existing `DatabaseManager` using `TRAINING_CLIENT_DB_PATH`, which defaults to `/data/training.db` when deployed in Docker.
- Application-level logging uses the standard Python `logging` module configured in the application entrypoint.
