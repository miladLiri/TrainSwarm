# Tasks: Bootstrap Relay and P2P Communication

**Feature**: `002-bootstrap-relay-p2p`
**Spec**: [`spec.md`](./spec.md) | **Plan**: [`plan.md`](./plan.md)
**Status**: Ready for Implementation

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize directory structures, package dependencies, environment templates, and configuration loaders for Bootstrap and Trainer components.

- [X] T001 [P] Create package directory structures for `src/Bootstrap/` and `src/Trainer/` (including `domain/`, `application/`, `infrastructure/`, `presentation/`) with `__init__.py` files
- [X] T002 [P] Create dependency files `src/Bootstrap/requirements.txt` (`fastapi`, `uvicorn`, `python-dotenv`) and `src/Trainer/requirements.txt` (`requests`, `python-dotenv`)
- [X] T003 [P] Create environment templates `src/Bootstrap/.env.example` (`PORT=6000`, `HOST=0.0.0.0`) and `src/Trainer/.env.example` (`TRAINER_NODE_ID=trainer-node-01`, `BOOTSTRAP_URL=http://localhost:6000`, `COORDINATOR_URL=http://localhost:5000`)
- [X] T004 [P] Implement environment configuration loaders in `src/Bootstrap/config.py` and `src/Trainer/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, state managers, and registry storage that MUST be complete before user stories can execute.

- [X] T005 [P] Define data transfer objects and schemas in `src/Bootstrap/models.py` (`RegisterPeerRequest`, `RegisterPeerResponse`, `PeerItem`, `SendRelayMessageRequest`, `RelayInboxResponse`)
- [X] T006 Implement thread-safe in-memory peer registry and relay message queue in `src/Bootstrap/registry.py`
- [X] T007 [P] Define domain models in `src/Trainer/domain/models.py` (`TrainerNode`, `PeerSession`, `TrainerStatus`)
- [X] T008 [P] Implement in-memory state manager in `src/Trainer/application/state.py` (`TrainerState`)

**Checkpoint**: Core data models and foundational state handlers ready.

---

## Phase 3: User Story 1 - Bootstrap Relay Node & Peer Registration (Priority: P1) [MVP]

**Goal**: Establish the Bootstrap FastAPI web service to register connecting nodes, assign unique `peerId`s, list active peers, and queue relayed messages.

**Independent Test**: Start Bootstrap service, invoke `POST /api/peers/register`, `GET /api/peers`, and `POST /api/relay/send`, and verify unique peer registration and message relaying.

### Implementation for User Story 1

- [X] T009 [US1] Implement FastAPI application entrypoint and routes in `src/Bootstrap/main.py` for health (`GET /api/health`), peer registration (`POST /api/peers/register`), peer listing (`GET /api/peers`), and relayed message exchange (`POST /api/relay/send`, `GET /api/relay/inbox/{peerId}`)
- [X] T010 [P] [US1] Implement Bootstrap relay HTTP client in `src/Trainer/infrastructure/bootstrap_client.py` for peer registration, peer discovery, and relay messaging with standard library fallback

**Checkpoint**: Bootstrap Relay web service is fully operational and capable of registering swarm peers.

---

## Phase 4: User Story 2 - Trainer Node Startup & Relay Connection (Priority: P2)

**Goal**: Enable Trainer console application to start, read environment configuration, auto-register with Bootstrap relay to acquire its `peerId`, query Coordinator status, and run an interactive REPL menu.

**Independent Test**: Start Bootstrap and launch Trainer console application; verify that the startup banner shows the assigned Peer ID and that menu options allow viewing status, querying peers, and checking Coordinator.

### Implementation for User Story 2

- [X] T011 [P] [US2] Implement Coordinator client in `src/Trainer/infrastructure/coordinator_client.py` for health and session queries
- [X] T012 [US2] Implement `TrainerService` use case in `src/Trainer/application/trainer_service.py` coordinating startup registration, state management, and peer queries
- [X] T013 [US2] Implement interactive console UI and REPL menu loop in `src/Trainer/presentation/console_ui.py` displaying banner, node ID, peer ID, relay status, and commands
- [X] T014 [US2] Implement main entrypoint in `src/Trainer/main.py` wiring configuration, services, startup auto-registration, and launching the console UI

**Checkpoint**: Trainer application connects to Bootstrap, manages peer state, and presents interactive console UI.

---

## Phase 5: User Story 3 - Client Bootstrap Relay Integration (Priority: P3)

**Goal**: Integrate the Client console application with the Bootstrap relay so that it loads `BOOTSTRAP_URL`, acquires a `peerId`, and participates in the swarm peer registry.

**Independent Test**: Start Bootstrap and launch Client console application; verify that Client registers with Bootstrap, displays its Peer ID alongside Coordinator session info, and appears in the Bootstrap peer list.

### Implementation for User Story 3

- [X] T015 [P] [US3] Update `src/Client/config.py` and `src/Client/.env.example` to support `BOOTSTRAP_URL` (default `http://localhost:6000`)
- [X] T016 [P] [US3] Create `src/Client/infrastructure/bootstrap_client.py` for peer registration against Bootstrap relay
- [X] T017 [US3] Update `src/Client/domain/models.py` and `src/Client/application/state.py` to track `peer_id` and `bootstrap_url`
- [X] T018 [US3] Update `src/Client/application/session_service.py` and `src/Client/presentation/console_ui.py` to connect to Bootstrap, acquire `peerId`, and display peer status in banner and menu
- [X] T019 [US3] Update `src/Client/main.py` to initialize Bootstrap client and trigger peer registration on startup

**Checkpoint**: Client application is connected to both Coordinator (for sessions) and Bootstrap (for peer relay).

---

## Phase 6: User Story 4 - Containerized Swarm Services (Priority: P4)

**Goal**: Provide lightweight Docker container definitions for Bootstrap and Trainer services supporting environment variable overrides.

**Independent Test**: Build and run Docker containers for Bootstrap and Trainer; verify containerized Trainer successfully connects to containerized Bootstrap.

### Implementation for User Story 4

- [X] T020 [P] [US4] Create `Dockerfile` and `.dockerignore` for Bootstrap service in `src/Bootstrap/Dockerfile` and `src/Bootstrap/.dockerignore`
- [X] T021 [P] [US4] Create `Dockerfile` and `.dockerignore` for Trainer application in `src/Trainer/Dockerfile` and `src/Trainer/.dockerignore`

**Checkpoint**: Bootstrap and Trainer services can be deployed and run in Docker containers.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end multi-node validation and documentation updates.

- [X] T022 Run end-to-end validation scenarios across Bootstrap, Trainer, Client, and Coordinator per `specs/002-bootstrap-relay-p2p/quickstart.md`
- [X] T023 [P] Update repository `README.md` with instructions for running Bootstrap and Trainer services alongside Coordinator and Client

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — blocks all User Stories.
- **User Story 1 (Phase 3)**: Depends on Foundational phase (MVP).
- **User Story 2 (Phase 4)**: Depends on User Story 1 (uses `bootstrap_client.py`).
- **User Story 3 (Phase 5)**: Depends on User Story 1 (integrates Client with Bootstrap).
- **User Story 4 (Phase 6)**: Depends on Bootstrap and Trainer application files being complete.
- **Polish (Phase 7)**: Runs after all user stories are complete.

### Parallel Opportunities
- In Phase 1: `T001`, `T002`, `T003`, `T004` can run in parallel.
- In Phase 2: `T005`, `T007`, `T008` can run in parallel.
- In Phase 3: `T010` can run in parallel with `T009`.
- In Phase 4: `T011` can run in parallel with `T012`.
- In Phase 5: `T015`, `T016` can run in parallel.
- In Phase 6: `T020`, `T021` can run in parallel.
- In Phase 7: `T023` can run in parallel with `T022`.

---

## Implementation Strategy

### MVP First (Phases 1, 2, & 3)
1. Complete Phase 1: Setup (`src/Bootstrap/` and `src/Trainer/` packages, configs, requirements).
2. Complete Phase 2: Foundational (schemas, in-memory registry, domain models).
3. Complete Phase 3: User Story 1 (Bootstrap FastAPI service routes & relay client).
4. **Validate MVP**: Launch Bootstrap, register simulated node, verify unique `peerId` returned.

### Incremental Delivery
- Add Phase 4 (US2): Trainer node startup, auto-registration, and interactive console UI.
- Add Phase 5 (US3): Client integration with Bootstrap relay.
- Add Phase 6 (US4): Docker container definitions for Bootstrap and Trainer.
- Add Phase 7: Multi-node quickstart validation and README documentation.