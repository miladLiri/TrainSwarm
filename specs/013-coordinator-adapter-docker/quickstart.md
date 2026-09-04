# Quickstart & Verification Guide: Coordinator Adapter & Docker Infrastructure

**Feature**: `013-coordinator-adapter-docker` | **Date**: 2026-09-04

This guide defines the runnable verification procedures to validate the Coordinator adapter implementation, infrastructure cleanup, and Docker volume persistence.

---

## 1. Syntax & Compilation Verification

Verify that all modified and newly created Python modules compile cleanly without syntax errors:

```bash
python -m py_compile src/Client/infrastructure/adapters/create_training_task.py
python -m py_compile src/Client/infrastructure/adapters/coordinator_adapter.py
python -m py_compile src/Client/infrastructure/adapters/__init__.py
python -m py_compile src/Client/infrastructure/__init__.py
python -m py_compile src/Client/main.py
python -m py_compile src/Client/presentation/console_ui.py
```

Expected Outcome: Zero exit code, zero compilation or syntax errors.

---

## 2. Active Verification Suite

Run the active, zero-mock verification suite in `samples/coordinator_adapter_test/verify_coordinator_adapter.py`:

```bash
python samples/coordinator_adapter_test/verify_coordinator_adapter.py
```

### Automated Checks Performed:
1. **Config Fast-Fail**: Verifies initializing `CoordinatorAdapter` without `COORDINATOR_ADDRESS` raises `CoordinatorConfigurationError`.
2. **URL Normalization**: Verifies trailing slashes (`http://coordinator:8080///`) are cleanly stripped.
3. **DTO Field Validation**: Verifies `CreateTrainingTaskDto` rejects empty strings, whitespace, and empty shard lists.
4. **Wire Serialization**: Verifies `to_dict()` outputs camelCase keys (`clientNodeId`, `modelId`, `modelVersion`, `dataSetId`, `shardIdList`) and zero snake_case keys.
5. **Success Response Handling**: Verifies HTTP 201 `{"trainingTaskIds": ["guid-1", "guid-2"]}` parses to `["guid-1", "guid-2"]`.
6. **HTTP Error Handling**: Verifies HTTP 400/500 responses log diagnostic context and raise `CoordinatorApiError` with status code and error text.
7. **Malformed Response Handling**: Verifies HTTP 200 with invalid JSON or missing `trainingTaskIds` raises `CoordinatorAdapterError`.
8. **Network Error Handling**: Verifies connection timeouts and unreachable hosts raise `CoordinatorNetworkError`.
9. **Architectural Isolation**: Verifies `CoordinatorAdapter` has zero imports of `sqlite3`, `DatabaseManager`, or `TrainingShardRepository`.
10. **Infrastructure Cleanliness**: Verifies obsolete `bootstrap_client.py` and `coordinator_client.py` do not exist.

Expected Outcome: `10/10 checks PASSED with 0 errors`.

---

## 3. End-to-End Live Coordinator Verification (Optional / Local Dev)

When running against a live Coordinator instance (from `src/Coordinator`):

```bash
# In shell 1: Start Coordinator
dotnet run --project src/Coordinator/TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj

# In shell 2: Test Training Client task creation
$env:COORDINATOR_ADDRESS = "http://localhost:5000"
$env:TRAINING_CLIENT_DB_PATH = "./test_training.db"
python src/Client/main.py
```

---

## 4. Docker Build & Persistent SQLite Volume Verification

### Step 4.1: Build the Docker Image
```bash
docker build -t trainswarm-client:latest src/Client/
```

Expected Outcome: Docker image builds successfully and tags `trainswarm-client:latest`.

### Step 4.2: Run Container with Mounted Persistent Volume
```bash
# Create a local persistent volume directory
mkdir -p ./test_docker_data

# Run container with volume mount and runtime environment variables
docker run --rm -d `
  --name trainswarm-client-test `
  -v "$(Get-Location)/test_docker_data:/data" `
  -e COORDINATOR_ADDRESS="http://coordinator:8080" `
  -e TRAINING_CLIENT_DB_PATH="/data/training.db" `
  trainswarm-client:latest

# Verify database file was created inside the mounted directory
Test-Path ./test_docker_data/training.db
```

### Step 4.3: Verify State Retention Across Container Restarts
```bash
# Stop the container
docker stop trainswarm-client-test

# Re-launch a new container with the exact same volume mount
docker run --rm `
  --name trainswarm-client-test-2 `
  -v "$(Get-Location)/test_docker_data:/data" `
  -e COORDINATOR_ADDRESS="http://coordinator:8080" `
  -e TRAINING_CLIENT_DB_PATH="/data/training.db" `
  trainswarm-client:latest

# Confirm the SQLite database file and schema remain intact
```

Expected Outcome: Container initializes cleanly, uses `/data/training.db`, and persists database records across container recreations.
