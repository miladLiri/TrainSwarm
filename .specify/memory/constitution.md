<!-- Sync Impact Report
Version: 1.0.0 -> 1.0.1
Modified Principles:
- (none — all five principles unchanged)
Added Sections:
- (none)
Removed Sections:
- (none)
Deferred Items:
- None
Notes:
- Re-validation pass with identical user input.
  All placeholders resolved, dates verified, principles unchanged.
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

### II. Language and Runtime Strictness
The technology stack is strict and MUST NOT be deviated from without
explicit governance approval.
- **.NET** MUST be used for `Bootstrap` and `Coordinator`
  (Control Plane).
- **Python** MUST be used for `Trainer` and `Client + Aggregator`
  (Data Plane).
- **PyTorch** MUST be used as the training framework on the Trainer
  side.
- **SQL Server** is the designated database if persistence is required.
- **REST** is the initial communication layer for control-plane and
  client-service interactions.
- Transfer of checkpoints, dataset shards, weights, and all data-plane
  communication MUST be peer-to-peer via NAT hole punching, relayed
  initially by the Bootstrap service.

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

1. **Bootstrap Service (Control Plane, .NET)**
   - Provides initial peer discovery and entry-point information.
   - Accepts node registration metadata.
   - Exposes peer lookup/bootstrap metadata via REST.
   - Performs relay role for NAT hole punching between clients and
     trainers.

2. **Coordinator Service (Control Plane, .NET)**
   - Registers Trainers and tracks their availability/liveness.
   - Creates and tracks training sessions, assigning Trainers to them.
   - Exposes session and assignment status via REST.

3. **Client + Aggregator Service (Data Plane, Python)**
   - Creates and owns training sessions.
   - Manages checkpoint metadata.
   - Receives training updates from Trainers, aggregates them, and
     performs weight aggregation.
   - Exposes progress and job state via REST.

4. **Trainer Service (Data Plane, Python)**
   - Registers with the system and receives assigned training sessions.
   - Loads checkpoints and dataset shards.
   - Performs local fine-tuning (PyTorch).
   - Submits update metadata or results back to the Client.

## Governance

This Constitution supersedes all other practices for the TrainSwarm
repository.
- **Amendments:** Any changes to these rules (especially language
  boundaries or service responsibilities) require documentation and
  approval.
- **Versioning:** The constitution follows semantic versioning. MAJOR
  for principle removals/redefinitions, MINOR for new principles or
  material expansions, PATCH for clarifications and wording.
- **Compliance:** All PRs, code generation, and reviews MUST verify
  compliance with these rules.
- **Production Assumptions:** Do NOT assume a finalized production
  deployment model at this stage.

**Version**: 1.0.1 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-19
