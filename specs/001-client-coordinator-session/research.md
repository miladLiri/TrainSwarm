# Phase 0 Research: Client-Coordinator Session Creation

**Feature**: `001-client-coordinator-session`
**Date**: 2026-08-21
**Status**: Completed

## 1. Architecture & Layering Pattern for Client Console Application

### Context
The client application is a Python console application responsible for initiating and managing distributed training sessions. Per requirements and constitution, it must be structured with presentation-independent architecture:
- `domain/`: Domain entities and core business rules (zero external dependencies).
- `application/`: Use cases, service coordination, and local in-memory state management.
- `infrastructure/`: Network I/O, Coordinator REST API client, and external systems.
- `presentation/`: Console user interface, REPL/menu loop, and formatted output.
- `config.py`: Environment configuration loading from `.env`.

### Decision
- Use standard Python typing and `dataclasses` in `domain/` (e.g., `Session`, `ClientNode`).
- Implement an explicit `CoordinatorGateway` interface in `application/ports/` or `infrastructure/` with a concrete `HttpCoordinatorClient` in `infrastructure/` using `requests`.
- Manage application state via a dedicated `ClientState` in `application/`.
- Present an interactive command loop via standard terminal I/O in `presentation/cli.py`.

### Rationale
- Decouples business rules and HTTP transport completely from the CLI presentation.
- Makes testing or substituting components straightforward without touching core logic.
- Complies strictly with Constitution Principle IV (MVP Focus & clean modular boundaries).

### Alternatives Considered
- *Monolithic single-file script*: Rejected because user explicitly specified a clean presentation-independent layered architecture.
- *Heavy CLI frameworks (Click/Typer)*: Evaluated, but standard library or minimal dependency is simpler and satisfies MVP without introducing bloat (Constitution Principle V: No Large Frameworks).

---

## 2. Coordinator Endpoint & Contract Schema Migration

### Context
In `TrainSwarm.Coordinator.Domain`, `TrainingSession` currently has `Guid ClientNodeId` and `CreateSessionDto` is `record CreateSessionDto(string Name, Guid ClientNodeId)`.
The requirement specifies:
- `CreateSession` accepts a string `clientNodeId` (arbitrary string format) and an optional `name`.
- Inserts a new row in the session table with `SessionId` (Guid/UUID) and `ClientNodeId` (string).
- Auto-generates a session name if omitted.

### Decision
- Update `TrainSwarm.Coordinator.Domain.Entities.TrainingSession`:
  - Change `public string ClientNodeId { get; set; } = string.Empty;`
  - Ensure `Name` defaults to auto-generated value if not supplied.
- Update `TrainSwarm.Coordinator.Api.Controllers.CreateSessionDto`:
  - `public record CreateSessionDto(string ClientNodeId, string? Name = null);`
- Update `SessionService.CreateSessionAsync` to handle string `ClientNodeId` and assign a default `Name` (`$"Session-{DateTime.UtcNow:yyyyMMddHHmmss}"`) when `string.IsNullOrWhiteSpace(session.Name)`.
- Update EF Core configuration / migration for string `ClientNodeId` with `MaxLength(128)`.

### Rationale
- Allows client nodes to use human-readable or arbitrary string IDs (e.g. `client-node-01`, UUID strings, hostnames).
- Preserves backwards compatibility while fulfilling the new specification.

### Alternatives Considered
- *Restricting NodeId to strict GUID strings*: Rejected because user specified arbitrary string identifier support.

---

## 3. Configuration Management & Environment Variables

### Context
Client configuration needs to support `.env` files and environment variable overrides for containerized execution.

### Decision
- Implement `src/Client/config.py` using `python-dotenv` and `os.getenv`.
- Variables:
  - `COORDINATOR_URL`: Base URL of Coordinator API (e.g., `http://localhost:5000` or `http://coordinator:5000`).
  - `CLIENT_NODE_ID`: Unique node identifier string (e.g., `client-node-local` or auto-generated UUID if unset).
  - `REQUEST_TIMEOUT_SECONDS`: HTTP request timeout in seconds (default: `5.0`).

### Rationale
- Pure `python-dotenv` with `os.getenv` is lightweight, zero-boilerplate, and standard across Python applications.

### Alternatives Considered
- *Hardcoded constants*: Rejected; violates environment configuration requirement.

---

## 4. Containerization Specification

### Context
A Dockerfile is required for the client application to run in containerized swarm deployments.

### Decision
- Base Image: `python:3.11-slim`
- Working Directory: `/app`
- Install dependencies from `requirements.txt` (`requests`, `python-dotenv`).
- Copy client source code into container.
- Entrypoint: `python main.py`

### Rationale
- Small image footprint (~150MB), secure, fast build time, and cross-platform compatibility.

### Alternatives Considered
- *Multi-stage build*: Unnecessary for a pure Python interpreted console application with no native compile steps.