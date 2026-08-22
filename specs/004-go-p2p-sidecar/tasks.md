# Implementation Tasks: Go P2P Node Sidecar

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per implementation plan in `src/p2p-node/`
- [x] T002 Initialize Go module `go mod init p2p-node` in `src/p2p-node/`
- [x] T003 [P] Configure `buf.yaml` or basic `protoc` generation scripts for gRPC in `src/p2p-node/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Generate Go gRPC and Protobuf code from `contracts/p2p.proto` into `src/p2p-node/internal/api/p2pv1/`
- [x] T005 [P] Implement persistent ed25519 identity generation and loading in `src/p2p-node/internal/node/identity.go`
- [x] T006 Implement base libp2p host creation with TCP/QUIC listeners in `src/p2p-node/internal/node/node.go`
- [x] T007 Implement internal thread-safe event bus for broadcasting `NodeEvent` messages in `src/p2p-node/internal/api/events.go`
- [x] T008 Implement gRPC server skeleton bounding strictly to `127.0.0.1` in `src/p2p-node/internal/api/server.go`
- [x] T009 Implement `GetNodeInfo` and `WatchEvents` RPCs in `src/p2p-node/internal/api/server.go` to support testing
- [x] T010 Create CLI entrypoint tying identity, host, and gRPC server together in `src/p2p-node/cmd/p2pd/main.go`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Reliable Direct Connection via DCUtR (Priority: P1) 🚀 MVP

**Goal**: Establish a robust peer-to-peer connection with another node, using a relay as a fallback and automatically upgrading to a direct connection via NAT hole punching.

**Independent Test**: Start two sidecars. Call `Connect` on Sidecar A with Sidecar B's relay address. Verify `RELAY_CONNECTED` followed by `CONNECTION_UPGRADED_TO_DIRECT` via `WatchEvents`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US1] Create E2E connection tests verifying direct, relay-only, and DCUtR upgrades in `src/p2p-node/tests/connection_test.go`

### Implementation for User Story 1

- [x] T012 [P] [US1] Implement Relay Client and background reservation refresh loop in `src/p2p-node/internal/nat/relay.go`
- [x] T013 [US1] Enable AutoNAT and DCUtR hole punching in `src/p2p-node/internal/nat/holepunch.go` and wire to host
- [x] T014 [US1] Implement `Connect` and `Disconnect` RPCs in `src/p2p-node/internal/api/server.go`
- [x] T015 [US1] Wire connection lifecycle events (`PEER_CONNECTED`, `CONNECTION_UPGRADED_TO_DIRECT`) to the event bus

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Resilient File Transfer Protocol (Priority: P1)

**Goal**: Send and receive large files reliably using chunked streaming, SHA-256 validation, and `.part` temporary files without excessive memory usage.

**Independent Test**: Initiate a large file transfer. Verify memory stays <100MB. Interrupt the transfer and verify `.part` file is discarded and original file is uncorrupted.

### Tests for User Story 2

- [x] T016 [P] [US2] Create E2E transfer tests (1MB, 1GB files, interruption recovery) in `src/p2p-node/tests/transfer_test.go`

### Implementation for User Story 2

- [x] T017 [P] [US2] Define protocol constants (`/p2p-file-transfer/1.0.0`) and chunk framing in `src/p2p-node/internal/transfer/protocol.go`
- [x] T018 [US2] Implement receiver logic: temporary `.part` file, SHA-256 verification, and atomic rename in `src/p2p-node/internal/transfer/receiver.go`
- [x] T019 [US2] Implement sender logic: read from disk, bounded chunk streaming in `src/p2p-node/internal/transfer/sender.go`
- [x] T020 [US2] Implement `SendFile` and `AcceptFile` RPCs in `src/p2p-node/internal/api/server.go` tying to transfer logic
- [x] T021 [US2] Implement `CancelTransfer` RPC mapping to context cancellation
- [x] T022 [US2] Emit transfer lifecycle events (`TRANSFER_STARTED`, `TRANSFER_PROGRESS`, `TRANSFER_COMPLETED`) to the event bus from sender/receiver

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Localhost gRPC API Contract (Priority: P2)

**Goal**: Ensure the gRPC API exposes all necessary informational endpoints for the Python application to track detailed connection and transfer statuses.

**Independent Test**: Query `GetConnectionStatus` and `GetTransferStatus` via `grpcurl` and verify accurate state reflection.

### Implementation for User Story 3

- [x] T023 [US3] Implement `GetConnectionStatus` and `GetTransferStatus` RPCs
- [x] T024 [P] [US3] Create tests verifying memory limits remain <100MB during large transfers
- [x] T025 [P] [US3] Create tests verifying gracefully closed or corrupted transfers don't corrupt target file

### Polish

- [x] T026 Resolve any linter (`golangci-lint`) and `go vet` warnings across the sidecar
- [x] T027 Add basic `Makefile` or build scripts for producing the `p2pd` executable
- [x] T028 Run the full test suite and confirm 100% pass rate for all Acceptance Criteria scenarios

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T026 Execute all test scenarios in `quickstart.md`
- [x] T027 Code cleanup and static analysis (`go vet`, `staticcheck`)
- [x] T028 Performance profiling for large file transfers (pprof)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - Phase 3 (US1) and Phase 4 (US2) can proceed in parallel once Phase 2 is complete.
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2).
- **User Story 2 (P1)**: Can start after Foundational (Phase 2). Depends on US1 for actual end-to-end network transmission, but protocol components can be built in parallel.
- **User Story 3 (P2)**: Can start after US1 and US2 are structurally complete to query their statuses.

### Parallel Opportunities

- Identity persistence (T005) and protoc generation (T004) can run in parallel in Phase 2.
- E2E Connection Tests (T011) and Relay Client (T012) can run in parallel in Phase 3.
- Protocol framing (T017) can be done in parallel with E2E Transfer Tests (T016) in Phase 4.
- `GetConnectionStatus` (T023) and `GetTransferStatus` (T024) can be implemented simultaneously.

---

## Parallel Example: Phase 4 (User Story 2)

```bash
# Developer A starts writing the framing and protocol boundaries:
Task: "Define libp2p stream /p2p-file-transfer/1.0.0 protocol constants... in protocol.go"

# Developer B starts writing the test harness for transfers:
Task: "Create E2E transfer tests verifying large files... in transfer_test.go"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (Connection management)
4. Complete Phase 4: User Story 2 (File transfer logic)
5. **STOP and VALIDATE**: Test both stories thoroughly using `quickstart.md`. This constitutes the MVP.

### Incremental Delivery

1. Foundation ready (API server running, identity generated).
2. Deliver US1: Nodes can connect directly or via relay.
3. Deliver US2: Nodes can send files over the established connections.
4. Deliver US3: Python application has full visibility into statuses and edge-case failures.
