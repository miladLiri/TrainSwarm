# Data Model: Client-Coordinator Session Creation

**Feature**: `001-client-coordinator-session`
**Date**: 2026-08-21
**Status**: Complete

## 1. Entities

### 1.1 TrainingSession (Coordinator Domain & Persistence)
Represents a training session tracked by the Coordinator.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `Id` | `Guid` (UUID) | Yes | Primary Key, auto-generated | Unique identifier of the session |
| `Name` | `string` | Yes | MaxLength 200, non-empty | Descriptive session name (defaults to `Session-<timestamp>` if omitted) |
| `Status` | `SessionStatus` (enum) | Yes | Default: `NONE` or `PENDING` | Current session lifecycle status |
| `ClientNodeId` | `string` | Yes | MaxLength 128, non-empty | Node identifier of the client initiating the session |
| `Trainers` | `ICollection<Trainer>` | No | Default: empty | Assigned trainer nodes (populated in subsequent swarm features) |

**Validation Rules**:
- `ClientNodeId` MUST NOT be null, empty, or whitespace-only.
- `Name` MUST NOT exceed 200 characters.

**State Transitions**:
```text
[Client Request] --> Created (Status: PENDING / NONE)
```

---

### 1.2 Session (Client Domain Model)
In-memory representation of an active session within the Python Client application.

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | `str` (UUID) | Yes | Identifier returned by Coordinator |
| `name` | `str` | Yes | Name of the session |
| `client_node_id` | `str` | Yes | Local node identifier |
| `status` | `str` | Yes | Lifecycle status string |

---

### 1.3 ClientNode (Client Domain & Config)
Represents local client node configuration and session state.

| Field | Type | Required | Description |
|---|---|---|---|
| `node_id` | `str` | Yes | Configured string identifier of this client |
| `coordinator_url` | `str` | Yes | URL of the target coordinator service |
| `active_session` | `Optional[Session]` | No | Currently active session object (if created) |

**State Transitions**:
```text
[Idle (active_session = None)] 
  -- (Trigger "Create Session") --> 
[Active (active_session = Session(...))]
  -- (Trigger "Create Session" again) --> 
[Active (active_session = New Session(...))]
```

---

## 2. Data Transfer Objects (DTOs)

### 2.1 CreateSessionDto (Request)
Sent from Client to Coordinator `POST /api/sessions`.

```json
{
  "clientNodeId": "client-node-01",
  "name": "CIFAR10-Distributed-Run-01"
}
```

- `clientNodeId`: `string` (required, non-empty)
- `name`: `string` (optional, nullable)

### 2.2 TrainingSessionResponse (Response)
Returned by Coordinator `POST /api/sessions` (HTTP 201 Created).

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "CIFAR10-Distributed-Run-01",
  "clientNodeId": "client-node-01",
  "status": "NONE"
}
```