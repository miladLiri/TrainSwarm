# Quickstart Guide: Training Client Submit Training Verification

**Feature Branch**: `015-client-submit-training`  
**Date**: 2026-09-05  
**Spec Reference**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/015-client-submit-training/spec.md)

---

## Overview

This quickstart guides you through validating the complete **Submit Training** workflow using the end-to-end verification sample suite located in `samples/submit_training_test/`.

The test runs against real containerized Coordinator and Client services connected over a Docker bridge network.

---

## Prerequisites

1. **Docker Engine & CLI**: Docker must be running with container virtualization enabled.
2. **Python 3.11+**: On the host machine to execute test runners and setup scripts.
3. **Dependencies**: Host needs `torch>=2.2.0` (to generate `.pt2` and `.pt` synthetic artifacts).

---

## Step 1: Environment Setup via Docker

From the repository root, run the setup script:

```bash
cd samples/submit_training_test
python setup.py
```

### What `setup.py` Performs:
1. Creates a Docker bridge network named `trainswarm-test-net`.
2. Starts the **Coordinator** container on `http://coordinator:8080`, binding port `8080` to the host.
3. Starts the **Client** container connected to `trainswarm-test-net` with:
   - Volume mount: `./artifacts:/artifacts`
   - Volume mount: `./db:/data`
   - Environment: `COORDINATOR_ADDRESS=http://coordinator:8080`
   - Environment: `TRAINING_CLIENT_WORKING_DIRECTORY=/artifacts`
4. Polls the Coordinator `/health` endpoint until healthy (HTTP 200).
5. Displays confirmation: `[OK] Coordinator and Client containers running and networked successfully.`

---

## Step 2: Execute the Multi-Path Verification Matrix

Run the end-to-end test suite:

```bash
python e2e-test.py
```

### Verification Matrix Scenarios:

| Scenario | Input Condition | Expected Result | Exit Code | Status |
| :--- | :--- | :--- | :---: | :---: |
| **Path 1: Happy Path** | Valid `.pt2` 1D-CNN, valid 50-sample `.pt` dataset, valid config | Smoke test passes, 5 shards created, saved as `CREATED`, Coordinator registers 5 tasks, shards updated to `READY` | 0 | PASS |
| **Path 2: Corrupted Model** | Corrupted / truncated `.pt2` checkpoint | Smoke test fails, sample deleted, submission aborted, diagnostic logged | 1 | PASS |
| **Path 3: Invalid Dataset** | Corrupted `.pt` file with non-tensor keys | Partitioner fails validation, aborts prior to smoke test | 1 | PASS |
| **Path 4: Malformed Config** | Missing required `batch_size` or bad optimizer | Parameter validation fails immediately fast | 1 | PASS |
| **Path 5: Coordinator Outage** | Coordinator container temporarily stopped | Shards saved locally as `CREATED`, Coordinator network error caught, user notified | 1 | PASS |

### Sample Output:
```text
================================================================================
TrainSwarm Client Submit Training: End-to-End Verification Suite
================================================================================
[TEST 1] Happy Path: Valid Model + Dataset + Training Config
  [PASS] Smoke test calculated throughput: 31.25 samples/s
  [PASS] Created 5 shards in /artifacts/shards/
  [PASS] Shards initially persisted as CREATED in SQLite
  [PASS] Coordinator registered 5 task IDs
  [PASS] Shards updated to READY in SQLite
  RESULT: PASS

[TEST 2] Error Path: Corrupted Model Checkpoint
  [PASS] Smoke test failed fast on corrupted weights
  [PASS] Temporary sample file deleted
  [PASS] Zero shards partitioned or persisted
  RESULT: PASS

[TEST 3] Error Path: Invalid Dataset Structure
  [PASS] Partitioner rejected invalid dataset format
  RESULT: PASS

[TEST 4] Error Path: Malformed Training Config JSON
  [PASS] Validation caught missing required field 'optimizer'
  RESULT: PASS

[TEST 5] Resilience Path: Coordinator Outage / Network Timeout
  [PASS] Shards created and safely stored in SQLite as CREATED
  [PASS] CoordinatorNetworkError caught and logged
  RESULT: PASS

================================================================================
ALL 5 VERIFICATION CHECKS PASSED (5/5)
================================================================================
```

---

## Step 3: Teardown & Clean Up

After completing verification, clean up all Docker containers, networks, and temporary artifacts:

```bash
python clean.py
```
*(Alternatively: `python setup.py --down`)*
