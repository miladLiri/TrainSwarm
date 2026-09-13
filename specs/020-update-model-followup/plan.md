# Implementation Plan: Model Update Follow-up & Distributed Aggregation Lifecycle

**Branch**: `020-update-model-followup` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-update-model-followup/spec.md`

## Summary

Expand the functionality of the distributed training lifecycle across Coordinator and Client services:
1. **Coordinator Control Plane**: Implement `DetachTrainerAsync` in `TrainerService` with status transition logic (`IDLE` if `IsTrainingComplete == true`, `UNCLEAR` if `false`, safe no-op if not `BUSY`) and expose `POST /api/trainers/detach` on `TrainerController`. Expose read-only inspection endpoints (`GET /api/trainers` and `GET /api/training-tasks`).
2. **Client Infrastructure & Application**: Implement `detach_trainer` in `CoordinatorAdapter`. In `UpdateModelCommandHandler`, detach the trainer upon recording shard results, check under a `threading.Lock` if all shards for the active round are completed, and trigger `AggregationOrchestrator` to synthesize and persist a new model version (`version + 1`). Add `submitted: bool` guard to `ClientState` to reject overlapping submissions and reset upon aggregation completion.
3. **Client Presentation & Queries**: Implement `GetTrainingShardsQuery` and `GetTrainedModelsQuery` in `Client/application/queries/`. Add "Training Shards" and "Trained Versions" tabs with artifact export in GUI, and a `watch-shards` subcommand in Console UI.
4. **End-to-End Test & Cleanup**: Enhance `samples/full_distributed_training_test/` to verify trainer reversion to `IDLE`, validate new version artifact creation, execute loss comparison asserting `aggregated_loss < base_loss`, and add a dedicated `clean.py` process teardown script.

---

## Technical Context

**Language/Version**: Python 3.10+ (Client & Trainer), .NET 10 (C# 14, Coordinator)

**Primary Dependencies**:
- Client: PyTorch (`torch>=2.2.0`), `requests>=2.28.0`, `PyQt6>=6.4.0` (GUI), `sqlite3`, `safetensors`.
- Coordinator: ASP.NET Core (.NET 10), Microsoft.EntityFrameworkCore.Sqlite 10.0.10, ErrorOr 2.0.1.
- Distributed Engine: PyTorch (`torch>=2.2.0`), `safetensors>=0.4.0`.

**Storage**: SQLite:
- Client: `training.db` (tables: `training_shards`, `models` with composite key `(model_id, model_version)`).
- Coordinator: `coordinator.db` via EF Core (tables: `Trainers`, `TrainingTasks`).

**Testing / Verification**: Automated live command-line test harness in `samples/full_distributed_training_test/` using native host background processes (zero mocks per Constitution Principle V & VI).

**Target Platform**: Windows / Linux / macOS native host execution.

**Project Type**: Distributed System: Data-Plane Client (CLI/GUI), Control-Plane Coordinator (Web API + gRPC), and Test Verification Sample.

**Performance Goals**:
- Trainer detachment REST call latency < 100ms.
- All-shards completion check under lock executes in < 10ms.
- Model aggregation triggered within 5 seconds of final shard update arrival.

**Constraints**:
- Zero mocks, zero simulated services; validation via live execution.
- Strict architectural boundary: Coordinator never accesses model weights or checkpoints.
- Thread safety in Client command handler using `threading.Lock`.

**Scale/Scope**: 4 primary areas: Coordinator API & Services, Client Application & Adapters, Client Presentation (GUI/CLI) & Queries, and `samples/full_distributed_training_test/`.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control/data plane separation | **PASS** | Coordinator manages trainer node availability state only; Client and Aggregator own checkpoints and weights. |
| **II. Language Strictness** | .NET for Coordinator, Python for Client/Trainer | **PASS** | Coordinator implemented in C# (.NET 10 Web API); Client implemented in Python 3.10+. |
| **III. Explicit Contracts** | Versioned contracts & DTOs | **PASS** | Detach DTOs defined in JSON schema; Client query models formalized in application layer. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, clear | **PASS** | Inline `threading.Lock` for aggregation evaluation; composite PK for model versioning; no external message brokers. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero crypto | **PASS** | Strictly zero mocks/stubs; live end-to-end multi-node execution for validation. |
| **VI. Real Functional Implementations** | Real SQLite, real HTTP/P2P, real PyTorch | **PASS** | Real SQLite table schemas, real REST calls, real PyTorch forward passes and loss computations. |
| **VII. Verification & Compilability** | Build & executable correctness | **PASS** | Mandatory validation via `dotnet build`, `python -m compileall`, and execution of `clean.py` + `run_local.py`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/020-update-model-followup/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architecture research and decisions
├── data-model.md        # Phase 1 data model and entity definitions
├── quickstart.md        # Phase 1 verification and run guide
├── contracts/           # Phase 1 interface and schema contracts
│   ├── coordinator-detach-api.json
│   ├── coordinator-inspection-api.json
│   ├── client-application-queries.md
│   └── client-gui-contracts.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Layout

```text
src/Coordinator/
├── TrainSwarm.Coordinator.Application/
│   ├── Services/
│   │   ├── DetachTrainerRequest.cs           # Detach request DTO
│   │   ├── TrainerService.cs                 # DetachTrainerAsync, GetTrainersAsync
│   │   └── TrainingTaskService.cs            # GetTrainingTasksAsync
├── TrainSwarm.Coordinator.Api/
│   └── Controllers/
│       ├── TrainerController.cs              # POST /api/trainers/detach, GET /api/trainers
│       └── TrainingTaskController.cs         # GET /api/training-tasks

src/Client/
├── infrastructure/
│   ├── adapters/
│   │   └── coordinator_adapter.py            # Add detach_trainer method
│   └── persistence/
│       ├── database.py                       # Composite PK (model_id, model_version)
│       ├── model_repository.py               # Composite query & save support
│       └── training_shard_repository.py      # Query helpers for round shards
├── application/
│   ├── state.py                              # submitted: bool state variable
│   ├── submit_training/
│   │   └── submit_training_command_handler.py# Check/set submitted flag
│   ├── commands/update_model/
│   │   └── update_model_handler.py           # Detach trainer, lock, aggregation, reset submitted
│   └── queries/
│       ├── get_training_shards/              # GetTrainingShardsQuery & Handler
│       └── get_trained_models/               # GetTrainedModelsQuery & Handler
└── presentation/
    ├── console_ui.py                         # Add watch-shards subcommand
    └── gui/
        └── main_window.py                    # Add Training Shards & Trained Versions tabs

samples/full_distributed_training_test/
├── clean.py                                  # Standalone teardown and cleanup utility
├── verify.py                                 # Verify trainer idle, v2 artifact, loss comparison
└── run_local.py                              # Multi-node runner incorporating full verification
```

---

## Complexity Tracking

> **No Constitution violations detected. All modules maintain strict architectural separation.**
