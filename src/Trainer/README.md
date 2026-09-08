# TrainSwarm Trainer

Worker plane application for TrainSwarm, responsible for connecting to the Coordinator control plane, receiving distributed training workload commands via gRPC streaming, and executing training tasks.

---

## Architecture

The Trainer follows the unified TrainSwarm client architecture with strict separation of concerns, lightweight dependency injection, and command/command-handler co-location:

```text
src/Trainer/
├── application/
│   ├── state.py                            # Runtime state with hardcoded client_node_id ("trainer-node-01")
│   ├── coordinator_commands/               # Incoming remote commands from Coordinator gRPC
│   │   ├── dispatcher.py                   # Routes gRPC envelope payloads to matching handlers
│   │   └── start_training/                 # Co-located command & handler for start training
│   │       ├── command.py
│   │       └── handler.py
│   └── trainer_commands/                   # Local Trainer lifecycle commands
│       └── connect_trainer/                # Co-located command & handler for connecting to Coordinator
│           ├── connect_trainer_command.py
│           └── connect_trainer_handler.py
├── config/                                 # Centralized configuration reading from .env & environment
│   ├── config_manager.py
│   ├── models.py
│   └── exceptions.py
├── dependency_injection/                   # Composition root wiring configuration, state, and handlers
│   └── container.py
├── infrastructure/
│   ├── adapters/                           # External HTTP adapters
│   │   └── coordinator_adapter.py          # HTTP adapter for POST /api/trainers/connect
│   └── coordinator_connection/             # gRPC streaming infrastructure
│       ├── coordinator_client.py
│       ├── trainer_command_listener.py
│       ├── coordinator_commands_pb2.py
│       └── coordinator_commands_pb2_grpc.py
└── presentation/
    ├── startup.py                          # Startup connection guard (halts on failure)
    ├── console_ui.py                       # Minimal headless CLI runner
    └── gui/                                # Standalone PyQt6 desktop GUI shell
        └── main_window.py
```

---

## Features

- **Startup Lifecycle Guard (`presentation/startup.py`)**:
  - Automatically executes during application boot before any UI or CLI loop starts.
  - Dispatches `ConnectTrainerCommand`, invoking `CoordinatorAdapter.connect_trainer()` against `POST /api/trainers/connect`.
  - Halts process immediately with exit code 1 if the Coordinator is unreachable or returns a failure, preventing headless hangs or blank GUI windows.
- **Dual Presentation Interfaces**:
  - **Headless Non-Interactive CLI**: `python main.py` for automated pipelines and containerized execution (default).
  - **Desktop GUI Shell**: `python main.py gui` built with PyQt6 displaying node identity, connection state, and registration session ID.
- **Co-Located Command Architecture**:
  - `application/coordinator_commands/`: Contains gRPC-received remote commands with matching handlers.
  - `application/trainer_commands/`: Contains local application commands.
  - The legacy `domain/` directory has been cleared in favor of explicit co-located command packages.
- **Containerized Volume Support**:
  - Docker container sets `WORKDIR /artifacts` and mounts `/artifacts` as a volume for storage of models, weights, and run outputs.

---

## Configuration

The Trainer is configured via environment variables or a `.env` file loaded at startup:

| Environment Variable | Description | Default |
| :--- | :--- | :--- |
| `COORDINATOR_ADDRESS` | Coordinator REST API base URL (**Required**) | `http://localhost:8080` |
| `COORDINATOR_GRPC_ADDRESS` | Coordinator gRPC host and port | `localhost:8081` |
| `TRAINER_NODE_ID` | Configured trainer node identifier | `trainer-node-01` |
| `P2P_GRPC_HOST` | Host of the local Go p2p-node sidecar | `127.0.0.1` |
| `P2P_GRPC_PORT` | Port of the local Go p2p-node sidecar | `50051` |
| `WORKING_DIR` | Directory where models, shards, and weights are stored | `./artifacts` (container: `/artifacts`) |
| `REQUEST_TIMEOUT_SECONDS` | HTTP request timeout in seconds | `10` |
| `TRAINER_WORKING_DIRECTORY`| Working directory for artifacts | `./artifacts` (container: `/artifacts`) |

---

## P2P Training Lifecycle

When Coordinator assigns a training task to the Trainer, the `StartTrainingHandler` executes a 6-step lifecycle:

```
+-----------------------------------------------------------------------------------------+
|                               Trainer 6-Step Execution                                  |
|                                                                                         |
| 1. Query Task Spec     --> GET /trainswarm/task/1.0.0 over P2P from Client              |
| 2. Check / Fetch Model --> Local cache check; stream /trainswarm/model/1.0.0 if missing |
| 3. Fetch Dataset Shard --> Stream /trainswarm/shard/1.0.0 over P2P from Client          |
| 4. Train Locally       --> Execute PyTorch training via TrainingOrchestrator            |
| 5. Transmit Update     --> Stream weights delta & metrics over /trainswarm/update/1.0.0 |
| 6. Ephemeral Cleanup   --> Delete local shard (.pt) and delta (.safetensors); keep model|
+-----------------------------------------------------------------------------------------+
```

## Real-Time Presentation Telemetry (`is_training`)

- **State Management**: `TrainerState.is_training` is set to `True` upon task entry and reset to `False` in a `finally` block.
- **Headless Console (`console_ui.py`)**:
  - Displays periodic heartbeat when idle: `[Trainer] [IDLE] Node: ... | Waiting for task assignment...`
  - Displays step descriptions and training metrics in real-time when `is_training` is `True`.
- **Desktop GUI (`main_window.py`)**:
  - Displays calm idle screen with node identity, P2P peer ID, and registration status when `is_training` is `False`.
  - Transitions to an animated progress screen showing step progress bar (1/6 to 6/6), pulsing loading indicator, active task, and real-time loss metrics when `is_training` is `True`.

---

## Installation & Running

### 1. Headless CLI (Default)

```bash
cd src/Trainer
pip install -r requirements.txt
python main.py
```

### 2. Desktop GUI

```bash
cd src/Trainer
pip install -r requirements.txt PyQt6
python main.py gui
```

### 3. Docker Compose (Bundled Sidecar)

Run Trainer with its private `p2p-node` sidecar without publishing internal gRPC ports to the host:

```bash
cd src/Trainer
docker compose up --build -d
```

