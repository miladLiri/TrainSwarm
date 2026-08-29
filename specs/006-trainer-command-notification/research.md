# Phase 0 Research: Trainer Command Notification Infrastructure

**Feature**: [006-trainer-command-notification](spec.md)
**Date**: 2026-08-29

## 1. gRPC Hosting in ASP.NET Core (.NET 10)

### Decision
Use `Grpc.AspNetCore` package in `TrainSwarm.Coordinator.Api`. Expose the `CoordinatorCommandService` implementing `SubscribeCommands(TrainerRegistrationRequest request, IServerStreamWriter<CommandEnvelope> responseStream, ServerCallContext context)`.

### Rationale
- `Grpc.AspNetCore` is the standard, first-party gRPC server implementation for ASP.NET Core.
- Seamlessly integrates with Kestrel HTTP/2 endpoints, dependency injection, and logging.
- `IServerStreamWriter<CommandEnvelope>` allows writing server-pushed envelopes directly to the open stream whenever a command is sent.
- Server call cancellation token (`context.CancellationToken`) automatically triggers when the client disconnects, enabling clean connection removal.

### Alternatives Considered
- *Custom WebSocket or raw TCP socket*: Rejected because gRPC provides strongly typed contract generation across .NET and Python, HTTP/2 multiplexing, and built-in streaming primitives without maintaining bespoke frame protocols.
- *Bidirectional streaming*: Rejected because the specification strictly limits this feature to one-way Coordinator → Trainer communication with no upstream application messages.

---

## 2. Python gRPC Client & Streaming

### Decision
Use `grpcio` and `grpcio-tools` in `src/Trainer/requirements.txt`. Generate Python stubs from `coordinator_commands.proto` (`coordinator_commands_pb2.py` and `coordinator_commands_pb2_grpc.py`).

### Rationale
- `grpcio` provides standard, battle-tested gRPC client bindings in Python.
- Server-streaming calls in `grpcio` return an iterator (`response_iterator = stub.SubscribeCommands(request)`), enabling a clean, sequential message loop: `for envelope in response_iterator: dispatcher.dispatch(envelope)`.
- Disconnections raise `grpc.RpcError`, which can be caught to trigger the 5-second fixed-interval reconnection loop.

### Alternatives Considered
- *AsyncIO gRPC (`grpc.aio`)*: Considered, but the Trainer console application is structured around standard synchronous threading and REPL loop. A background daemon thread consuming the sync streaming iterator keeps architecture simple and prevents event loop conflicts with UI/PyTorch.

---

## 3. Coordinator Connection Management & Thread Safety

### Decision
Implement `ITrainerConnectionManager` / `TrainerConnectionManager` as a `Singleton` in `TrainSwarm.Coordinator.Domain` or `TrainSwarm.Coordinator.Api` backed by a thread-safe `ConcurrentDictionary<string, TrainerConnection>`. Each `TrainerConnection` encapsulates a `Channel<CommandEnvelope>` (or direct write lock with `SemaphoreSlim`) writing to `IServerStreamWriter<CommandEnvelope>`.

### Rationale
- `ConcurrentDictionary` provides thread-safe addition, retrieval, replacement, and removal of active trainer connections by `trainerId`.
- In gRPC for .NET, concurrent writes to `IServerStreamWriter<T>` must be serialized (gRPC disallows concurrent `WriteAsync` calls on the same stream writer). Using a `Channel<CommandEnvelope>` or `SemaphoreSlim` ensures safe, ordered message delivery to the stream writer.
- When a Trainer reconnects with an existing `trainerId`, the manager supersedes the old connection and completes the previous channel, cleanly terminating stale stream tasks.

### Alternatives Considered
- *Ephemeral database table for socket pointers*: Rejected because stream handles and writers are in-memory process resources that cannot be shared via SQL Server.

---

## 4. Message Serialization & Shared Contract

### Decision
Envelopes use protobuf with dynamic JSON payloads:
- Wire format: Protobuf `CommandEnvelope` containing `string id`, `string type`, and `string data` (UTF-8 JSON string).
- JSON Serialization: .NET uses `System.Text.Json` with `JsonNamingPolicy.CamelCase` (`JsonSerializerDefaults.Web`). Python uses standard `json.loads` / `json.dumps` mapping directly to dataclass models with camelCase property dictionaries.
- Command models:
  - `StartTrainingCommand` in .NET: `TrainingClientNodeId` (string), `SessionId` (string).
  - `StartTrainingCommand` in Python: `training_client_node_id` (str), `session_id` (str), with `from_dict` / `to_dict` camelCase parsing.

### Rationale
- Keeps protobuf schemas minimal and stable: adding new commands never requires recompiling `.proto` files or updating gRPC service stubs.
- JSON payload parsing is isolated at the application/handler boundary.
- Matching camelCase naming ensures seamless cross-language interoperability.

### Alternatives Considered
- *Protobuf Any or Struct*: Adds substantial mapping complexity and type registry maintenance across languages without tangible benefits over plain JSON payloads.

---

## 5. Trainer Command Dispatcher & Handler Registry

### Decision
Create a generic `CommandDispatcher` in `src/Trainer/infrastructure/` or `application/`:
- Maintains a registry mapping `CommandType` -> tuple of `(CommandModelClass, ICommandHandlerInstance)`.
- Protocol `ICommandHandler`: Defines `handle(command: Any) -> None`.
- Dispatch flow:
  1. Inspect `envelope.type`.
  2. Lookup registered handler and model class. If unknown, log warning and safely discard.
  3. Parse `envelope.data` JSON string into `model_class.from_dict(payload_dict)`. If invalid, log error and skip.
  4. Invoke `handler.handle(typed_command)`.
- Handlers are free to run synchronously or spawn background tasks according to their domain requirements.

### Rationale
- OCP (Open-Closed Principle): New command types are added simply by creating a model, a handler, and registering them with `dispatcher.register_handler(...)`. The gRPC transport and stream reader code remain completely untouched.
- Handlers receive strongly typed models, completely insulated from gRPC and transport details.

### Alternatives Considered
- *Hardcoded `if/elif` statements in the stream loop*: Rejected because it tightly couples the transport loop with business logic and violates the extensibility requirement.

---

## 6. Connection Lifecycle & Reconnection Strategy

### Decision
The Python Trainer runs a background connection worker (`TrainerCommandListener`):
- Connects to Coordinator gRPC endpoint and calls `SubscribeCommands(TrainerRegistrationRequest(trainer_id=...))`.
- Iterates over the stream.
- On stream completion, EOF, or `grpc.RpcError` (e.g. Coordinator restart or network failure):
  - Logs warning with error details.
  - Sleeps for the fixed 5-second interval.
  - Reconnects and resumes listening.

### Rationale
- Complies directly with clarification decision (5-second fixed retry).
- Operates autonomously in the background without blocking the console UI or application logic.

### Alternatives Considered
- *Manual reconnect triggered by console menu*: Kept as an optional manual action, but automated background reconnection is required for unattended operation.
