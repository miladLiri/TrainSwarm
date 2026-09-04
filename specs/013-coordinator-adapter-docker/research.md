# Research & Technical Decisions: Coordinator Adapter & Docker Infrastructure

**Feature**: `013-coordinator-adapter-docker` | **Date**: 2026-09-04

## 1. HTTP Client Selection & Lifecycle Management

### Decision
Use the Python `requests` library (`requests>=2.31.0`), configured with an explicit timeout (default 10.0 seconds) and support for an injected `requests.Session`.

### Rationale
- `requests` is already present in `src/Client/requirements.txt`, avoiding introducing redundant HTTP libraries.
- Managing connections via `requests.Session` (or scoped calls) prevents unclosed socket warnings and connection leaks across repeated calls.
- Accepting an optional `session` or transport handler in `CoordinatorAdapter.__init__` enables zero-mock automated testability: tests can inject custom adapters or mock transports (e.g. `requests_mock` or custom HTTP adapters) without requiring a live Coordinator instance.
- Synchronous I/O aligns with the synchronous Python console application model of `src/Client/`.

### Alternatives Considered
- `urllib.request`: Standard library, but significantly more boilerplate for JSON encoding, custom headers, status code inspection, and error parsing.
- `httpx`: Provides both sync and async APIs, but introduces a new third-party dependency with unnecessary complexity for a simple REST adapter.
- `aiohttp`: Requires an asynchronous event loop (`asyncio`), which introduces unnecessary architectural complexity given the current synchronous Client runtime.

---

## 2. DTO Design, Validation, and Wire Protocol Mapping

### Decision
Implement `CreateTrainingTaskDto` as a pure Python dataclass in `src/Client/infrastructure/adapters/create_training_task.py` with eager validation in `__post_init__` (or factory method) and explicit serialization to camelCase JSON via `to_dict()`.

### Rationale
- Decouples Python code conventions (`snake_case`) from Coordinator HTTP contract (`camelCase`).
- Eager validation catches missing, empty, or whitespace fields and empty shard lists immediately in memory before any network packet is transmitted.
- Dataclasses are built into the Python standard library, requiring no external validation frameworks (e.g. Pydantic).

### Alternatives Considered
- Direct Python dictionaries: Lacks static type hints, validation guarantees, and autocomplete; error-prone.
- Pydantic models: Adds an external dependency, which is unnecessary for a straightforward 5-field DTO.

---

## 3. Configuration Management & Fast Failure

### Decision
Read the Coordinator base address strictly from the `COORDINATOR_ADDRESS` environment variable (via `os.getenv("COORDINATOR_ADDRESS")` and `config.py`), normalizing it by stripping trailing slashes. If missing, empty, or whitespace-only, raise `CoordinatorConfigurationError` immediately.

### Rationale
- Conforms to Twelve-Factor App principles and containerized deployment practices.
- Prohibits hardcoded hostnames (`localhost`, `127.0.0.1`, `coordinator`) and silent fallback defaults, preventing accidental misdirection of training tasks to unintended environments.
- Normalizing trailing slashes ensures URL construction (`f"{self.base_url}/api/training-tasks"`) produces valid paths without double slashes.

### Alternatives Considered
- Defaulting to `http://localhost:8080`: Rejected because it silently masks configuration mistakes in containerized or staging deployments.
- CLI argument only: Inconvenient for Docker deployments where environment variables are the standard mechanism.

---

## 4. Exception Hierarchy & Diagnostic Logging

### Decision
Define a custom exception hierarchy rooted at `CoordinatorAdapterError`:
- `CoordinatorConfigurationError(CoordinatorAdapterError)`: Missing or invalid configuration.
- `CoordinatorApiError(CoordinatorAdapterError)`: Non-2xx HTTP responses from Coordinator, containing `status_code` and `response_text`.
- `CoordinatorNetworkError(CoordinatorAdapterError)`: Connection refused, timeout, DNS resolution failure, connection reset.

Logging uses standard `logging.getLogger("infrastructure.adapters.coordinator_adapter")` emitting structured context (address, endpoint, HTTP method, status code, error body, model ID, model version, dataset ID, shard count) at `ERROR` level before raising exceptions.

### Rationale
- Allows callers in the application layer to catch adapter errors broadly (`except CoordinatorAdapterError`) or handle specific failure classes distinctly.
- Structured logging captures necessary diagnostics without logging irrelevant payloads or sensitive data.
- Exceptions are never swallowed (e.g. returning `[]` on failure is strictly forbidden).

### Alternatives Considered
- Raising generic `RuntimeError` or `Exception`: Callers cannot differentiate between network failures and application logic errors.
- Using `print()` for error reporting: Violates TrainSwarm standards and makes production log capture unstructured.

---

## 5. Infrastructure Directory Restructuring

### Decision
Under `src/Client/infrastructure/`, maintain strictly two subdirectories:
- `adapters/`: Contains `__init__.py`, `coordinator_adapter.py`, and `create_training_task.py`.
- `persistence/`: Contains SQLite connection manager, repository, and models.

Remove obsolete files `src/Client/infrastructure/bootstrap_client.py` and `src/Client/infrastructure/coordinator_client.py`. Update `src/Client/main.py` and clear `src/Client/presentation/console_ui.py` to be a minimal dormant interface free of obsolete dependencies.

### Rationale
- Cleans technical debt and aligns with the target directory layout specified in AC-01 and AC-02.
- Maintains total isolation between persistence and networking (AC-12).
- Ensures `main.py` and `console_ui.py` do not break when obsolete clients are removed.

---

## 6. Docker Containerization & SQLite Volume Persistence

### Decision
Update `src/Client/Dockerfile` to use `python:3.11-slim`, set `WORKDIR /app`, install dependencies from `requirements.txt`, copy application source, declare `/data` volume, and configure default entrypoint `CMD ["python", "main.py"]`.

The database path is externalized via `TRAINING_CLIENT_DB_PATH` (defaulting to `/data/training.db` when containerized), and `COORDINATOR_ADDRESS` is provided at runtime.

### Rationale
- SQLite database resides in `/data`, which is mounted to a Docker volume, ensuring all local shard state persists across container restarts and recreations.
- Neither `COORDINATOR_ADDRESS` nor `TRAINING_CLIENT_DB_PATH` are hardcoded in the Docker image, satisfying AC-15.
- Unbuffered Python (`ENV PYTHONUNBUFFERED=1`) ensures container logs stream in real time.
