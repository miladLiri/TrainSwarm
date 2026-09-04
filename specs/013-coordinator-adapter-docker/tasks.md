# Tasks: Training Client — Coordinator Adapter and Docker Infrastructure

**Branch**: `013-coordinator-adapter-docker` | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/013-coordinator-adapter-docker/spec.md) | **Plan**: [plan.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/013-coordinator-adapter-docker/plan.md)

---

## Phase 1: Setup & Scaffolding

**Purpose**: Establish adapters directory layout, package files, and configuration updates.

- [X] T001 Create adapters directory structure in src/Client/infrastructure/adapters/ and test directory in samples/coordinator_adapter_test/
- [X] T002 [P] Update configuration loader in src/Client/config.py to read COORDINATOR_ADDRESS and coordinator_url

---

## Phase 2: Foundational (DTO Model, Exceptions & Contract)

**Purpose**: Core DTO entity model, exception hierarchy, and adapter interface contract needed across all stories.

**CRITICAL**: Foundational tasks must complete before user story implementation can begin.

- [X] T003 [P] Implement Coordinator adapter exception hierarchy (CoordinatorAdapterError, CoordinatorConfigurationError, CoordinatorApiError, CoordinatorNetworkError) in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T004 [P] Implement CreateTrainingTaskDto dataclass with strict field validation (non-empty strings, min 1 shard ID) and to_dict() camelCase serialization in src/Client/infrastructure/adapters/create_training_task.py
- [X] T005 [P] Configure package re-exports in src/Client/infrastructure/adapters/__init__.py and src/Client/infrastructure/__init__.py

**Checkpoint**: Core DTO, validation logic, exception hierarchy, and package exports are defined and ready for adapter implementation.

---

## Phase 3: User Story 1 - Submit Training Task Creation Request via Coordinator Adapter (Priority: P1) [MVP]

**Goal**: Enable Training Client to submit task creation requests via `CoordinatorAdapter.create_training_task(dto)`, sending `POST /api/training-tasks` with camelCase JSON and returning `list[str]` of created task GUIDs.

**Independent Test**: Initialize adapter with an injected test session or simulated endpoint, invoke `create_training_task(dto)` with a valid DTO, verify `POST /api/training-tasks` is dispatched with camelCase JSON payload, and verify returned task IDs match the response list.

- [X] T006 [US1] Implement CoordinatorAdapter.__init__ with address resolution, normalization (strip trailing slashes), timeout, and session lifecycle in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T007 [US1] Implement CoordinatorAdapter.create_training_task(request: CreateTrainingTaskDto) -> list[str] URL construction (POST /api/training-tasks) and request dispatch in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T008 [US1] Implement successful response parsing (validating HTTP 200/201, JSON structure, and extracting trainingTaskIds list[str]) in src/Client/infrastructure/adapters/coordinator_adapter.py

**Checkpoint**: User Story 1 (MVP) is functional and capable of constructing and sending valid training task creation requests to the Coordinator API.

---

## Phase 4: User Story 2 - Resilient Error Handling, Logging, and Escalation (Priority: P2)

**Goal**: Detect HTTP errors (4xx, 5xx), malformed bodies, and network failures; log contextual diagnostics via `logging.getLogger`; escalate typed exceptions (`CoordinatorApiError`, `CoordinatorNetworkError`, `CoordinatorAdapterError`) without swallowing errors.

**Independent Test**: Simulate 400 Bad Request, 500 Internal Server Error, invalid JSON / missing `trainingTaskIds`, connection timeout, and connection refused; verify error logging and exception escalation.

- [X] T009 [US2] Implement non-success HTTP status (4xx/5xx) detection, diagnostic logging (address, method, endpoint, status, error body, model/dataset metadata, shard count), and CoordinatorApiError escalation in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T010 [US2] Implement malformed success response handling (invalid JSON or missing trainingTaskIds), diagnostic error logging, and CoordinatorAdapterError escalation in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T011 [US2] Implement network exception handling (requests.exceptions.ConnectionError, Timeout, RequestException), error logging, and CoordinatorNetworkError escalation in src/Client/infrastructure/adapters/coordinator_adapter.py

**Checkpoint**: User Story 2 is functional with full diagnostic logging and zero swallowed exceptions across API and transport errors.

---

## Phase 5: User Story 3 - Environment-Driven Configuration and Fast Failure (Priority: P3)

**Goal**: Ensure `COORDINATOR_ADDRESS` is loaded strictly from the environment, failing fast on missing or empty string with `CoordinatorConfigurationError`, with zero default fallback.

**Independent Test**: Instantiate `CoordinatorAdapter` without `COORDINATOR_ADDRESS` in environment and verify immediate `CoordinatorConfigurationError`. Instantiate with `http://coordinator:8080/` and verify trailing slash is stripped.

- [X] T012 [US3] Implement strict environment validation for COORDINATOR_ADDRESS raising CoordinatorConfigurationError when unset, empty, or whitespace in src/Client/infrastructure/adapters/coordinator_adapter.py
- [X] T013 [US3] Ensure no hardcoded fallback hostnames or silent defaults exist in src/Client/infrastructure/adapters/coordinator_adapter.py and src/Client/config.py

**Checkpoint**: User Story 3 is functional with strict configuration enforcement and zero hardcoded hostnames.

---

## Phase 6: User Story 4 - Infrastructure Directory Restructuring and Architectural Isolation (Priority: P4)

**Goal**: Remove obsolete legacy infrastructure files (`bootstrap_client.py` and `coordinator_client.py`), leaving only `adapters/` and `persistence/`. Wire `CoordinatorAdapter` and `TrainingShardRepository` in `main.py` and clear `console_ui.py`.

**Independent Test**: Verify `src/Client/infrastructure/` contains only `adapters/` and `persistence/`. Verify zero persistence imports in adapter and zero adapter imports in repository. Launch `main.py` to confirm clean startup without broken imports.

- [X] T014 [US4] Remove obsolete files src/Client/infrastructure/bootstrap_client.py and src/Client/infrastructure/coordinator_client.py
- [X] T015 [US4] Clear legacy session and bootstrap menu workflows from src/Client/presentation/console_ui.py to keep it minimal and dormant
- [X] T016 [US4] Update application entry point in src/Client/main.py to initialize CoordinatorAdapter and TrainingShardRepository cleanly without legacy dependencies
- [X] T017 [US4] Verify architectural isolation between src/Client/infrastructure/adapters/ and src/Client/infrastructure/persistence/

**Checkpoint**: User Story 4 is functional with clean infrastructure layout, dead code eliminated, and working application entry point.

---

## Phase 7: User Story 5 - Containerized Execution with Persistent SQLite Volume (Priority: P5)

**Goal**: Update `Dockerfile` to build the Training Client on `python:3.11-slim`, accept runtime environment variables, and configure a mountable `/data` volume for the SQLite database.

**Independent Test**: Build the Docker image. Run a container mounting host storage to `/data` with runtime envs. Stop and restart container with same volume to verify SQLite persistence.

- [X] T018 [US5] Update src/Client/Dockerfile with python:3.11-slim, volume declaration for /data, runtime environment variables, and entrypoint CMD ["python", "main.py"]
- [X] T019 [US5] Ensure Dockerfile does not hardcode COORDINATOR_ADDRESS or TRAINING_CLIENT_DB_PATH
- [X] T020 [US5] Verify /data volume persistence and SQLite database creation at /data/training.db

**Checkpoint**: User Story 5 is functional with containerized build, externalized runtime configuration, and durable volume persistence.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Active verification suite, syntax checking, and quickstart scenario validation.

- [X] T021 [P] Implement active zero-mock verification suite in samples/coordinator_adapter_test/verify_coordinator_adapter.py covering config fast-fail, serialization, response parsing, error escalation, and isolation
- [X] T022 Validate compilability and syntax across all modified modules using python -m py_compile per Constitution Principle VII
- [X] T023 Execute active verification suite python samples/coordinator_adapter_test/verify_coordinator_adapter.py and confirm all 10 checks pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately; establishes directory structure and config loader.
- **Foundational (Phase 2)**: Depends on Phase 1; establishes DTO, exception hierarchy, and contracts. Blocks all User Stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2; implements adapter URL building, request dispatch, and response parsing (MVP).
- **User Story 2 (Phase 4)**: Depends on Phase 3; implements non-success HTTP status handling, response validation, network errors, and logging.
- **User Story 3 (Phase 5)**: Depends on Phase 3; refines strict environment validation and eliminates default hostnames.
- **User Story 4 (Phase 6)**: Depends on Phase 3-5; deletes obsolete infrastructure files and updates `main.py` / `console_ui.py`.
- **User Story 5 (Phase 7)**: Depends on Phase 6; updates Dockerfile and validates volume persistence.
- **Polish (Phase 8)**: Depends on all User Stories; creates runnable verification suite and runs compilability checks.

### Parallel Opportunities

- In Phase 1: `T002` can run alongside `T001`.
- In Phase 2: `T003`, `T004`, `T005` can run in parallel (independent modules).
- In Phase 8: `T021` can be authored in parallel with final reviews.

---

## Parallel Example: Foundational Phase

```bash
# Author exceptions, DTO, and package exports in parallel:
Task: "Implement Coordinator adapter exception hierarchy in src/Client/infrastructure/adapters/coordinator_adapter.py"
Task: "Implement CreateTrainingTaskDto dataclass in src/Client/infrastructure/adapters/create_training_task.py"
Task: "Configure package re-exports in src/Client/infrastructure/adapters/__init__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (`T001` - `T002`)
2. Complete Phase 2: Foundational (`T003` - `T005`)
3. Complete Phase 3: User Story 1 (`T006` - `T008`)
4. **STOP and VALIDATE**: Verify task creation serialization and dispatch independently against live or test session.

### Incremental Delivery
1. Phase 1 + Phase 2: Foundational contracts ready.
2. Phase 3: Core adapter request/response operational (MVP!).
3. Phase 4: Full error resilience, diagnostic logging, and exception propagation added.
4. Phase 5: Fast-fail environment configuration hardened.
5. Phase 6: Obsolete files removed and application entry point cleanly rewired.
6. Phase 7: Containerized deployment and durable SQLite volume ready.
7. Phase 8: Active verification suite runs all 10 checks to 100% pass.
