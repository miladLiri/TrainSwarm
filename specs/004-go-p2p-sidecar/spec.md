# Feature Specification: Go P2P Node Sidecar for Python Applications

**Feature Branch**: `004-go-p2p-sidecar`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

## Clarifications

### Session 2026-08-22
- Q: How should the receiving Python application be notified of an incoming file transfer so it can call AcceptFile? → A: The sidecar emits a `TRANSFER_REQUESTED` event via `WatchEvents` containing the metadata (transfer ID, filename, size).
- Q: If `overwrite=false` is passed to `AcceptFile` and the destination file already exists, how should the sidecar handle it? → A: Reject the transfer at the libp2p protocol level (sending a `REJECT` message) and return an error to the caller.
- Q: Does the localhost gRPC API require authentication between the Python application and the Go sidecar? → A: No authentication required; binding to `127.0.0.1` is sufficient.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Direct Connection via DCUtR (Priority: P1)

As a Python Application (Trainer or Client), I want the Go sidecar to establish a robust peer-to-peer connection with another node, using a relay as a fallback and automatically upgrading to a direct connection via NAT hole punching, so that I can communicate efficiently without worrying about complex networking logic.

**Why this priority**: Core networking capability required to decouple the Python application from libp2p implementation details while ensuring reliable NAT traversal.

**Independent Test**: Can be tested by starting two sidecar instances behind simulated NATs and a public relay. Python application instructs Sidecar A to connect to Sidecar B via the relay. Sidecar A reports `RELAY_CONNECTED`, then shortly after reports `CONNECTION_UPGRADED_TO_DIRECT`.

**Acceptance Scenarios**:

1. **Given** two sidecars behind NATs and a configured public relay, **When** one sidecar calls `Connect` with the other's peer ID, **Then** the sidecar connects via the relay and coordinates a DCUtR hole punch to establish a direct connection, preferring it for all subsequent traffic.
2. **Given** a direct connection attempt fails, **When** the sidecar falls back to the relay, **Then** the connection is maintained via the relay and reported as `RELAY_CONNECTED` to the Python application.

---

### User Story 2 - Resilient File Transfer Protocol (Priority: P1)

As a Python Application, I want to send and receive files through a simple API while the sidecar handles the streaming, hashing, and state management, so that large file transfers complete reliably without consuming excessive memory or leaving corrupted files.

**Why this priority**: Essential for sharing model weights and datasets between Trainer and Client.

**Independent Test**: Initiate a large file transfer (> 1GB) between two sidecars. Verify memory usage remains low. Interrupt the transfer midway and verify that no corrupted destination file exists.

**Acceptance Scenarios**:

1. **Given** an established connection, **When** the Python app calls `SendFile`, **Then** the sidecar streams the file in bounded chunks, sending progress events, without loading the whole file into memory.
2. **Given** an incoming file transfer, **When** the sidecar receives the transfer metadata, **Then** it emits a `TRANSFER_REQUESTED` event via `WatchEvents`, allowing the Python app to validate the metadata and call `AcceptFile`. The sidecar then writes incoming chunks to a `.part` file, incrementally hashing them, and atomically renames the file upon successful completion.
3. **Given** an interrupted or failed transfer, **When** the connection drops, **Then** the `.part` file is discarded and the destination file is never left in an incomplete state.

---

### User Story 3 - Localhost gRPC API Contract (Priority: P2)

As a Python Application Developer, I want to interact with the P2P sidecar exclusively through a strongly-typed, localhost-only gRPC API, so that I can easily integrate networking capabilities without managing raw sockets or streams.

**Why this priority**: Defines the strict boundary between application logic (Python) and networking infrastructure (Go).

**Independent Test**: Can be tested by starting the sidecar and querying its endpoints (`GetNodeInfo`, `Connect`, `SendFile`) via a generic gRPC client on `127.0.0.1`.

**Acceptance Scenarios**:

1. **Given** the sidecar is running, **When** the Python app requests `GetNodeInfo`, **Then** it returns the persistent `peer_id`, listening addresses, and reachability status.
2. **Given** a long-running sidecar, **When** the Python app subscribes to `WatchEvents`, **Then** it receives real-time node-level events (e.g., `PEER_CONNECTED`, `TRANSFER_PROGRESS`).

---

### Edge Cases

- What happens when a node restarts? The sidecar must load its persistent libp2p identity from disk so its PeerID remains unchanged.
- What happens if the public relay goes offline? The sidecar must detect the failure, attempt to reconnect, and report reachability changes via the event stream.
- What happens if both direct connection and hole punching are impossible (e.g., symmetric NATs)? A `HOLE_PUNCH_FAILED` event is emitted (triggered immediately if both nodes discover symmetric NATs, or after a 10-second timeout), and the sidecar MUST seamlessly fall back to maintaining the Circuit Relay connection and routing file transfers over it, albeit slower.
- What happens if the Python application crashes during a transfer? The sidecar should detect the dropped gRPC stream and gracefully cancel active transfers.
- What happens if an incoming file transfer matches an existing destination file? If `overwrite=false`, the sidecar rejects the transfer protocol handshake to save bandwidth.
- What happens if the local disk runs out of space or encounters permission issues during a transfer? The sidecar MUST immediately abort the transfer, discard the `.part` file, and emit a `TRANSFER_FAILED` event.
- What happens if a direct connection drops midway through a transfer? The `.part` file is immediately deleted and `TRANSFER_FAILED` is emitted. Partial transfer resumption is NOT supported in this MVP; dropped connections require a full restart.
- What happens if the sender disconnects immediately after sending the transfer metadata but before sending any data chunks? The `.part` file MUST be immediately deleted and `TRANSFER_FAILED` is emitted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The sidecar MUST act as a standalone executable exposing a versioned, localhost-only gRPC API (e.g., `p2p.v1`) on Windows/Linux.
- **FR-002**: The sidecar MUST generate a persistent libp2p identity on first run and reuse it on subsequent restarts to maintain a stable `peer_id`.
- **FR-003**: The sidecar MUST support standard go-libp2p features: identity, security, stream multiplexing, TCP/QUIC, Identify, AutoNAT/reachability detection, and Circuit Relay v2 client.
- **FR-004**: The sidecar MUST attempt direct connections first. If unreachable directly, it MUST establish a Circuit Relay v2 connection and use the DCUtR protocol to attempt NAT hole punching.
- **FR-005**: If DCUtR hole punching succeeds, new streams MUST use the direct connection. The relay connection MUST be kept open for a 30-second grace period after a successful direct upgrade to ensure pending packets are flushed. If hole punching fails, the system MUST fall back to the relay connection and report it as `RELAY_CONNECTED`.
- **FR-006**: The file transfer API MUST use a dedicated libp2p stream protocol (`/p2p-file-transfer/1.0.0`), supporting streaming in explicitly bounded chunks (maximum 256KB per chunk) to avoid excessive memory usage.
- **FR-007**: File receivers MUST write to a temporary `<destination>.part` file, incrementally verify the SHA-256 hash, and atomically rename it upon full verification.
- **FR-008**: Failed or cancelled transfers MUST NOT leave a corrupted or partial file in the final destination path. If a destination file already exists and `overwrite=false` is provided to `AcceptFile`, the sidecar MUST send a `REJECT` message over the libp2p protocol to save bandwidth and return an `ALREADY_EXISTS` error code to the gRPC caller.
- **FR-009**: The gRPC API MUST provide server-streaming endpoints for transfers (`SendFile`, `AcceptFile`) and node events (`WatchEvents`). `WatchEvents` MUST emit a `TRANSFER_REQUESTED` event containing transfer metadata before a file can be accepted.
- **FR-010**: The sidecar MUST automatically refresh and maintain its relay reservation while running (e.g., refreshing every 2 minutes with exponential backoff on failure, up to a maximum of 5 retries).
- **FR-011**: End-to-end tests MUST be implemented to verify direct transfers, relay-only transfers, DCUtR upgrades, identity persistence, and transfer cancellations.

### Key Entities

- **Peer Identity**: The libp2p cryptographic keypair and derived `peer_id`.
- **Connection State**: The status of a peer connection (e.g., `DISCONNECTED`, `CONNECTING`, `RELAY_CONNECTED`, `PUNCHING`, `DIRECT_CONNECTED`).
- **File Transfer Metadata**: Header information exchanged before data transfer (transfer ID, file name, size, SHA-256 hash).
- **Node Event**: A discrete notification sent to the Python app (e.g., `PEER_CONNECTED`, `TRANSFER_REQUESTED`, `TRANSFER_STARTED`, `TRANSFER_PROGRESS`, `HOLE_PUNCH_FAILED`). Transfer status states in the protocol layer (e.g., `START`, `ACCEPT`, `DATA`) MUST map exactly to corresponding gRPC `WatchEvents` types (e.g., `TRANSFER_STARTED`, `TRANSFER_PROGRESS`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two sidecars behind typical restrictive NATs (non-symmetric) successfully establish a direct P2P connection via DCUtR in >90% of attempts within 10 seconds.
- **SC-002**: File transfers >1GB complete successfully without the sidecar process exceeding 100MB of RAM usage. To guarantee this ceiling, the sidecar MUST enforce a hard limit of a maximum of 5 concurrent file transfers (additional transfers must be queued or rejected).
- **SC-003**: A transfer intentionally corrupted or disconnected midway results in 0 byte corruption of the target file.
- **SC-004**: End-to-end automated tests pass 100% of the scenarios (relay, direct, DCUtR, restart, cancellation) in simulated networks.

## Assumptions

- The Python application is responsible for application-level signaling (e.g., discovering the remote `peer_id` via the Coordinator/Bootstrap nodes).
- The Bootstrap server runs a compatible libp2p Circuit Relay v2 server.
- The target environment supports spawning child processes (Go executable) from the Python host application.
- The machine running the sidecar is considered trusted; the `127.0.0.1` gRPC API requires no explicit authentication token to accept commands.
