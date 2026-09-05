# Implementation Plan: Training Client — Submit Training Application Command, Dual Presentation, and Shard Lifecycle

**Branch**: `015-client-submit-training` | **Date**: 2026-09-05 | **Spec**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/015-client-submit-training/spec.md)

**Input**: Feature specification from `/specs/015-client-submit-training/spec.md`

## Summary

Implement the complete **Submit Training** capability for the TrainSwarm Client:
1. An application command and handler (`src/Client/application/submit_training/`) that validates model and dataset paths, stages checkpoints to `{working_directory}/{model_id}/{model_id}_{model_version}.pt2`, runs an automated pre-flight smoke test via `SmokeTestCommandHandler` to determine optimal shard sizing, partitions the dataset into `{working_directory}/shards/{dataset_id}/`, persists shard metadata in SQLite via `TrainingShardRepository` with initial status `CREATED`, registers tasks with the Coordinator REST API, and atomically updates shard records to `READY` upon confirmation.
2. A domain and persistence extension adding `TrainingShardStatus.CREATED` and implementing atomic batch status updates `update_status(shard_ids, status)` in `TrainingShardRepository`.
3. Dual presentation interfaces:
   - Non-interactive CLI argument flags in [`console_ui.py`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/presentation/console_ui.py) and [`main.py`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/main.py).
   - Modern, minimalist desktop GUI under [`src/Client/presentation/gui/`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/presentation) built with PyQt6 featuring Submit Training and Logs tabs, form inputs, dropdowns, and a background `QThread` worker isolating UI from command execution.
4. Packaging updates: core `torch` and `safetensors` in [`requirements.txt`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/requirements.txt), desktop `PyQt6` in `requirements-gui.txt`, and updated [`Dockerfile`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/Dockerfile) with `/artifacts` volume.
5. A comprehensive containerized end-to-end verification sample suite in [`samples/submit_training_test/`](file:///C:/Users/azure-dev/dev/TrainSwarm/samples) (`setup.py`, `clean.py`, `e2e-test.py`) validating a 5-scenario test matrix via `docker exec`.

---

## Technical Context

**Language/Version**: Python 3.11+ (Data plane Client application).

**Primary Dependencies**:
- Core / Headless: `torch>=2.2.0`, `safetensors`, `requests>=2.31.0`, `python-dotenv>=1.0.0`, standard library (`sqlite3`, `pathlib`, `uuid`, `dataclasses`, `argparse`, `logging`).
- Desktop GUI (Optional): `PyQt6>=6.6.0`.

**Storage**: Local SQLite persistence via `DatabaseManager` and `TrainingShardRepository`, configured via `ClientConfig.db_path`.

**Testing**: Syntax validation via `python -m py_compile`, containerized active zero-mock verification suite in `samples/submit_training_test/` per Constitution Principle V (NO MOCKS, NO TEST FRAMEWORKS) and Principle VII (Mandatory Post-Change Quality Gate).

**Target Platform**: Windows, Linux (Docker container `python:3.11-slim`), macOS.

**Project Type**: Data Plane Client Command, Persistence Extension, Dual UI, and E2E Verification Sample.

**Performance Goals**:
- Fast-fail input and configuration validation < 50ms.
- High-precision monotonic timing via `time.perf_counter()`.
- Zero UI thread blocking (60 fps event loop) during autograd smoke test runs via `QThread`.
- Zero orphaned files: sample files deleted post-smoke-test in 100% of runs.

**Constraints**:
- Strict architecture boundary: No Coordinator state in Client, zero mocks.
- Pure-Python constructor injection via `DIContainer` without third-party DI frameworks.
- Headless Docker image remains lightweight without X11/Qt libraries.

**Scale/Scope**:
- 3 new application modules in `src/Client/application/submit_training/`
- Domain enum & repository update in `domain/training_shard.py` and `infrastructure/persistence/training_shard_repository.py`
- Refactored `console_ui.py` and `main.py`
- 3 new GUI modules in `src/Client/presentation/gui/`
- Updated `requirements.txt`, `requirements-gui.txt`, `Dockerfile`, `README.md`
- 3 new sample verification scripts in `samples/submit_training_test/`

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Semi-Distributed Architecture & Separation of Concerns**: PASS. Client retains complete ownership of dataset partitions, local staging, and shard states. Coordinator only receives task registration DTOs without owning raw data or model files.
- **II. Language, Runtime, and Application Strictness**: PASS. Client remains in Python 3.11+. Coordinator remains in .NET. Communication occurs via documented REST endpoints.
- **III. Explicit Contracts & Boundaries**: PASS. `SubmitTrainingCommand`, `SubmitTrainingResult`, and `CreateTrainingTaskDto` establish strict schemas without hidden coupling.
- **IV. Engineering & Coding Standards (MVP Focus)**: PASS. Clean MVP structure, minimal classes, explicit constructor parameters, and clear separation between UI, application, and persistence layers.
- **V. Explicit Prohibitions & AI Guidelines**: PASS. Zero mocks, zero stubs, zero test frameworks (no pytest/unittest), zero crypto, zero RCE.
- **VI. Real Functional Implementations (Zero Mocks)**: PASS. All operations run against real PyTorch models, real SQLite databases, and real containerized Coordinator APIs.
- **VII. Verification, Compilability, and Executable Correctness**: PASS. Complete end-to-end active verification suite in `samples/submit_training_test/` validates all 5 execution paths directly against real containers.

---

## Project Structure

### Documentation (this feature)

```text
specs/015-client-submit-training/
├── spec.md              # Feature specification with recorded clarifications
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 technical research & design decisions
├── data-model.md        # Phase 1 DTO, container & handler models
├── quickstart.md        # Phase 1 verification & execution guide
├── contracts/           # Phase 1 interface contracts & schemas
│   ├── submit-training-command.schema.json
│   ├── submit-training-result.schema.json
│   ├── cli-contract.md
│   └── gui-contract.md
└── checklists/
    └── requirements.md  # Requirements quality checklist (16/16 passing)
```

### Source Code (repository root)

```text
src/Client/
├── Dockerfile                                      # Updated: /artifacts volume, WORKING_DIRECTORY env
├── requirements.txt                                # Updated: torch>=2.2.0, safetensors
├── requirements-gui.txt                            # New: PyQt6>=6.6.0 for desktop GUI
├── README.md                                       # Updated: CLI & GUI usage, docker run instructions
├── main.py                                         # Updated: submit-training CLI flags & gui launcher
│
├── application/
│   ├── __init__.py
│   └── submit_training/
│       ├── __init__.py                             # Re-exports Command, Handler, Result
│       ├── submit_training_command.py              # Command DTO & validator
│       ├── submit_training_command_handler.py      # Orchestrates staging, smoke test, partitioning, DB, Coordinator
│       └── submit_training_result.py               # Result DTO
│
├── dependency_injection/
│   ├── __init__.py
│   └── container.py                                # Updated: wires SubmitTrainingCommandHandler
│
├── domain/
│   └── training_shard.py                           # Updated: adds TrainingShardStatus.CREATED
│
├── infrastructure/
│   └── persistence/
│       └── training_shard_repository.py            # Updated: adds atomic update_status(shard_ids, status)
│
└── presentation/
    ├── console_ui.py                               # Updated: CLI parser & high-level progress logger
    └── gui/
        ├── __init__.py
        ├── main_window.py                          # PyQt6 MainWindow with Submit Training & Logs tabs
        └── worker.py                               # QThread background worker isolating UI from execution

samples/submit_training_test/
├── setup.py                                        # Docker network & container launcher + health check
├── clean.py                                        # Container, network, and test artifact teardown
└── e2e-test.py                                     # 5-path test matrix runner via docker exec
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| **Separate `requirements-gui.txt`** | PyQt6 desktop dependencies are large and require X11/Wayland libraries. | Adding PyQt6 to core `requirements.txt` would bloat headless Docker containers and cause import failures on headless servers. |
| **QThread Background Worker** | Smoke testing executes real PyTorch autograd computation. | Running synchronously on the main thread would freeze the PyQt6 GUI event loop and cause OS "Application Not Responding" hangs. |
| **Model Staging Directory** | `{working_directory}/{model_id}/` isolates artifacts. | Placing files directly in root would cause filename collisions across concurrent or repeated training submissions. |
