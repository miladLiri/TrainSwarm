# Implementation Plan: Training Client Configuration, Dependency Injection, and Smoke Test

**Branch**: `014-client-config-smoke-test` | **Date**: 2026-09-04 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/014-client-config-smoke-test/spec.md)

**Input**: Feature specification from `/specs/014-client-config-smoke-test/spec.md`

## Summary

Extend the Python Training Client with three interrelated capabilities:
1. A centralized **Configuration Manager** (`src/Client/config/`) that serves as the single authoritative component for reading, parsing, and validating all client environment variables with fast-fail behavior, completely migrating and eliminating direct `os.getenv` reads elsewhere in `src/Client`.
2. A lightweight **Composition Root / Dependency Injection** mechanism (`src/Client/dependency_injection/`) that explicitly wires infrastructure adapters (`CoordinatorAdapter`), persistence (`DatabaseManager`, `TrainingShardRepository`), training execution engines (`TrainingOrchestrator`), and application command handlers using pure-Python constructor injection without third-party frameworks or service locators.
3. A **Smoke Test Application Use Case** (`src/Client/application/smoke_test/`) executing small real training benchmarks through the `TrainingOrchestrator`, measuring elapsed duration via high-precision monotonic timing (`time.perf_counter()`), computing training throughput, estimating shard sample capacities within configured time limits, escalating training failures cleanly, and automatically cleaning up output model delta artifacts.

## Technical Context

**Language/Version**: Python 3.11+ (Data plane Python console application).

**Primary Dependencies**: `torch>=2.0.0`, `requests>=2.31.0`, `python-dotenv>=1.0.0`, standard library (`pathlib`, `logging`, `dataclasses`, `time`, `typing`, `sqlite3`, `json`). Zero third-party dependency injection frameworks.

**Storage**: Local SQLite persistence via existing `DatabaseManager` and `TrainingShardRepository`, configured strictly through constructor injection via `ClientConfig.db_path`.

**Testing**: Syntax validation via `python -m py_compile`, active zero-mock verification harness in `samples/client_smoke_test/verify_client_config_smoke_test.py` per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux (Docker container `python:3.11-slim`), macOS.

**Project Type**: Data Plane Client Architecture Refactoring & Application Use Case.

**Performance Goals**:
- Configuration Manager fast-fail startup validation overhead < 10ms.
- Sub-millisecond elapsed duration precision via `time.perf_counter()`.
- Zero memory leaks or lingering file descriptors across repeated smoke runs.
- Instantaneous automatic cleanup of output delta files after benchmark completion.

**Constraints**:
- Strict boundary isolation: Zero `os.getenv`, `os.environ`, or `environ.get` calls outside `src/Client/config/`.
- Zero third-party DI frameworks and zero global service locator queries (`container.get` or `container.resolve` in application code).
- Real training path only: Smoke test MUST execute through the real `TrainingOrchestrator` without mocks or synthetic shortcuts.
- Backward compatibility: Existing `CoordinatorAdapter`, `DatabaseManager`, and `main.py` continue to function reliably after constructor migration.

**Scale/Scope**: 7 new/migrated modules in `src/Client/`, 2 refactored infrastructure classes (`CoordinatorAdapter`, `DatabaseManager`), updated `main.py`, and 1 end-to-end active verification suite in `samples/client_smoke_test/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. The Client remains the authoritative owner of local sessions and shard sizing; control-plane coordination remains on Coordinator; zero coordinator state merged into data plane.
- **II. Language, Runtime, and Application Strictness**: PASS. Implemented exclusively in Python 3.11+ for the Client console application.
- **III. Explicit Contracts & Boundaries**: PASS. `ClientConfig`, `SmokeTestCommand`, `SmokeTestResult`, and `DIContainer` define explicit, strongly typed contracts and schemas.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Lightweight composition root, explicit constructor parameters, simple dataclasses, and zero premature abstractions.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero stubs, zero test frameworks (no unittest/pytest), zero crypto, zero RCE, zero third-party DI frameworks.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. Executes real PyTorch autograd training loop via `TrainingOrchestrator`, real monotonic duration measurement, real SQLite persistence, and real filesystem operations.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Active executable verification script `samples/client_smoke_test/verify_client_config_smoke_test.py` runs all scenarios end-to-end to satisfy the post-change quality gate.

## Project Structure

### Documentation (this feature)

```text
specs/014-client-config-smoke-test/
├── spec.md              # Feature specification with recorded clarifications
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 technical research & design decisions
├── data-model.md        # Phase 1 DTO, container & handler models
├── quickstart.md        # Phase 1 verification & execution guide
├── contracts/           # Phase 1 interface contracts & schemas
│   ├── configuration-di-contracts.md
│   ├── smoke-test-command.schema.json
│   └── smoke-test-result.schema.json
└── checklists/
    └── requirements.md  # Requirements quality checklist (16/16 passing)
```

### Source Code (repository root)

```text
src/Client/
├── Dockerfile                                      # Existing Dockerfile
├── requirements.txt                                # torch, requests, python-dotenv
├── main.py                                         # Refactored entry point: boots ConfigManager and DIContainer
│
├── config/
│   ├── __init__.py                                 # Re-exports ConfigManager, ClientConfig, exceptions
│   └── config_manager.py                           # Centralized environment variable loader & validator
│
├── dependency_injection/
│   ├── __init__.py                                 # Re-exports DIContainer
│   └── container.py                                # Composition root for explicit dependency construction
│
├── application/
│   ├── __init__.py
│   ├── state.py                                    # Client state
│   └── smoke_test/
│       ├── __init__.py                             # Re-exports SmokeTestCommand, Handler, Result, exceptions
│       ├── smoke_test_command.py                   # SmokeTestCommand DTO
│       ├── smoke_test_command_handler.py           # SmokeTestCommandHandler implementation
│       └── smoke_test_result.py                    # SmokeTestResult DTO
│
├── domain/
│   ├── __init__.py
│   ├── models.py
│   └── training_shard.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── coordinator_adapter.py                  # Refactored: constructor injection only (no os.getenv)
│   │   └── create_training_task.py
│   └── persistence/
│       ├── __init__.py
│       ├── database.py                             # Refactored: constructor injection only (no os.getenv)
│       ├── exceptions.py
│       └── training_shard_repository.py
│
└── presentation/
    ├── __init__.py
    └── console_ui.py                               # Dormant/minimal console UI

samples/client_smoke_test/
└── verify_client_config_smoke_test.py              # Zero-mock active verification harness
```

**Structure Decision**: Extends `src/Client/` with two new architectural packages (`config/` and `dependency_injection/`) and introduces a command/command-handler feature package under `application/smoke_test/`. Migrates existing infrastructure constructors (`CoordinatorAdapter`, `DatabaseManager`) and removes legacy single-file `config.py`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No constitutional violations. Zero third-party DI frameworks introduced; pure-Python constructor injection used throughout.*
