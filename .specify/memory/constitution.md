<!-- Sync Impact Report
Version: 4.1.0 -> 4.2.0
Modified Principles:
- IV. Engineering & Coding Standards (MVP Focus) (Added post-change verification rule)
Added Sections:
- VII. Verification, Compilability, and Executable Correctness (Mandatory Post-Change Quality Gate)
Removed Sections:
- (none)
Deferred Items:
- None
Notes:
- Added non-negotiable principle requiring that after any code modification or feature implementation, the agent must verify build integrity (compilability), executability (runnability), and functional correctness through active execution before marking work complete.
-->
# TrainSwarm Constitution

## Core Principles

### I. Semi-Distributed Architecture & Separation of Concerns
Control-plane services (`Bootstrap` and `Coordinator`) MUST be kept
completely separate from data-plane services (`Trainer`, `Client + Aggregator`, and `p2p-node`).
- `Coordinator` MUST NOT own model checkpoints, gradients, or datasets.
- `Bootstrap` MUST NOT participate in training or aggregation.
- `Trainer` MUST NOT own global session state.
- `Client` is the authoritative owner of training sessions and
  aggregation results.
- Storage ownership MUST remain local to the owning service.
- `p2p-node` MUST own all Internet-facing P2P networking and NAT traversal, insulating the application from libp2p complexity.

### II. Language, Runtime, and Application Strictness
The technology stack and application forms are strict and MUST NOT be
deviated from without explicit governance approval.
- **.NET** MUST be used for `Coordinator` (Control Plane).
- **Go** MUST be used for `Bootstrap` (Control Plane) and `p2p-node` (Data Plane Sidecar).
- **Python** MUST be used for `Trainer` and `Client + Aggregator` (Data Plane).
- **Application Models**:
  - `Client` and `Trainer` MUST be implemented as **console applications**.
  - `Coordinator` MUST be implemented as a **web API application**.
  - `Bootstrap` MUST be implemented as a **Go p2p hole punching relay server using go-libp2p**.
  - `p2p-node` MUST be implemented as a **standalone Go sidecar executable**.
- **PyTorch** MUST be used as the training framework on the Trainer
  side.
- **SQL Server** is the designated database if persistence is required.
- **REST** is the initial communication layer for control-plane and
  client-service interactions.
- **P2P & DCUtR Communication**: Transfer of checkpoints, dataset shards,
  weights, and peer-to-peer communication MUST use NAT hole punching
  via DCUtR (Direct Connection Upgrade through Relay) relay P2P
  communication, with `Bootstrap` serving as the relay node and `p2p-node` handling the local execution.

### III. Explicit Contracts & Boundaries
Cross-service interactions MUST be treated as versioned contracts.
- Use DTOs for network boundaries.
- Prefer explicit contracts over implicit coupling.
- Do NOT create hidden cross-service dependencies.
- Shared models MUST be kept minimal and stable.
- Do NOT silently change message formats.
- Preserve the current module split unless a documented decision
  changes it.
- Communication between Python applications and the Go `p2p-node` MUST occur exclusively over a localhost-bound gRPC API.

### IV. Engineering & Coding Standards (MVP Focus)
The project is in an MVP stage focusing on functionality over premature
optimization or over-design.
- Optimize for clarity over premature abstraction; prefer simple,
  explicit code.
- Build contracts before implementation, preferring small vertical
  slices over large speculative frameworks.
- Keep files small, responsibilities clear, and use
  configuration-driven behavior.
- Add comments only when code is not self-explanatory.
- Use consistent naming across services and shared contracts.
- Security hardening beyond basic transport and input handling is NOT
  required at this stage.
- Make failure states explicit and state transitions observable.
- Every code modification MUST be actively tested for compilation and execution validity before concluding tasks.

### V. Explicit Prohibitions & AI Guidelines
To maintain architecture integrity, the following are strictly
prohibited:
- **NO MOCKS:** Do NOT write mock, stub, simulated, or placeholder
  implementations. All modules, APIs, and infrastructure components
  MUST deliver real working functionality within specification scope.
- **NO TESTS:** Do NOT write any kind of test. **EXCEPTION**: End-to-End tests are explicitly permitted and required ONLY for the `p2p-node` service to verify complex P2P hole-punching and networking reliability.
- **NO CRYPTO:** Do NOT add blockchain, token, or incentive mechanics.
- **NO RCE:** Do NOT introduce remote code execution or unsafe
  file/network/process shortcuts.
- **NO MERGING ROLES:** Do NOT merge Trainer logic into Coordinator or
  make Bootstrap a training/aggregation service.
- **NO UNDOCUMENTED SHARED STATE:** Do NOT introduce undocumented
  shared state across services.
- **NO LARGE FRAMEWORKS:** Do NOT add large frameworks unless
  justified.
- **NO PRODUCTION ASSUMPTIONS:** Do NOT assume a finalized production
  deployment model.
- **AI GUIDELINES:** Before making changes, AI agents MUST identify
  affected services, the plane (control/data/shared), runtime vs
  structure impact, new state/persistence, and documentation updates.
  Keep AI-generated changes reviewable and narrow in scope.

### VI. Real Functional Implementations (Zero Mocks)
Every feature, infrastructure component, module, API, and subsystem MUST
provide real, working functionality within the scope of its specification.
- **No Stubs or Placeholders:** Code MUST NOT contain dummy routines,
  no-op placeholders, hardcoded fake return values, or simulated network/storage
  calls in place of real logic.
- **End-to-End Operational Integrity:** All specified behaviors—including
  P2P networking, gRPC endpoints, REST APIs, relay forwarding, model training,
  checkpoint streaming, and coordinator sessions—MUST execute actual runtime
  operations against real systems, protocols, and I/O.
- **Spec-Complete Deliverables:** Every task and deliverable must be fully
  functional in adherence to its design contract and specifications; partial
  scaffolding with fake behaviors is strictly unacceptable.

### VII. Verification, Compilability, and Executable Correctness (Mandatory Post-Change Quality Gate)
For every feature implemented and after every code modification, agents and developers MUST verify that the codebase compiles, runs cleanly, and produces correct results.
- **Compilability (Build Integrity):** After modifying code, the agent MUST execute the relevant compiler, build, or syntax check commands (e.g., `go build ./...`, `dotnet build`, `python -m py_compile`) and confirm zero compilation or syntax errors.
- **Executability (Runnability):** The agent MUST verify that modified services, scripts, or executables launch and execute without runtime panics, unhandled exceptions, or crash loops.
- **Verification of Correctness:** The agent MUST actively inspect and confirm the correctness of outputs, communication streams, and returned data against specifications (via real command execution, CLI calls, or E2E validation) before considering an implementation complete.
- **No Unverified Assumptions:** Code MUST NOT be declared functional based on visual inspection alone; concrete validation of build and execution correctness is mandatory.

## Architecture Boundaries & Service Definitions

The system consists of five primary services with strict
responsibilities:

1. **Bootstrap Service (Control Plane, Go Relay Server)**
   - Implemented as a Go application using go-libp2p.
   - Provides initial peer discovery and entry-point information.
   - Accepts node registration metadata.
   - Functions as a relay node in DCUtR (Direct Connection Upgrade
     through Relay) relay P2P communication to facilitate NAT hole
     punching between clients and trainers.

2. **Coordinator Service (Control Plane, .NET Web API)**
   - Implemented as a .NET web API.
   - Registers Trainers and tracks their availability/liveness.
   - Creates and tracks training sessions, assigning Trainers to them.
   - Exposes session and assignment status via REST.

3. **Client + Aggregator Service (Data Plane, Python Console Application)**
   - Implemented as a Python console application.
   - Creates and owns training sessions.
   - Manages checkpoint metadata.
   - Receives training updates from Trainers, aggregates them, and
     performs weight aggregation.
   - Exposes progress and job state.

4. **Trainer Service (Data Plane, Python Console Application)**
   - Implemented as a Python console application.
   - Registers with the system and receives assigned training sessions.
   - Loads checkpoints and dataset shards.
   - Performs local fine-tuning (PyTorch).
   - Submits update metadata or results back to the Client via P2P.

5. **p2p-node Service (Data Plane, Go Standalone Executable)**
   - Implemented as a standalone Go executable running alongside the Python applications.
   - Owns all Internet-facing P2P networking using go-libp2p (Identity, AutoNAT, Circuit Relay v2, DCUtR hole punching).
   - Manages NAT traversal and resilient chunked file transfers.
   - Exposes a strictly localhost-bound gRPC API for the Python application to manage connections and initiate file transfers.

## Governance

This Constitution supersedes all other practices for the TrainSwarm
repository.
- **Amendments:** Any changes to these rules (especially language
  boundaries, application types, or service responsibilities) require
  documentation and approval.
- **Versioning:** The constitution follows semantic versioning. MAJOR
  for principle removals/redefinitions, MINOR for new principles or
  material expansions, PATCH for clarifications and wording.
- **Compliance:** All PRs, code generation, and reviews MUST verify
  compliance with these rules.
- **Production Assumptions:** Do NOT assume a finalized production
  deployment model at this stage.

**Version**: 4.2.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-29
