# Implementation Research: Training Client — Local Training Shard Persistence Infrastructure

**Feature Branch**: `011-training-shard-persistence`  
**Date**: 2026-09-03  
**Status**: Completed  

## Overview

This document captures the architectural decisions, technology selections, and concurrency patterns for the local SQLite persistence infrastructure in the Python Training Client.

---

## Technical Decisions

### 1. SQLite Persistence Engine: Python Standard Library `sqlite3`

- **Decision**: Use Python's built-in `sqlite3` module directly without third-party ORMs or external database frameworks.
- **Rationale**:
  - `sqlite3` is part of the Python standard library, requiring zero additional package dependencies.
  - Aligns with TrainSwarm Constitution Principle IV (MVP Focus: clarity over premature abstraction; build simple, explicit code) and Principle V (No Large Frameworks).
  - Provides deterministic transaction control (`BEGIN`, `COMMIT`, `ROLLBACK`) and direct SQL inspection.
  - Complete control over parameterized queries and constraint handling without ORM magic or leaky abstractions.
- **Alternatives Considered**:
  - *SQLAlchemy / Peewee*: Rejected due to unnecessary dependency footprint, complex session lifecycles, and risk of leaking ORM model classes into the pure domain layer.
  - *Raw JSON / Flat-File Storage*: Rejected because flat files lack ACID transaction guarantees, process crash recovery, indexed composite lookups, and concurrent access safety.

---

### 2. SQLite Concurrency & Connection Lifecycle Pattern

- **Decision**: Scoped, context-managed connections per repository operation with explicit timeout and foreign key pragmas.
- **Rationale**:
  - SQLite connections in Python default to `check_same_thread=True` and cannot be safely passed across thread boundaries without concurrency hazards or lock contention.
  - A scoped connection manager (`DatabaseManager.get_connection()`) creates a short-lived connection per operation (or uses a clean context manager pattern with `autocommit=False`), ensuring all operations commit or rollback cleanly within their execution context.
  - Setting `PRAGMA busy_timeout = 5000` ensures concurrent threads wait up to 5 seconds for lock release rather than immediately failing with `sqlite3.OperationalError: database is locked`.
  - Enables thread-safety for concurrent worker threads in the Training Client without global locking bottlenecks.
- **Alternatives Considered**:
  - *Global Singleton Connection*: Rejected because SQLite connections cannot be safely shared across concurrent threads in Python without disabling thread checks and risking corruption.
  - *Thread-Local Connection Pooling*: Rejected as premature complexity for an MVP console application. Context-managed short-lived connections in SQLite have near-zero overhead on local disks.

---

### 3. Serialization Strategy for `metrics` and `training_metadata`

- **Decision**: Serialize arbitrary dictionary payloads into UTF-8 JSON text strings for storage in SQLite `TEXT` columns, deserializing back to native Python `dict` structures on read.
- **Rationale**:
  - Training metrics (e.g., loss, accuracy, gradient norms) and execution metadata (e.g., duration, hardware info) vary widely across models and training tasks.
  - JSON serialization preserves nested structure and arbitrary primitive types (`int`, `float`, `str`, `list`, `dict`) while keeping the SQLite schema rigid and normalized.
  - Native Python `json.dumps()` and `json.loads()` provide fast, safe, standards-compliant parsing.
  - Shard instances with `None` metrics/metadata store SQL `NULL` and deserialize to `None`.
- **Alternatives Considered**:
  - *Pickle / Binary BLOB*: Rejected due to security vulnerabilities, non-human-readability, and version compatibility risks across Python runtimes.
  - *Normalized Metrics Table*: Rejected as premature optimization. Training metrics are written once upon completion and retrieved as a cohesive unit with the shard.

---

### 4. Idempotent Schema Creation and Table Initialization

- **Decision**: Execute DDL statements using `CREATE TABLE IF NOT EXISTS` and `CREATE UNIQUE INDEX IF NOT EXISTS` during application startup within `DatabaseManager.initialize_database()`.
- **Rationale**:
  - Guarantees that the required tables and indexes exist before any repository operation executes.
  - Completely idempotent: running initialization multiple times across process restarts leaves existing tables, columns, constraints, and persisted records intact.
  - Automatically provisions parent directories using `os.makedirs(db_path.parent, exist_ok=True)` if they do not yet exist.
- **Alternatives Considered**:
  - *External Migration Engines (Alembic / Flyway)*: Rejected as unnecessary overhead for a single-table client persistence layer in MVP phase.
  - *Lazy Schema Initialization on First Save*: Rejected because initialization failures (such as directory permission errors) should fail fast at startup rather than during training.

---

### 5. Environment-Based Configuration Resolution

- **Decision**: Resolve database path from `TRAINING_CLIENT_DB_PATH`, falling back silently to `./training.db` when unset or empty (per Clarification Q1).
- **Rationale**:
  - Fully externalizes the database path, allowing containerized runs, testing environments, and different deployment hosts to configure storage without source modifications.
  - Silent fallback to `./training.db` enables immediate local developer execution without mandatory environment variable setup.
  - Path resolution converts relative paths to absolute paths (`pathlib.Path.resolve()`) so behavior remains stable regardless of directory switches.
- **Alternatives Considered**:
  - *Mandatory Environment Variable (Fail Fast)*: Evaluated and presented in Clarification Q1, but user chose Option B (silent fallback to `./training.db`).
  - *Hardcoded Path in Repository*: Strictly forbidden by Constitution and specification.

---

### 6. Strict Insert-Only Semantics and Duplicate Enforcement

- **Decision**: Implement `save()` and `bulk_save()` as strictly insert-only operations (`INSERT INTO training_shards`), catching `sqlite3.IntegrityError` to raise `DuplicateShardError` (per Clarification Q4).
- **Rationale**:
  - Composite uniqueness is enforced over `(model_id, model_version, dataset_id, shard_id)`.
  - Enforcing insert-only semantics prevents accidental overwrite of existing shard state.
  - The user explicitly decided in Clarification Q4 that in-place updates are deferred to future training execution features.
  - When a unique constraint violation occurs, the transaction rolls back cleanly, leaving zero partial or mutated state.
- **Alternatives Considered**:
  - *Upsert (`INSERT ... ON CONFLICT DO UPDATE`)*: Rejected because the user chose Option C in clarification to keep `save()` strictly insert-only and prevent masked bugs.
  - *Explicit `update()` Method*: Rejected because updating mutable lifecycle state is explicitly deferred to future features.

---

### 7. Exception Hierarchy and Failure Propagation

- **Decision**: Provide custom domain exceptions in `src/Client/infrastructure/persistence/exceptions.py` inheriting from a base `PersistenceError`.
  - `PersistenceError` (base)
    - `DatabaseConfigurationError` (invalid path or configuration)
    - `DatabaseInitializationError` (schema/DDL failure or unwriteable directory)
    - `DuplicateShardError` (composite key uniqueness violation)
    - `ShardNotFoundError` (lookup failure when expected)
    - `SerializationError` (metrics/metadata JSON encoding or decoding failure)
- **Rationale**:
  - Hides internal `sqlite3.Error` implementation details from calling layers.
  - Provides rich error messages with context (model_id, shard_id, path).
  - Guarantees that persistence errors are never silently swallowed.
