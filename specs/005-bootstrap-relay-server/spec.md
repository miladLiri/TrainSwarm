# Feature Specification: Bootstrap Relay Server

**Feature Branch**: `005-bootstrap-relay-server`

**Created**: 2026-08-22

**Status**: Draft

**Input**: User description: "Rewise and recreate Bootstap service completely to act as Go relay-server service..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Public Relay Infrastructure (Priority: P1)

As a network operator, I want to deploy a standalone public relay server using standard go-libp2p protocols, so that private nodes behind NATs can discover each other and establish connections without relying on custom or proprietary networking logic.

**Why this priority**: Without a publicly reachable relay, nodes behind NATs cannot establish initial connections, completely blocking all peer-to-peer communication.

**Independent Test**: Deploy the relay via Docker. Verify it logs its PeerID and listening addresses on startup, and that an external test node can successfully connect to it and perform the Identify protocol.

**Acceptance Scenarios**:

1. **Given** a fresh deployment of the relay via Docker, **When** the service starts, **Then** it generates and persists its cryptographic identity, and logs its public PeerID and listening multiaddresses.
2. **Given** a running relay, **When** it receives a connection on TCP or QUIC, **Then** it accepts the connection and responds appropriately to the standard libp2p Identify protocol.

---

### User Story 2 - Circuit Relay & DCUtR Support (Priority: P1)

As a private P2P node behind a NAT, I want to reserve a slot on the public relay and use it to route traffic to another private node, so that we can eventually coordinate a direct connection upgrade (DCUtR) or fall back to the relay if hole punching fails.

**Why this priority**: This is the core networking functionality that enables the TrainSwarm data plane to connect disparate nodes securely.

**Independent Test**: Connect two private nodes (Node A and Node B) to the relay. Node A requests a reservation. Node B dials Node A through the relay. Verify the circuit is established and the relay logs the circuit creation without dropping or buffering the underlying application streams.

**Acceptance Scenarios**:

1. **Given** a private node requests a reservation, **When** the relay receives the request, **Then** the relay accepts the reservation, tracks it, and allows the node to refresh it according to Circuit Relay v2 specifications.
2. **Given** Node B attempts to connect to Node A via the relay address, **When** the circuit is requested, **Then** the relay establishes the hop circuit and blindly proxies the end-to-end streams (including DCUtR negotiation) between the two nodes.
3. **Given** Node A and Node B successfully negotiate a direct connection via DCUtR, **When** they transition their application traffic to the direct connection, **Then** the relay gracefully closes the circuit after a brief inactivity grace period.

---

### User Story 3 - Resource Limits & Security (Priority: P2)

As a system administrator, I want to configure explicit resource limits for the relay via environment variables, so that the relay does not become an unrestricted proxy that consumes excessive bandwidth or memory.

**Why this priority**: A public relay without limits is a target for abuse and bandwidth exhaustion.

**Independent Test**: Configure the relay with an artificially low `P2P_RELAY_MAX_CIRCUITS` (e.g., 2). Attempt to establish 3 concurrent circuits and verify the 3rd is rejected and the rejection is logged.

**Acceptance Scenarios**:

1. **Given** the relay is configured with maximum limits, **When** a new reservation or circuit request exceeds these limits, **Then** the relay actively rejects the request and logs a resource-limit rejection event.
2. **Given** application data flowing through an established circuit, **When** the total transferred bytes exceeds `P2P_RELAY_MAX_RELAYED_BYTES` or the duration exceeds `P2P_RELAY_MAX_RELAY_DURATION`, **Then** the relay strictly terminates the circuit.
3. **Given** the relay is operating normally, **When** inspecting the logs, **Then** the operational logs show connection and reservation metrics but explicitly contain zero application payloads or file contents.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST be a standalone Go executable utilizing the standard go-libp2p networking stack without proprietary hole-punching modifications.
- **FR-002**: The service MUST listen for incoming connections on both TCP and QUIC transports where supported.
- **FR-003**: The service MUST generate a persistent libp2p identity at startup (stored at a configured path) and expose its PeerID and usable multiaddresses.
- **FR-004**: The service MUST enable the libp2p Identify protocol to allow peers to discover observed addresses.
- **FR-005**: The service MUST act as a Circuit Relay v2 server, accepting and managing reservations from private nodes.
- **FR-006**: The service MUST proxy end-to-end circuits between peers, explicitly supporting the passage of DCUtR negotiation messages without inspecting, transforming, buffering, or terminating application streams.
- **FR-007**: The service MUST enforce strict resource limits on reservations and circuits based on configuration.
- **FR-008**: The service MUST output operational logs for startup, PeerID assignment, reservations (accepted/rejected), circuit lifecycle (established/closed), resource limit rejections, and shutdowns. Logs MUST NOT expose application data.
- **FR-009**: The service MUST be fully configurable via environment variables and/or a configuration file, specifically supporting: `P2P_RELAY_LISTEN_TCP`, `P2P_RELAY_LISTEN_QUIC`, `P2P_RELAY_IDENTITY_PATH`, `P2P_RELAY_MAX_RESERVATIONS`, `P2P_RELAY_MAX_CIRCUITS`, `P2P_RELAY_MAX_RELAYED_BYTES`, `P2P_RELAY_MAX_RELAY_DURATION`, and `P2P_RELAY_LOG_LEVEL`.
- **FR-010**: The service MUST include a `Dockerfile` and a `setup.md` providing complete instructions for deploying the service to a functional state via Docker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The relay service successfully boots and accepts TCP/QUIC connections in a Docker environment in under 5 seconds.
- **SC-002**: Two private nodes can successfully negotiate a DCUtR direct connection through the relay in >90% of non-symmetric NAT scenarios.
- **SC-003**: The relay correctly enforces 100% of configured resource limits (e.g., actively denying the N+1 circuit when the limit is N).
- **SC-004**: The relay operates stably as a generic proxy without consuming more memory or CPU than expected for a baseline go-libp2p relay under moderate load.

## Assumptions

- **Target Deployment**: The service is intended to be deployed on a publicly reachable server with a static IP address or stable DNS name.
- **NAT Limitations**: The implementation acknowledges that hole punching is inherently conditional (e.g., symmetric NATs may fail), and the relay will act as the continuous fallback connection when direct connectivity cannot be established.
- **Network Environment**: The host running the Docker container has the configured TCP and UDP (for QUIC) ports publicly exposed.
