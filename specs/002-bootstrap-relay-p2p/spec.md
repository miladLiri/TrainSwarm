# Feature Specification: Bootstrap Relay and P2P Communication

**Feature Branch**: `002-bootstrap-relay-p2p`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "this feature is about communication between bootstrap, trainer and client trainer node is a console application for console applications (client and Trainer) Structure it around presentation-independent application logic: keep the domain models and business rules in a domain/ layer, use application/ for use cases/services and state management, infrastructure/ io and other external dependencies, and presentation/ for the console UI and manage .env configuration in config.py file trainer has a variable NodeId like trainer create basic trainer as described with a docker file bootstrap act as relay in DCUtR implement it and create a docker file trainer and clients as they started should connect to relay and get peer id both trainer and client should have bootstrap and coordinator address as environmental variable"

## Clarifications

### Session 2026-08-21
- Q: How should the Bootstrap DCUtR relay service handle message forwarding between registered peers when relaying is needed? → A: HTTP REST relay endpoints (`POST /api/relay/send` and `GET /api/relay/inbox/{peerId}`) for queued message exchange.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bootstrap Relay Node & Peer Registration (Priority: P1)

As a swarm node operator (Client or Trainer), I want the Bootstrap service to act as a DCUtR relay node so that when nodes connect, it assigns and tracks peer identities and facilitates peer-to-peer relay messaging.

**Why this priority**: The Bootstrap relay is the foundational network entry point and relay coordinator required for all subsequent P2P discovery and NAT traversal across the swarm.

**Independent Test**: Can be tested by starting the Bootstrap web service, sending registration/connection requests from simulated node endpoints, and verifying that unique peer IDs are generated, registered, and queryable.

**Acceptance Scenarios**:

1. **Given** the Bootstrap relay service is running, **When** a node (Client or Trainer) establishes connection and sends its node identifier and address metadata, **Then** the Bootstrap relay registers the peer, assigns a unique peer ID, and returns the peer metadata and active relay status.
2. **Given** registered peers in the Bootstrap relay, **When** a node queries for peer lookup or sends a relayed message via `POST /api/relay/send`, **Then** the Bootstrap service stores the message in the recipient's relay inbox and makes it retrievable via `GET /api/relay/inbox/{peerId}`.

---

### User Story 2 - Trainer Node Startup & Relay Connection (Priority: P2)

As a Trainer node operator, I want to launch the Trainer console application configured with Bootstrap and Coordinator addresses, so that it automatically connects to the Bootstrap relay on startup, obtains its Peer ID, and presents an interactive console interface.

**Why this priority**: Trainer nodes must establish connectivity to the control plane and peer relay network before they can accept training tasks or exchange data with clients.

**Independent Test**: Can be tested by starting the Trainer console application with `BOOTSTRAP_URL` and `COORDINATOR_URL` configured, verifying that it connects to the Bootstrap relay, receives its Peer ID, and displays active network status on the console menu.

**Acceptance Scenarios**:

1. **Given** the Bootstrap relay is running and the Trainer application is launched with `BOOTSTRAP_URL` and `TRAINER_NODE_ID` in `.env`, **When** the application starts, **Then** it automatically connects to the Bootstrap relay, acquires its assigned Peer ID, updates its local state, and displays the Peer ID on the console UI.
2. **Given** the Trainer console menu, **When** the operator inspects the active network status, **Then** the UI shows the Trainer Node ID, Peer ID, Bootstrap URL, and Coordinator URL.

---

### User Story 3 - Client Bootstrap Relay Integration (Priority: P3)

As a Client node operator, I want my Client console application to connect to the Bootstrap relay alongside the Coordinator, so that it acquires a Peer ID and prepares for relayed data-plane communication.

**Why this priority**: Enables the Client to be a full participant in the swarm peer network for subsequent direct model/shard transfer.

**Independent Test**: Can be tested by running the Client application with `BOOTSTRAP_URL` configured, executing the relay connect action, and verifying that the Client receives a Peer ID and stores it in its active state.

**Acceptance Scenarios**:

1. **Given** the Bootstrap relay is running and the Client application is launched with `BOOTSTRAP_URL` configured, **When** the Client connects to the relay, **Then** it acquires a unique Peer ID and updates its local `ClientState`.
2. **Given** the Client console menu, **When** the operator displays active node status, **Then** both Coordinator session information and Bootstrap Peer ID are displayed.

---

### User Story 4 - Containerized Swarm Services (Priority: P4)

As a DevOps engineer or node operator, I want Docker container definitions for Bootstrap and Trainer services with environment variable support, so that the entire topology can be launched cleanly in isolated environments.

**Why this priority**: Containerization ensures consistent execution across cloud, local, and heterogeneous swarm nodes.

**Independent Test**: Can be tested by building and running Docker containers for Bootstrap and Trainer, injecting environment variables, and verifying that the Trainer container connects to the Bootstrap container successfully.

**Acceptance Scenarios**:

1. **Given** built Docker images for Bootstrap and Trainer, **When** the containers are started with matching network and environment configurations, **Then** Bootstrap starts listening on its designated port and Trainer starts, connects to Bootstrap, and acquires its Peer ID.

---

### Edge Cases

- **Bootstrap Relay Unreachable on Startup**: If the Bootstrap service is down when Trainer or Client starts, the application logs a clear connection warning, remains operational in the interactive menu loop, and provides an option to retry connection.
- **Node Reconnection / Duplicate Registration**: If a node disconnects and reconnects with the same Node ID, Bootstrap updates the existing registration or renews the Peer ID session without raising duplicate key errors.
- **Malformed or Incompatible Network Payloads**: If a peer sends invalid JSON or missing node identifiers, the Bootstrap relay rejects the request with standard error status and descriptive reason.
- **Network Timeout during Peer Registration**: If a registration request times out, the client/trainer handles the timeout gracefully and keeps the previous state intact.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Bootstrap MUST be implemented as a Python web application operating in the control plane to serve as a peer registry and DCUtR relay.
- **FR-002**: Bootstrap MUST provide an endpoint (`POST /api/peers/register`) allowing nodes to register their `nodeId`, node role (`trainer` or `client`), and network endpoint information.
- **FR-003**: Bootstrap MUST generate and return a unique `peerId` (UUID/string) and relay session information upon successful registration.
- **FR-004**: Bootstrap MUST provide an endpoint (`GET /api/peers`) to query registered active peers.
- **FR-005**: Bootstrap MUST provide relay messaging endpoints (`POST /api/relay/send` to enqueue messages for a target peer and `GET /api/relay/inbox/{peerId}` to retrieve queued relayed messages).
- **FR-006**: Bootstrap MUST provide a `Dockerfile` supporting container build and configurable port exposure (default: `6000`).
- **FR-007**: Trainer MUST be implemented as a Python console application following presentation-independent clean architecture:
  - `domain/`: Domain models and business rules (`TrainerNode`, `PeerSession`).
  - `application/`: Use cases, service coordination, and local state management (`TrainerState`, `TrainerService`).
  - `infrastructure/`: Network I/O, Bootstrap relay client, and Coordinator client.
  - `presentation/`: Console user interface / interactive REPL menu.
  - `config.py`: Environment configuration loading from `.env`.
- **FR-008**: Trainer MUST maintain a configurable `NodeId` string identifier initialized from `.env` configuration (`TRAINER_NODE_ID`).
- **FR-009**: Trainer MUST accept both `BOOTSTRAP_URL` and `COORDINATOR_URL` via `.env` configuration.
- **FR-010**: Trainer MUST automatically attempt connection to the Bootstrap relay on startup to register its node identity and obtain its `peerId`.
- **FR-011**: Trainer MUST provide an interactive console UI with options to view node/peer status, reconnect to Bootstrap, check Coordinator status, and exit.
- **FR-012**: Trainer MUST provide a `Dockerfile` for containerized execution.
- **FR-013**: Client application MUST be updated to accept `BOOTSTRAP_URL` via `.env` and `config.py`.
- **FR-014**: Client MUST provide capability to connect to the Bootstrap relay, obtain its `peerId`, and display peer status in its presentation layer.

### Key Entities *(include if feature involves data)*

- **PeerRegistration**: Represents a node registered with the Bootstrap relay.
  - Attributes: `peerId` (unique string/UUID), `nodeId` (logical string identifier), `role` (`trainer` or `client`), `registeredAt` (timestamp), `lastSeenAt` (timestamp), `relayAddress` (string).
- **TrainerNode**: Represents local trainer node configuration and state.
  - Attributes: `nodeId` (string identifier), `peerId` (optional string, assigned by Bootstrap), `bootstrapUrl` (string), `coordinatorUrl` (string), `status` (e.g., `INITIALIZED`, `REGISTERED`, `DISCONNECTED`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Bootstrap relay responds to peer registration requests with an assigned `peerId` in under 1 second under standard local network conditions.
- **SC-002**: 100% of Trainer and Client startup flows attempt peer registration against the configured Bootstrap relay.
- **SC-003**: 100% of network failures or unreachable relay scenarios are caught with user-friendly error messages on the console without terminating the console REPL loop.
- **SC-004**: Bootstrap and Trainer container images can be built and launched via Docker in under 60 seconds from clean cache.
- **SC-005**: Architectural layering boundaries are strictly maintained across both Client and Trainer applications.

## Assumptions

- Bootstrap relay uses lightweight HTTP REST protocols for peer registration and control-plane relay metadata exchange.
- DCUtR relaying protocols for initial peer identity and discovery adhere to the non-negotiable constitution stack (Python web application for Bootstrap).
- No test files or unit test suites are to be generated, adhering strictly to Constitution Principle V.
- SQLite or in-memory storage is sufficient for the Bootstrap relay registry during the MVP phase.

