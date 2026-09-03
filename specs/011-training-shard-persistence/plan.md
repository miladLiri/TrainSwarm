# Implementation Plan: Training Client — Local Training Shard Persistence Infrastructure

**Branch**: `011-training-shard-persistence` | **Date**: 2026-09-03 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/011-training-shard-persistence/spec.md)

**Input**: Feature specification from `/specs/011-training-shard-persistence/spec.md`

## Summary

Implement the local persistence infrastructure for the Python Training Client to durably track dataset shards available for training. The implementation introduces pure domain models (`TrainingShard` and `TrainingShardStatus`), a dedicated persistence infrastructure layer (`DatabaseManager` and `TrainingShardRepository`), and a local SQLite storage backend. The design strictly preserves domain isolation from persistence technologies (zero database imports in domain), externalizes database configuration via `TRAINING_CLIENT_DB_PATH` with a transparent `./training.db` fallback, provides idempotent schema initialization, ensures composite key uniqueness over `(model_id, model_version, dataset_id, shard_id)`, handles JSON serialization of arbitrary `metrics` and `training_metadata`, executes atomic batch transactions, provides thread-safe synchronous operations, and delivers a runnable zero-mock verification suite in `samples/persistence_test/` satisfying TrainSwarm Constitution quality gates.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: Python standard library (`sqlite3`, `pathlib`, `logging`, `typing`, `dataclasses`, `enum`, `json`, `uuid`, `os`, `contextlib`) — zero external third-party dependencies required.

**Storage**: Local SQLite database file configured via `TRAINING_CLIENT_DB_PATH` (defaulting to `./training.db`) containing table `training_shards` and composite unique index `uq_training_shards_logical_shard`.

**Testing**: Active execution and standalone CLI validation via `samples/persistence_test/verify_persistence.py` and syntax check via `python -m py_compile` per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux, macOS (Cross-platform Python execution).

**Project Type**: Data Plane Client Local Persistence Infrastructure & Domain Models.

**Performance Goals**:
- Single shard insert latency < 5ms.
- Bulk shard save (100 records) latency < 50ms via single atomic transaction batch.
- Point lookups (`get_by_id`, `get_by_shard_key`) < 1ms using primary key and composite unique B-Tree indexes.
- Zero memory leakage via scoped connection lifecycle management.

**Constraints**:
- Strict domain decoupling: `domain/` MUST NOT import `sqlite3` or persistence infrastructure classes.
- Insert-only create operations: `save()` and `bulk_save()` reject existing composite keys with `DuplicateShardError`; in-place updates are deferred.
- Thread safety: connection-per-operation pattern with `PRAGMA busy_timeout = 5000` to prevent thread-crossing and database-lock errors.
- Atomic transactions: all-or-nothing writes; failed transactions leave zero partial records.
- Zero mocks or stubs.

**Scale/Scope**: 5 new/updated source files in `src/Client/`, 1 verification script in `samples/persistence_test/`, and 5 specification/design artifacts in `specs/011-training-shard-persistence/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. The persistence subsystem is purely local to the Client data plane. Coordinator and Bootstrap services have zero awareness of or access to the local SQLite database.
- **II. Language, Runtime, and Application Strictness**: PASS. Implemented strictly in Python using standard library `sqlite3` within the existing Python console application (`Client`).
- **III. Explicit Contracts & Boundaries**: PASS. `TrainingShard` domain model and `TrainingShardRepository` contract define explicit, strongly typed boundaries with JSON schema and repository interface specifications.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Uses simple, explicit standard library code without heavy ORMs (like SQLAlchemy) or unnecessary abstractions; clear custom exception hierarchy; descriptive structured logging.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero stubs, zero test frameworks (no unittest/pytest), zero crypto, zero RCE. Uses real SQLite files, real transactions, and active execution validation.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Real table creation, real SQLite B-tree unique indexes, real parameterized SQL queries, real JSON serialization/deserialization, and real error handling.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Mandatory post-change verification via `python -m py_compile` and standalone executable verification script `samples/persistence_test/verify_persistence.py`.

## Project Structure

### Documentation (this feature)

```text
specs/011-training-shard-persistence/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 research output (technical decisions & patterns)
├── data-model.md        # Phase 1 data model & SQLite schema
├── quickstart.md        # Phase 1 verification & execution guide
├── contracts/           # Phase 1 interface contracts
│   ├── training-shard.schema.json
│   └── training-shard-repository-contract.md
├── checklists/
│   └── requirements.md  # Requirements quality checklist (16/16 passing)
└── tasks.md             # Phase 2 task decomposition (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/Client/
├── domain/
│   ├── __init__.py                                 # Re-exports models, TrainingShard, TrainingShardStatus
│   ├── models.py                                   # Existing Client models (Session, ClientNode)
│   └── training_shard.py                           # New TrainingShard entity & TrainingShardStatus enum
│
├── infrastructure/
│   ├── persistence/
│   │   ├── __init__.py                             # Re-exports DatabaseManager, TrainingShardRepository, exceptions
│   │   ├── exceptions.py                           # PersistenceError, DuplicateShardError, etc.
│   │   ├── database.py                             # DatabaseManager, path resolution, idempotent DDL init
│   │   └── training_shard_repository.py            # TrainingShardRepository implementation
│   ├── bootstrap_client.py                         # Existing Bootstrap client
│   └── coordinator_client.py                       # Existing Coordinator client
│
├── config.py                                       # Client configuration
└── main.py                                         # Console application entry point

samples/
└── persistence_test/
    └── verify_persistence.py                       # Active runnable verification script
```

**Structure Decision**:
- Domain models are placed in `src/Client/domain/training_shard.py` to maintain total decoupling from persistence infrastructure and database libraries.
- Database configuration, connection management, and schema initialization are encapsulated in `src/Client/infrastructure/persistence/database.py`.
- Repository implementation is placed in `src/Client/infrastructure/persistence/training_shard_repository.py`.
- Custom exceptions are isolated in `src/Client/infrastructure/persistence/exceptions.py`.
- All persistence components are re-exported through clean package `__init__.py` files.
- Active verification script is placed in `samples/persistence_test/verify_persistence.py` following repo conventions (e.g. `samples/distributed_training_test/`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | Direct standard library `sqlite3` without ORM chosen to maintain minimum complexity. |
