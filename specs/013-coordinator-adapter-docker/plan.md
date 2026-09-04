# Implementation Plan: Training Client — Coordinator Adapter and Docker Infrastructure

**Branch**: `013-coordinator-adapter-docker` | **Date**: 2026-09-04 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/013-coordinator-adapter-docker/spec.md)

**Input**: Feature specification from `/specs/013-coordinator-adapter-docker/spec.md`

## Summary

Extend the Python Training Client with a dedicated Coordinator API adapter (`CoordinatorAdapter`), enabling the Training Client to submit training task creation requests to the Coordinator (`POST /api/training-tasks`). The implementation introduces `infrastructure/adapters/coordinator_adapter.py` and `create_training_task.py` with `CreateTrainingTaskDto` (mapping Python attributes to camelCase wire JSON), reads `COORDINATOR_ADDRESS` with fast-fail validation, executes robust response validation and diagnostic error logging, and surfaces typed exceptions (`CoordinatorApiError`, `CoordinatorNetworkError`, `CoordinatorAdapterError`). 

The implementation cleans up obsolete infrastructure files (`bootstrap_client.py` and `coordinator_client.py`), leaving strictly `adapters/` and `persistence/` under `src/Client/infrastructure/`, updates `src/Client/main.py`, and clears `src/Client/presentation/console_ui.py`. Finally, it updates the Training Client `Dockerfile` with runtime environment configuration and configures `/data` as a mountable persistent Docker volume for the local SQLite database.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `requests>=2.31.0`, `python-dotenv>=1.0.0`, standard library (`pathlib`, `logging`, `dataclasses`, `os`, `json`, `typing`, `sqlite3`).

**Storage**: Local SQLite database via existing `DatabaseManager` and `TrainingShardRepository`, configured via `TRAINING_CLIENT_DB_PATH` (defaults to `/data/training.db` when containerized, or `./training.db` locally).

**Testing**: Syntax validation via `python -m py_compile`, active zero-mock execution via `samples/coordinator_adapter_test/verify_coordinator_adapter.py` validating fast-fail config, serialization, error escalation, and isolation per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux (Docker container `python:3.11-slim`), macOS.

**Project Type**: Data Plane Client Infrastructure Adapter & Docker Containerization.

**Performance Goals**:
- Adapter request serialization and dispatch latency < 5ms local CPU overhead.
- Explicit network request timeout: default 10.0 seconds to prevent thread blocking.
- Zero socket or connection leaks via managed `requests.Session`.

**Constraints**:
- Strict boundary isolation: `CoordinatorAdapter` MUST NOT import SQLite, `DatabaseManager`, or `TrainingShardRepository`.
- No hardcoded addresses: `COORDINATOR_ADDRESS` must be supplied at runtime; missing variable immediately raises `CoordinatorConfigurationError`.
- Clean infrastructure: only `adapters/` and `persistence/` remain under `src/Client/infrastructure/`.
- No swallowed exceptions: all HTTP and network errors are logged and propagated.
- Persistent SQLite state: Docker volume mount at `/data` retains database file across container recreation.

**Scale/Scope**: 5 modified/new files in `src/Client/`, 2 obsolete files deleted, 1 Dockerfile update, 1 verification suite in `samples/coordinator_adapter_test/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. The adapter strictly communicates over REST to the Coordinator control plane; data plane storage remains strictly local in SQLite.
- **II. Language, Runtime, and Application Strictness**: PASS. Implemented in Python 3.11 for the Client console application, using REST for control-plane communication.
- **III. Explicit Contracts & Boundaries**: PASS. `CreateTrainingTaskDto` strictly encapsulates the wire contract with explicit camelCase JSON mapping and DTO validation.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Uses established `requests` library; simple, explicit dataclass and adapter class; custom exception hierarchy; structured logging via Python `logging`.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero stubs, zero test frameworks (no unittest/pytest), zero crypto, zero RCE. Uses real HTTP calls or real injectable transport handlers for active verification.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Real HTTP serialization, real socket timeouts, real status code validation, real logging, and real Docker volume mounts.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Post-change validation via `python -m py_compile` and standalone executable verification script `samples/coordinator_adapter_test/verify_coordinator_adapter.py`.

## Project Structure

### Documentation (this feature)

```text
specs/013-coordinator-adapter-docker/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 technical research & decisions
├── data-model.md        # Phase 1 DTO & adapter design models
├── quickstart.md        # Phase 1 verification & execution guide
├── contracts/           # Phase 1 interface contracts
│   ├── coordinator-adapter-contract.md
│   └── create-training-task.schema.json
├── checklists/
│   └── requirements.md  # Requirements quality checklist (16/16 passing)
└── tasks.md             # Phase 2 task decomposition (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/Client/
├── Dockerfile                                      # Updated Dockerfile: /data volume, python:3.11-slim
├── requirements.txt                                # requests>=2.31.0, python-dotenv>=1.0.0
├── config.py                                       # Loads COORDINATOR_ADDRESS and client config
├── main.py                                         # Console application entry point (wired with adapter & repo)
├── domain/
│   ├── __init__.py                                 # Domain models exports
│   ├── models.py                                   # Client models
│   └── training_shard.py                           # TrainingShard & TrainingShardStatus
│
├── infrastructure/
│   ├── __init__.py                                 # Re-exports adapters & persistence
│   ├── adapters/
│   │   ├── __init__.py                             # Re-exports CoordinatorAdapter, CreateTrainingTaskDto, exceptions
│   │   ├── coordinator_adapter.py                  # CoordinatorAdapter class & exceptions
│   │   └── create_training_task.py                 # CreateTrainingTaskDto dataclass
│   └── persistence/
│       ├── __init__.py                             # Re-exports DatabaseManager, TrainingShardRepository, exceptions
│       ├── database.py                             # DatabaseManager & SQLite connection lifecycle
│       ├── exceptions.py                           # PersistenceError, DuplicateShardError, etc.
│       └── training_shard_repository.py            # TrainingShardRepository implementation
│
└── presentation/
    ├── __init__.py
    └── console_ui.py                               # Cleared minimal/dormant console UI

samples/
└── coordinator_adapter_test/
    └── verify_coordinator_adapter.py               # Active runnable verification suite
```

**Structure Decision**:
- `src/Client/infrastructure/adapters/` contains `coordinator_adapter.py` and `create_training_task.py`, encapsulating all HTTP communication, URL building, and JSON mapping.
- Obsolete infrastructure files (`src/Client/infrastructure/bootstrap_client.py` and `src/Client/infrastructure/coordinator_client.py`) are deleted.
- `src/Client/infrastructure/persistence/` remains untouched and fully isolated from adapter logic.
- `src/Client/main.py` is updated to initialize `CoordinatorAdapter` and `TrainingShardRepository` cleanly, and `src/Client/presentation/console_ui.py` is cleared of legacy session/bootstrap menu workflows.
- `src/Client/Dockerfile` is configured with `VOLUME ["/data"]` and runtime environment variable support.
- A runnable verification suite is placed in `samples/coordinator_adapter_test/verify_coordinator_adapter.py` to verify all acceptance criteria without third-party test runners.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | Direct `requests` library and pure dataclasses chosen to maintain minimal complexity. |
