# Implementation Plan: Distributed File Transfer and P2P Training Execution

**Branch**: `019-distributed-file-transfer` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-distributed-file-transfer/spec.md`

## Summary

Implement peer-to-peer data-plane communication, artifact transfer, trainer execution lifecycle, and multi-node NAT verification across the TrainSwarm distributed training platform:
1. **P2P Node Sidecar & Adapters**: Update Go `p2p-node` and implement `TrainerP2PNodeAdapter` and `ClientP2PNodeAdapter` over localhost gRPC to support the 4 core P2P workflows: (a) `get_training_task`, (b) `get_model` (with local cache check), (c) `get_shard`, and (d) `send_update` with overwrite semantics (`O_TRUNC`) in designated working directories.
2. **Node ID Discovery & Startup Guard**: Provide `get_p2p_node_id()` on both adapters; implement `SetNodeIdCommand` in Client and Trainer executed as the very first startup step in `main.py`, halting immediately on failure.
3. **Trainer Start Training Lifecycle**: Complete `StartTrainingHandler` to orchestrate task fetching, model cache check/download, shard download, PyTorch fine-tuning via `TrainingOrchestrator`, update delivery, and local cleanup of ephemeral shard and update files.
4. **Trainer Real-Time Presentation**: Add `is_training` boolean state flag; update `console_ui.py` to display waiting status when idle and real-time step progress when active; update GUI with wait screen and loading animations.
5. **Sidecar Containerization**: Update Dockerfiles and create Docker Compose configurations for Client and Trainer bundling isolated `p2p-node` sidecars on private networks.
6. **Documentation**: Update READMEs across `p2p-node`, `Trainer`, `Client`, and `Coordinator`.
7. **Multi-Node Distributed Verification Suite**: Build `samples/full_distributed_training_test/` (`data_generator.py`, `docker-compose.yml`, `setup.py`, `test.py`, `verify.py`) simulating 3 NAT networks (`c`, `t1`, `t2`) and verifying end-to-end task submission, P2P transfer, training, and database convergence.

---

## Technical Context

**Language/Version**:
- Go 1.22+ (`p2p-node` sidecar executable, `bootstrap-relay`)
- Python 3.10+ (`Client` application, `Trainer` application, test sample scripts)
- .NET 10 / C# 14 (`Coordinator` control-plane API)

**Primary Dependencies**:
- Go: `github.com/libp2p/go-libp2p` v0.35+, `google.golang.org/grpc`, `google.golang.org/protobuf`
- Python: `grpcio>=1.62.0`, `protobuf>=4.25.0`, `torch>=2.2.0`, `safetensors>=0.4.2`, `PyQt6` (GUI)
- .NET: Microsoft.EntityFrameworkCore.Sqlite 10.0.10, ErrorOr 2.0.1, Grpc.AspNetCore 2.66.0

**Storage**:
- Client SQLite Database: `training.db` (tables: `training_shards`, `models`)
- Local Filesystems: Working directories (`WORKING_DIR`) for staged models (`.pt2`), shards (`.pt`), configuration JSONs, and trained delta safetensors

**Testing / Verification**:
- Zero mocks, zero unit tests per Constitution Principle V & VI.
- Automated end-to-end multi-container NAT validation test suite in `samples/full_distributed_training_test/`.

**Target Platform**:
- Linux Docker containers (Debian/Alpine-based) and native Windows / Linux host environments.

**Project Type**:
- Distributed System: Control Plane (Bootstrap Relay, Coordinator), Data-Plane Edge Sidecars (`p2p-node`), and Data-Plane Applications (Client, Trainer).

**Performance Goals**:
- P2P file transfers stream in 32KB/64KB chunks with zero in-memory buffer saturation.
- Model download skipped 100% of the time when valid checkpoint exists in local working directory.
- Startup connection guard validates `p2p-node` responsiveness or fails fast within 5 seconds.

**Constraints**:
- Communication between Python applications and Go `p2p-node` MUST occur exclusively over a localhost-bound gRPC API (Constitution Principle III).
- Control plane (`Coordinator`) MUST NOT touch checkpoints, weights, or datasets (Constitution Principle I).
- Ephemeral shards and updates must be purged from Trainer upon successful delivery; base model retained.

**Scale/Scope**:
- 3 core data-plane components (`p2p-node`, `Client`, `Trainer`), documentation updates across 4 services, and 1 complete test sample suite.

---

## Constitution Check

*GATE: Evaluated against TrainSwarm Constitution v4.2.0. Must pass before Phase 0 research and re-checked post-design.*

| Principle | Check | Status | Evaluation Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control vs data plane separation | **PASS** | `Coordinator` only routes assignments; direct data transfer (models, shards, updates) occurs strictly between `Trainer` and `Client` data planes via `p2p-node`. |
| **II. Language & Application Strictness** | Strict languages and execution forms | **PASS** | `p2p-node` is Go standalone executable; `Client` and `Trainer` are Python console/GUI apps; `Coordinator` is .NET 10 Web API. |
| **III. Explicit Contracts & Boundaries** | Versioned contracts & DTOs | **PASS** | Communication between Python and Go `p2p-node` uses versioned gRPC contract (`p2p.proto`); libp2p wire protocols use explicit version tags (`/trainswarm/.../1.0.0`). |
| **IV. Engineering Standards (MVP)** | Clarity over premature abstraction | **PASS** | Explicit command handlers, simple chunked file streaming, and clear sequential training lifecycle steps. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero unit tests, zero crypto | **PASS** | No mocks or stubbed networks; verified via live containerized execution in `samples/full_distributed_training_test/`. |
| **VI. Real Functional Implementations** | Operational end-to-end integrity | **PASS** | Real libp2p stream I/O, real file disk streaming with `O_TRUNC`, real PyTorch model training via `TrainingOrchestrator`, and real SQLite updates. |
| **VII. Verification & Compilability** | Build integrity and runnability gates | **PASS** | Mandatory validation using `go build ./...`, `python -m py_compile`, and execution of `setup.py` + `test.py` + `verify.py`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/019-distributed-file-transfer/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architectural research and decisions
├── data-model.md        # Phase 1 data entities and lifecycle state models
├── quickstart.md        # Phase 1 runnable validation guide
├── contracts/           # Phase 1 interface and schema contracts
│   ├── p2p.proto
│   ├── python_adapters.md
│   └── command_contracts.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Layout

```text
src/p2p-node/
├── internal/
│   ├── api/
│   │   ├── p2pv1/
│   │   │   ├── p2p.pb.go                       # Re-generated protobuf definitions
│   │   │   └── p2p_grpc.pb.go                  # Re-generated gRPC stubs
│   │   └── server.go                           # Implement GetTrainingTask, GetModel, GetShard, SendUpdate, ServeClientRequests
│   └── transfer/
│       └── protocol.go                         # Add /trainswarm/{task,model,shard,update}/1.0.0 libp2p stream handlers
└── cmd/p2pd/
    └── main.go                                 # Pass WORKING_DIR env var to server and transfer manager

src/Client/
├── domain/
│   └── training_shard.py                       # Add trainer_node_id attribute and validation
├── infrastructure/
│   ├── persistence/
│   │   ├── database.py                         # Add trainer_node_id column to training_shards table DDL
│   │   └── training_shard_repository.py        # Update queries, row mapper, and update_status/assignment methods
│   └── adapters/
│       ├── __init__.py                         # Export ClientP2PNodeAdapter
│       └── client_p2p_node_adapter.py          # Implement IClientP2PNodeAdapter and ServeClientRequests handler
├── application/
│   ├── state.py                                # Store p2p_node_id and client_node_id
│   └── commands/
│       ├── set_node_id/                        # SetNodeIdCommand and handler
│       ├── get_training_task/                  # GetTrainingTaskCommand and handler
│       ├── transfer_model/                     # TransferModelCommand and handler
│       ├── transfer_shard/                     # TransferShardCommand and handler
│       └── update_model/                       # UpdateModelCommand and handler
├── dependency_injection/container.py           # Register client_p2p_node_adapter and command handlers
├── main.py                                     # Invoke SetNodeIdCommand at boot, abort on failure; start P2P listener
├── Dockerfile                                  # Update environment variables and volumes
└── docker-compose.yml                          # Client + private p2p-node sidecar compose stack

src/Trainer/
├── application/
│   ├── state.py                                # Add is_training property, store p2p_node_id
│   ├── trainer_commands/
│   │   └── set_node_id/                        # SetNodeIdCommand and handler
│   └── coordinator_commands/
│       └── start_training/
│           └── handler.py                      # Implement full 6-step P2P training execution lifecycle
├── infrastructure/
│   └── adapters/
│       ├── __init__.py                         # Export TrainerP2PNodeAdapter
│       └── trainer_p2p_node_adapter.py         # Implement ITrainerP2PNodeAdapter via gRPC
├── presentation/
│   ├── console_ui.py                           # Display "waiting for task" vs real-time training step progress
│   └── gui/                                    # Display wait screen vs loading/progress animations
├── dependency_injection/container.py           # Register trainer_p2p_node_adapter and set_node_id handler
├── main.py                                     # Invoke SetNodeIdCommand at boot, abort on failure
├── Dockerfile                                  # Update environment variables and volumes
└── docker-compose.yml                          # Trainer + private p2p-node sidecar compose stack

samples/full_distributed_training_test/
├── data_generator.py                           # Generate canonical .pt2 model, 50-sample .pt dataset, config JSON
├── docker-compose.yml                          # 1 Public network + 3 NAT networks (c, t1, t2)
├── setup.py                                    # Build & launch containers, verify health
├── test.py                                     # Execute task submission from inside Client container
└── verify.py                                   # Verify database status, P2P transfers, model training, and cleanup
```

---

## Complexity Tracking

> No constitutional violations. All implementations adhere strictly to the TrainSwarm Constitution.

| Item | Architectural Scope | Design Decision |
|---|---|---|
| **P2P Bidirectional Inbound Dispatch** | Data-Plane Sidecar Interface | Utilized single gRPC stream `ServeClientRequests` from Python to Go `p2p-node` to avoid running a reverse gRPC server in Python, adhering to Principle III. |
| **Simulated NAT Networks** | Test Environment | Configured 3 isolated bridge networks in Docker Compose connected solely via Bootstrap Relay to validate genuine DCUtR hole punching per Principle II & VII. |
