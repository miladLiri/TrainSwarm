# Implementation Tasks: Distributed File Transfer and P2P Training Execution

**Feature**: `019-distributed-file-transfer` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup (Shared Infrastructure & Protobuf Contracts)

**Purpose**: Update communication contracts, generate language stubs, and configure project dependencies.

- [X] T001 Update gRPC protobuf contract in `src/p2p-node/p2p.proto` (and sync with `specs/019-distributed-file-transfer/contracts/p2p.proto`) adding `GetTrainingTask`, `GetModel`, `GetShard`, `SendUpdate`, and `ServeClientRequests`
- [X] T002 Generate Go protobuf and gRPC stubs in `src/p2p-node/internal/api/p2pv1/p2p.pb.go` and `src/p2p-node/internal/api/p2pv1/p2p_grpc.pb.go`
- [X] T003 [P] Generate Python gRPC stubs `p2p_pb2.py` and `p2p_pb2_grpc.py` in `src/Trainer/infrastructure/adapters/p2p_pb2.py` and `src/Client/infrastructure/adapters/p2p_pb2.py`
- [X] T004 [P] Update Python dependencies in `src/Client/requirements.txt` and `src/Trainer/requirements.txt` ensuring `grpcio`, `protobuf`, and `safetensors` are pinned

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema updates, libp2p wire protocols, and sidecar streaming infrastructure.

**⚠️ CRITICAL**: Must complete before user story execution can begin.

- [X] T005 Update SQLite database schema in `src/Client/infrastructure/persistence/database.py` adding `trainer_node_id TEXT NULL` column to `training_shards` table DDL
- [X] T006 Update `TrainingShard` domain model in `src/Client/domain/training_shard.py` adding `trainer_node_id: Optional[str] = None` field and validation
- [X] T007 Update `TrainingShardRepository` in `src/Client/infrastructure/persistence/training_shard_repository.py` to persist, read, and map `trainer_node_id`, and support assignment status updates
- [X] T008 Implement libp2p wire transfer protocols (`/trainswarm/task/1.0.0`, `/trainswarm/model/1.0.0`, `/trainswarm/shard/1.0.0`, `/trainswarm/update/1.0.0`) with `O_TRUNC` overwrite semantics in `src/p2p-node/internal/transfer/protocol.go`
- [X] T009 Implement gRPC server dispatching and bidirectional client stream `ServeClientRequests` in `src/p2p-node/internal/api/server.go`
- [X] T010 Update `p2p-node` entry point in `src/p2p-node/cmd/p2pd/main.go` to parse `WORKING_DIR` environment variable and pass to transfer manager and server

**Checkpoint**: Core data contracts and sidecar protocols ready - user story implementations can begin.

---

## Phase 3: User Story 1 - P2P Node Identity Retrieval and Fail-Fast Startup Guard (Priority: P1) 🎯 MVP

**Goal**: Both Client and Trainer verify local `p2p-node` sidecar availability on boot, retrieve its libp2p peer ID via `get_p2p_node_id()`, update application state, and abort immediately with code 1 if unreachable.

**Independent Test**: Run Trainer or Client with `p2p-node` down; assert immediate process termination with code 1 and diagnostic error log. Run with healthy `p2p-node`; assert peer ID is recorded in state and printed cleanly.

- [X] T011 [P] [US1] Implement `get_p2p_node_id()` method in `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py`
- [X] T012 [P] [US1] Implement `get_p2p_node_id()` method in `src/Client/infrastructure/adapters/client_p2p_node_adapter.py`
- [X] T013 [P] [US1] Implement `SetNodeIdCommand` and `SetNodeIdCommandHandler` in `src/Trainer/application/trainer_commands/set_node_id/handler.py`
- [X] T014 [P] [US1] Implement `SetNodeIdCommand` and `SetNodeIdCommandHandler` in `src/Client/application/commands/set_node_id/handler.py`
- [X] T015 [US1] Register `SetNodeIdCommandHandler` in `src/Trainer/dependency_injection/container.py` and `src/Client/dependency_injection/container.py`
- [X] T016 [US1] Update `src/Trainer/main.py` to execute `SetNodeIdCommand` as the very first boot action, catching connection errors and exiting with code 1
- [X] T017 [US1] Update `src/Client/main.py` to execute `SetNodeIdCommand` as the very first boot action, catching connection errors and exiting with code 1

**Checkpoint**: User Story 1 functional - nodes verify P2P sidecar identity on startup and fail-fast safely.

---

## Phase 4: User Story 2 - P2P Training Task Retrieval and Shard State Transition (Priority: P1)

**Goal**: Trainer queries Client for `TrainingTask` over P2P; Client looks up model and shard, marks shard status as `training` and assigns `trainer_node_id`, and returns compiled `TrainingTask`.

**Independent Test**: Dispatch a `get_training_task` request from Trainer to Client over P2P; assert Client SQLite updates shard status to `training` with `trainer_node_id` and Trainer receives a valid `TrainingTask` instance.

- [X] T018 [P] [US2] Implement `GetTrainingTaskCommand` and `GetTrainingTaskCommandHandler` in `src/Client/application/commands/get_training_task/handler.py` (loading config JSON, updating shard in SQLite, returning `TrainingTask`)
- [X] T019 [US2] Wire `ACTION_GET_TRAINING_TASK` inbound dispatch in `src/Client/infrastructure/adapters/client_p2p_node_adapter.py` to invoke `GetTrainingTaskCommandHandler`
- [X] T020 [US2] Implement `get_training_task()` in `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py` calling `p2p-node` gRPC `GetTrainingTask`
- [X] T021 [US2] Register `GetTrainingTaskCommandHandler` in `src/Client/dependency_injection/container.py`

**Checkpoint**: User Story 2 functional - trainers can pull task specifications directly from clients across P2P.

---

## Phase 5: User Story 3 - P2P Model Checkpoint Retrieval with Local Cache Bypass (Priority: P1)

**Goal**: Trainer checks local working directory for base model checkpoint; skips transfer if file exists, or streams checkpoint from Client over P2P.

**Independent Test**: Call `get_model` when the checkpoint file is present; verify no network transfer occurs. Call `get_model` when file is missing; verify model is streamed over P2P and saved to local working directory.

- [X] T022 [P] [US3] Implement `TransferModelCommand` and `TransferModelCommandHandler` in `src/Client/application/commands/transfer_model/handler.py` (retrieving `model_artifact_path` from `ModelRepository`)
- [X] T023 [US3] Wire `ACTION_TRANSFER_MODEL` inbound dispatch in `src/Client/infrastructure/adapters/client_p2p_node_adapter.py` to invoke `TransferModelCommandHandler`
- [X] T024 [US3] Implement `get_model()` in `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py` calling `p2p-node` gRPC `GetModel` and saving into `WORKING_DIR`
- [X] T025 [US3] Register `TransferModelCommandHandler` in `src/Client/dependency_injection/container.py`

**Checkpoint**: User Story 3 functional - base models streamed over P2P with local cache bypass.

---

## Phase 6: User Story 4 - P2P Dataset Shard Retrieval and Local Ingestion (Priority: P1)

**Goal**: Trainer streams assigned dataset shard from Client over P2P into local working directory.

**Independent Test**: Issue a `get_shard` request from Trainer to Client; verify shard is streamed over P2P, written to Trainer working directory, and path returned.

- [X] T026 [P] [US4] Implement `TransferShardCommand` and `TransferShardCommandHandler` in `src/Client/application/commands/transfer_shard/handler.py` (retrieving `artifact_path` from `TrainingShardRepository`)
- [X] T027 [US4] Wire `ACTION_TRANSFER_SHARD` inbound dispatch in `src/Client/infrastructure/adapters/client_p2p_node_adapter.py` to invoke `TransferShardCommandHandler`
- [X] T028 [US4] Implement `get_shard()` in `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py` calling `p2p-node` gRPC `GetShard` and saving into `WORKING_DIR`
- [X] T029 [US4] Register `TransferShardCommandHandler` in `src/Client/dependency_injection/container.py`

**Checkpoint**: User Story 4 functional - dataset shards streamed over P2P directly to assigned trainers.

---

## Phase 7: User Story 5 - Local Model Training, Update Transmission, and Ephemeral Cleanup (Priority: P1)

**Goal**: Trainer trains via `TrainingOrchestrator`, sends update delta and `TrainingResult` to Client via P2P; Client marks shard `completed` and saves update; Trainer deletes local shard and update files while preserving model.

**Independent Test**: Execute full training cycle; assert delta safetensors and `TrainingResult` are received by Client, SQLite shard transitions to `completed`, and Trainer removes local shard and update files while keeping base model.

- [X] T030 [P] [US5] Implement `UpdateModelCommand` and `UpdateModelCommandHandler` in `src/Client/application/commands/update_model/handler.py` (updating `update_artifact_path`, metrics, and setting status to `COMPLETED` in SQLite)
- [X] T031 [US5] Wire `ACTION_UPDATE_MODEL` inbound dispatch in `src/Client/infrastructure/adapters/client_p2p_node_adapter.py` to invoke `UpdateModelCommandHandler`
- [X] T032 [US5] Implement `send_update()` in `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py` calling `p2p-node` gRPC `SendUpdate`
- [X] T033 [US5] Register `UpdateModelCommandHandler` in `src/Client/dependency_injection/container.py`
- [X] T034 [US5] Implement the complete 6-step execution lifecycle in `src/Trainer/application/coordinator_commands/start_training/handler.py`:
  (1) `get_training_task` $\rightarrow$ (2) cache check / `get_model` $\rightarrow$ (3) `get_shard` $\rightarrow$ (4) train via `TrainingOrchestrator` $\rightarrow$ (5) `send_update` $\rightarrow$ (6) purge local ephemeral shard & update files while retaining model; retain files on failure

**Checkpoint**: User Story 5 functional - distributed training execution and update submission loop completed end-to-end.

---

## Phase 8: User Story 6 - Real-Time Trainer State Presentation and Progress Telemetry (Priority: P2)

**Goal**: Maintain `is_training` flag in `TrainerState`; show "waiting for task" when idle and progress when training in `console_ui.py` and PyQt6 `gui/`.

**Independent Test**: Launch Trainer in CLI and GUI modes; verify wait screen / "waiting for task" displays when idle, and transitions to step-by-step progress during active training.

- [X] T035 [US6] Add `is_training: bool = False` property and state update methods to `src/Trainer/application/state.py`
- [X] T036 [US6] Integrate `is_training` toggling in `src/Trainer/application/coordinator_commands/start_training/handler.py` (`is_training=True` during steps 1-5, `False` on completion/finally)
- [X] T037 [P] [US6] Update `src/Trainer/presentation/console_ui.py` to render waiting status when idle, and step-by-step progress and training metrics when `is_training` is True
- [X] T038 [P] [US6] Update PyQt6 GUI in `src/Trainer/presentation/gui/main_window.py` to render a wait/idle screen when `is_training` is False, and step progress with loading animations when `is_training` is True

**Checkpoint**: User Story 6 functional - real-time training telemetry rendered in console and GUI.

---

## Phase 9: User Story 7 - Standardized Sidecar Containerization & Isolation (Priority: P2)

**Goal**: Update Dockerfiles and create standalone `docker-compose.yml` for Client and Trainer bundling private `p2p-node` sidecars.

**Independent Test**: Launch Client and Trainer via Docker Compose; assert `p2p-node` starts first, application connects cleanly, and sidecar gRPC port is not published to host network.

- [X] T039 [P] [US7] Update `src/Client/Dockerfile` and create `src/Client/docker-compose.yml` (booting `p2p-node` first, unexposed gRPC, mounted volumes for `WORKING_DIR` and `training.db`)
- [X] T040 [P] [US7] Update `src/Trainer/Dockerfile` and create `src/Trainer/docker-compose.yml` (booting `p2p-node` first, unexposed gRPC, mounted volumes for `WORKING_DIR`)

**Checkpoint**: User Story 7 functional - isolated containerized deployments operational.

---

## Phase 10: User Story 8 - Full Distributed Training Multi-Node End-to-End Test Suite (Priority: P3)

**Goal**: Build comprehensive automated multi-NAT verification suite in `samples/full_distributed_training_test/`.

**Independent Test**: Run `python setup.py`, `python test.py`, and `python verify.py` in `samples/full_distributed_training_test/`; verify 0 errors, 2 trainers assigned, P2P transfers verified, updates saved in Client SQLite, and ephemeral files cleaned up.

- [X] T041 [US8] Create `samples/full_distributed_training_test/data_generator.py` generating canonical `.pt2` model, 50-sample `.pt` dataset, and `training_config.json`
- [X] T042 [US8] Create `samples/full_distributed_training_test/docker-compose.yml` setting up 1 public network (`bootstrap-relay`, `coordinator`) and 3 simulated NAT networks (`c` with Client, `t1` with Trainer 1, `t2` with Trainer 2)
- [X] T043 [US8] Create `samples/full_distributed_training_test/setup.py` booting the Docker Compose stack, streaming logs, and verifying service health
- [X] T044 [US8] Create `samples/full_distributed_training_test/test.py` executing training task submission inside the Client container
- [X] T045 [US8] Create `samples/full_distributed_training_test/verify.py` asserting coordinator task assignments, P2P transfers, training completion, update storage, database transitions to `completed`, and ephemeral file cleanup

**Checkpoint**: User Story 8 functional - multi-node NAT distributed training verified end-to-end.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates across services, compilability verification, and quality gates.

- [X] T046 [P] Update documentation in `src/p2p-node/README.md` with new gRPC RPCs, wire protocols, and run instructions
- [X] T047 [P] Update documentation in `src/Trainer/README.md` with P2P training flows, `is_training` UI, and Docker Compose instructions
- [X] T048 [P] Update documentation in `src/Client/README.md` with P2P request dispatch, shard lifecycle, and Docker Compose instructions
- [X] T049 [P] Update documentation in `src/Coordinator/README.md` with scheduler integration notes and sample verification instructions
- [X] T050 Verify build integrity and compilability across all services via `go build ./...` in `src/p2p-node` and `python -m py_compile` across `src/Client` and `src/Trainer`

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1: Setup (T001-T004)
       │
       ▼
Phase 2: Foundational (T005-T010)
       │
       ▼
Phase 3: User Story 1 - Startup Guard (T011-T017) 🎯 MVP
       │
       ├────────────────────────────────────────┬────────────────────────────────────────┐
       ▼                                        ▼                                        ▼
Phase 4: US2 - Task Retrieval (T018-T021)   Phase 8: US6 - Presentation (T035-T038)   Phase 9: US7 - Containerization (T039-T040)
       │
       ▼
Phase 5: US3 - Model Transfer (T022-T025)
       │
       ▼
Phase 6: US4 - Shard Transfer (T026-T029)
       │
       ▼
Phase 7: US5 - Training & Updates (T030-T034)
       │
       ▼
Phase 10: US8 - Multi-Node E2E Test Suite (T041-T045)
       │
       ▼
Phase 11: Polish & Documentation (T046-T050)
```

### User Story Dependencies
- **User Story 1 (P1)**: Depends on Foundational (Phase 2). Blocks all subsequent user stories.
- **User Story 2 (P1)**: Depends on US1 (requires verified node IDs).
- **User Story 3 (P1)**: Depends on US2 (requires model ID from task).
- **User Story 4 (P1)**: Depends on US2 (requires shard ID from task).
- **User Story 5 (P1)**: Depends on US2, US3, US4 (requires task, model, and shard staged to train and send update).
- **User Story 6 (P2)**: Depends on US1 (independent of data transfer, can proceed in parallel once state is established).
- **User Story 7 (P2)**: Depends on US1 (can proceed in parallel for Docker packaging).
- **User Story 8 (P3)**: Depends on US1 through US7 (validates entire cluster integration end-to-end).

---

## Parallel Execution Opportunities

### Phase 1: Setup
```bash
# Generate Python stubs and update requirements in parallel:
Task T003: "Generate Python gRPC stubs in src/Trainer/ and src/Client/"
Task T004: "Update Python dependencies in src/Client/requirements.txt and src/Trainer/requirements.txt"
```

### Phase 3: User Story 1
```bash
# Implement adapter methods and commands in parallel across services:
Task T011: "Implement get_p2p_node_id() in src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py"
Task T012: "Implement get_p2p_node_id() in src/Client/infrastructure/adapters/client_p2p_node_adapter.py"
Task T013: "Implement SetNodeIdCommand in src/Trainer/application/trainer_commands/set_node_id/handler.py"
Task T014: "Implement SetNodeIdCommand in src/Client/application/commands/set_node_id/handler.py"
```

### Phase 8, 9 & 11: Presentation, Containers & Polish
```bash
# UI updates in parallel:
Task T037: "Update src/Trainer/presentation/console_ui.py"
Task T038: "Update PyQt6 GUI in src/Trainer/presentation/gui/main_window.py"

# Container configurations in parallel:
Task T039: "Update src/Client/Dockerfile and create src/Client/docker-compose.yml"
Task T040: "Update src/Trainer/Dockerfile and create src/Trainer/docker-compose.yml"

# Documentation in parallel:
Task T046: "Update src/p2p-node/README.md"
Task T047: "Update src/Trainer/README.md"
Task T048: "Update src/Client/README.md"
Task T049: "Update src/Coordinator/README.md"
```

---

## Implementation Strategy

### MVP Scope (Phases 1, 2, and 3: User Story 1)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1: `get_p2p_node_id()` and fail-fast startup guard).
3. **Validate**: Test launching Client and Trainer with `p2p-node` online and offline. Verify immediate failure when offline and state persistence when online.

### Incremental Feature Delivery
1. **P2P Data-Plane Transfers (US2, US3, US4)**: Incrementally build task query, cached model streaming, and shard streaming over libp2p.
2. **Execution & Lifecycle Closure (US5)**: Implement `TrainingOrchestrator` execution, update streaming, and ephemeral file deletion.
3. **Telemetry & Presentation (US6)**: Hook `is_training` into CLI and GUI.
4. **Containerization (US7)**: Package sidecar stacks into standalone Docker Compose profiles.
5. **System Validation (US8)**: Execute full multi-NAT verification suite in `samples/full_distributed_training_test/`.
