# Tasks: Trainer Command Notification Infrastructure

**Feature**: [006-trainer-command-notification](spec.md)
**Plan**: [plan.md](plan.md)
**Date**: 2026-08-29

## Phase 1: Setup (Shared Infrastructure & Protobuf)

**Purpose**: Project dependency configuration and protobuf contract tooling

- [X] T001 Configure gRPC package dependencies (`Grpc.AspNetCore`) in `src/Coordinator/TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj`
- [X] T002 Copy `coordinator_commands.proto` into `src/Coordinator/TrainSwarm.Coordinator.Api/Protos/coordinator_commands.proto` and configure `<Protobuf>` server compilation in `src/Coordinator/TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj`
- [X] T003 [P] Add `grpcio>=1.60.0` and `grpcio-tools>=1.60.0` to `src/Trainer/requirements.txt`
- [X] T004 [P] Generate Python gRPC stubs into `src/Trainer/infrastructure/coordinator_commands_pb2.py` and `src/Trainer/infrastructure/coordinator_commands_pb2_grpc.py`
- [X] T005 [P] Add `coordinator_grpc_url` configuration variable in `src/Trainer/config.py`

---

## Phase 2: Foundational (Core Abstractions & Domain Contracts)

**Purpose**: Core message contracts and connection management infrastructure that all user stories depend on

- [X] T006 [P] Implement `CommandType` enum in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandType.cs` and `src/Trainer/domain/commands.py`
- [X] T007 [P] Implement `CommandEnvelope` domain model in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandEnvelope.cs` and `src/Trainer/domain/commands.py`
- [X] T008 [P] Implement `CommandDispatchResult` record in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandDispatchResult.cs`
- [X] T009 [P] Define `ITrainerConnectionManager` interface and `TrainerConnection` model in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/ITrainerConnectionManager.cs`
- [X] T010 Implement `TrainerConnectionManager` with thread-safe `ConcurrentDictionary` and `Channel<CommandEnvelope>` in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/TrainerConnectionManager.cs`
- [X] T011 Register `TrainerConnectionManager` as singleton service in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`

---

## Phase 3: User Story 1 - Coordinator Dispatches StartTraining Command to Connected Trainer (Priority: P1) 🎯 MVP

**Goal**: Deliver end-to-end dispatch of the strongly typed `StartTraining` command from Coordinator `ICommandCenter` to Trainer `StartTrainingHandler` over a long-lived gRPC stream.

**Independent Test**: Start Coordinator and Trainer, dispatch a `StartTrainingCommand` via `ICommandCenter.SendAsync`, and verify the Trainer receives and parses the payload with `sessionId` and `trainingClientNodeId`.

- [X] T012 [P] [US1] Implement `StartTrainingCommand` payload DTO with camelCase JSON attributes in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/StartTrainingCommand.cs`
- [X] T013 [P] [US1] Implement `StartTrainingCommand` dataclass with `from_dict`/`to_dict` in `src/Trainer/domain/commands.py`
- [X] T014 [US1] Define `ICommandCenter` interface in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/ICommandCenter.cs`
- [X] T015 [US1] Implement `CommandCenter` with message ID generation, JSON serialization, and stream channel writing in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandCenter.cs`
- [X] T016 [US1] Register `ICommandCenter` / `CommandCenter` in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`
- [X] T017 [US1] Implement `CoordinatorCommandServiceImpl` server-streaming RPC in `src/Coordinator/TrainSwarm.Coordinator.Api/Grpc/CoordinatorCommandServiceImpl.cs` and map gRPC service in `src/Coordinator/TrainSwarm.Coordinator.Api/Program.cs`
- [X] T018 [US1] Implement `StartTrainingHandler` in `src/Trainer/application/command_handlers.py`
- [X] T019 [US1] Implement gRPC stream listener client in `src/Trainer/infrastructure/trainer_command_listener.py`
- [X] T020 [US1] Integrate `TrainerCommandListener` initialization into `src/Trainer/main.py`

**Checkpoint**: At this point, User Story 1 is fully functional and delivers a complete, independently testable MVP.

---

## Phase 4: User Story 2 - Extensible Trainer Command Dispatching and Typed Handling (Priority: P2)

**Goal**: Provide a generic, extensible `CommandDispatcher` on the Trainer that dynamically maps command types to typed handlers without modifying gRPC transport code.

**Independent Test**: Register a new command handler in `CommandDispatcher`, dispatch the corresponding envelope, and verify the handler is executed without touching gRPC transport files.

- [X] T021 [P] [US2] Define `ICommandHandler` abstract base class/protocol in `src/Trainer/application/command_handlers.py`
- [X] T022 [US2] Implement generic `CommandDispatcher` with handler registry, JSON deserialization, and type resolution in `src/Trainer/application/command_dispatcher.py`
- [X] T023 [US2] Connect `CommandDispatcher` to `TrainerCommandListener` and register `StartTrainingHandler` in `src/Trainer/main.py`

**Checkpoint**: At this point, new command types can be added and handlers replaced purely via dispatcher registration.

---

## Phase 5: User Story 3 - Connection Lifecycle, Identification, and Reconnection (Priority: P3)

**Goal**: Implement robust connection lifecycle management, detecting dropped streams, superseding stale connections, and automatically reconnecting on a 5-second fixed interval.

**Independent Test**: Stop and restart the Coordinator while Trainer is active; verify Trainer reconnects after 5 seconds and resumes receiving commands on the new stream.

- [X] T024 [US3] Implement stream cancellation token handling and stale connection cleanup in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/TrainerConnectionManager.cs` and `src/Coordinator/TrainSwarm.Coordinator.Api/Grpc/CoordinatorCommandServiceImpl.cs`
- [X] T025 [US3] Implement 5-second fixed-interval reconnection loop with error logging in `src/Trainer/infrastructure/trainer_command_listener.py`
- [X] T026 [US3] Implement graceful stop/cleanup on Trainer shutdown in `src/Trainer/main.py`

**Checkpoint**: Stream drops and reconnects are handled autonomously by transport layer with zero application logic impact.

---

## Phase 6: User Story 4 - Resilient Command Routing and Error Handling (Priority: P4)

**Goal**: Guard against offline target trainers, malformed JSON envelopes, and unknown command types with observable logging and non-crashing failure results.

**Independent Test**: Dispatch a command to a non-existent `trainerId` (verifying `CommandDispatchResult(IsSuccess = false)`) and send an unrecognized command type to Trainer (verifying safe warning log without crash).

- [X] T027 [P] [US4] Add target connection validation in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandCenter.cs` returning `CommandDispatchResult` with explicit error reasons
- [X] T028 [P] [US4] Add defensive error catching for corrupted JSON data and unknown enum types in `src/Trainer/application/command_dispatcher.py`
- [X] T029 [US4] Add structured logging for connection open/close, command dispatch, and handler execution across Coordinator in `src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/CommandCenter.cs` and Trainer in `src/Trainer/application/command_dispatcher.py`

**Checkpoint**: All edge cases and error states are handled defensively with clear diagnostic logs.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, build checks, and developer tooling

- [X] T030 [P] Add developer dispatch API endpoint in `src/Coordinator/TrainSwarm.Coordinator.Api/Controllers/CommandDispatchController.cs` for invoking `ICommandCenter.SendAsync` via HTTP POST
- [X] T031 Execute build and syntax verification for Coordinator (`dotnet build`) and Trainer (`python -m py_compile`)
- [X] T032 Execute quickstart validation scenarios per `specs/006-trainer-command-notification/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion.
- **User Story 2 (Phase 4)**: Depends on User Story 1 foundational handler structure.
- **User Story 3 (Phase 5)**: Depends on User Story 1 transport listener.
- **User Story 4 (Phase 6)**: Depends on User Story 1 & 2 dispatchers.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### User Story Completion Order

```text
[Phase 1: Setup] ──► [Phase 2: Foundational]
                             │
                             ▼
                 [Phase 3: US1 - StartTraining MVP]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
[Phase 4: US2 - Extensible Dispatcher]  [Phase 5: US3 - Reconnection Loop]
            └────────────────┬────────────────┘
                             ▼
                 [Phase 6: US4 - Resilient Error Handling]
                             │
                             ▼
                 [Phase 7: Polish & Verification]
```

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 can execute in parallel.
- **Phase 2**: T006, T007, T008, T009 can execute in parallel.
- **Phase 3 (US1)**: T012 and T013 can execute in parallel.
- **Phase 6 (US4)**: T027 and T028 can execute in parallel.
- **Phase 7**: T030 can execute in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch model definitions in parallel:
Task: "Implement StartTrainingCommand in src/Coordinator/TrainSwarm.Coordinator.Domain/Commands/StartTrainingCommand.cs"
Task: "Implement StartTrainingCommand in src/Trainer/domain/commands.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (User Story 1)
4. **STOP and VALIDATE**: Verify `StartTrainingCommand` reaches Trainer over gRPC stream.
5. Proceed with incremental delivery of US2 (Extensibility), US3 (Lifecycle/Reconnect), and US4 (Defensive Error Handling).
