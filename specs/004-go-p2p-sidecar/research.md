# Phase 0: Research

## File Transfer Protocol over go-libp2p Streams

**Decision**: The file transfer protocol (`/trainswarm/file/1.0.0`) uses a JSON metadata header followed immediately by raw file bytes chunked over the stream. In addition, a file request protocol (`/trainswarm/request/1.0.0`) enables receivers to actively request files by name from remote owners.

**Rationale**:
go-libp2p streams are bidirectional byte streams. To send both structured metadata (filename, size, hash) and arbitrary binary data, the transfer manager sends a JSON header, waits for acceptance, and streams raw bytes directly to disk. Supporting `/trainswarm/request/1.0.0` allows pulling files on demand without requiring the sender to know ahead of time when the receiver is ready.

**Alternatives considered**:
- Wrapping every chunk in a Protobuf envelope: High CPU/memory overhead for large files.
- Push-only transfer model: Inflexible when requesters need to initiate retrieval of specific checkpoints.

## Circuit Relay v2, DCUtR, and Transient Stream Management

**Decision**: The sidecar configures `libp2p.EnableRelay()` and `libp2p.EnableHolePunching()`, tracks its bootstrap relay internally, and wraps stream negotiation with `network.WithUseTransient()`.

**Rationale**:
go-libp2p marks Circuit Relay v2 connections as transient. By default, `NewStream` blocks on transient connections waiting for direct upgrades via DCUtR. Using `network.WithUseTransient` allows application streams to negotiate and transfer data immediately across relay circuits while DCUtR attempts hole punching in the background. Automating internal relay circuit addresses (`/p2p/<relayID>/p2p-circuit`) simplifies client integration by allowing callers to specify only target peer IDs.

**Alternatives considered**:
- Requiring callers to supply full circuit relay multiaddresses: Leaks internal networking topology to host applications.
- Blocking on DCUtR before allowing transfers: Fails or times out on symmetric or restrictive NATs where direct hole punching is impossible.
