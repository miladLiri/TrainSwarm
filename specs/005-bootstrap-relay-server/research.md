# Research: Bootstrap Relay Server

## 1. Technical Context Verification
The feature requires a Go standalone application utilizing the `go-libp2p` library to implement a Circuit Relay v2 server.
- **Language**: Go
- **Primary Dependency**: `github.com/libp2p/go-libp2p`
- **Network Stack**: TCP, QUIC, Identify, Circuit Relay v2 (relay service).

## 2. Findings & Best Practices

### go-libp2p Circuit Relay v2 Configuration
- **Decision**: Use the standard `go-libp2p` Relay Service implementation `circuitv2.NewRelay(host, options...)`.
- **Rationale**: The spec mandates using the standard go-libp2p stack without proprietary hole-punching protocol implementations. DCUtR is inherently supported by relay clients; the relay just needs to provide the standard `v2` relay service.
- **Alternatives considered**: Writing a custom proxy. Rejected because it violates the specification and would lack interoperability with the `p2p-node` sidecar which uses standard libp2p.

### Resource Limits Enforcements
- **Decision**: Configure the `go-libp2p` relay `Resources` struct dynamically via environment variables mapping to `P2P_RELAY_MAX_RESERVATIONS`, `P2P_RELAY_MAX_CIRCUITS`, `P2P_RELAY_MAX_RELAYED_BYTES`, and `P2P_RELAY_MAX_RELAY_DURATION`.
- **Rationale**: Fulfills the explicit configuration constraints demanded by the spec.

### Docker Deployment Strategy
- **Decision**: Create a minimal `Dockerfile` using a multi-stage Go builder, producing an Alpine or scratch-based image.
- **Rationale**: Aligns with the "standalone executable deployable independently" mandate.

## Conclusion
There are no unknowns. The architecture requires a straightforward integration of the existing `go-libp2p` primitives into a dedicated entrypoint with environment-based configuration bindings.
