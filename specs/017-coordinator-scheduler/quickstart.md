# Quickstart & Validation Guide: Coordinator Scheduler

## Overview

This guide details how to build, run, and validate the Coordinator Scheduler feature end-to-end against live services without mocks.

---

## Prerequisites

1. **.NET 10 SDK**: Verify via `dotnet --version`.
2. **Python 3.10+**: Verify via `python --version`.
3. **Python `requests` Library**: Installed in test environment (`pip install requests`).

---

## Step 1: Build the Coordinator Service

Build the Coordinator solution to confirm compilability:

```powershell
dotnet build src\Coordinator\TrainSwarm.Coordinator.slnx
```

Expected Outcome: `Build succeeded. 0 Error(s)`.

---

## Step 2: Launch the Coordinator Web API

Set the SQLite connection string and launch the Coordinator service:

```powershell
$env:COORDINATOR_DB_CONNECTION_STRING = "Data Source=coordinator_scheduler_test.db"
dotnet run --project src\Coordinator\TrainSwarm.Coordinator.Api
```

Verify the service is running by querying the health endpoint:

```powershell
curl http://localhost:5000/health
```

Expected Response: `{"status":"Healthy"}`.

---

## Step 3: Run the Automated Verification Suite

Navigate to the sample test suite directory and run the verification harness:

```powershell
cd samples\scheduling_test
python setup.py
python test.py
```

### What `test.py` Validates (All 12 Cases):

1. **Test 1 — Single Model FIFO**: 2 idle trainers, 3 tasks for Model A. Verifies T1→A1, T2→A2, A3 unassigned.
2. **Test 2 — Basic Model Fairness**: 3 idle trainers, tasks for Model A, B, C. Verifies T1→A1, T2→B1, T3→C1.
3. **Test 3 — More Trainers than Models**: 5 idle trainers, 3 tasks for Model A, 1 task for Model B. Verifies T1→A1, T2→B1, T3→A2, T4→A3, T5 remains idle.
4. **Test 4 — Model with One Task & Cursor Continuity**: 3 idle trainers, tasks A1, B1, C1, D1. Verifies T1→A1, T2→B1, T3→C1. Subsequent call with 1 idle trainer verifies T1→D1.
5. **Test 5 — FIFO Preservation within a Model**: Models with staggered timestamps verify strict `SubmitTime ASC` ordering.
6. **Test 6 — Large Imbalance Starvation Prevention**: Model A has 10 tasks; Models B & C have 1 task. Verifies T1→A1, T2→B1, T3→C1, T4→A2, T5→A3, T6→A4.
7. **Test 7 — Trainer Status Filtering**: Trainers with `BUSY` and `UNCLEAR` statuses receive zero tasks; only `IDLE` trainers receive tasks.
8. **Test 8 — Zero Tasks**: Zero tasks present results in 0 assignments; trainers remain `IDLE`.
9. **Test 9 — Zero Idle Trainers**: All trainers `BUSY`/`UNCLEAR` results in 0 assignments; tasks remain unassigned.
10. **Test 10 — Pre-Assigned Task Exclusion**: Tasks with existing `TrainerNodeId` are ignored by the scheduler.
11. **Test 11 — Model Exhaustion Rotation Removal**: As smaller models exhaust pending tasks, they are pruned from rotation and remaining trainers are assigned to remaining active models.
12. **Test 12 — Deterministic Tie-Breaking for Equal SubmitTime**: Tasks with identical `SubmitTime` are ordered deterministically by `TrainingTaskId ASC`.

Expected Outcome: All 12 test cases print formatted green `[PASS]` output, with 0 errors and return code 0.
