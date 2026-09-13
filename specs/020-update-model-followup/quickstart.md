# Quickstart Validation Guide: Model Update Follow-up & Distributed Aggregation Lifecycle

**Feature**: `020-update-model-followup`  
**Date**: 2026-09-13  
**Status**: Ready  

---

## 1. Prerequisites

- **.NET 10 SDK** (`dotnet --version` >= 10.0)
- **Python 3.10+** with `torch`, `requests`, `PyQt6` (optional for headless CLI)
- **Go 1.22+** (for bootstrap-relay and p2p-node binaries)
- Host OS: Windows (PowerShell) or Linux/macOS (bash)

---

## 2. Compilation and Build Verification

Before running multi-node execution, verify that all modified projects compile cleanly per Constitution Principle VII:

```powershell
# 1. Build Coordinator (.NET)
cd src/Coordinator
dotnet build
if ($LASTEXITCODE -ne 0) { throw "Coordinator build failed" }

# 2. Syntax Check Python Client & Trainer
cd ../../src/Client
python -m compileall .
cd ../Trainer
python -m compileall .
```

---

## 3. Automated End-to-End Verification Test

The complete feature is verified using the non-dockerized multi-node test harness in `samples/full_distributed_training_test/`:

### Step 1: Clean Lingering Processes and Test Artifacts
```powershell
cd samples/full_distributed_training_test
python clean.py
```
- **Expected Outcome**: All background processes on ports 4001, 8090, 8080, 8081, 50051-50053, 9001-9003 are terminated, and `work/` test caches are cleaned.

### Step 2: Execute Live Multi-Node Distributed Training Runner
```powershell
python run_local.py
```
- **What this does**:
  1. Spins up Relay, Coordinator, 3 p2p-node sidecars, Client daemon, and 2 Trainers.
  2. Submits a 50-sample dataset partitioned into 2 shards for training.
  3. Trainers execute local PyTorch fine-tuning and send update deltas to Client.
  4. Client `UpdateModelCommandHandler` detaches each trainer via Coordinator REST API.
  5. Upon second shard completion, Client triggers `AggregationOrchestrator` under lock.
  6. Aggregated model checkpoint (`version 2`) is generated.
  7. Verifies Coordinator reports both trainers in status `IDLE`.
  8. Executes evaluation comparison: asserts `aggregated_loss < base_loss` with finite loss values.
  9. Automatically cleans up test processes in `finally` block.

---

## 4. Manual / Interactive Verification Scenarios

### Scenario A: Coordinator Detach Trainer & Inspection API
1. Start Coordinator:
   ```powershell
   cd src/Coordinator/TrainSwarm.Coordinator.Api
   dotnet run --urls "http://127.0.0.1:8080"
   ```
2. In a separate terminal, query trainers:
   ```powershell
   curl.exe -s http://127.0.0.1:8080/api/trainers
   ```
3. Test Detach API:
   ```powershell
   curl.exe -X POST http://127.0.0.1:8080/api/trainers/detach `
     -H "Content-Type: application/json" `
     -d '{"trainerNodeId": "trainer-test-1", "isTrainingComplete": true}'
   ```
   - **Expected Outcome**: Returns HTTP 200 OK with `{"trainerNodeId":"trainer-test-1","status":"IDLE"}` (or safe no-op if not found/busy).

### Scenario B: Client Shard Watch CLI
1. With training database present, run:
   ```powershell
   cd src/Client
   python main.py watch-shards
   ```
2. **Expected Outcome**: An aligned ASCII table displaying Model ID, Version, Shard ID, Status, and Trainer Node ID, with an interactive prompt allowing `Enter` to refresh or `q` to quit.

### Scenario C: Client GUI Shards and Trained Versions Tabs
1. Launch Desktop GUI:
   ```powershell
   cd src/Client
   python main.py gui
   ```
2. Navigate to `"Training Shards"` tab:
   - Click `"Refresh Shards"` -> table displays active shard statuses.
3. Navigate to `"Trained Versions"` tab:
   - Table displays completed model versions.
   - Select version 2, click `"Export / Save Artifact..."`.
   - Choose export location in file dialog -> confirms model `.pt2` checkpoint saved to selected path.
