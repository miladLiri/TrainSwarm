# Phase 0: Research

## File Transfer Protocol over go-libp2p Streams

**Decision**: The file transfer protocol (`/p2p-file-transfer/1.0.0`) will use a length-prefixed Protobuf metadata header followed immediately by raw file bytes chunked over the stream.

**Rationale**:
go-libp2p streams are bidirectional byte streams. To send both structured metadata (filename, size, hash) and arbitrary binary data, the simplest approach is to send a protobuf message length-prefixed using `go-msgio` (or standard `encoding/binary` varint). The receiver reads the length, decodes the protobuf metadata, validates it, and then streams the remaining raw bytes directly to disk. This avoids the CPU overhead of wrapping every file chunk in a protobuf message.

**Alternatives considered**:
- Wrapping every chunk in a Protobuf envelope: High CPU/memory overhead for large files.
- Two separate streams (one for metadata, one for data): Requires complex correlation and state management.

## Circuit Relay v2 and DCUtR Configuration

**Decision**: The sidecar will use `libp2p.EnableRelayClient()` and `libp2p.EnableHolePunching()` built into go-libp2p.

**Rationale**:
go-libp2p natively supports DCUtR (Direct Connection Upgrade through Relay) via the `p2p/host/autorelay` and `p2p/protocol/holepunch` packages. When the node is configured with `libp2p.EnableRelayClient()` and connected to a public relay, it can be dialed via its circuit relay multiaddress. The `libp2p.EnableHolePunching()` option automatically runs the DCUtR protocol whenever an incoming relayed connection is detected, coordinating a hole punch.

**Alternatives considered**:
- Custom TURN server / WebRTC: Adds significant infrastructure complexity; libp2p is already being used.
- Manual hole punching coordination: Prone to errors, reinventing the built-in go-libp2p standard.
