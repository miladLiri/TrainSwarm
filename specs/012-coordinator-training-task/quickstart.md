# Quickstart & Verification Guide: Coordinator Clean Architecture & TrainingTask

**Branch**: `012-coordinator-training-task` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

This guide provides step-by-step instructions to build, run, and verify the Coordinator Clean Architecture solution and the new `TrainingTask` endpoint.

---

## 1. Prerequisites

- **.NET SDK**: 10.0+ (`dotnet --version` outputs `10.0.x`)
- **PowerShell / Bash** with `curl` or `Invoke-RestMethod`
- **SQLite CLI** (optional, e.g. `sqlite3`)

---

## 2. Solution Build Verification

Restore and build all four projects from the repository root:

```powershell
dotnet restore src/Coordinator/TrainSwarm.Coordinator.slnx
dotnet build src/Coordinator/TrainSwarm.Coordinator.slnx --no-restore
```

**Expected Outcome**: Zero build errors and zero warnings across all four projects:
- `TrainSwarm.Coordinator.Domain`
- `TrainSwarm.Coordinator.Application`
- `TrainSwarm.Coordinator.Infrastructure`
- `TrainSwarm.Coordinator.Api`

---

## 3. Local Startup & Database Initialization

Set the required environment variable and start the API:

```powershell
$env:COORDINATOR_DB_CONNECTION_STRING = "Data Source=coordinator_local.db"
dotnet run --project src/Coordinator/TrainSwarm.Coordinator.Api
```

**Verification Steps**:
1. **Startup Fail-Fast Check**: Stop the application, unset the variable (`$env:COORDINATOR_DB_CONNECTION_STRING = ""`), and run again. Verify the application immediately halts with:
   `COORDINATOR_DB_CONNECTION_STRING environment variable is missing or empty.`
2. **Schema Creation Check**: When run with a valid connection string, verify the SQLite database file `coordinator_local.db` is created and EF Core migrations provision the `TrainingTasks` table.

---

## 4. End-to-End API Verification Scenarios

### Scenario A: Successful Multi-Shard Task Creation (HTTP 201)

Send a valid creation request with 3 shards:

```powershell
$body = @{
    clientNodeId = "client-001"
    modelId = "gpt2"
    modelVersion = "12"
    dataSetId = "dataset-alpha"
    shardIdList = @("shard-01", "shard-02", "shard-03")
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/api/training-tasks" -Method Post -Body $body -ContentType "application/json"
```

**Expected Response**:
- **HTTP Status**: `201 Created`
- **Response Body**:
  ```json
  {
    "trainingTaskIds": [
      "<guid-1>",
      "<guid-2>",
      "<guid-3>"
    ]
  }
  ```
- **Database Verification**:
  ```powershell
  # Query SQLite table directly
  sqlite3 coordinator_local.db "SELECT TrainingTaskId, ShardId, TrainerNodeId FROM TrainingTasks;"
  ```
  Confirms 3 rows are inserted with matching identifiers and `TrainerNodeId = ''`.

---

### Scenario B: Validation Failure — Duplicate Shard IDs (HTTP 400)

Send a request containing duplicate shard IDs:

```powershell
$badBody = @{
    clientNodeId = "client-001"
    modelId = "gpt2"
    modelVersion = "12"
    dataSetId = "dataset-alpha"
    shardIdList = @("shard-01", "shard-01")
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "http://localhost:8080/api/training-tasks" -Method Post -Body $badBody -ContentType "application/json"
} catch {
    $_.Exception.Response.StatusCode
    $_.ErrorDetails.Message
}
```

**Expected Response**:
- **HTTP Status**: `400 Bad Request`
- **ProblemDetails Body**:
  ```json
  {
    "title": "One or more validation errors occurred.",
    "status": 400,
    "errors": {
      "Invalid.DuplicateShardId": [
        "ShardIdList cannot contain duplicate shard IDs."
      ]
    }
  }
  ```
- **Database State**: Zero new rows written to SQLite.

---

### Scenario C: Existing Command Dispatch & gRPC Preservation

Verify that the relocated `Commands/` continue to function without regression:

```powershell
$dispatchBody = @{
    trainerId = "trainer-node-01"
    trainingClientNodeId = "client-001"
    sessionId = "session-123"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/api/commanddispatch/start-training" -Method Post -Body $dispatchBody -ContentType "application/json"
```

---

## 5. Docker Build and Storage Verification

Build and run the Coordinator container:

```bash
docker build -f src/Coordinator/TrainSwarm.Coordinator.Api/Dockerfile -t trainswarm-coordinator src/Coordinator/
docker run --rm -p 8080:8080 -v coordinator_data:/data -e COORDINATOR_DB_CONNECTION_STRING="Data Source=/data/coordinator.db" trainswarm-coordinator
```

**Expected Outcome**: The container boots cleanly, applies migrations to `/data/coordinator.db`, and accepts API requests on port 8080.
