# Implementation Plan: Fair Model-Level Round-Robin Coordinator Scheduler

**Branch**: `017-coordinator-scheduler` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-coordinator-scheduler/spec.md`

## Summary

Implement a fair, starvation-free, model-level round-robin scheduler within the Coordinator control-plane service, assigning unassigned `TrainingTask` records to available `Trainer` records. The feature adds a `DateTime SubmitTime` property to the `TrainingTask` domain entity (populated with `DateTime.Now` upon creation and persisted via EF Core migrations), introduces administrative table clearance methods (`ClearTrainersAsync` and `ClearTasksAsync`), adds an in-memory cursor rotation state service to preserve fairness across successive API calls, implements `SchedulerService.AssignTasksAsync()`, exposes these capabilities via REST controllers (`SchedulingController`, `TrainerController`, `TrainingTaskController`), and delivers an automated zero-mock 12-case verification suite in `samples/scheduling_test/`.

## Technical Context

**Language/Version**: .NET 10 (C# 14), Python 3.10+ (for verification harness)

**Primary Dependencies**: ASP.NET Core, Microsoft.EntityFrameworkCore.Sqlite 10.0.10, ErrorOr 2.0.1

**Storage**: SQLite via Entity Framework Core (`CoordinatorDbContext`), migrations auto-applied on application boot

**Testing**: Python live API integration test suite (`samples/scheduling_test/test.py` via `requests`), zero mocks

**Target Platform**: Windows / Linux / Docker container runtime

**Project Type**: Control Plane Web API service and integration test sample

**Performance Goals**: Task scheduling evaluation completes in < 50ms for pools of up to 1,000 tasks; 100% utilization of idle trainers

**Constraints**: Single coordinator instance in-memory cursor; atomic single-transaction task-to-trainer persistence; no external Redis or complex messaging dependencies

**Scale/Scope**: Coordinator Domain, Infrastructure, Application, and Api projects + `samples/scheduling_test/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control-plane separation | **PASS** | Coordinator manages tasks and trainers; does not touch model weights, checkpoints, or data plane operations. |
| **II. Language & Application Strictness** | .NET Web API | **PASS** | Implemented strictly in C# .NET 10 Web API; REST endpoints exposed. |
| **III. Explicit Contracts & Boundaries** | Versioned contracts & DTOs | **PASS** | DTOs defined for `AssignedTaskDto`, clean separation between Domain, Application, and Api. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, clear | **PASS** | In-memory cursor rotation without speculative clustering frameworks; single transaction commit. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero crypto | **PASS** | No test mocks used; tests run against live Coordinator Web API and real SQLite database. |
| **VI. Real Functional Implementations** | Real SQLite persistence | **PASS** | Real EF Core database mutations and real HTTP endpoints. |
| **VII. Verification & Compilability** | Build & executable correctness | **PASS** | Mandatory `dotnet build` and running `samples/scheduling_test/test.py` against active Coordinator. |

## Project Structure

### Documentation (this feature)

```text
specs/017-coordinator-scheduler/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architecture research and decisions
├── data-model.md        # Phase 1 data model and entity definitions
├── quickstart.md        # Phase 1 verification and run guide
├── contracts/           # Phase 1 OpenAPI contracts
│   └── coordinator-scheduler-api.yaml
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/Coordinator/
├── TrainSwarm.Coordinator.Domain/
│   └── Entities/
│       ├── TrainingTask.cs              # Add DateTime SubmitTime property
│       ├── Trainer.cs                   # Existing Trainer entity
│       └── TrainerStatus.cs             # Existing TrainerStatus enum
├── TrainSwarm.Coordinator.Infrastructure/
│   └── Persistence/
│       ├── Configurations/
│       │   └── TrainingTaskConfiguration.cs # Map SubmitTime property
│       └── Migrations/
│           └── <Timestamp>_AddSubmitTimeToTrainingTask.cs # EF Core migration
├── TrainSwarm.Coordinator.Application/
│   └── Services/
│       ├── TrainingTaskService.cs       # Set SubmitTime = DateTime.Now, ClearTasksAsync
│       ├── TrainerService.cs            # ClearTrainersAsync
│       ├── ISchedulerCursorState.cs     # In-memory cursor interface
│       ├── SchedulerCursorState.cs      # Thread-safe in-memory cursor implementation
│       ├── SchedulerService.cs          # AssignTasksAsync fair round-robin algorithm
│       └── AssignedTaskDto.cs           # DTO returned by AssignTasks
├── TrainSwarm.Coordinator.Api/
│   ├── Controllers/
│   │   ├── SchedulingController.cs      # POST /api/scheduler/assign
│   │   ├── TrainerController.cs         # POST /api/trainers/clear
│   │   └── TrainingTaskController.cs    # POST /api/training-tasks/clear
│   └── Program.cs                       # DI registration for SchedulerService, ISchedulerCursorState

samples/scheduling_test/
├── setup.py                             # Coordinator startup and healthcheck verification
├── test.py                              # 12-case end-to-end verification suite with formatted output
└── README.md                            # Documentation of test cases and run instructions
```

**Structure Decision**: Monorepo standard structure: Coordinator components reside within their respective clean architecture layers (`Domain`, `Infrastructure`, `Application`, `Api`), while end-to-end sample verification resides in `samples/scheduling_test/`.

## Complexity Tracking

*No constitutional violations identified. Design adheres strictly to MVP and clean architecture standards.*
