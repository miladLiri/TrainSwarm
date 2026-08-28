# Implementation Tasks: Bootstrap Relay Server

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure `src/bootstrap-relay/cmd/relay/` and `src/bootstrap-relay/internal/`
- [x] T002 Initialize Go module `go mod init bootstrap-relay` in `src/bootstrap-relay/`
- [x] T003 [P] Create initial `Dockerfile` for multi-stage Go builder in `src/bootstrap-relay/Dockerfile`
- [x] T004 [P] Create `setup.md` with complete instructions for running via Docker in `src/bootstrap-relay/setup.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement environment-based configuration loader mapped to `P2P_RELAY_*` limits in `src/bootstrap-relay/internal/config/config.go`
- [x] T006 [P] Add dependencies for `github.com/libp2p/go-libp2p` via `go get`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Public Relay Infrastructure (Priority: P1) 🚀 MVP

**Goal**: Deploy a standalone public relay server using standard go-libp2p protocols for private nodes to discover each other.

**Independent Test**: Deploy the relay via Docker. Verify it logs its PeerID and listening addresses on startup, and that an external test node can successfully connect to it and perform the Identify protocol.

### Implementation for User Story 1

- [x] T007 [P] [US1] Implement persistent ed25519 identity generation and loading in `src/bootstrap-relay/internal/relay/identity.go`
- [x] T008 [US1] Implement `go-libp2p` host creation bound to TCP and QUIC multiaddresses in `src/bootstrap-relay/internal/relay/host.go`
- [x] T009 [US1] Explicitly enable the libp2p Identify protocol on the host in `src/bootstrap-relay/internal/relay/host.go`
- [x] T010 [US1] Create application entrypoint wiring config, identity, and host together with startup logging in `src/bootstrap-relay/cmd/relay/main.go`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Circuit Relay & DCUtR Support (Priority: P1)

**Goal**: Reserve a slot on the public relay and use it to route traffic to another private node for DCUtR fallback.

**Independent Test**: Connect two private nodes to the relay. Request a reservation and establish a circuit. Verify circuit is proxied opaquely.

### Implementation for User Story 2

- [x] T011 [US2] Initialize `circuitv2.NewRelay` service tied to the libp2p host in `src/bootstrap-relay/internal/relay/service.go`
- [x] T012 [US2] Wire the relay service initialization into the main entrypoint in `src/bootstrap-relay/cmd/relay/main.go`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Resource Limits & Security (Priority: P2)

**Goal**: Configure explicit resource limits via environment variables so the relay does not become an unrestricted proxy.

**Independent Test**: Configure the relay with an artificially low `P2P_RELAY_MAX_CIRCUITS`. Attempt to establish concurrent circuits and verify rejection.

### Implementation for User Story 3

- [x] T013 [P] [US3] Map the parsed `config.Config` limits to the `circuitv2.Resources` struct passed to `circuitv2.NewRelay` in `src/bootstrap-relay/internal/relay/service.go`
- [x] T014 [US3] Attach operational logging (reservations, limits, circuit creation) to the relay service limits in `src/bootstrap-relay/internal/relay/service.go`
- [x] T015 [US3] Ensure graceful shutdown logic is implemented and logs shutdown events in `src/bootstrap-relay/cmd/relay/main.go`

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T016 Run `go vet ./...` and `go fmt ./...` across the codebase
- [x] T017 Verify operational logs output zero application payloads or file contents
- [x] T018 Validate end-to-end deployment instructions in `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - Phase 3 (US1) and Phase 4 (US2) can proceed in priority order (P1), followed by Phase 5 (US3).
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P1)**: Can start after US1 - Relies on the libp2p host existing.
- **User Story 3 (P2)**: Can start after US2 - Relies on the `circuitv2.NewRelay` service existing to apply limits.

### Parallel Opportunities

- Setup tasks (T003, T004) can run in parallel with project initialization.
- Identity management (T007) can be developed concurrently with config (T005) or tests if any were permitted.

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete Setup & Foundational phases.
2. Complete US1 to ensure the node boots and listens on TCP/QUIC.
3. Complete US2 to ensure the node acts as a functional generic relay for DCUtR.
4. **STOP and VALIDATE**: Verify the relay successfully allows two external peers to punch holes.

### Incremental Delivery

1. Implement MVP (US1 + US2).
2. Deliver US3: Restrict and log relay operations dynamically based on environment configuration.
