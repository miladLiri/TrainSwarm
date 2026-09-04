# Quickstart & Verification Guide: Client Configuration, DI, and Smoke Test

**Feature Branch**: `014-client-config-smoke-test`  
**Date**: 2026-09-04  
**Author**: Antigravity  
**Status**: Completed  

---

## 1. Overview

This guide provides end-to-end verification workflows to validate:
1. Centralized configuration management with fast-fail validation.
2. Lightweight composition root dependency injection without service locators.
3. Codebase audit ensuring zero `os.getenv` calls remain outside `src/Client/config/`.
4. Smoke test execution using the real `TrainingOrchestrator`, accurate throughput measurement, shard sizing estimation, and automatic delta cleanup.
5. Error handling and diagnostic reporting for failing training runs.

---

## 2. Prerequisites

Ensure Python 3.10+ is active and required packages are available:

```powershell
python --version
python -c "import torch; import requests; print('Prerequisites verified successfully')"
```

---

## 3. Automated Verification Harness

We provide an active, zero-mock end-to-end verification script located at:
`samples/client_smoke_test/verify_client_config_smoke_test.py`

Run the verification harness directly:

```powershell
python samples/client_smoke_test/verify_client_config_smoke_test.py
```

### Expected Output Summary

```text
================================================================================
TrainSwarm Client: Configuration, DI, and Smoke Test Verification
================================================================================
[TEST 1] Verifying Centralized Configuration Manager...
  ✓ Missing COORDINATOR_ADDRESS raises MissingConfigurationError (fast-fail)
  ✓ Malformed SHARD_TRAINING_TIME_LIMIT raises InvalidConfigurationValueError
  ✓ Valid environment variables parse into strongly typed ClientConfig
  ✓ Documented defaults (300.0s time limit, 1.0 safety factor) populated

[TEST 2] Verifying Audit of Environment Variable Reads...
  ✓ Scanning src/Client for unauthorized os.getenv / os.environ / environ.get...
  ✓ Found exactly 0 unauthorized environment reads outside src/Client/config/

[TEST 3] Verifying Refactored Infrastructure Constructors...
  ✓ CoordinatorAdapter requires explicit coordinator_address (no os.getenv)
  ✓ DatabaseManager requires explicit db_path (no os.getenv)

[TEST 4] Verifying Composition Root (DIContainer)...
  ✓ DIContainer constructs DatabaseManager, TrainingShardRepository, CoordinatorAdapter
  ✓ DIContainer wires TrainingOrchestrator and SmokeTestCommandHandler
  ✓ Zero container.get / container.resolve service locator lookups exist

[TEST 5] Verifying Smoke Test Execution (Success Path)...
  ✓ Executed real TrainingOrchestrator across 10 samples
  ✓ Monotonic training duration recorded: 0.142 seconds
  ✓ Calculated throughput: 70.42 samples/second
  ✓ Estimated samples per shard (300s limit): 21126
  ✓ Recommended samples per shard (safety factor 0.8): 16900
  ✓ SmokeTestResult.success == True
  ✓ Model delta artifact (.safetensors) automatically cleaned up from working dir

[TEST 6] Verifying Smoke Test Execution (Failure Path)...
  ✓ Invoked TrainingOrchestrator on invalid training task (corrupted configuration)
  ✓ Exception caught and logged cleanly
  ✓ SmokeTestResult.success == False
  ✓ Error details captured in result.error
  ✓ Throughput and shard estimates suppressed (None)

================================================================================
ALL VERIFICATION CHECKS PASSED (6/6)
================================================================================
```

---

## 4. Manual Step-by-Step Validation Scenarios

### Scenario A: Verify Fast-Fail Startup

1. Unset `COORDINATOR_ADDRESS` and run the Client console entry point:
   ```powershell
   $env:COORDINATOR_ADDRESS=""
   python src/Client/main.py
   ```
2. **Expected Result**: Process exits with code 1 and prints an explicit error:
   ```text
   [Client] [ERROR] Configuration validation failed: Missing required environment variable 'COORDINATOR_ADDRESS'.
   ```

3. Set `COORDINATOR_ADDRESS` with valid configuration and run again:
   ```powershell
   $env:COORDINATOR_ADDRESS="http://localhost:5000"
   $env:SHARD_TRAINING_TIME_LIMIT="300"
   python src/Client/main.py
   ```
4. **Expected Result**: Process starts cleanly and initializes persistence and adapters.

---

### Scenario B: Verify No Direct Environment Variable Access

Run the PowerShell grep check across `src/Client`:

```powershell
Get-ChildItem -Path "src\Client" -Recurse -Filter "*.py" | ForEach-Object {
    $file = $_.FullName
    if ($file -notmatch "src\\Client\\config") {
        Select-String -Path $file -Pattern "os\.getenv", "os\.environ", "environ\.get"
    }
}
```

**Expected Result**: Zero matching lines found outside `src/Client/config/`.

---

### Scenario C: Verify Programmatic Smoke Test Command & Sizing

Execute a smoke test command using the Composition Root:

```python
from Client.config import ConfigManager
from Client.dependency_injection import DIContainer
from Client.application.smoke_test import SmokeTestCommand
from distributed_training_engine.training import TrainingTask

# 1. Initialize composition root
config = ConfigManager().get_config()
container = DIContainer(config=config)

# 2. Build test command
task = TrainingTask.from_dict(...)
command = SmokeTestCommand(training_task_model=task, sample_count=100)

# 3. Handle command
result = container.smoke_test_handler.handle(command)

# 4. Inspect result
print("Success:", result.success)
print("Throughput (samples/s):", result.samples_per_second)
print("Recommended Shard Size:", result.recommended_samples_per_shard)
```
