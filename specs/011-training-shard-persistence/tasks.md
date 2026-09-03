# Tasks: Training Client — Local Training Shard Persistence Infrastructure

**Branch**: `011-training-shard-persistence` | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/011-training-shard-persistence/spec.md) | **Plan**: [plan.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/011-training-shard-persistence/plan.md)

---

## Phase 1: Setup & Scaffolding

**Purpose**: Establish persistence directory layout, module scaffolding, and package re-exports.

- [X] T001 Create directory structure for client persistence infrastructure in `src/Client/infrastructure/persistence/` and sample verification in `samples/persistence_test/`
- [X] T002 [P] Configure module re-exports in `src/Client/domain/__init__.py` and `src/Client/infrastructure/persistence/__init__.py`

---

## Phase 2: Foundational (Core Domain Models, Exceptions & Contract)

**Purpose**: Establish pure domain entity models, status enum, exception hierarchy, and abstract repository interface.

**CRITICAL**: Foundational tasks must complete before user story implementation can begin.

- [X] T003 [P] Implement `TrainingShardStatus` enum with stable lowercase values (`"ready"`, `"training"`, `"completed"`, `"failed"`) in `src/Client/domain/training_shard.py`
- [X] T004 [P] Implement `TrainingShard` domain model with validation rules (`id` UUID, `sample_count > 0`, non-empty strings, zero database imports) in `src/Client/domain/training_shard.py`
- [X] T005 [P] Implement persistence exception hierarchy (`PersistenceError`, `DatabaseConfigurationError`, `DatabaseInitializationError`, `DuplicateShardError`, `SerializationError`) in `src/Client/infrastructure/persistence/exceptions.py`
- [X] T006 [P] Implement abstract `ITrainingShardRepository` interface contract in `src/Client/infrastructure/persistence/training_shard_repository.py`

**Checkpoint**: Core domain models, exceptions, and repository interface are defined and decoupled from database technologies.

---

## Phase 3: User Story 1 - Persistent Local Tracking and Atomic Shard Storage (Priority: P1) [MVP]

**Goal**: Persist and track local dataset shards in a durable local SQLite database via `TrainingShardRepository.save()` and `bulk_save()` with atomic transaction guarantees and strict sample count validation.

**Independent Test**: Instantiate a `TrainingShard` domain model with valid identifiers, positive sample count, and status `READY`. Invoke `TrainingShardRepository.save(shard)` and verify the record is committed to SQLite. Attempt saving with `sample_count <= 0` and verify rejection. Execute `bulk_save` and verify all-or-nothing transaction rollback on failure.

- [X] T007 [US1] Implement SQLite table creation DDL (`training_shards`) with column types and `CHECK (sample_count > 0)` constraint in `src/Client/infrastructure/persistence/database.py`
- [X] T008 [US1] Implement scoped connection manager (`get_connection()`) with context management, commit/rollback, and `PRAGMA busy_timeout = 5000` in `src/Client/infrastructure/persistence/database.py`
- [X] T009 [US1] Implement `save(training_shard)` atomic insert operation with parameterized SQL in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T010 [US1] Implement `bulk_save(training_shards)` atomic batch insert operation with single-transaction rollback in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T011 [US1] Implement domain entity validation before database execution in `TrainingShardRepository.save()` and `bulk_save()` in `src/Client/infrastructure/persistence/training_shard_repository.py`

**Checkpoint**: User Story 1 (MVP) is functional and capable of atomically persisting individual shards and batches into SQLite.

---

## Phase 4: User Story 2 - Structured Metrics and Training Metadata Serialization (Priority: P2)

**Goal**: Transparently serialize arbitrary `metrics` and `training_metadata` Python dictionaries to JSON in SQLite and deserialize them back into native Python dictionaries on retrieval via `get_by_id()` and `get_by_shard_key()`.

**Independent Test**: Save a `TrainingShard` with populated `metrics` and `training_metadata`. Reload through `get_by_id()` and `get_by_shard_key()`. Assert 100% round-trip fidelity matching the original structured dictionary. Verify unpopulated / `None` fields remain `None`.

- [X] T012 [US2] Implement JSON serialization helpers (`_serialize_json`, `_deserialize_json`) handling `None`, dicts, and invalid JSON error handling in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T013 [US2] Implement `get_by_id(id)` primary key query reconstructing `TrainingShard` domain entity with deserialized metrics and metadata in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T014 [US2] Implement `get_by_shard_key(model_id, model_version, dataset_id, shard_id)` composite query returning reconstructed `TrainingShard` in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T015 [US2] Handle nullable fields (`metrics`, `training_metadata`, `update_artifact_path`, `training_task_id`) cleanly between SQLite `NULL` and Python `None` in `src/Client/infrastructure/persistence/training_shard_repository.py`

**Checkpoint**: User Story 2 is functional with full round-trip JSON serialization and point retrieval by primary key and logical composite key.

---

## Phase 5: User Story 3 - Composite Key Uniqueness and Duplicate Shard Protection (Priority: P3)

**Goal**: Enforce composite uniqueness over `(model_id, model_version, dataset_id, shard_id)` using a SQLite unique index, rejecting duplicate saves with `DuplicateShardError` while permitting new checkpoint versions.

**Independent Test**: Persist a shard with `(M1, 1, D1, S1)`. Attempt to persist another shard with different UUID `id` but identical composite key attributes. Verify that `DuplicateShardError` is raised and the transaction is rolled back.

- [X] T016 [US3] Implement composite unique index DDL (`uq_training_shards_logical_shard`) on `(model_id, model_version, dataset_id, shard_id)` in `src/Client/infrastructure/persistence/database.py`
- [X] T017 [US3] Implement `sqlite3.IntegrityError` detection and translation to `DuplicateShardError` during `save()` in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T018 [US3] Implement atomic rollback and `DuplicateShardError` translation during `bulk_save()` batch execution in `src/Client/infrastructure/persistence/training_shard_repository.py`
- [X] T019 [US3] Ensure distinct `model_version` values for the same `(model_id, dataset_id, shard_id)` are permitted and successfully persisted in `src/Client/infrastructure/persistence/training_shard_repository.py`

**Checkpoint**: User Story 3 is functional with composite uniqueness enforcement and explicit `DuplicateShardError` domain exceptions.

---

## Phase 6: User Story 4 - Environment-Driven Configuration and Idempotent Initialization (Priority: P4)

**Goal**: Resolve the database path via `TRAINING_CLIENT_DB_PATH` with silent fallback to `./training.db`, automatically create parent directories, and execute idempotent schema creation without mutating existing records.

**Independent Test**: Initialize with `TRAINING_CLIENT_DB_PATH` set to a nested non-existent directory and verify directory creation and schema creation. Unset variable and verify fallback to `./training.db`. Re-initialize on an existing populated database and verify zero data loss.

- [X] T020 [US4] Implement `TRAINING_CLIENT_DB_PATH` environment variable resolution with silent fallback to `./training.db` in `src/Client/infrastructure/persistence/database.py`
- [X] T021 [US4] Implement automatic parent directory provisioning (`os.makedirs(exist_ok=True)`) in `src/Client/infrastructure/persistence/database.py`
- [X] T022 [US4] Implement idempotent schema initialization (`DatabaseManager.initialize()`) executing `IF NOT EXISTS` DDL without mutating existing records in `src/Client/infrastructure/persistence/database.py`
- [X] T023 [US4] Implement error handling for unwriteable paths or filesystem permission failures raising `DatabaseConfigurationError` or `DatabaseInitializationError` in `src/Client/infrastructure/persistence/database.py`

**Checkpoint**: User Story 4 is functional with robust environment configuration and safe, idempotent initialization across process lifecycles.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Application integration, active zero-mock verification tooling, and compilation validation.

- [X] T024 [P] Integrate `DatabaseManager` and `TrainingShardRepository` instantiation into Client startup in `src/Client/main.py`
- [X] T025 [P] Implement zero-mock standalone active verification runner in `samples/persistence_test/verify_persistence.py`
- [X] T026 Validate compilability and syntax across all modified modules using `python -m py_compile` per Constitution Principle VII
- [X] T027 Execute end-to-end verification script `python samples/persistence_test/verify_persistence.py` and confirm all 9 validation scenarios pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion — delivers core MVP persistence.
- **User Story 2 (Phase 4)**: Depends on Phase 3 completion — adds serialization and retrieval queries.
- **User Story 3 (Phase 5)**: Depends on Phase 3 completion — adds composite unique constraint and duplicate handling.
- **User Story 4 (Phase 6)**: Depends on Phase 3 completion — finalizes externalized environment resolution.
- **Polish (Phase 7)**: Depends on completion of all User Stories (Phases 3–6).

### User Story Dependencies

```text
Phase 1: Setup
    │
    ▼
Phase 2: Foundational (Models, Status Enum, Exceptions, Contract)
    │
    ▼
Phase 3: User Story 1 (Atomic Shard Persistence - MVP)
    │
    ├───────────────────┬───────────────────┐
    ▼                   ▼                   ▼
Phase 4: US2         Phase 5: US3        Phase 6: US4
(JSON Metrics/       (Composite Unique   (Env Configuration &
 Retrieval API)      Protection)         Idempotent Init)
    │                   │                   │
    └───────────────────┼───────────────────┘
                        ▼
Phase 7: Polish (Client Startup Integration & Verification Suite)
```

---

## Parallel Execution Opportunities

- **Phase 1**: `T002` can execute in parallel once `T001` directories exist.
- **Phase 2**: `T003`, `T004`, `T005`, and `T006` can all execute concurrently across separate files.
- **Post-US1 Stories**: Once User Story 1 (Phase 3) is established, Phases 4, 5, and 6 can proceed concurrently or sequentially.
- **Phase 7**: `T024` (Client startup) and `T025` (Verification script) can be authored in parallel.

---

## Implementation Strategy

### MVP First (Phases 1, 2, and 3)
1. Complete Setup (`T001`, `T002`) and Foundational (`T003`–`T006`).
2. Implement User Story 1 (`T007`–`T011`).
3. **STOP and VALIDATE**: Verify that a valid `TrainingShard` can be saved to SQLite and that invalid sample counts are rejected.

### Incremental Delivery
1. Foundation + US1 -> Deliver core persistent storage (MVP).
2. Add US2 -> Deliver JSON serialization and point retrieval (`get_by_id`, `get_by_shard_key`).
3. Add US3 -> Deliver composite uniqueness and duplicate rejection.
4. Add US4 -> Deliver environment configuration and directory creation.
5. Polish -> Integrate into `main.py` and run standalone verification suite `verify_persistence.py`.
