# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The feature builds a standalone Go P2P Sidecar executable that runs alongside the Python Application. The sidecar owns all Internet-facing P2P networking using `go-libp2p` (Identity, AutoNAT, Circuit Relay v2, DCUtR hole punching) and exposes a localhost-only gRPC API for the Python app to manage connections and file transfers.

## Technical Context

**Language/Version**: Go 1.21+

**Primary Dependencies**: `go-libp2p`, `grpc`, `protobuf`

**Storage**: Local filesystem (writes to configured destination paths)

**Testing**: `go test` (Integration/E2E tests required by spec, overriding constitution)

**Target Platform**: Windows, Linux

**Project Type**: Standalone gRPC Service / Child Process

**Performance Goals**: Low memory footprint for streaming (>1GB files under 100MB RAM), fast connection upgrade (<10s).

**Constraints**: MUST bind gRPC to `127.0.0.1` only, MUST implement DCUtR, MUST use `/trainswarm/file/1.0.0` and `/trainswarm/request/1.0.0`.

**Scale/Scope**: Single sidecar per Python application instance.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Violations Detected**:
1. **Language Strictness**: Constitution Principle II dictates Python for Client and Trainer. This feature introduces Go. Justification: Python's `py-libp2p` lacks functional DCUtR support, and the user explicitly mandated a Go sidecar to handle NAT traversal.
2. **Prohibited Practices**: Constitution Principle V strictly states "NO TESTS: Do NOT write any kind of test." The feature spec FR-011 mandates end-to-end tests. Justification: Feature spec explicitly overrides the constitution for this component to ensure network reliability.

These violations are justified by the explicit user requirements for the sidecar architecture and will be tracked in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/p2p-node/
├── cmd/
│   └── p2pd/
│       └── main.go
├── internal/
│   ├── node/
│   │   ├── node.go
│   │   ├── identity.go
│   │   └── reachability.go
│   ├── nat/
│   │   ├── autonat.go
│   │   ├── relay.go
│   │   └── holepunch.go
│   ├── transfer/
│   │   ├── sender.go
│   │   ├── receiver.go
│   │   └── protocol.go
│   └── api/
│       ├── server.go
│       └── p2p.proto
└── go.mod
```

**Structure Decision**: A new `src/p2p-node` directory will be created to house the Go project, using standard Go directory layout (`cmd/` for executables, `internal/` for private application code).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New Language (Go) | Required for robust NAT traversal via libp2p DCUtR. | Python's `py-libp2p` lacks functional hole-punching and relay support, rendering it unsuitable for the environment. |
| End-to-End Tests | Required to verify complex P2P hole-punching and transfer reliability. | Skipping tests for infrastructural networking components leads to untestable application regressions. |
