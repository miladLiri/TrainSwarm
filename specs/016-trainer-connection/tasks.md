# Tasks: Trainer Connection — Coordinator Trainer Entity & Service, Trainer Architectural Parity, and Startup Lifecycle

**Feature Branch**: `016-trainer-connection`  
**Date**: 2026-09-06  
**Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/016-trainer-connection/spec.md)  
**Plan**: [plan.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/016-trainer-connection/plan.md)  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize directory structure, packages, and configuration templates for Trainer refactoring and sample verification.

- [X] T001 [P] Create directory structure for Trainer config, DI, commands, and adapters in src/Trainer/config/, src/Trainer/dependency_injection/, src/Trainer/application/trainer_commands/, src/Trainer/application/coordinator_commands/, src/Trainer/infrastructure/coordinator_connection/, src/Trainer/infrastructure/adapters/, and src/Trainer/presentation/gui/
- [X] T002 [P] Create sample test directory structure in samples/trainer_init_test/
- [X] T003 [P] Create configuration templates src/Trainer/.env.example and src/Trainer/.env defining COORDINATOR_ADDRESS, COORDINATOR_GRPC_ADDRESS, TRAINER_NODE_ID, and REQUEST_TIMEOUT_SECONDS

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Coordinator domain entity, enum, and EF Core persistence schema required before API and service implementation.

**CRITICAL**: Foundational database entities and context mappings must be defined before user story implementation begins.

- [X] T004 [P] Define TrainerStatus enum (UNCLEAR=0, IDLE=1, BUSY=2) in src/Coordinator/TrainSwarm.Coordinator.Domain/Entities/TrainerStatus.cs
- [X] T005 [P] Define Trainer domain entity (Id: Guid, TrainerNodeId: string, Status: TrainerStatus) in src/Coordinator/TrainSwarm.Coordinator.Domain/Entities/Trainer.cs
- [X] T006 [P] Define TrainerConfiguration EF Core mapping for Trainers table in src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Configurations/TrainerConfiguration.cs
- [X] T007 Register DbSet<Trainer> Trainers in src/Coordinator/TrainSwarm.Coordinator.Application/Contracts/ICoordinatorDbContext.cs and src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/CoordinatorDbContext.cs
- [X] T008 Generate and configure EF Core migration for Trainers table in src/Coordinator/TrainSwarm.Coordinator.Infrastructure/Persistence/Migrations/

**Checkpoint**: Foundation ready — user story implementations can now proceed.

---

## Phase 3: User Story 1 - Coordinator Trainer Registration & Idempotent Connection (Priority: P1) ⭐ MVP

**Goal**: Implement `TrainerService.ConnectTrainerAsync` with atomic replacement semantics and expose the REST endpoint `POST /api/trainers/connect`.

**Independent Test**: Send HTTP POST to `/api/trainers/connect` with `{ "trainerNodeId": "trainer-node-01" }`; verify HTTP 200/201 response with `IDLE` status and GUID; send a second request with the same `trainerNodeId` and verify the previous database record is removed and replaced with exactly one row having a new GUID.

### Implementation for User Story 1

- [X] T009 [P] [US1] Implement ConnectTrainerDto and ConnectTrainerResult in src/Coordinator/TrainSwarm.Coordinator.Application/Services/ConnectTrainerDto.cs and src/Coordinator/TrainSwarm.Coordinator.Application/Services/ConnectTrainerResult.cs
- [X] T010 [US1] Implement TrainerService with ConnectTrainerAsync providing atomic removal of previous records and insertion of new IDLE trainer in src/Coordinator/TrainSwarm.Coordinator.Application/Services/TrainerService.cs
- [X] T011 [P] [US1] Implement ConnectTrainerResponseDto and TrainerController with POST /api/trainers/connect in src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainerController.cs
- [X] T012 [US1] Register TrainerService in src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs and verify Coordinator builds cleanly

**Checkpoint**: User Story 1 complete. Coordinator can idempotently register trainers and persist them in SQLite.

---

## Phase 4: User Story 2 - Trainer Architectural Standardization & State Management (Priority: P2)

**Goal**: Implement centralized configuration management, dependency injection composition root, and application state in Trainer matching Client's architecture.

**Independent Test**: Initialize `ConfigManager` from environment variables, instantiate `DIContainer`, and verify that `TrainerState` stores and exposes `client_node_id` as the hardcoded string constant `"trainer-node-01"`.

### Implementation for User Story 2

- [X] T013 [P] [US2] Implement typed configuration exceptions in src/Trainer/config/exceptions.py and TrainerConfig dataclass in src/Trainer/config/models.py
- [X] T014 [US2] Implement ConfigManager reading .env and environment variables in src/Trainer/config/config_manager.py and export in src/Trainer/config/__init__.py
- [X] T015 [P] [US2] Implement TrainerState holding strictly hardcoded client_node_id constant ("trainer-node-01") and runtime status in src/Trainer/application/state.py
- [X] T016 [US2] Implement composition root DIContainer wiring configuration and state in src/Trainer/dependency_injection/container.py and export in src/Trainer/dependency_injection/__init__.py

**Checkpoint**: User Story 2 complete. Trainer has centralized configuration, dependency injection, and state management matching Client.

---

## Phase 5: User Story 3 - Trainer Connect Command & Infrastructure Adapter (Priority: P3)

**Goal**: Implement `CoordinatorAdapter` to encapsulate HTTP requests to Coordinator, and `ConnectTrainerCommandHandler` to read state and invoke the adapter.

**Independent Test**: Invoke `ConnectTrainerCommandHandler.handle()`; verify it retrieves `client_node_id` from `TrainerState`, calls `CoordinatorAdapter.connect_trainer()`, and returns a `ConnectTrainerResult` without raising network exceptions.

### Implementation for User Story 3

- [X] T017 [US3] Implement CoordinatorAdapterResult and CoordinatorAdapter encapsulating HTTP calls to POST /api/trainers/connect in src/Trainer/infrastructure/adapters/coordinator_adapter.py and export in src/Trainer/infrastructure/adapters/__init__.py
- [X] T018 [P] [US3] Implement ConnectTrainerCommand and ConnectTrainerResult in src/Trainer/application/trainer_commands/connect_trainer/connect_trainer_command.py
- [X] T019 [US3] Implement ConnectTrainerCommandHandler reading client_node_id from TrainerState and calling CoordinatorAdapter.connect_trainer() in src/Trainer/application/trainer_commands/connect_trainer/connect_trainer_handler.py and export in src/Trainer/application/trainer_commands/connect_trainer/__init__.py
- [X] T020 [US3] Wire CoordinatorAdapter and ConnectTrainerCommandHandler into DIContainer in src/Trainer/dependency_injection/container.py

**Checkpoint**: User Story 3 complete. Trainer can programmatically dispatch the connect command through its adapter.

---

## Phase 6: User Story 4 - Startup Lifecycle Guard, Presentation Shells, & Domain Cleanup (Priority: P4)

**Goal**: Relocate gRPC streaming and command handlers into modular packages, clear legacy `domain/` and interactive `console_ui.py`, implement `startup.py` connection guard, provide PyQt6 window shell, and route entrypoint `main.py`.

**Independent Test**: Launch `python main.py` with an unreachable Coordinator; verify process terminates immediately with exit code 1; launch with reachable Coordinator; verify headless CLI starts cleanly; launch `python main.py gui`; verify PyQt6 desktop window shell appears.

### Implementation for User Story 4

- [X] T021 [P] [US4] Relocate Coordinator gRPC connection files into src/Trainer/infrastructure/coordinator_connection/ (coordinator_client.py, trainer_command_listener.py, proto stubs) and export in src/Trainer/infrastructure/coordinator_connection/__init__.py
- [X] T022 [P] [US4] Reorganize remote commands into src/Trainer/application/coordinator_commands/ with dispatcher.py and co-located start_training/command.py and start_training/handler.py
- [X] T023 [US4] Remove all legacy command and model files in src/Trainer/domain/ to complete the co-location architecture
- [X] T024 [US4] Implement idempotent startup guard in src/Trainer/presentation/startup.py executing ConnectTrainerCommandHandler and halting with exit code 1 on failure
- [X] T025 [P] [US4] Implement minimalist PyQt6 window shell in src/Trainer/presentation/gui/main_window.py and export run_gui in src/Trainer/presentation/gui/__init__.py
- [X] T026 [P] [US4] Clear legacy interactive REPL logic in src/Trainer/presentation/console_ui.py to support headless CLI execution
- [X] T027 [US4] Refactor src/Trainer/main.py to invoke presentation/startup.py, start gRPC listener, and route to headless CLI by default or PyQt6 GUI when gui argument is provided

**Checkpoint**: User Story 4 complete. Startup guard enforces connection before UI or CLI launches; command co-location and domain cleanup are verified.

---

## Phase 7: User Story 5 - Containerized Packaging & Automated Initialization Verification (Priority: P5)

**Goal**: Update Trainer Dockerfile with volume mounts and implement the automated Docker-only verification script in `samples/trainer_init_test/setup.py`.

**Independent Test**: Run `python samples/trainer_init_test/setup.py`; verify Coordinator and Trainer containers build and start over `trainswarm-test-net`, and SQLite query confirms a row exists in `Trainers` table with status `1` (`IDLE`).

### Implementation for User Story 5

- [X] T028 [P] [US5] Update src/Trainer/Dockerfile to declare volume /artifacts, set WORKDIR /artifacts, and configure environment variables
- [X] T029 [US5] Implement containerized verification runner in samples/trainer_init_test/setup.py that builds Coordinator and Trainer images, launches them on trainswarm-test-net, queries Coordinator SQLite DB, and asserts Trainers table record with status = 1 (IDLE)
- [X] T030 [P] [US5] Create documentation in samples/trainer_init_test/README.md explaining test steps, prerequisites, and cleanup commands (setup.py --down)

**Checkpoint**: User Story 5 complete. Feature packaging and containerized end-to-end verification are automated.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Build integrity validation, syntax verification, documentation updates, and end-to-end execution.

- [X] T031 [P] Verify compilability of Coordinator with dotnet build src/Coordinator/TrainSwarm.Coordinator.slnx
- [X] T032 [P] Verify syntax validity of all Trainer modules with python -m py_compile across src/Trainer/
- [X] T033 [P] Update documentation in src/Coordinator/README.md and src/Trainer/README.md with new endpoints, configuration, and architecture details
- [X] T034 Execute end-to-end validation via samples/trainer_init_test/setup.py and confirm zero-mock containerized pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3–7)**:
  - **User Story 1 (P1)**: Can start after Foundational (Phase 2).
  - **User Story 2 (P2)**: Can start after Setup (Phase 1); independent of US1.
  - **User Story 3 (P3)**: Depends on US1 (Coordinator endpoint) and US2 (Trainer state & DI).
  - **User Story 4 (P4)**: Depends on US3 (ConnectTrainerCommandHandler available for startup guard).
  - **User Story 5 (P5)**: Depends on US1, US2, US3, and US4 (requires working Coordinator and Trainer containers).
- **Polish (Phase 8)**: Depends on all user stories (Phase 3–7) being complete.

### Within Each User Story

- Domain models / DTOs before services
- Services before controllers / adapters
- Adapters before command handlers
- Handlers before UI / presentation startup
- Story complete before integration in subsequent phases

### Parallel Opportunities

- **Phase 1**: T001, T002, T003 can run in parallel.
- **Phase 2**: T004, T005, T006 can run in parallel.
- **Phase 3 (US1)**: T009 and T011 can run in parallel.
- **Phase 4 (US2)**: T013 and T015 can run in parallel.
- **Phase 5 (US3)**: T018 can run in parallel with T017.
- **Phase 6 (US4)**: T021, T022, T025, T026 can run in parallel.
- **Phase 7 (US5)**: T028 and T030 can run in parallel.
- **Phase 8**: T031, T032, T033 can run in parallel.

---

## Parallel Example: User Story 1 & User Story 2

```bash
# Parallel tasks within US1 (Coordinator):
Task: "T009 [P] [US1] Implement ConnectTrainerDto and ConnectTrainerResult in src/Coordinator/TrainSwarm.Coordinator.Application/Services/ConnectTrainerDto.cs"
Task: "T011 [P] [US1] Implement ConnectTrainerResponseDto and TrainerController with POST /api/trainers/connect in src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/TrainerController.cs"

# Parallel tasks between US1 and US2 (Coordinator vs Trainer):
Task: "T010 [US1] Implement TrainerService in Coordinator"
Task: "T014 [US2] Implement ConfigManager in Trainer"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Coordinator Trainer persistence & API)
4. **STOP and VALIDATE**: Verify Coordinator builds and accepts `POST /api/trainers/connect` via curl.

### Incremental Delivery

1. Complete Phase 1 & 2 → Foundations ready.
2. Complete Phase 3 (US1) → Coordinator endpoint ready.
3. Complete Phase 4 (US2) → Trainer state and DI ready.
4. Complete Phase 5 (US3) → Trainer command and HTTP adapter ready.
5. Complete Phase 6 (US4) → Startup guard and UI routing ready.
6. Complete Phase 7 (US5) → Containerized test suite verifies end-to-end flow.
7. Complete Phase 8 → Full build verification and documentation polish.
