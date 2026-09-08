# Quickstart & Validation Guide: Completing Submit Flow

**Feature**: `018-complete-submit-flow` | **Date**: 2026-09-08

## Overview

This guide details the step-by-step procedure to execute and validate the end-to-end submission, background scheduling, command dispatch, and trainer ingestion flow using the test harness in `samples/task_assignment_test/`.

---

## Prerequisites

1. **.NET SDK**: .NET 10 installed and available on `PATH` (`dotnet --version`).
2. **Python**: Python 3.10+ installed with PyTorch (`torch>=2.2.0`) in the active environment.
3. **Network Ports**: Dedicated local ports available (e.g., HTTP 5050 and gRPC 5051 for Coordinator).

---

## Validation Scenario: Automated Task Assignment Test

The automated sample in `samples/task_assignment_test/` exercises all components across Client, Coordinator, and Trainer without Docker.

### Step 1: Environment Cleanup & Process Startup

Run `startup.py` to start the Coordinator Web API, start the Trainer node, verify connectivity, and generate synthetic test artifacts:

```powershell
python samples/task_assignment_test/startup.py
```

**Expected Outcome**:
- Coordinator starts on designated port and responds `HTTP 200 OK` on `/health`.
- Trainer connects to Coordinator, registers, and starts background `TrainerCommandListener`.
- Background process IDs are recorded in `samples/task_assignment_test/.test_pids.txt`.
- Synthetic model checkpoint (`test_model.pt2`), tiny dataset (`test_dataset.pt`), and `training_config.json` are created under `samples/task_assignment_test/artifacts/`.
- Terminal outputs `[Setup] Environment is ready for submit.py!`.

---

### Step 2: Submit Training Task via Client CLI

In the same terminal, run `submit.py` to submit the training task and perform end-to-end assertions:

```powershell
python samples/task_assignment_test/submit.py
```

**Expected Outcome**:
1. **Client Submission Execution**:
   - Client CLI parses arguments, stages the model checkpoint, runs automated smoke testing, partitions the dataset into shards, and saves shards with status `CREATED`.
   - Client persists `Model` entity to the local SQLite database via `ModelRepository`.
   - Client submits `CreateTrainingTaskDto` to Coordinator and updates local shard statuses to `READY`.
2. **Coordinator Background Scheduling**:
   - Coordinator saves tasks and dispatches `SchedulerService.AssignTasksAsync()` in the background under thread-safe synchronization.
   - Scheduler identifies the idle trainer, sets `task.TrainerNodeId` and `trainer.Status = BUSY`.
   - Coordinator dispatches `StartTrainingCommand` containing `ClientNodeId`, `ModelId`, `ModelVersion`, `DataSetId`, and `ShardId` to the trainer over gRPC.
3. **Trainer Command Receipt**:
   - Trainer's `TrainerCommandListener` receives the command over gRPC and invokes `StartTrainingHandler`.
   - Trainer logs the received 5 command fields.
4. **Harness Assertions**:
   - Asserts Client SQLite database has 1 `models` record and corresponding `training_shards` records.
   - Asserts Coordinator database has `TrainingTask` assigned to the trainer.
   - Asserts Trainer process log records the `StartTrainingCommand` receipt.
   - Terminal outputs:
     ```text
     ================================================================================
     === [PASS] All Task Assignment Test Assertions Passed! ===
     ================================================================================
     ```

---

### Step 3: Teardown & Cleanup

Clean up background processes, temporary databases, and generated test files:

```powershell
python samples/task_assignment_test/clean.py
```

**Expected Outcome**:
- Coordinator and Trainer background processes terminated cleanly.
- `samples/task_assignment_test/.test_pids.txt` deleted.
- Temporary SQLite databases and test artifacts removed.

---

## Build Integrity & Syntax Verification

Per TrainSwarm Constitution Principle VII (Verification, Compilability, and Executable Correctness):

```powershell
# Verify .NET Coordinator build integrity
dotnet build src/Coordinator/TrainSwarm.Coordinator.sln

# Verify Python syntax across Client, Trainer, and sample harness
python -m py_compile src/Client/application/submit_training/submit_training_command_handler.py
python -m py_compile src/Client/infrastructure/persistence/model_repository.py
python -m py_compile src/Trainer/presentation/startup.py
python -m py_compile src/Trainer/application/coordinator_commands/start_training/command.py
python -m py_compile samples/task_assignment_test/startup.py
python -m py_compile samples/task_assignment_test/submit.py
python -m py_compile samples/task_assignment_test/clean.py
```
