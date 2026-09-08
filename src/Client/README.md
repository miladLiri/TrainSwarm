# TrainSwarm Client

Data-plane client application for TrainSwarm, responsible for PyTorch model staging, representative smoke testing, dataset partitioning into training shards, local SQLite persistence, and task registration with the Coordinator API.

---

## Features

- **Submit Training Application Command (`SubmitTrainingCommandHandler`)**:
  - Validates PyTorch 2 model checkpoints (`.pt2`) and datasets (`.pt`).
  - Stages models into isolated directories: `{working_directory}/{model_id}/{model_id}_{model_version}.pt2`.
  - Executes representative autograd smoke test via `SmokeTestCommandHandler` to determine optimal shard sizing (`recommended_samples_per_shard`), immediately cleaning up temporary sample artifacts.
  - Partitions full datasets into shards stored at `{working_directory}/shards/{dataset_id}/` via `PartitioningOrchestrator`.
  - Persists shards in local SQLite database with status `CREATED`.
  - Submits `CreateTrainingTaskDto` to the Coordinator REST API (`POST /api/training-tasks`).
  - Atomically transitions local shard statuses from `CREATED` to `READY` upon Coordinator acknowledgement.

- **Dual Presentation Interfaces**:
  - **Headless Non-Interactive CLI**: `python main.py submit-training` for automated pipelines and containerized execution.
  - **Modern Desktop GUI**: `python main.py gui` built with PyQt6, featuring Submit Training and live Logs tabs, form controls, and background `QThread` execution.

---

## Installation

### Core CLI (Headless / Containerized)
```bash
cd src/Client
pip install -r requirements.txt
```

Core dependencies include:
- `torch>=2.2.0`
- `safetensors`
- `requests>=2.31.0`
- `python-dotenv>=1.0.0`

### Desktop GUI (Optional)
To run the interactive PyQt6 graphical interface:
```bash
pip install -r requirements-gui.txt
```

---

## Configuration

The client is configured via environment variables (or `.env` file):

| Environment Variable | Description | Default |
| :--- | :--- | :--- |
| `COORDINATOR_ADDRESS` | Coordinator REST API base URL (**Required**) | `http://localhost:8080` |
| `P2P_GRPC_HOST` | Host of the local Go p2p-node sidecar | `127.0.0.1` |
| `P2P_GRPC_PORT` | Port of the local Go p2p-node sidecar | `50051` |
| `WORKING_DIR` | Root working directory for staged models and shards | `./Artifacts` (container: `/artifacts`) |
| `TRAINING_CLIENT_WORKING_DIRECTORY` | Root working directory for staged models and shards | `./Artifacts` (container: `/artifacts`) |
| `TRAINING_CLIENT_DB_PATH` | Path to local SQLite database file | `./training.db` (container: `/data/training.db`) |
| `CLIENT_NODE_ID` | Unique identifier for this client node | Auto-generated UUID |

---

## P2P Request Dispatch & Shard Lifecycle

The Client runs an active inbound listener (`ClientP2PNodeAdapter.start_listening()`) connected to its local `p2p-node` over the `ServeClientRequests` bidirectional gRPC stream. When assigned Trainers make P2P calls to the Client, the adapter dispatches them to co-located command handlers:

1. **`GetTrainingTaskCommand`**: Looks up model and training config, queries the assigned `TrainingShard`, updates its status to `training`, sets `trainer_node_id`, and returns the compiled `TrainingTask` envelope.
2. **`TransferModelCommand`**: Queries `ModelRepository` and returns the file path of the base model checkpoint (`.pt2`) for streaming.
3. **`TransferShardCommand`**: Queries `TrainingShardRepository` and returns the file path of the assigned dataset shard (`.pt`) for streaming.
4. **`UpdateModelCommand`**: Receives the trained weights delta safetensors file and `TrainingResult` metadata, records `update_artifact_path` and metrics, and transitions the shard status to `completed`.

### Shard Lifecycle Transitions

```
[CREATED] --(Coordinator Ack)--> [READY] --(Trainer GetTask)--> [TRAINING] --(Trainer SendUpdate)--> [COMPLETED]
```

---

## CLI Usage Reference

Submit a model and dataset for distributed training:

```bash
python main.py submit-training \
  --model-path /path/to/model.pt2 \
  --dataset-path /path/to/dataset.pt \
  --model-version v1.0 \
  --model-type canonical_torch \
  --training-config /path/to/training_config.json
```

### CLI Arguments

- `--model-path` *(required)*: Path to the exported PyTorch 2 model checkpoint (`.pt2`).
- `--dataset-path` *(required)*: Path to the canonical PyTorch dataset file (`.pt`).
- `--model-version` *(required)*: Version identifier string (e.g. `v1.0`).
- `--model-type` *(optional)*: Engine model type (default: `canonical_torch`).
- `--training-config` *(required)*: Path to JSON configuration file containing training hyperparameters.

### Training Config Format (`training_config.json`)

```json
{
  "batch_size": 2,
  "shuffle": true,
  "epochs": 1,
  "gradient_accumulation_steps": 1,
  "optimizer": "AdamW",
  "learning_rate": 0.001,
  "loss": "MSELoss",
  "weight_decay": 0.01,
  "scheduler": "CosineAnnealingLR"
}
```

---

## Desktop GUI Usage

Launch the PyQt6 graphical user interface:

```bash
python main.py gui
```

### GUI Features
- **Submit Training Tab**:
  - File picker dialogs filtered by `.pt2` and `.pt` extensions.
  - Model type, optimizer, scheduler, and loss criterion dropdowns.
  - Numeric spinboxes for batch size, epochs, gradient accumulation, learning rate, and weight decay.
  - Inline progress bar (0–100%) and color-coded status banner.
  - Background `QThread` execution (`SubmitTrainingWorker`) preventing UI freezes.
- **Logs Tab**: Live diagnostic event streaming with a "Clear Logs" utility.

*Note*: If launched on a headless server without a display server (`DISPLAY` unset on Linux), the application safely prints an error message instructing the user to use CLI mode.

---

## Docker Compose Deployment (Bundled Sidecar)

Launch Client with its private `p2p-node` sidecar without publishing internal gRPC ports to the host:

```bash
cd src/Client
docker compose up --build -d
```


---

## Verification Sample Suite

An end-to-end multi-path verification suite is provided under `samples/submit_training_test/`:

- `python setup.py`: Sets up Docker network and launches Coordinator & Client containers.
- `python e2e-test.py`: Executes 5 verification scenarios (Happy Path, Corrupted Model, Invalid Dataset, Malformed Config, Coordinator Outage).
- `python clean.py`: Tears down containers, network, and test artifacts.
