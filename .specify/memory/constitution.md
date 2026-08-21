<!-- Sync Impact Report
Version: 1.0.1 -> 2.0.0
Modified Principles:
- II. Language and Runtime Strictness -> II. Language, Runtime, and Application Strictness (Updated Bootstrap runtime from .NET to Python; defined explicit application models: Client and Trainer as console applications, Bootstrap as a web application, Coordinator as a web API; specified DCUtR relay node role for Bootstrap in P2P communication)
- Architecture Boundaries & Service Definitions (Updated Bootstrap service to Python Web Application with DCUtR relay node role; updated Client and Trainer service definitions as Python Console Applications; updated Coordinator as .NET Web API)
Added Sections:
- (none)
Removed Sections:
- (none)
Deferred Items:
- None
Notes:
- Bootstrap runtime transitioned from .NET to Python, functioning as a web application and DCUtR relay node.
- Client and Trainer explicitly defined as Python console applications.
-->
# TrainSwarm Constitution

## Core Principles

### I. Semi-Distributed Architecture & Separation of Concerns
Control-plane services (`Bootstrap` and `Coordinator`) MUST be kept
completely separate from data-plane services (`Trainer` and
`Client + Aggregator`).
- `Coordinator` MUST NOT own model checkpoints, gradients, or datasets.
- `Bootstrap` MUST NOT participate in training or aggregation.
- `Trainer` MUST NOT own global session state.
- `Client` is the authoritative owner of training sessions and
  aggregation results.
- Storage ownership MUST remain local to the owning service.

### II. Language, Runtime, and Application Strictness
The technology stack and application forms are strict and MUST NOT be
deviated from without explicit governance approval.
- **.NET** MUST be used for `Coordinator` (Control Plane).
- **Python** MUST be used for `Bootstrap` (Control Plane), `Trainer`,
  and `Client + Aggregator` (Data Plane).
- **Application Models**:
  - `Client` and `Trainer` MUST be implemented as **console applications**.
  - `Bootstrap` MUST be implemented as a **web application**.
  - `Coordinator` MUST be implemented as a **web API application**.
- **PyTorch** MUST be used as the training framework on the Trainer
  side.
- **SQL Server** is the designated database if persistence is required.
- **REST** is the initial communication layer for control-plane and
  client-service interactions.
- **P2P & DCUtR Communication**: Transfer of checkpoints, dataset shards,
  weights, and peer-to-peer communication MUST use NAT hole punching
  via DCUtR (Direct Connection Upgrade through Relay) relay P2P
  communication, with `Bootstrap` serving as the relay node.

### III. Explicit Contracts & Boundaries
Cross-service interactions MUST be treated as versioned contracts.
- Use DTOs for network boundaries.
- Prefer explicit contracts over implicit coupling.
- Do NOT create hidden cross-service dependencies.
- Shared models MUST be kept minimal and stable.
- Do NOT silently change message formats.
- Preserve the current module split unless a documented decision
  changes it.

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

### V. Explicit Prohibitions & AI Guidelines
To maintain architecture integrity, the following are strictly
prohibited:
- **NO TESTS:** Do NOT write any kind of test.
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

## Architecture Boundaries & Service Definitions

The system consists of four primary services with strict
responsibilities:

1. **Bootstrap Service (Control Plane, Python Web Application)**
   - Implemented as a Python web application.
   - Provides initial peer discovery and entry-point information.
   - Accepts node registration metadata.
   - Exposes peer lookup/bootstrap metadata via REST.
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

**Version**: 2.0.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-21
