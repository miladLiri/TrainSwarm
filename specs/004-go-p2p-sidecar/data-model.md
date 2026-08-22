# Data Model

The data model for the Go P2P Sidecar focuses entirely on connection state management and file transfer metadata. It does not persist relational data to a database; state is primarily kept in memory and passed across the gRPC boundary.

## Core Entities

### Peer Identity
- **Description**: The cryptographic identity of a P2P node.
- **Persistence**: Stored on disk (e.g., `identity.key`) so the node maintains a stable ID across restarts.
- **Fields**:
  - `PrivateKey` (ed25519)
  - `PeerID` (derived from public key, string formatted as base58)

### Connection State
- **Description**: Represents the current relationship with a remote peer.
- **States**:
  - `DISCONNECTED`: No active connection.
  - `CONNECTING`: Attempting to dial.
  - `RELAY_CONNECTED`: Connected via Circuit Relay v2 (transient).
  - `PUNCHING`: DCUtR hole punch in progress.
  - `DIRECT_CONNECTED`: Connected directly (TCP/QUIC).
  - `FAILED`: Connection attempt failed.

### Transfer Metadata (libp2p Stream Header)
- **Description**: The length-prefixed Protobuf/JSON payload sent at the start of the `/p2p-file-transfer/1.0.0` stream.
- **Fields**:
  - `TransferID` (string, UUID)
  - `FileName` (string)
  - `FileSize` (int64)
  - `SHA256` (string, hex encoded)
  - `ChunkSize` (uint32)

### Transfer Status
- **Description**: The state of an ongoing file transfer.
- **States**:
  - `START`
  - `ACCEPT`
  - `DATA`
  - `PROGRESS`
  - `COMPLETE`
  - `CANCEL`
  - `ERROR`
  - `REJECT`

### Node Events (gRPC `WatchEvents`)
- **Description**: Notifications pushed to the Python application.
- **Types**:
  - `PEER_CONNECTED`
  - `PEER_DISCONNECTED`
  - `CONNECTION_UPGRADED_TO_DIRECT`
  - `HOLE_PUNCH_FAILED`
  - `TRANSFER_REQUESTED` (contains transfer metadata)
  - `TRANSFER_STARTED`
  - `TRANSFER_PROGRESS` (bytes transferred, total bytes)
  - `TRANSFER_COMPLETED`
  - `TRANSFER_FAILED`
  - `TRANSFER_CANCELLED`
