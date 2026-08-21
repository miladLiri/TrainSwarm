# Phase 1 Data Model: Bootstrap Relay and P2P Communication

## Core Entities

### 1. PeerRegistration (Bootstrap Service)

Represents a node actively registered with the Bootstrap relay service.

| Field | Type | Required | Description |
|---|---|---|---|
| `peerId` | `string` (UUID) | Yes | Unique peer identifier assigned by Bootstrap upon registration. |
| `nodeId` | `string` | Yes | Operator-assigned logical node identifier (e.g., `trainer-node-01`, `client-node-dev`). |
| `role` | `string` | Yes | Node role: `"trainer"` or `"client"`. |
| `endpoint` | `string` (optional) | No | Advertised IP/hostname and port (e.g., `"192.168.1.50:8000"`). |
| `registeredAt` | `string` (ISO 8601) | Yes | Timestamp of initial registration. |
| `lastSeenAt` | `string` (ISO 8601) | Yes | Timestamp of most recent heartbeat or request. |
| `relayAddress` | `string` | Yes | Canonical address of relay endpoint assigned to this peer. |

---

### 2. RelayMessage (Bootstrap Service)

Represents an in-transit message routed between two swarm peers via the Bootstrap relay.

| Field | Type | Required | Description |
|---|---|---|---|
| `messageId` | `string` (UUID) | Yes | Unique identifier for the message. |
| `sourcePeerId` | `string` (UUID) | Yes | Sending peer's `peerId`. |
| `targetPeerId` | `string` (UUID) | Yes | Destination peer's `peerId`. |
| `payload` | `string` or `object` | Yes | Opaque payload / JSON body being relayed. |
| `timestamp` | `string` (ISO 8601) | Yes | Time when message was enqueued in relay inbox. |

---

### 3. TrainerNode (Trainer Application)

Represents local configuration and network state for the Trainer node runtime.

| Field | Type | Required | Description |
|---|---|---|---|
| `nodeId` | `string` | Yes | Configured string identifier from `.env`. |
| `peerId` | `string` (UUID, optional) | No | Assigned peer ID from Bootstrap relay (populated upon connection). |
| `bootstrapUrl` | `string` | Yes | URL of target Bootstrap service. |
| `coordinatorUrl` | `string` | Yes | URL of target Coordinator API. |
| `status` | `string` | Yes | Current network status: `"INITIALIZED"`, `"REGISTERED"`, `"DISCONNECTED"`. |

---

### 4. ClientNode (Client Application Enhancement)

Represents enhanced local configuration and network state for the Client application.

| Field | Type | Required | Description |
|---|---|---|---|
| `nodeId` | `string` | Yes | Configured string identifier from `.env`. |
| `peerId` | `string` (UUID, optional) | No | Assigned peer ID from Bootstrap relay. |
| `bootstrapUrl` | `string` | Yes | URL of target Bootstrap service. |
| `coordinatorUrl` | `string` | Yes | URL of target Coordinator API. |
| `activeSession` | `Session` (optional) | No | Currently active training session from Coordinator. |

---

## Data Transfer Objects (DTOs)

### `RegisterPeerRequest`
```json
{
  "nodeId": "trainer-node-01",
  "role": "trainer",
  "endpoint": "127.0.0.1:8001"
}
```

### `RegisterPeerResponse`
```json
{
  "peerId": "e1f2a3b4-5678-4abc-9def-0123456789ab",
  "nodeId": "trainer-node-01",
  "role": "trainer",
  "relayAddress": "http://localhost:6000",
  "registeredAt": "2026-08-21T20:30:00Z"
}
```

### `SendRelayMessageRequest`
```json
{
  "sourcePeerId": "e1f2a3b4-5678-4abc-9def-0123456789ab",
  "targetPeerId": "c9d8e7f6-5432-4cba-8fed-9876543210fe",
  "payload": {
    "type": "PING",
    "content": "Hello from Trainer"
  }
}
```

### `RelayInboxResponse`
```json
{
  "peerId": "c9d8e7f6-5432-4cba-8fed-9876543210fe",
  "messages": [
    {
      "messageId": "9a8b7c6d-5e4f-4321-ba98-fedcba098765",
      "sourcePeerId": "e1f2a3b4-5678-4abc-9def-0123456789ab",
      "targetPeerId": "c9d8e7f6-5432-4cba-8fed-9876543210fe",
      "payload": {
        "type": "PING",
        "content": "Hello from Trainer"
      },
      "timestamp": "2026-08-21T20:30:05Z"
    }
  ]
}
```