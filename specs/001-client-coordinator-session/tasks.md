# Tasks: Client-Coordinator Session Creation

**Feature**: `001-client-coordinator-session`
**Spec**: [`spec.md`](./spec.md) | **Plan**: [`plan.md`](./plan.md)
**Status**: Ready for Implementation

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Python client project structure and configuration initialization

- [X] T001 [P] Create Python client package directory structure (`domain/`, `application/`, `infrastructure/`, `presentation/`) under `src/Client/`
- [X] T002 [P] Create dependencies definition in `src/Client/requirements.txt`
- [X] T003 [P] Create environment template in `src/Client/.env.example`
- [X] T004 [P] Implement environment configuration loader in `src/Client/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Coordinator entity updates, DTOs, service layer, and Client domain foundation

- [X] T005 [P] Update `TrainingSession` domain entity in `src/Coordinator/TrainSwarm.Coordinator.Domain/Entities/TrainingSession.cs` to change `ClientNodeId` from `Guid` to `string`
- [X] T006 [P] Update `CreateSessionDto` record in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/CreateSessionDto.cs` to accept `string ClientNodeId` and optional `string? Name`
- [X] T007 Update `SessionService.cs` in `src/Coordinator/TrainSwarm.Coordinator.Domain/Services/SessionService.cs` to validate non-empty `ClientNodeId` and assign auto-generated default `Name` if omitted
- [X] T008 Update EF Core entity configuration in `src/Coordinator/TrainSwarm.Coordinator.Domain/Context/CoordinatorDbContext.cs` for string `ClientNodeId`
- [X] T009 Update `SessionsController.cs` in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/SessionsController.cs` to bind updated DTO and return 201 Created with `TrainingSession`
- [X] T010 [P] Define `Session` and `ClientNode` domain dataclasses in `src/Client/domain/models.py`
- [X] T011 [P] Implement `ClientState` in-memory state manager in `src/Client/application/state.py`

**Checkpoint**: Core Coordinator schema and Client domain foundations ready.

---

## Phase 3: User Story 1 - Client Initiates Session Creation (Priority: P1) [MVP]

**Goal**: Enable the client operator to trigger session creation via an interactive console menu, register the session with the Coordinator, and store the active session ID locally.

**Independent Test**: Start Coordinator and Client console app, trigger menu option 1 (Create Session), and verify session is created on Coordinator and session ID is displayed and stored in Client state.

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement HTTP REST client for Coordinator API communication in `src/Client/infrastructure/coordinator_client.py`
- [X] T013 [US1] Implement `SessionService` application use-case in `src/Client/application/session_service.py` to coordinate session creation and update `ClientState` (depends on T010, T011, T012)
- [X] T014 [US1] Implement interactive console UI and REPL menu loop in `src/Client/presentation/console_ui.py` (depends on T013)
- [X] T015 [US1] Implement main entrypoint in `src/Client/main.py` to wire configuration, services, and launch the console UI (depends on T004, T014)

**Checkpoint**: User Story 1 is fully functional and delivers an end-to-end working MVP slice.

---

## Phase 4: User Story 2 - Resilient Client Error Handling (Priority: P2)

**Goal**: Provide clear error messaging when Coordinator is unreachable or returns errors without crashing the Client REPL loop.

**Independent Test**: Stop Coordinator service, invoke Create Session command from Client menu, and verify informative error output with graceful return to main menu.

### Implementation for User Story 2

- [X] T016 [US2] Implement comprehensive network error, connection refused, and timeout handling in `src/Client/infrastructure/coordinator_client.py`
- [X] T017 [US2] Enhance `src/Client/presentation/console_ui.py` with descriptive user error feedback without crashing the REPL loop

**Checkpoint**: User Stories 1 and 2 work reliably with resilient error handling.

---

## Phase 5: User Story 3 - Containerized Client Execution (Priority: P3)

**Goal**: Package the Client application into a lightweight Docker container supporting environment variable configuration.

**Independent Test**: Build and run the Client Docker container with environment overrides and verify interactive execution and successful communication with Coordinator.

### Implementation for User Story 3

- [X] T018 [P] [US3] Create `Dockerfile` for Python Client in `src/Client/Dockerfile`
- [X] T019 [P] [US3] Create `.dockerignore` for Python Client in `src/Client/.dockerignore`

**Checkpoint**: Client application can be containerized and run across heterogeneous swarm environments.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and documentation updates

- [X] T020 Run end-to-end validation scenarios across Coordinator and Client per `specs/001-client-coordinator-session/quickstart.md`
- [X] T021 [P] Update repository `README.md` with instructions for running Coordinator and Client

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — blocks User Stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion.
- **User Story 2 (Phase 4)**: Enhances User Story 1 client components.
- **User Story 3 (Phase 5)**: Depends on Client application files being complete.
- **Polish (Phase 6)**: Runs after all user stories are complete.

### User Story Dependencies
- **User Story 1 (P1)**: Independent after Foundational phase (MVP).
- **User Story 2 (P2)**: Builds upon Client infrastructure and presentation layers.
- **User Story 3 (P3)**: Packages the complete Python Client application into Docker.

### Parallel Opportunities
- In Phase 1: `T001`, `T002`, `T003`, `T004` can be executed in parallel.
- In Phase 2: `T005`, `T006`, `T010`, `T011` can be executed in parallel.
- In Phase 5: `T018`, `T019` can be executed in parallel.
- In Phase 6: `T021` can run in parallel with `T020`.

---

## Implementation Strategy

### MVP First (Phases 1, 2, & 3)
1. Complete Phase 1: Setup (`src/Client/` structure & `config.py`).
2. Complete Phase 2: Foundational (Coordinator C# entity & DTO string `ClientNodeId` updates, Client domain models).
3. Complete Phase 3: User Story 1 (`HttpCoordinatorClient`, `SessionService`, `console_ui.py`, `main.py`).
4. **Validate MVP**: Run Coordinator and Client, verify session creation works end-to-end.

### Incremental Delivery
- Add Phase 4 (US2) for resilient error handling.
- Add Phase 5 (US3) for Docker containerization.
- Add Phase 6 for documentation and final quickstart verification.