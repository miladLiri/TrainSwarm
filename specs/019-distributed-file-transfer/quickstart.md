# Quickstart Validation Guide: Distributed File Transfer and P2P Training Execution

**Feature**: `019-distributed-file-transfer` | **Phase**: 1 | **Date**: 2026-09-08

This guide details the step-by-step procedure to validate the distributed file transfer, P2P node adapter, trainer lifecycle, and multi-node NAT test suite.

---

## 1. Prerequisites

- **Docker & Docker Compose**: Installed and operational.
- **Python 3.10+**: Host environment with `torch>=2.2.0`, `grpcio`, `protobuf`.
- **Go 1.22+**: Required for building `p2p-node` and `bootstrap-relay` (or Docker handles builds).
- **.NET 10 SDK**: Required for `Coordinator` (or Docker handles builds).

---

## 2. Fast Non-Docker Unit Verification

Before launching the multi-container cluster, verify component compilability and contracts:

```powershell
# 1. Verify Go p2p-node builds cleanly
cd src/p2p-node
go build ./...

# 2. Verify Python modules compile cleanly
cd ../..
python -m py_compile src/Trainer/main.py
python -m py_compile src/Client/main.py
```

---

## 3. End-to-End Multi-Node NAT Validation Suite

The complete verification harness is located at:
`samples/full_distributed_training_test/`

### Step 3.1: Generate Synthetic Model, Dataset & Configuration
```powershell
cd samples/full_distributed_training_test
python data_generator.py
```
**Expected Outcome**:
- Generates `canonical_model.pt2` (TorchScript / canonical model artifact).
- Generates `dataset_50_samples.pt` (50 samples tensor dataset).
- Generates `training_config.json` with training hyperparameters.

---

### Step 3.2: Launch the Virtual Multi-NAT Cluster
```powershell
python setup.py
```
**What `setup.py` executes**:
1. Invokes `docker compose up -d --build`.
2. Spins up 1 public network containing `bootstrap-relay` (port 4001, 8090) and `coordinator` (port 5000).
3. Spins up 3 isolated simulated NAT networks:
   - Network `c`: Client container + private sidecar `p2p-node`.
   - Network `t1`: Trainer 1 container + private sidecar `p2p-node`.
   - Network `t2`: Trainer 2 container + private sidecar `p2p-node`.
4. Polls health endpoints until all services and sidecars report readiness.

---

### Step 3.3: Submit Training Task & Trigger Distributed P2P Execution
```powershell
python test.py
```
**What `test.py` executes**:
1. Connects into the `client` container.
2. Executes `python main.py submit-training` using the mounted model, dataset, and configuration.
3. Client partitions dataset into 2 shards (`shard_000`, `shard_001`), saves them locally in SQLite, and registers the training task with the Coordinator.
4. Coordinator scheduler assigns 1 shard to Trainer 1 and 1 shard to Trainer 2, dispatching `StartTrainingCommand`.
5. Each Trainer receives `StartTrainingCommand` and initiates the 6-step P2P sequence:
   - Queries Client over P2P for `TrainingTask`.
   - Checks local cache for base model; streams model over P2P if absent.
   - Streams assigned dataset shard over P2P.
   - Runs local PyTorch training via `TrainingOrchestrator`.
   - Streams trained safetensors update artifact and `TrainingResult` back to Client over P2P.
   - Confirms delivery and deletes local shard and update files while preserving the base model.
6. Client receives both updates, saves safetensors in its working directory, and transitions both shard records to `completed` in SQLite.

---

### Step 3.4: Assert Cluster Convergence & Correctness
```powershell
python verify.py
```
**What `verify.py` validates**:
- **Coordinator Database**: Both training tasks assigned and marked complete.
- **Client SQLite Database**: Both shards in `training_shards` have status `completed`, valid `trainer_node_id`, and existing `update_artifact_path`.
- **Client Filesystem**: Update artifacts exist on disk and are valid safetensors files.
- **Trainer Filesystems**: Ephemeral shard files and update delta files have been removed; base model checkpoint is preserved.
- **Logs**: Structured logs confirm DCUtR hole punching through the relay and zero communication errors.

---

### Step 3.5: Teardown
```powershell
docker compose down -v
```
Reclaims all containers, networks, and temporary volumes.
