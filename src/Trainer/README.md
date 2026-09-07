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
| `COORDINATOR_GRPC_ADDRESS` | Coordinator gRPC host and port | `localhost:8080` |
| `TRAINER_NODE_ID` | Configured trainer node identifier | `trainer-node-01` |
| `REQUEST_TIMEOUT_SECONDS` | HTTP request timeout in seconds | `10` |
| `TRAINER_WORKING_DIRECTORY`| Working directory for artifacts | `./artifacts` (container: `/artifacts`) |

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

### 3. Docker Container

Build and run the Trainer container with the `/artifacts` volume mount:

```bash
docker build -t trainswarm-trainer -f src/Trainer/Dockerfile src/Trainer/

docker run --rm -d \
  --name trainer-node-01 \
  --network trainswarm-net \
  -v trainer_artifacts:/artifacts \
  -e COORDINATOR_ADDRESS=http://coordinator:8080 \
  -e COORDINATOR_GRPC_ADDRESS=coordinator:8080 \
  trainswarm-trainer
```
