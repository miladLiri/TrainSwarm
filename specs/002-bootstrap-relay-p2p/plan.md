# Implementation Plan: Bootstrap Relay and P2P Communication

**Branch**: `002-bootstrap-relay-p2p` | **Date**: 2026-08-21 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `specs/002-bootstrap-relay-p2p/spec.md`

## Summary

Implement the Bootstrap Relay web application (FastAPI) and the Trainer console application in Python with presentation-independent architecture (`domain/`, `application/`, `infrastructure/`, `presentation/`, `config.py`), and enhance the Client console application to connect to the Bootstrap relay for peer discovery and DCUtR relay messaging. Provide Docker container definitions for Bootstrap and Trainer.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- Bootstrap: `fastapi>=0.110.0`, `uvicorn>=0.28.0`, `python-dotenv>=1.0.0`
- Trainer: `requests>=2.31.0`, `python-dotenv>=1.0.0`
- Client: `requests>=2.31.0`, `python-dotenv>=1.0.0`
**Storage**: In-memory thread-safe peer registry & message queue store for Bootstrap Relay.
**Testing**: None (Strictly NO TESTS per Constitution Principle V).
**Target Platform**: Linux / Windows / Docker containers.
**Project Type**: Multi-component distributed system (FastAPI web service + Python console applications).
**Performance Goals**: Peer registration and relay message response time < 1 second.
**Constraints**: Presentation-independent layering for console apps, zero external broker dependencies, standard environment variable configuration via `.env`.
**Scale/Scope**: Swarm topology with 1 Bootstrap relay, 1 Coordinator API, multiple Trainer nodes, and Client nodes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I: Semi-Distributed Architecture & Separation of Concerns**: Bootstrap operates as a control-plane peer registry/relay and does not participate in training or aggregation.
- [x] **Principle II: Language, Runtime, and Application Strictness**: Bootstrap is a Python web app; Coordinator is .NET Web API; Client and Trainer are Python console apps.
- [x] **Principle III: Explicit Contracts & Boundaries**: OpenAPI specification (`bootstrap-api.yaml`) and CLI contract (`trainer-cli.md`) defined.
- [x] **Principle IV: Engineering & Coding Standards**: MVP focus, clean 4-layer architecture for Trainer and Client.
- [x] **Principle V: Explicit Prohibitions**: NO test files, NO cryptocurrency, NO RCE, NO merging node roles.

## Project Structure

### Documentation (this feature)

```text
specs/002-bootstrap-relay-p2p/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── bootstrap-api.yaml
│   └── trainer-cli.md
└── checklists/
    └── requirements.md
```

### Source Code Layout

```text
src/
├── Bootstrap/                         # Python Web Application (FastAPI)
│   ├── main.py                        # FastAPI entrypoint & routes
│   ├── models.py                      # Request/Response schemas & dataclasses
│   ├── registry.py                    # In-memory peer registry & relay message queue
│   ├── config.py                      # Environment config (PORT, HOST)
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── .dockerignore
│
├── Trainer/                           # Python Console Application
│   ├── domain/                        # Domain entities & business rules
│   │   ├── __init__.py
│   │   └── models.py                  # TrainerNode, PeerSession, TrainerStatus
│   ├── application/                   # Use cases & state management
│   │   ├── __init__.py
│   │   ├── state.py                   # TrainerState in-memory coordinator
│   │   └── trainer_service.py         # TrainerService use cases
│   ├── infrastructure/                # External I/O & API clients
│   │   ├── __init__.py
│   │   ├── bootstrap_client.py        # HTTP client for Bootstrap relay
│   │   └── coordinator_client.py      # HTTP client for Coordinator API
│   ├── presentation/                  # Console interface
│   │   ├── __init__.py
│   │   └── console_ui.py              # Interactive REPL menu loop
│   ├── config.py                      # Configuration loader (.env)
│   ├── main.py                        # Entrypoint
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── .dockerignore
│
├── Client/                            # Enhanced Python Console Application
│   ├── domain/models.py               # Enhanced with Peer ID & Bootstrap URL
│   ├── infrastructure/
│   │   └── bootstrap_client.py        # Added Bootstrap client
│   ├── application/
│   │   └── session_service.py         # Enhanced with relay registration
│   ├── presentation/console_ui.py     # Enhanced with peer display
│   ├── config.py                      # Added BOOTSTRAP_URL
│   └── .env.example                   # Added BOOTSTRAP_URL
│
└── Coordinator/                       # Control Plane .NET 10 API (Existing)
```

## Complexity Tracking

*No constitution violations.*

