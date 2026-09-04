# Tasks: Training Client Configuration, Dependency Injection, and Smoke Test

**Feature Branch**: `014-client-config-smoke-test`  
**Date**: 2026-09-04  
**Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/014-client-config-smoke-test/spec.md)  
**Plan**: [plan.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/014-client-config-smoke-test/plan.md)  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize directory structure and package definitions for configuration, DI, and smoke test.

- [X] T001 Create configuration package directory in src/Client/config/__init__.py and DI package in src/Client/dependency_injection/__init__.py
- [X] T002 [P] Create smoke test application package directory in src/Client/application/smoke_test/__init__.py
- [X] T003 [P] Create verification sample directory in samples/client_smoke_test/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core exception hierarchies and DTO models required across configuration, DI, and command handling.

**CRITICAL**: Foundational DTOs and exceptions must be defined before story implementation begins.

- [X] T004 [P] Define ClientConfigurationError, MissingConfigurationError, and InvalidConfigurationValueError in src/Client/config/exceptions.py
- [X] T005 [P] Define ClientConfig immutable dataclass in src/Client/config/models.py
- [X] T006 [P] Define SmokeTestError, SmokeTestValidationError, and SmokeTestExecutionError in src/Client/application/smoke_test/exceptions.py
- [X] T007 [P] Define SmokeTestResult DTO with to_dict and from_dict methods in src/Client/application/smoke_test/smoke_test_result.py
- [X] T008 [P] Define SmokeTestCommand DTO with sample_count validation in src/Client/application/smoke_test/smoke_test_command.py

**Checkpoint**: Core contracts and exceptions ready — user story implementations can now proceed.

---

## Phase 3: User Story 1 - Centralized Configuration Management and Fast-Fail Validation (Priority: P1) ⭐ MVP

**Goal**: Centralize all Client environment-variable reads into a single `ConfigManager` with fast-fail validation and typed defaults.

**Independent Test**: Instantiate `ConfigManager` without `COORDINATOR_ADDRESS` to verify `MissingConfigurationError`; supply non-numeric timeout to verify `InvalidConfigurationValueError`; supply valid environment variables to confirm typed attributes and defaults (`SHARD_TRAINING_TIME_LIMIT=300.0`, `SHARD_SAFETY_FACTOR=1.0`).

### Implementation for User Story 1

- [X] T009 [US1] Implement ConfigManager in src/Client/config/config_manager.py with environment loading, fast-fail validation, and type conversions
- [X] T010 [US1] Expose public configuration API and re-exports in src/Client/config/__init__.py

**Checkpoint**: User Story 1 complete. Configuration can be loaded and validated with fast-fail behavior.

---

## Phase 4: User Story 2 - Composition Root and Clean Dependency Wiring (Priority: P2)

**Goal**: Implement a lightweight Composition Root (`DIContainer`) that wires persistence, adapters, and command handlers without third-party frameworks or service locators.

**Independent Test**: Construct `DIContainer` passing a `ClientConfig` instance; verify that `DatabaseManager`, `TrainingShardRepository`, `CoordinatorAdapter`, `TrainingOrchestrator`, and `SmokeTestCommandHandler` are constructed and accessible via typed properties without calling `container.get` or `container.resolve`.

### Implementation for User Story 2

- [X] T011 [US2] Implement DIContainer composition root in src/Client/dependency_injection/container.py to explicitly construct and wire adapters, persistence, and command handlers
- [X] T012 [US2] Expose DIContainer in src/Client/dependency_injection/__init__.py

**Checkpoint**: User Stories 1 and 2 complete. All dependencies can be assembled cleanly at the application boundary.

---

## Phase 5: User Story 3 - Pre-Distribution Training Validation via Smoke Test (Priority: P3)

**Goal**: Execute training validation runs on small sample counts using the real `TrainingOrchestrator`, report training failures safely, and clean up generated output delta files.

**Independent Test**: Dispatch a `SmokeTestCommand` to `SmokeTestCommandHandler.handle()`; verify execution through the real `TrainingOrchestrator`, confirm failing runs return `SmokeTestResult(success=False)` with diagnostic details, and confirm output `.safetensors` delta files are deleted.

### Implementation for User Story 3

- [X] T013 [US3] Implement SmokeTestCommandHandler in src/Client/application/smoke_test/smoke_test_command_handler.py to validate commands and invoke TrainingOrchestrator.run()
- [X] T014 [US3] Add failure handling and error logging in src/Client/application/smoke_test/smoke_test_command_handler.py to return SmokeTestResult with success=False on training exceptions
- [X] T015 [US3] Add automated cleanup of generated output delta .safetensors artifacts in src/Client/application/smoke_test/smoke_test_command_handler.py
- [X] T016 [US3] Expose SmokeTestCommand, SmokeTestCommandHandler, and SmokeTestResult in src/Client/application/smoke_test/__init__.py

**Checkpoint**: User Stories 1, 2, and 3 complete. Training tasks can be smoke-tested before dataset distribution.

---

## Phase 6: User Story 4 - Training Throughput Measurement and Shard Sizing Estimation (Priority: P4)

**Goal**: Measure elapsed training duration with monotonic precision, calculate throughput, and derive estimated and recommended shard capacities.

**Independent Test**: Execute a smoke test with known sample count; verify elapsed monotonic seconds via `time.perf_counter()`, verify `samples_per_second` matches `sample_count / duration`, and verify `estimated_samples_per_shard` and `recommended_samples_per_shard` calculations.

### Implementation for User Story 4

- [X] T017 [US4] Integrate high-precision monotonic timing via time.perf_counter around orchestrator execution in src/Client/application/smoke_test/smoke_test_command_handler.py
- [X] T018 [US4] Implement throughput, estimated shard capacity, and recommended shard capacity calculations with safety factor in src/Client/application/smoke_test/smoke_test_command_handler.py

**Checkpoint**: User Stories 1 through 4 complete. Smoke tests return verified throughput and sizing recommendations.

---

## Phase 7: User Story 5 - Client Codebase Migration and Environment Variable Audit (Priority: P5)

**Goal**: Refactor existing infrastructure constructors (`CoordinatorAdapter`, `DatabaseManager`), update `main.py`, remove legacy `config.py`, and ensure zero unauthorized `os.getenv` calls remain outside `src/Client/config/`.

**Independent Test**: Scan `src/Client` for `os.getenv` or `os.environ` outside `config/` (0 matches); verify `CoordinatorAdapter` and `DatabaseManager` require explicit constructor parameters; run `src/Client/main.py` to confirm clean boot.

### Implementation for User Story 5

- [X] T019 [US5] Refactor CoordinatorAdapter constructor in src/Client/infrastructure/adapters/coordinator_adapter.py to require coordinator_address without calling os.getenv
- [X] T020 [US5] Refactor DatabaseManager constructor in src/Client/infrastructure/persistence/database.py to accept db_path without calling os.getenv
- [X] T021 [US5] Refactor application entry point in src/Client/main.py to initialize ConfigManager and DIContainer
- [X] T022 [US5] Remove or redirect legacy single-file configuration in src/Client/config.py to use src/Client/config/
- [X] T023 [US5] Perform codebase audit across src/Client/ to verify zero direct os.getenv or os.environ calls remain outside src/Client/config/

**Checkpoint**: All user stories complete. Architectural migration and environment centralization fully achieved.

---

## Phase 8: Polish & Verification Quality Gate

**Purpose**: Execute compilability checks and active zero-mock end-to-end verification to satisfy Constitution Principle VII.

- [X] T024 [P] Implement active zero-mock verification harness in samples/client_smoke_test/verify_client_config_smoke_test.py covering all quickstart scenarios
- [X] T025 Verify Python syntax and compilability across all modified and created files via python -m py_compile
- [X] T026 Execute samples/client_smoke_test/verify_client_config_smoke_test.py to validate configuration, DI, smoke test execution, failure handling, and delta cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — blocks all User Stories.
- **Phase 3 (User Story 1 - P1)**: Depends on Phase 2 — MVP foundation.
- **Phase 4 (User Story 2 - P2)**: Depends on Phase 3 (needs ConfigManager).
- **Phase 5 (User Story 3 - P3)**: Depends on Phase 2 (needs Command, Result DTOs) and Phase 4 (wiring).
- **Phase 6 (User Story 4 - P4)**: Extends Phase 5 handler with timing and throughput math.
- **Phase 7 (User Story 5 - P5)**: Depends on Phase 3 and 4 (migrates existing classes to consume DI and config).
- **Phase 8 (Polish & Quality Gate)**: Depends on all implementation phases being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Independent after Phase 2 foundation.
- **User Story 2 (P2)**: Depends on US1 (`ClientConfig`).
- **User Story 3 (P3)**: Depends on US2 (`DIContainer` and `TrainingOrchestrator`).
- **User Story 4 (P4)**: Enhances US3 handler calculations.
- **User Story 5 (P5)**: Depends on US1 and US2 (wires migrated constructors into container).

---

## Parallel Opportunities

- **Phase 1**: Tasks T002 and T003 can be executed in parallel with T001.
- **Phase 2**: Tasks T004, T005, T006, T007, T008 can all be implemented in parallel.
- **Phase 5 & 6**: Timing measurement (T017) and throughput math (T018) can be developed alongside cleanup logic (T015).
- **Phase 7**: Tasks T019 and T020 can be executed in parallel (different files: adapter vs database).
- **Phase 8**: T024 can be authored in parallel with Phase 7 refactoring.

---

## Parallel Example: User Story 5 Migration

```bash
# Parallel constructor refactoring for independent modules:
Task: "Refactor CoordinatorAdapter constructor in src/Client/infrastructure/adapters/coordinator_adapter.py"
Task: "Refactor DatabaseManager constructor in src/Client/infrastructure/persistence/database.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational DTOs & exceptions).
2. Complete Phase 3 (US1: ConfigManager).
3. Complete Phase 4 (US2: DIContainer).
4. **VALIDATE MVP**: Verify client boots with centralized configuration and container wiring.

### Incremental Delivery

1. Add Phase 5 (US3: Smoke Test execution & failure handling).
2. Add Phase 6 (US4: Monotonic timing, throughput, shard sizing).
3. Add Phase 7 (US5: Codebase migration & audit).
4. Run Phase 8 (Polish: `py_compile` and `verify_client_config_smoke_test.py`).

