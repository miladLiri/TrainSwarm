# Trainer Connection Verification Sample Suite

This sample directory provides zero-mock, end-to-end verification of the TrainSwarm Trainer connection workflow with the Coordinator API using native `dotnet` and `python` CLIs (no Docker required).

## Overview

The verification workflow:
1. Creates local test storage directories (`./db` and `./artifacts`).
2. Spawns the **Coordinator** service via `dotnet run` on port 8080 with SQLite database storage directed to `./db/coordinator.db`.
3. Polls the Coordinator health endpoint at `http://127.0.0.1:8080/health`.
4. Spawns the **Trainer** node via `python` CLI (`src/Trainer/main.py`).
5. Trainer automatically triggers its startup connection guard (`presentation/startup.py`), dispatching `POST /api/trainers/connect` to the Coordinator.
6. The verification runner inspects the Coordinator's SQLite database directly to assert that a record for `TrainerNodeId = 'trainer-node-01'` exists with `Status = 1` (`IDLE`).
7. Gracefully shuts down all spawned processes and cleans up temporary resources.

## Prerequisites

- **.NET SDK**: .NET 10 SDK (`dotnet` in PATH).
- **Python**: Python 3.10+ (`python` in PATH).

## Quick Start

### Run Verification

```bash
python setup.py
```

### Expected Output

```text
================================================================================
      TrainSwarm Trainer Connection: CLI Verification Runner (No Docker)       
================================================================================
================================================================================
=== [Clean] Cleaning Trainer Connection Test Environment ===
================================================================================
[Clean] Teardown complete.
================================================================================
[Setup] Database directory:  .../samples/trainer_init_test/db
[Setup] Artifacts directory: .../samples/trainer_init_test/artifacts
[Setup] Starting Coordinator on port 8080 via dotnet CLI...
[Setup] Waiting for Coordinator health endpoint at http://127.0.0.1:8080/health...
[Setup] [OK] Coordinator healthy (HTTP 200 via http://127.0.0.1:8080/health) on attempt 2.
[Setup] Starting Trainer via python CLI (...)...
[Setup] Verifying Trainer registration in SQLite database at .../coordinator.db...
[Setup] [OK] Found Trainer record on attempt 2: Id=..., TrainerNodeId='trainer-node-01', Status=1
[Setup] [SUCCESS] Status is 1 (IDLE) as required!
[Setup] Stopping test processes...
================================================================================
  [SUCCESS] ZERO-MOCK CLI VERIFICATION PASSED!                                  
  Trainer successfully registered with Coordinator via dotnet and python CLI.   
================================================================================
```

### Options

- `--keep-alive`: Keep the Coordinator and Trainer processes running after verification for manual debugging or inspection.
- `--down`: Terminate any running test processes, free port 8080, and remove `./db`, `./artifacts`, and logs.

### Teardown and Cleanup

To clean up manually:

```bash
python setup.py --down
```

Or run the cleanup script directly:

```bash
python clean.py
```
