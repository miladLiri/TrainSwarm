# Quickstart & Verification Guide: Trainer Connection

**Feature**: Trainer Connection (`016-trainer-connection`)  
**Status**: Completed  
**Date**: 2026-09-06  

This guide provides step-by-step instructions to build, execute, and verify the Trainer Connection feature end-to-end across Coordinator (.NET) and Trainer (Python) subsystems.

---

## 1. Prerequisites

- **.NET 9.0 SDK**: Required to build and run Coordinator locally.
- **Python 3.11+**: Required to run Trainer commands.
- **Docker & Docker Compose**: Required for containerized execution and automated sample testing.
- **SQLite3 CLI** (optional): For manual inspection of `coordinator.db`.

---

## 2. Fast Build & Syntax Verification

### 2.1 Coordinator (.NET)
Verify compilability and build integrity of all Coordinator projects:

```powershell
cd src\Coordinator
dotnet build TrainSwarm.Coordinator.slnx
```

**Expected Outcome**: Build succeeds with 0 errors and 0 warnings.

### 2.2 Trainer (Python)
Verify syntax correctness across all Trainer modules:

```powershell
cd src\Trainer
python -m py_compile main.py
python -m py_compile config\config_manager.py
python -m py_compile dependency_injection\container.py
python -m py_compile application\state.py
python -m py_compile application\trainer_commands\connect_trainer\connect_trainer_command.py
python -m py_compile application\trainer_commands\connect_trainer\connect_trainer_handler.py
python -m py_compile application\coordinator_commands\dispatcher.py
python -m py_compile infrastructure\adapters\coordinator_adapter.py
python -m py_compile presentation\startup.py
```

**Expected Outcome**: All modules compile with exit code 0.

---

## 3. Automated Containerized End-to-End Verification

The complete feature verification is automated inside `samples/trainer_init_test/setup.py`:

```powershell
cd samples\trainer_init_test
python setup.py
```

### What `setup.py` Performs:
1. **Network Initialization**: Creates Docker bridge network `trainswarm-test-net`.
2. **Coordinator Boot**: Builds `src/Coordinator/TrainSwarm.Coordinator.Api/Dockerfile` and launches the container with volume-mapped SQLite persistence on port `8080`.
3. **Health Verification**: Polls `http://127.0.0.1:8080/health` until Coordinator responds `200 OK`.
4. **Trainer Boot**: Builds `src/Trainer/Dockerfile` and launches the container attached to `trainswarm-test-net`.
5. **Startup Connection Guard**: Trainer's `startup.py` triggers `ConnectTrainerCommandHandler`, calling Coordinator `POST /api/trainers/connect`.
6. **Database Verification**: Queries the SQLite database to assert:
   - Row exists where `TrainerNodeId == 'trainer-node-01'`
   - `Status == 1` (`TrainerStatus.IDLE`)
   - `Id` is a valid 36-character GUID string
7. **Idempotent Reconnect Verification**: Executes a second connect call for the same node ID and asserts that the previous record was removed and replaced with a new record with status `IDLE`.

### Teardown
To stop and clean up containers, networks, and test databases:

```powershell
python setup.py --down
```

---

## 4. Manual Verification Steps

### Step 1: Start Coordinator
```powershell
$env:COORDINATOR_DB_CONNECTION_STRING = "Data Source=coordinator_manual.db"
cd src\Coordinator\TrainSwarm.Coordinator.Api
dotnet run
```
Coordinator starts and listens on `http://localhost:5000` (HTTP) and `http://localhost:5001` (gRPC).

### Step 2: Test Direct HTTP Connection (curl / REST)
```powershell
curl.exe -X POST http://localhost:5000/api/trainers/connect `
  -H "Content-Type: application/json" `
  -d '{"trainerNodeId": "trainer-manual-01"}'
```
**Expected Response**:
```json
{
  "id": "e9c1f678-2d8f-4cb1-87a3-1811804cb9e1",
  "trainerNodeId": "trainer-manual-01",
  "status": "IDLE"
}
```

### Step 3: Run Trainer Headless CLI
```powershell
$env:COORDINATOR_ADDRESS = "http://localhost:5000"
$env:COORDINATOR_GRPC_ADDRESS = "localhost:5001"
cd src\Trainer
python main.py
```
**Expected Output**:
```text
[Trainer] Running startup connection guard...
[Trainer] Connected to Coordinator successfully! Trainer Registration ID: e9c1f678-2d8f-4cb1-87a3-1811804cb9e1
[Trainer] Listening for Coordinator commands...
```

### Step 4: Run Trainer PyQt6 GUI Window Shell
```powershell
python main.py gui
```
**Expected Output**:
Startup connection completes, followed by display of the standalone PyQt6 desktop window shell.
