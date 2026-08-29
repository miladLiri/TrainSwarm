# Quickstart & Validation Guide: Trainer Command Notification Infrastructure

**Feature**: [006-trainer-command-notification](spec.md)
**Date**: 2026-08-29

This guide provides end-to-end instructions to run and validate the gRPC command notification infrastructure between the .NET Coordinator and Python Trainer nodes.

---

## 1. Prerequisites

- **.NET 10 SDK** installed (`dotnet --version`)
- **Python 3.10+** installed (`python --version`)
- Running SQL Server instance (or container) configured in `.env` / environment variables for the Coordinator.

---

## 2. Setup & Build

### 2.1 Coordinator Build & Protobuf Generation
```powershell
cd src/Coordinator/TrainSwarm.Coordinator.Api
dotnet build
```

### 2.2 Trainer Environment Setup & Code Generation
```powershell
cd src/Trainer
python -m pip install -r requirements.txt
python -m grpc_tools.protoc -I../../specs/006-trainer-command-notification/contracts --python_out=infrastructure --grpc_python_out=infrastructure ../../specs/006-trainer-command-notification/contracts/coordinator_commands.proto
```

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Trainer Starts and Establishes Command Stream
1. Start the Coordinator:
   ```powershell
   cd src/Coordinator/TrainSwarm.Coordinator.Api
   dotnet run
   ```
2. Start the Trainer in a separate terminal:
   ```powershell
   cd src/Trainer
   $env:TRAINER_NODE_ID = "trainer-node-01"
   $env:COORDINATOR_URL = "http://localhost:5000"
   $env:COORDINATOR_GRPC_URL = "http://localhost:5000"
   python main.py
   ```
3. **Expected Outcome**:
   - Coordinator logs: `[TrainerConnectionManager] Trainer 'trainer-node-01' registered active command stream.`
   - Trainer logs: `[Trainer] Connected to Coordinator command stream at http://localhost:5000.`

---

### Scenario 2: Coordinator Issues `StartTraining` Command to Connected Trainer
1. Trigger a `StartTraining` command via Coordinator application logic (e.g. an API endpoint or internal service dispatch):
   - Target: `trainer-node-01`
   - Payload: `{"trainingClientNodeId": "client-node-01", "sessionId": "4b6ec6b9-9ef3-40e1-8848-d3e923e59530"}`
2. **Expected Outcome**:
   - Coordinator: `ICommandCenter.SendAsync` returns `CommandDispatchResult(isSuccess=True, commandId="...")`.
   - Coordinator logs: `[CommandCenter] Dispatched command 'StartTraining' (ID: ...) to trainer 'trainer-node-01'.`
   - Trainer logs: `[StartTrainingHandler] Received StartTrainingCommand - Session: 4b6ec6b9-9ef3-40e1-8848-d3e923e59530, Client: client-node-01.`

---

### Scenario 3: Targeted Command to Offline Trainer
1. Issue a command to an unconnected trainer identifier (e.g., `trainer-node-99`):
   ```csharp
   var result = await commandCenter.SendAsync("trainer-node-99", CommandType.StartTraining, payload);
   ```
2. **Expected Outcome**:
   - `result.IsSuccess` is `false`.
   - `result.ErrorMessage` indicates `Trainer 'trainer-node-99' is not connected`.
   - No exception crashes the Coordinator.

---

### Scenario 4: Connection Recovery & Reconnect Loop
1. Stop the Coordinator while the Trainer is running.
2. Observe Trainer logs:
   - `[TrainerCommandListener] Stream disconnected: <RpcError>. Reconnecting in 5 seconds...`
3. Restart the Coordinator.
4. **Expected Outcome**:
   - Trainer reconnects after the 5-second interval.
   - Coordinator logs new registration for `trainer-node-01`.
   - Subsequent `StartTraining` commands are delivered to the reconnected stream.
