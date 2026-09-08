# Technical Architecture & Research: Distributed File Transfer and P2P Training Execution

**Feature**: `019-distributed-file-transfer` | **Phase**: 0 | **Date**: 2026-09-08

## Overview

This document captures the architectural decisions, design patterns, protocol strategies, and alternatives evaluated for implementing distributed file transfer, P2P node adapter interfaces, trainer execution orchestration, containerization, and the multi-node verification test suite.

---

## Decision 1: Go `p2p-node` $\leftrightarrow$ Python Application Communication Strategy

### Decision
Implement a localhost-bound bidirectional gRPC streaming contract (`ServeClientRequests`) for the Client-side Python adapter (`client_p2p_node_adapter.py`) to receive incoming P2P requests (`get_training_task`, `transfer_model`, `transfer_shard`, `update_model`) from the Go `p2p-node` sidecar, while Trainer uses direct unary and streaming gRPC calls (`GetTrainingTask`, `GetModel`, `GetShard`, `SendUpdate`) to its local `p2p-node`.

### Rationale
- **Constitution Compliance**: Principle III strictly requires that communication between Python applications and the Go `p2p-node` must occur exclusively over a localhost-bound gRPC API.
- **NAT & Sidecar Encapsulation**: Connections between peers are initiated from Trainer to Client across libp2p relay/DCUtR hole punching. In the Client node, Go `p2p-node` listens for libp2p streams and needs to trigger Python application commands. A long-lived bidirectional gRPC stream initiated by Python maintains Go as the single gRPC server while enabling Go to push incoming actions to Python and await handler responses without running a reverse gRPC server in Python.
- **Simplicity & Concurrency**: gRPC streaming supports asynchronous request multiplexing using unique correlation request IDs (`request_id`), allowing concurrent shard requests from multiple trainers without blocking.

### Alternatives Considered
1. **Reverse gRPC Server in Python Client**: Python runs a gRPC server on another port and Go dials Python as a client. Rejected because it introduces dual gRPC servers, additional port configuration, firewall complexity, and complicates container networking.
2. **Polling Queue via Unary gRPC**: Python periodically polls `p2p-node` for pending transfer actions. Rejected because polling introduces unnecessary latency (50-500ms) and CPU overhead compared to reactive streaming.
3. **Local Unix Domain Sockets (UDS) / Named Pipes**: Rejected because Windows compatibility and Docker container volume socket sharing are error-prone compared to localhost TCP loopback.

---

## Decision 2: Libp2p Stream Protocols & Chunked Wire Transfer

### Decision
Define distinct, versioned libp2p protocol handlers in Go `p2p-node`:
- `/trainswarm/task/1.0.0`: Unary-style JSON message stream for `get_training_task` request and response.
- `/trainswarm/model/1.0.0`: Streaming file transfer protocol for base model checkpoint (`.pt2`), supporting chunked streaming with SHA256 integrity verification.
- `/trainswarm/shard/1.0.0`: Streaming file transfer protocol for dataset shards (`.pt`).
- `/trainswarm/update/1.0.0`: Compound stream protocol sending `TrainingResult` JSON metadata followed by streaming trained weights delta artifact (`safetensors`).

### Rationale
- **Protocol Isolation**: Clear protocol IDs allow libp2p's multistream-select to multiplex different transfer types over the same direct or relayed libp2p connection without message ambiguity.
- **Resource Efficiency**: Streaming file transfers in 32KB/64KB chunks prevents loading entire checkpoints (which can be gigabytes) into memory, maintaining a low memory footprint on edge nodes.
- **Strict Overwrite Semantics**: All incoming files written by `p2p-node` use `os.O_CREATE | os.O_TRUNC | os.O_WRONLY` to ensure existing or stale files in the designated working directory (`WORKING_DIR`) are overwritten cleanly.

### Alternatives Considered
1. **Single Unified libp2p Protocol with Binary Multiplexing**: Packaging all requests into a single multiplexed custom framing protocol. Rejected as overly complex for MVP (violates Constitution Principle IV).
2. **HTTP/REST over Relay**: Using HTTP over libp2p streams. Rejected as libp2p raw streams with JSON envelope headers are simpler, native to `go-libp2p`, and carry lower framing overhead.

---

## Decision 3: P2P Node Identity & Startup Fail-Fast Guard

### Decision
Both `TrainerP2PNodeAdapter` and `ClientP2PNodeAdapter` implement `get_p2p_node_id() -> str` using the existing `GetNodeInfo` gRPC RPC. During application boot (`main.py`), Client and Trainer execute a dedicated command (`SetNodeIdCommand`) as the very first operation. If `p2p-node` cannot be reached within 5 seconds or returns an error, the application halts immediately with code 1 and a descriptive error message.

### Rationale
- **Authoritative Identity**: The `peer_id` returned by the local `p2p-node` becomes the authoritative `client_node_id` registered with the Coordinator and assigned to training tasks, ensuring that trainers dial the exact libp2p peer ID across the relay.
- **Fail-Fast Safety**: Prevents launching GUI or console command listeners when the underlying data plane is broken, providing clear diagnostic feedback to operators instead of silent downstream timeouts.

### Alternatives Considered
1. **Static Configuration from `.env`**: Hardcoding peer IDs in environment variables. Rejected because libp2p peer IDs are cryptographically derived from private keys; manual configuration causes synchronization mismatches if keys are regenerated.
2. **Lazy Node ID Resolution**: Resolving node ID on the first P2P operation. Rejected because a broken sidecar would only be discovered after training tasks are scheduled, disrupting cluster workflow.

---

## Decision 4: Trainer Execution Sequence & Ephemeral File Cleanup

### Decision
`StartTrainingHandler` orchestrates a strict sequential pipeline:
1. `get_training_task`: Retrieve task envelope from Client over P2P.
2. `get_model`: Check filesystem existence of base model checkpoint in working directory. If file exists, skip download; if absent, stream from Client.
3. `get_shard`: Stream assigned dataset shard from Client to local working directory.
4. `train`: Invoke `TrainingOrchestrator.run(task, work_dir)` to train locally via PyTorch and generate `TrainingResult` and delta artifact.
5. `send_update`: Stream delta artifact and `TrainingResult` to Client via P2P.
6. `cleanup`: If send succeeds, delete the local shard file and update artifact file; retain base model checkpoint. If send fails, retain files on disk for diagnostics and log failure.

### Rationale
- **Bandwidth & Storage Optimization**: Caching base models locally avoids redundant re-downloads across multiple assigned shards.
- **Disk Boundedness**: Dataset shards are ephemeral and specific to a single run; purging them after confirmed update delivery prevents unbounded disk consumption on edge trainers.
- **Post-Failure Auditability**: Retaining files upon transfer failure allows manual inspection, crash analysis, and offline recovery.

### Alternatives Considered
1. **Always Re-download Base Model**: Rejected because multi-gigabyte models would exhaust network bandwidth on repetitive training cycles.
2. **Purge Shard Immediately After Training**: Deleting shard before `send_update` succeeds. Rejected because if update sending fails, the training run cannot be re-inspected or retried.

---

## Decision 5: Trainer Real-Time Presentation State Machine

### Decision
Add `is_training: bool = False` to `TrainerState`.
- `StartTrainingHandler` toggles `is_training = True` upon entering step 1 and `is_training = False` upon exiting step 6 (or upon error in `finally` block).
- In `console_ui.py`: when `is_training` is False, print and refresh "Waiting for task..." status; when True, print real-time step progress logs and final metrics.
- In `gui/`: when `is_training` is False, render an idle wait screen; when True, render step indicators and progress/loading animations.

### Rationale
- **Thread Safety & Observable State**: `TrainerState` acts as the single source of truth for presentation layers.
- **Non-Blocking UI**: Background threads running `TrainerCommandListener` and command handlers update state without freezing the GUI event loop.

### Alternatives Considered
1. **Polling Coordinator for Training State**: Presentation polling Coordinator. Rejected because Trainer is data-plane authoritative for its local execution status.

---

## Decision 6: Isolated Containerization & Simulation Network Topology

### Decision
1. **Sidecar Containerization**: Client and Trainer Docker Compose stacks run `p2p-node` as a private sidecar service on internal bridge networks without publishing port 50051 to the host.
2. **Multi-NAT Verification Test (`samples/full_distributed_training_test/`)**:
   - 1 Public bridge network: runs `bootstrap-relay` (Go relay server on 4001/8090) and `coordinator` (.NET API on 5000/5001).
   - 3 Simulated NAT networks:
     - `c` (Client network): Client + sidecar `p2p-node` connected to public network only through the relay.
     - `t1` (Trainer 1 network): Trainer 1 + sidecar `p2p-node`.
     - `t2` (Trainer 2 network): Trainer 2 + sidecar `p2p-node`.
   - `data_generator.py`: Synthesizes canonical PyTorch `.pt2` model, 50-sample `.pt` dataset, and `training_config.json`.
   - `setup.py`, `test.py`, `verify.py`: Orchestrates lifecycle, triggers Client submission, and asserts full cluster convergence.

### Rationale
- **Security & Constitutional Integrity**: `p2p-node` gRPC API is unauthenticated localhost-only; isolating it within container networks prevents unauthorized network control.
- **Realistic NAT Validation**: Running Trainers and Client in distinct Docker networks connected solely via Bootstrap Relay proves real DCUtR hole punching and NAT traversal under genuine production conditions.

### Alternatives Considered
1. **Single Docker Network for All Services**: Rejected because it would allow direct TCP connections, bypassing relay/NAT validation and masking hole-punching defects.
2. **Host Networking Mode**: Rejected because port collisions would occur across multiple instances and NAT isolation would be lost.
