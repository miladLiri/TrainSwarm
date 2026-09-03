# Feature Specification: Training Client — Local Training Shard Persistence Infrastructure

**Feature Branch**: `011-training-shard-persistence`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Implement local persistence infrastructure for the Python Training Client. The Training Client must maintain persistent local state for every dataset shard that has been created and is available for training using SQLite, accessed via TrainingShardRepository, configured via TRAINING_CLIENT_DB_PATH, with TrainingShard domain model, TrainingShardStatus enum, JSON serialized metrics and training metadata, composite uniqueness protection, and clear architectural separation."

## Clarifications

### Session 2026-09-03

- **Q1: Missing Database Configuration Behavior**: When `TRAINING_CLIENT_DB_PATH` is not defined or empty, how should initialization behave?
  - **A**: Silently fall back to `./training.db` relative to the application working directory (Option B).
- **Q2: Query & Retrieval Methods on `TrainingShardRepository`**: Which query methods should be included in the initial repository interface?
  - **A**: Include primary key lookup `get_by_id(id: str) -> Optional[TrainingShard]` and composite key lookup `get_by_shard_key(model_id: str, model_version: str, dataset_id: str, shard_id: str) -> Optional[TrainingShard]` (Option A).
- **Q3: Concurrency and Execution Model Interface**: How should the repository execution interface be shaped?
  - **A**: Provide a thread-safe synchronous repository API with scoped connection management matching the current synchronous Training Client runtime and safe for worker threads (Option A).
- **Q4: Shard Lifecycle Updates Scope**: How should `TrainingShardRepository` handle updating mutable lifecycle fields on an existing persisted shard?
  - **A**: Keep `save()` and `bulk_save()` strictly insert-only; in-place updating of existing shard records is explicitly out of scope for this initial persistence slice and deferred to future training execution features (Option C).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persistent Local Tracking and Atomic Shard Storage (Priority: P1)

As the Training Client application, I want to store and track local dataset shards (including model ID, distributed engine model type, model version, dataset ID, shard ID, local artifact path, sample count, and training status) in a durable local database through a clean repository abstraction, so that dataset shards available for training are persistently recorded and remain resilient to client restarts.

**Why this priority**: Core foundational capability of local training data management. Without persistent shard state, the client cannot track local dataset partitions across training iterations or resume pending training runs after restarts.

**Independent Test**: Instantiate a `TrainingShard` domain model with valid identifiers, positive sample count, and status `READY`. Invoke `TrainingShardRepository.save(shard)`. Inspect the underlying storage to verify that all attributes are faithfully persisted without data loss or schema truncation, and verify that attempting to save an invalid shard (e.g. non-positive sample count) is rejected.

**Acceptance Scenarios**:

1. **Given** a valid `TrainingShard` instance with required fields (`id` as a UUID, `model_id`, `model_type`, `model_version`, `dataset_id`, `shard_id`, `artifact_path`, `sample_count > 0`, and `status = TrainingShardStatus.READY`), **When** `TrainingShardRepository.save()` is executed, **Then** all fields are committed atomically to the local persistence store.
2. **Given** a list of multiple valid `TrainingShard` instances, **When** `TrainingShardRepository.bulk_save()` is executed, **Then** all shards are persisted within an atomic transaction, ensuring either all records are saved or none are committed on failure.
3. **Given** an invalid `TrainingShard` where `sample_count <= 0`, **When** persistence is attempted, **Then** the repository rejects the operation with an explicit validation error, preventing invalid state from entering the database.
4. **Given** persisted shards in the database, **When** the Training Client process restarts, **Then** the database does not re-initialize destructively, and all previously stored shard records remain intact and recoverable.

---

### User Story 2 - Structured Metrics and Training Metadata Serialization (Priority: P2)

As the Training Client application, I want to associate arbitrary training metrics (e.g., loss, accuracy, epochs) and training execution metadata (e.g., duration, hardware info) with a training shard using native Python dictionaries that are transparently serialized to JSON in SQLite and deserialized back into structured Python objects upon retrieval, so that diverse model architectures and training routines can record custom telemetry without altering database schemas.

**Why this priority**: Different training algorithms and model families produce varied telemetry. Flexible, schema-independent serialization decouples application metrics from the relational schema while preserving structured object representations in the domain layer.

**Independent Test**: Save a `TrainingShard` containing populated `metrics` and `training_metadata` dictionaries. Reload the record through `TrainingShardRepository.get_by_id()` and assert that the returned domain object contains identical structured dictionary values matching the original payload.

**Acceptance Scenarios**:

1. **Given** a `TrainingShard` with arbitrary metrics (e.g., `{"loss": 0.342, "accuracy": 0.87, "epochs": 3}`) and metadata (e.g., `{"duration": 1000}`), **When** saved via the repository, **Then** the dictionaries are stored as serialized JSON strings in the database.
2. **Given** a persisted shard record with serialized JSON metrics and metadata, **When** retrieved through `get_by_id()` or `get_by_shard_key()`, **Then** the JSON strings are parsed back into native structured Python dictionaries.
3. **Given** a newly created shard before training has commenced (`metrics = None`, `training_metadata = None`, `update_artifact_path = None`, `training_task_id = None`), **When** saved and retrieved, **Then** these nullable fields remain `None` without serialization errors.
4. **Given** corrupted or non-JSON data encountered in storage for metrics or metadata, **When** the repository attempts to load the record, **Then** it raises an explicit deserialization error rather than returning corrupt or partially parsed structures.

---

### User Story 3 - Composite Key Uniqueness and Duplicate Shard Protection (Priority: P3)

As the Training Client application, I want the persistence layer to enforce composite uniqueness over `(model_id, model_version, dataset_id, shard_id)`, so that the client cannot inadvertently persist duplicate records for the same logical dataset shard and model version.

**Why this priority**: Guarantees data integrity. Multiple training jobs or repeated partition announcements must not create competing or duplicate records for the same training shard and model checkpoint version.

**Independent Test**: Persist a shard with a specific `(model_id, model_version, dataset_id, shard_id)`. Attempt to persist a second shard with a different primary key `id` but identical composite key attributes. Verify that the repository rejects the operation with a duplicate record / unique constraint violation error.

**Acceptance Scenarios**:

1. **Given** an existing persisted shard for `(model_id = M1, model_version = 1, dataset_id = D1, shard_id = S1)`, **When** an attempt is made to save a new record with identical composite key values, **Then** the repository raises a `DuplicateShardError` (or unique constraint violation) and the duplicate record is rejected.
2. **Given** a `bulk_save()` operation containing duplicate composite keys within the batch or conflicting with an existing record, **When** executed, **Then** the entire batch transaction rolls back atomically, leaving no duplicate or partially written records.
3. **Given** an existing record, **When** saving a new shard with the same `(model_id, dataset_id, shard_id)` but a *different* `model_version` (e.g., version 2), **Then** the record is successfully persisted as a distinct training state.

---

### User Story 4 - Environment-Driven Configuration and Idempotent Initialization (Priority: P4)

As a system operator or developer deploying the Training Client, I want the persistence layer to configure its SQLite database path through the environment variable `TRAINING_CLIENT_DB_PATH` with fallback to `./training.db`, automatically creating parent directories when necessary and initializing schemas idempotently, so that database management is fully decoupled from application code and resilient to repeated process launches.

**Why this priority**: Required for containerized and automated deployments across diverse host environments, preventing hardcoded file paths and ensuring predictable startup behavior.

**Independent Test**: Set `TRAINING_CLIENT_DB_PATH` to a temporary path with nested non-existent directories. Trigger persistence initialization. Verify that all parent directories are safely created, the SQLite database is provisioned with the `training_shards` table and indexes, and subsequent re-initializations do not alter existing tables or delete existing rows. Unset `TRAINING_CLIENT_DB_PATH` and verify silent fallback to `./training.db`.

**Acceptance Scenarios**:

1. **Given** `TRAINING_CLIENT_DB_PATH` pointing to a file in a non-existent parent directory, **When** the database infrastructure initializes, **Then** the directory hierarchy is created and the SQLite database file is initialized with the required schema.
2. **Given** `TRAINING_CLIENT_DB_PATH` is not set or is empty, **When** persistence initializes, **Then** the system silently falls back to `./training.db`.
3. **Given** an already initialized database containing existing shard records, **When** the application starts again and runs initialization, **Then** the initialization executes idempotently without destroying existing tables or modifying existing records.
4. **Given** an unwriteable database path or permission failure, **When** persistence initialization runs, **Then** an explicit persistence configuration/initialization error is raised, aborting startup cleanly.

---

### Edge Cases

- **Missing Configuration Variable**: When `TRAINING_CLIENT_DB_PATH` is unset or empty, the persistence layer cleanly falls back to `./training.db` in the current working directory.
- **Process Termination During Persistence**: If the client process terminates abruptly during `save()` or `bulk_save()`, transactional rollback ensures no orphaned or half-written rows exist in SQLite.
- **Corrupted JSON Strings**: If database contents are manually altered to contain invalid JSON strings in `metrics` or `training_metadata`, loading the shard via `get_by_id()` or `get_by_shard_key()` must fail with a descriptive parsing error instead of crashing silently.
- **Extreme Sample Counts**: Sample counts of 0 or negative integers must be rejected by both domain validation and database check constraints (`sample_count > 0`).
- **Concurrent Repository Access**: Scoped connection management ensures each thread or operation maintains its own SQLite connection or uses appropriate serialization locks to avoid database lock contention.
- **Special Characters in Identifiers**: Model IDs, versions, dataset IDs, and shard IDs containing slashes, dashes, dots, or underscores must be preserved accurately as opaque strings without SQL injection vulnerability via parameterized queries.
- **Attempting to Overwrite or Update Existing Records**: Because `save()` and `bulk_save()` are strictly insert-only, passing an existing record raises `DuplicateShardError` rather than updating in-place.

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Domain Model (`domain/training_shard.py`)
- **FR-001**: System MUST provide a `TrainingShard` domain model representing the local persistent training state of one dataset shard for one model version.
- **FR-002**: `TrainingShard` MUST contain exactly the following attributes:
  - `id` (`str`): Unique local identifier (UUID string, database primary key).
  - `model_id` (`str`): Identifier of the model being trained (required, non-empty).
  - `model_type` (`str`): Distributed training engine model type / architecture (required, opaque string).
  - `model_version` (`str`): Version of the global model/checkpoint against which this shard is trained (required, non-empty).
  - `dataset_id` (`str`): Identifier of the dataset (required, non-empty).
  - `shard_id` (`str`): Identifier of the dataset shard (required, non-empty).
  - `artifact_path` (`str`): Local filesystem path to the dataset shard artifact (required, full path).
  - `sample_count` (`int`): Number of training samples contained in the shard (required, strictly positive `> 0`).
  - `status` (`TrainingShardStatus`): Training lifecycle status.
  - `metrics` (`Optional[Dict[str, Any]]`): Arbitrary training metrics dictionary (nullable).
  - `training_metadata` (`Optional[Dict[str, Any]]`): Arbitrary training metadata dictionary (nullable).
  - `update_artifact_path` (`Optional[str]`): Full local filesystem path to the generated update/delta artifact (initially `None`, populated upon training completion).
  - `training_task_id` (`Optional[str]`): Identifier of the assigned training task (initially `None`, populated upon task assignment).
- **FR-003**: System MUST provide a `TrainingShardStatus` enum containing exactly four states: `READY`, `TRAINING`, `COMPLETED`, and `FAILED`, with stable lowercase string values (`"ready"`, `"training"`, `"completed"`, `"failed"`).
- **FR-004**: Domain models MUST NOT depend on SQLite, SQL libraries, or persistence infrastructure classes.

#### 2. Persistence Infrastructure & Database Schema (`infrastructure/persistence/database.py`)
- **FR-005**: SQLite database MUST store records in a table named `training_shards` with the following schema:
  - `id TEXT PRIMARY KEY`
  - `model_id TEXT NOT NULL`
  - `model_type TEXT NOT NULL`
  - `model_version TEXT NOT NULL`
  - `dataset_id TEXT NOT NULL`
  - `shard_id TEXT NOT NULL`
  - `artifact_path TEXT NOT NULL`
  - `sample_count INTEGER NOT NULL CHECK (sample_count > 0)`
  - `status TEXT NOT NULL`
  - `metrics TEXT NULL`
  - `training_metadata TEXT NULL`
  - `update_artifact_path TEXT NULL`
  - `training_task_id TEXT NULL`
- **FR-006**: SQLite database MUST enforce a composite unique constraint or unique index on `(model_id, model_version, dataset_id, shard_id)`.
- **FR-007**: Database initialization MUST be idempotent, creating tables and indexes if they do not exist while preserving existing records across application restarts.
- **FR-008**: Database infrastructure MUST automatically create parent directories for the database file if they do not exist.
- **FR-009**: Database path MUST be read from the environment variable `TRAINING_CLIENT_DB_PATH`.
- **FR-010**: If `TRAINING_CLIENT_DB_PATH` is not defined or is empty, the database infrastructure MUST silently fall back to `./training.db`.

#### 3. Repository Abstraction (`infrastructure/persistence/training_shard_repository.py`)
- **FR-011**: System MUST provide a `TrainingShardRepository` class that abstracts all database access and operates exclusively using `TrainingShard` domain models.
- **FR-012**: `TrainingShardRepository` MUST provide `save(training_shard: TrainingShard) -> None` to atomically persist a single new shard. This operation is strictly insert-only; in-place updating of existing records is deferred to future training execution features.
- **FR-013**: `TrainingShardRepository` MUST provide `bulk_save(training_shards: List[TrainingShard]) -> None` to atomically persist multiple new shards in a single transaction (strictly insert-only).
- **FR-014**: `TrainingShardRepository` MUST provide point retrieval methods:
  - `get_by_id(id: str) -> Optional[TrainingShard]` to look up a shard by its primary key UUID.
  - `get_by_shard_key(model_id: str, model_version: str, dataset_id: str, shard_id: str) -> Optional[TrainingShard]` to look up a shard by its unique logical composite key.
- **FR-015**: `TrainingShardRepository` MUST provide a thread-safe synchronous API (`save`, `bulk_save`, `get_by_id`, `get_by_shard_key`) with scoped connection management.
- **FR-016**: `TrainingShardRepository` MUST serialize `metrics` and `training_metadata` to JSON strings on storage, and deserialize JSON strings back into Python dictionaries on retrieval.
- **FR-017**: `TrainingShardRepository` MUST serialize `status` using the stable string representation of `TrainingShardStatus`.
- **FR-018**: If a save operation encounters a duplicate composite key `(model_id, model_version, dataset_id, shard_id)`, the repository MUST raise an explicit domain exception (`DuplicateShardError`).
- **FR-019**: All failed database transactions MUST roll back cleanly without leaving partial or corrupted records.
- **FR-020**: Persistence errors (connection failure, disk error, schema error, constraint violation) MUST NOT be swallowed and MUST be surfaced to callers as meaningful persistence exceptions (`PersistenceError`, `DuplicateShardError`, `DatabaseConfigurationError`, `DatabaseInitializationError`).

#### 4. Architectural Boundaries
- **FR-021**: The persistence layer MUST NOT contain business logic for downloading/uploading dataset shards, scheduling training, training models, generating updates, or communicating over the network with the Coordinator or P2P sidecar.
- **FR-022**: Application layers outside the persistence infrastructure MUST NOT open SQLite connections, execute raw SQL, construct database tables, or directly read `TRAINING_CLIENT_DB_PATH`.
- **FR-023**: In-place updating or mutation of already-persisted `TrainingShard` records is explicitly out of scope for this persistence infrastructure capability and will be specified in future training task execution features.

### Key Entities

- **`TrainingShard`**: Domain entity representing the local lifecycle and state of a single dataset shard partition for a specific model checkpoint version.
  - Attributes: `id` (str UUID), `model_id` (str), `model_type` (str), `model_version` (str), `dataset_id` (str), `shard_id` (str), `artifact_path` (str), `sample_count` (int), `status` (TrainingShardStatus), `metrics` (dict|None), `training_metadata` (dict|None), `update_artifact_path` (str|None), `training_task_id` (str|None).
- **`TrainingShardStatus`**: Domain enumeration representing shard lifecycle states (`READY`, `TRAINING`, `COMPLETED`, `FAILED`).
- **`TrainingShardRepository`**: Repository abstraction exposing clean persistence operations (`save`, `bulk_save`, `get_by_id`, `get_by_shard_key`) to the application layer.
- **`DatabaseManager` / Persistence Infrastructure**: Internal persistence component responsible for environment resolution, connection lifecycle, migration, schema creation, and transaction management.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of persisted `TrainingShard` records survive application restarts with complete state preservation across all 13 domain fields.
- **SC-002**: 100% of duplicate persistence attempts for the same `(model_id, model_version, dataset_id, shard_id)` combination are rejected with explicit uniqueness errors without corrupting the database.
- **SC-003**: 100% round-trip fidelity for arbitrary `metrics` and `training_metadata` dictionaries between Python domain objects and SQLite JSON text.
- **SC-004**: 0% partial records written when transaction failures occur during single or bulk save operations (strict all-or-nothing atomicity).
- **SC-005**: 100% decoupling of domain models: zero imports of `sqlite3` or persistence modules anywhere in `domain/`.
- **SC-006**: 100% of database path configuration externalized: zero hardcoded database file paths in domain or repository source code.

## Assumptions

- Python 3.10+ standard library `sqlite3` is available in the runtime environment.
- The Training Client application process has filesystem write permissions to the directory specified by `TRAINING_CLIENT_DB_PATH` or the working directory for `./training.db`.
- Dataset shard files (`artifact_path`) and training delta artifacts (`update_artifact_path`) reside on the local filesystem and are managed by other Training Client components; SQLite stores only their absolute paths.
- Training shard `id` values are UUID4 strings generated in Python before passing to `save()`.
- Metrics and metadata dictionaries contain JSON-serializable primitives (numbers, strings, booleans, lists, nested dicts).
