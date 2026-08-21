# Feature Specification: Client-Coordinator Session Creation

**Feature Branch**: `001-client-coordinator-session`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "this feature is about communication between client and coordinator coordinator should have an Endpoint CreateSession that gets a string NodeId from client and insert a new row in session table with a SessionId and ClientNodeId client should have a variable string variable NodeId with an arbitrary value and a command that sends its NodeId to coordinator via Create Session Api for console applications (client and Trainer) Structure it around presentation-independent application logic: keep the domain models and business rules in a domain/ layer, use application/ for use cases/services and state management, infrastructure/ io and other external dependencies, and presentation/ for the console UI and manage .env configuration in config.py file create docker file for client"

## Clarifications

### Session 2026-08-21
- Q: How should the Client console application expose and trigger the session creation command to the operator? → A: Interactive console menu / REPL loop prompting the operator with numbered/named commands.
- Q: What request payload should the Coordinator's CreateSession endpoint accept from the Client? → A: Client sends clientNodeId with optional name; Coordinator auto-generates name if omitted.
- Q: How should the Client application manage local session state if the operator triggers session creation while an active session is already stored in memory? → A: Automatically replace the active session ID with the newly created session ID and display it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Client Initiates Session Creation (Priority: P1)

As a Client node operator, I want to execute a command that registers a new training session with the Coordinator using my node identifier, so that the Coordinator establishes a tracked session and acknowledges it with a unique session ID.

**Why this priority**: Establishing a session between the Client and Coordinator is the fundamental entry point for orchestrating distributed training jobs in the swarm.

**Independent Test**: Can be tested by starting the Client console application, executing the session creation command, and verifying that the Coordinator records the session with the Client's node identifier and returns the generated session identifier to the Client.

**Acceptance Scenarios**:

1. **Given** the Coordinator service is reachable and the Client is configured with a node identifier (e.g., `"node-client-01"`), **When** the operator invokes the create session command from the Client console interface, **Then** the Client sends its node identifier (and optional session name) to the Coordinator, the Coordinator registers a new session record with a unique session identifier and the Client node identifier, and the Client displays the assigned session identifier to the operator.
2. **Given** the Coordinator service successfully creates the session, **When** the response is received by the Client, **Then** the Client stores/replaces the active session identifier in its local application state for subsequent operations and outputs confirmation.

---

### User Story 2 - Resilient Client Error Handling (Priority: P2)

As a Client node operator, I want clear feedback if the Coordinator is unreachable or fails to create a session, so that I understand why session creation did not succeed.

**Why this priority**: Clear error reporting prevents silent failures and helps operators diagnose configuration or connectivity issues immediately.

**Independent Test**: Can be tested by attempting to initiate session creation while the Coordinator service is stopped or misconfigured, verifying that a user-friendly error message is displayed on the console and the Client remains responsive.

**Acceptance Scenarios**:

1. **Given** the Coordinator is unreachable or returns an error response, **When** the operator triggers the session creation command, **Then** the Client outputs a descriptive error message without crashing and preserves its previous state.

---

### User Story 3 - Containerized Client Execution (Priority: P3)

As a DevOps engineer or node operator, I want to run the Client application inside a container with environment configuration, so that deployment and local execution are reproducible and isolated.

**Why this priority**: Containerization ensures consistent execution across heterogeneous environments and enables seamless deployment in distributed swarm environments.

**Independent Test**: Can be tested by building the Client container image, supplying environment configuration (including node identifier and coordinator endpoint), running the container, and invoking the session creation command.

**Acceptance Scenarios**:

1. **Given** a built Client container image with configured environment variables, **When** the container is launched, **Then** the Client starts successfully, loads its configuration (including node identifier and Coordinator URL), and can communicate with the Coordinator.

---

### Edge Cases

- **Empty or Whitespace Node Identifier**: If a client attempts to create a session with an empty or whitespace-only node identifier, the Coordinator rejects the request with a validation error, and the Client displays the validation failure.
- **Special Characters in Node Identifier**: Node identifiers containing arbitrary string characters (such as alphanumeric, dashes, underscores) must be accepted and persisted without corruption or truncation.
- **Duplicate Concurrent Session Requests**: If a client sends multiple session creation requests, each request generates a distinct session record with a unique session identifier linked to the client's node identifier.
- **Coordinator Timeout / Network Partition**: If the network connection drops or times out during the request, the Client handles the timeout cleanly, informs the user, and allows retrying the command.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Coordinator MUST provide an endpoint to create a training session accepting a JSON body with a required string `clientNodeId` and an optional string `name`. If `name` is omitted or empty, Coordinator auto-generates a default session name.
- **FR-002**: Coordinator MUST validate that the incoming client `clientNodeId` is non-empty and well-formed.
- **FR-003**: Coordinator MUST generate a unique `SessionId` (GUID/UUID) for each valid session creation request.
- **FR-004**: Coordinator MUST persist a new session record containing the generated `SessionId`, the client `NodeId`, initial session status, and timestamp.
- **FR-005**: Coordinator MUST return the created session details (including `SessionId`, `Name`, `ClientNodeId`, and `Status`) upon successful creation.
- **FR-006**: Client MUST maintain a configurable `NodeId` string identifier initialized from environment configuration with support for arbitrary string values.
- **FR-007**: Client MUST provide an interactive console menu / REPL loop with options to trigger session creation against the Coordinator and exit cleanly.
- **FR-008**: Client MUST structure its codebase with presentation-independent architecture:
  - `domain/`: Domain models and business rules.
  - `application/`: Use cases, services, and state management.
  - `infrastructure/`: Network I/O, Coordinator HTTP client, and external communication.
  - `presentation/`: Console user interface / CLI interaction.
  - `config.py`: Environment configuration management loading from `.env`.
- **FR-009**: Client MUST provide a container definition (`Dockerfile`) supporting build, configuration injection via environment variables, and execution.
- **FR-010**: Client MUST display operation outcomes (success with session ID, or descriptive error message on failure) via the console presentation interface.

### Key Entities *(include if feature involves data)*

- **TrainingSession**: Represents a distributed training session coordinated by the system.
  - Attributes: `SessionId` (unique identifier), `ClientNodeId` (string identifier of the creating client node), `Status` (current lifecycle status, e.g., Pending/Active), `CreatedAt` (timestamp).
- **ClientNode**: Represents the client endpoint initiating and managing training sessions.
  - Attributes: `NodeId` (string identifier), `CoordinatorUrl` (target coordinator base address), `ActiveSessionId` (currently active session identifier, optional).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client operator can execute the session creation command and receive an assigned session ID from the Coordinator within 2 seconds under standard network conditions.
- **SC-002**: 100% of valid session creation requests result in a persistent session entry associating the generated session ID with the client's node ID string.
- **SC-003**: 100% of invalid or empty node ID requests are rejected with explicit error responses without creating invalid session records.
- **SC-004**: The client console application can be built and launched via container in under 60 seconds from clean environment.
- **SC-005**: Architectural layering boundaries are strictly maintained, ensuring zero direct dependencies from domain/business logic onto console UI or network I/O primitives.

## Assumptions

- The Coordinator uses SQL Server / EF Core persistence for session records as established in the architecture constitution.
- Network communication between Client and Coordinator uses standard REST JSON protocol.
- Client node identifiers are arbitrary string values assigned per deployment or generated locally by the operator.
- Security and authentication are minimal for the MVP phase, adhering to Constitution Principle IV.
