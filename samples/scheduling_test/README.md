# Coordinator Scheduler Verification Suite

This sample directory contains an end-to-end integration verification suite for the **Fair Model-Level Round-Robin Coordinator Scheduler** in TrainSwarm.

---

## Architecture & Algorithm Overview

The Coordinator Scheduler implements a fair, starvation-free round-robin task allocator assigning unassigned `TrainingTask` records to eligible `Trainer` records.

### Core Scheduling Guarantees

1. **Model-Level Fairness**: Pending tasks are logically partitioned by `TrainingTask.ModelId`. Models receive turns in round-robin sequence, ensuring that large batch submissions (e.g. 10+ tasks) cannot starve smaller models.
2. **Idle Trainer Utilization**: When multiple idle trainers are available, the scheduler repeatedly performs round-robin decisions across active models until either idle trainers or tasks are exhausted. Trainers are never artificially left idle.
3. **FIFO Intra-Model Order**: Within each model queue, tasks are strictly assigned in order of `SubmitTime ASC`.
4. **Deterministic Tie-Breaking**: If tasks share identical submission timestamps, `TrainingTaskId ASC` is used as an unambiguous tie-breaker.
5. **In-Memory Cursor Rotation**: The scheduler maintains an in-memory cursor storing the next model eligible for assignment, preventing earlier models from monopolizing resources across multiple scheduling invocations.
6. **Status Isolation & Concurrency Safety**: Only trainers with status `IDLE` receive tasks; `BUSY` and `UNCLEAR` nodes are ignored. Already assigned tasks are skipped. Assignments are committed atomically within a single database transaction.

---

## Test Cases Detailed

The test suite in `test.py` executes 12 distinct scenarios directly against live Coordinator HTTP endpoints without mocks:

| Test Case | Scenario | Architectural Importance |
|---|---|---|
| **Test 1 — Single Model** | 2 idle trainers, 3 tasks for Model A | Validates baseline FIFO assignment (`SubmitTime ASC`) and unassigned task queuing. |
| **Test 2 — Basic Model Fairness** | 3 idle trainers, tasks for Models A, B, C | Verifies that Model A does not consume all trainers; each model receives 1 turn. |
| **Test 3 — More Trainers than Models** | 5 idle trainers, 3 tasks for Model A, 1 for Model B | Verifies full idle trainer utilization beyond a single 1-task-per-model cycle. |
| **Test 4 — Model with One Task & Cursor Continuity** | 3 trainers for models A, B, C, D; then 1 new trainer | Validates in-memory cursor preservation across separate HTTP API calls. |
| **Test 5 — FIFO Within a Model** | Mixed timestamps across models | Verifies that round-robin fairness never violates strict FIFO order within a model. |
| **Test 6 — Large Imbalance Between Models** | Model A has 10 tasks; Models B & C have 1 task each | Prevents starvation: Models B and C receive turns in the first round. |
| **Test 7 — Trainer Status Filtering** | Trainers with `BUSY`, `UNCLEAR`, `IDLE` statuses | Verifies only `IDLE` trainers receive tasks; `BUSY` and `UNCLEAR` nodes are untouched. |
| **Test 8 — No Tasks** | 2 idle trainers, 0 tasks | Verifies clean empty-queue handling with 0 assignments. |
| **Test 9 — No Idle Trainers** | All trainers `BUSY` or `UNCLEAR` | Verifies tasks remain unassigned when no compute capacity is available. |
| **Test 10 — Already Assigned Tasks Ignored** | Tasks with non-empty `TrainerNodeId` | Ensures pre-assigned tasks are never reassigned or modified by the scheduler. |
| **Test 11 — Model Disappears from Rotation** | Models with unequal queues (A: 1, B: 2, C: 3) | Verifies dynamic removal of exhausted models from active rotation. |
| **Test 12 — Deterministic Tie-Breaking** | Identical `SubmitTime` with known UUIDs | Verifies secondary deterministic sort on `TrainingTaskId ASC`. |

---

## Prerequisites

1. **.NET 10 SDK**: Required to run the Coordinator Web API.
2. **Python 3.10+**: Standard Python installation (uses standard library `urllib` and `json`).

---

## How to Run (Separate Command Line Workflow)

The test suite uses separate command lines for service execution, test running, and cleanup—without generating any log files:

### Command Line 1: Start Coordinator Service

In your first terminal / command line:

```powershell
python setup.py
```

`setup.py` launches the Coordinator Web API on port 5000 with a dedicated SQLite database (`db/coordinator_scheduler.db`).
- Live ASP.NET Core logs stream directly to this console—**no log files are generated**.
- It waits until `/health` returns `200 OK`.
- Press `Ctrl+C` in this terminal at any time to shut down the service.
- *(On Windows, you can optionally pass `python setup.py --new-window` to launch in a new dedicated console window).*

### Command Line 2: Run Verification Test Suite

In a **separate command line / terminal**:

```powershell
python test.py
```

`test.py` executes all 12 test scenarios against the active Coordinator endpoint and displays real-time results for each test case, ending with a 12/12 pass summary.

### Command Line 3: Teardown and Cleanup

When testing is complete, remove the generated SQLite test databases and stop any active Coordinator process:

```powershell
python clean.py
```

To preserve a running Coordinator instance and only delete unlocked database files:

```powershell
python clean.py --no-kill
```




