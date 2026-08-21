# Implementation Plan: Client-Coordinator Session Creation

**Branch**: `001-client-coordinator-session` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-client-coordinator-session/spec.md`

## Summary

This feature implements the foundational control-plane communication between the Client console application and the Coordinator Web API. The Coordinator exposes a `POST /api/sessions` endpoint that accepts a string `clientNodeId` and optional `name`, creates a persisted `TrainingSession` record in the database, and returns the assigned `SessionId`. 

The Client is developed as a Python console application following presentation-independent clean architecture (`domain/`, `application/`, `infrastructure/`, `presentation/`, `config.py`), featuring an interactive console REPL menu for creating and inspecting sessions, environment-driven configuration via `.env`, and Docker containerization.

## Technical Context

**Language/Version**: C# / .NET 10 (Coordinator), Python 3.11+ (Client)

**Primary Dependencies**: 
- Coordinator: ASP.NET Core, Microsoft.EntityFrameworkCore (SQL Server)
- Client: `requests`, `python-dotenv`

**Storage**: 
- Coordinator: SQL Server / EF Core `TrainingSessions` table (migrated to string `ClientNodeId`)
- Client: In-memory `ClientState` for active session tracking

**Testing**: None (strictly adhering to Constitution Principle V: NO TESTS)

**Target Platform**: Linux / Windows / Docker containers

**Project Type**: Web API (Coordinator) + Console Application (Client)

**Performance Goals**: End-to-end session creation roundtrip < 2.0s under standard network conditions

**Constraints**: Presentation-independent layering for Client; support for arbitrary string node IDs; zero test files created; `.env` configuration support

**Scale/Scope**: Initial MVP distributed session orchestration slice

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Separation of Concerns**: PASS. Coordinator tracks session lifecycle metadata; Client is authoritative session creator.
- **Principle II: Language, Runtime, & Application Strictness**: PASS. Coordinator is .NET Web API; Client is Python console application.
- **Principle III: Explicit Contracts & Boundaries**: PASS. Network boundary clearly defined with `CreateSessionDto` and OpenAPI contract.
- **Principle IV: Engineering & Coding Standards**: PASS. Simple, explicit presentation-independent layering.
- **Principle V: Explicit Prohibitions**: PASS. NO TESTS (zero test code/files), NO CRYPTO, NO RCE, NO MERGING ROLES.

## Project Structure

### Documentation (this feature)

```text
specs/001-client-coordinator-session/
├── plan.md              # Implementation plan (/speckit-plan output)
├── research.md          # Phase 0 research & technology decisions
├── data-model.md        # Phase 1 data models, entities, DTOs
├── quickstart.md        # Phase 1 end-to-end validation guide
├── contracts/           # Phase 1 interface contracts
│   ├── coordinator-api.yaml
│   └── client-cli.md
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/
├── Coordinator/
│   ├── TrainSwarm.Coordinator.Api/
│   │   └── Controllers/
│   │       ├── CreateSessionDto.cs
│   │       └── SessionsController.cs
│   └── TrainSwarm.Coordinator.Domain/
│       ├── Entities/
│       │   └── TrainingSession.cs
│       └── Services/
│           └── SessionService.cs
└── Client/
    ├── domain/
    │   ├── __init__.py
    │   └── models.py
    ├── application/
    │   ├── __init__.py
    │   ├── session_service.py
    │   └── state.py
    ├── infrastructure/
    │   ├── __init__.py
    │   └── coordinator_client.py
    ├── presentation/
    │   ├── __init__.py
    │   └── console_ui.py
    ├── config.py
    ├── main.py
    ├── requirements.txt
    ├── .env.example
    └── Dockerfile
```

**Structure Decision**: Multi-service repository split cleanly between `.NET` Coordinator (`src/Coordinator/`) and `Python` Client console application (`src/Client/`). Client strictly enforces presentation-independent layering across `domain/`, `application/`, `infrastructure/`, and `presentation/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | N/A | Fully compliant with architecture constitution |

