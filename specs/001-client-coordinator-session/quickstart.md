# Quickstart Validation Guide: Client-Coordinator Session Creation

**Feature**: `001-client-coordinator-session`
**Date**: 2026-08-21
**Status**: Complete

This guide details runnable scenarios to validate end-to-end communication between the Python Client console application and the .NET Coordinator Web API.

---

## 1. Prerequisites

- **.NET SDK 10.0** installed.
- **Python 3.11+** installed with virtual environment support.
- **Docker** (optional, for container validation).
- SQL Server LocalDB or in-memory / containerized database accessible for Coordinator.

---

## 2. Step 1: Start the Coordinator Service

From repository root:
```powershell
cd src/Coordinator
dotnet run --project TrainSwarm.Coordinator.Api
```

Verify that the Coordinator is listening on `http://localhost:5000` (or `https://localhost:5001`).

---

## 3. Step 2: Configure and Run the Python Client

From repository root:
```bash
cd src/Client
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run Client console application
python main.py
```

---

## 4. Step 3: Execute End-to-End Validation Scenarios

### Scenario A: Successful Session Creation
1. In the Client console menu, select option `1` (Create Training Session).
2. Enter a session name (e.g. `CIFAR-Run-01`) or press Enter to auto-generate.
3. Verify output displays:
   ```text
   [SUCCESS] Session created successfully!
   Session ID: <GUID>
   Name: CIFAR-Run-01
   Status: NONE
   ```
4. In Client menu, select option `2` (Show Active Session) and verify the active session ID matches the returned GUID.

### Scenario B: Verify Session Persistence in Coordinator
Execute a GET request against the Coordinator API:
```bash
curl http://localhost:5000/api/sessions
```
Verify the returned JSON array contains the newly created session with matching `id`, `name`, and `clientNodeId`.

### Scenario C: Resilient Error Handling (Coordinator Down)
1. Stop the Coordinator service.
2. In the Client console menu, select option `1` (Create Training Session).
3. Verify the Client displays a clear error message (e.g. `[ERROR] Failed to create session: Connection refused`) without crashing and returns to the main menu loop.

---

## 5. Step 4: Containerized Client Validation

Build and execute the Client container image:
```bash
cd src/Client
docker build -t trainswarm-client .

# Run container in interactive mode with coordinator network access
docker run -it --rm \
  -e COORDINATOR_URL="http://host.docker.internal:5000" \
  -e CLIENT_NODE_ID="client-node-docker-01" \
  trainswarm-client
```
Verify the container launches the console REPL and creates a session when option 1 is triggered.