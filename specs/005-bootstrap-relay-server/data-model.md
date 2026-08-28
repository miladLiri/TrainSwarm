# Data Model: Bootstrap Relay Server

## Configuration Entity
The service is entirely stateless apart from the configuration provided at startup and its cryptographic identity loaded from disk.

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `P2P_RELAY_LISTEN_TCP` | `string` | TCP multiaddress to bind to (e.g., `/ip4/0.0.0.0/tcp/4001`) | Yes | - |
| `P2P_RELAY_LISTEN_QUIC` | `string` | QUIC UDP multiaddress to bind to (e.g., `/ip4/0.0.0.0/udp/4001/quic-v1`) | No | - |
| `P2P_RELAY_IDENTITY_PATH` | `string` | Path to persistent ed25519 identity key file | Yes | - |
| `P2P_RELAY_MAX_RESERVATIONS` | `int` | Maximum number of concurrent reservations accepted | Yes | `128` |
| `P2P_RELAY_MAX_CIRCUITS` | `int` | Maximum concurrent relayed connections active | Yes | `16` |
| `P2P_RELAY_MAX_RELAYED_BYTES` | `int` | Maximum bytes that can pass over a single circuit before termination | Yes | `10485760` (10MB) |
| `P2P_RELAY_MAX_RELAY_DURATION` | `string` | Maximum duration a circuit can be kept alive | Yes | `2m` |
| `P2P_RELAY_LOG_LEVEL` | `string` | Operational log level (`debug`, `info`, `warn`, `error`) | No | `info` |

## Resource Limits Constraints
The Circuit Relay v2 limits are strictly enforced. The byte and duration limits are intentionally kept low to incentivize peers to negotiate a direct connection (DCUtR) as quickly as possible rather than proxying raw file transfers through the relay.

## State Transitions
**Identity Management**:
- `Startup`: If `P2P_RELAY_IDENTITY_PATH` exists, load it. If not, generate a new Ed25519 keypair, save it to the path, and use it.
