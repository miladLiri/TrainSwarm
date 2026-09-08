# Feature Specification: Distributed File Transfer and P2P Training Execution

**Feature Branch**: `019-distributed-file-transfer`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "distributed file transfer\n\n1- p2p-node adapter\n\nthe p2p-node is responsible for 4 functionlities for connection between trainer and client \nfor all of them connecton is started from trainer to cient \n\n1-1- get training task -> it connects to client_node_id\n\ttrainer sends\n            model_id,\n            model_version,\n            data_set_id,\n            shard_id,\n\tand get retured training_task_model \n\tvia adapter to p2p-node\n\n\tclient in applicaton has get_training_task_command with \n            model_id,\n            model_version,\n            data_set_id,\n            shard_id,\n\n\tin its handler it will look up model using model repository then load the training config json and then look up Training Shard and with gathered data it builds a training_task_model and returns it also it updates the training shard trainer node id and status to training\n\twhen trainer calls get training task from its adapter then the request goes to client via p2p-node connection then client calls the get training task command handler and sends back the result to trainer via its p2p-node adapter then trainer recieves it via its adapter\n\t\n\ttrainer -> |(trainer_p2p_node_adapter) -> send request to p2p-node   |(trainer p2p-node) -> (client p2p-node)|(client_p2p_node_adapter) calls the cammand handler and get result | -> client\n                   |                           <- return training_task_model |                   <-                  |                          send result to p2p-node                  | <-\n\n\n\n1-2- get model -> it connects to client_node_id\n\ttrainer sends\n\t\tmodel_id,\n            \tmodel_version,\n\tand gets returned path\n\tvia adapter to p2p-node\n\n\tclient in application has transfer_model command with\n\t\tmodel_id,\n            \tmodel_version,\n\t\n\tin its handler it will look up model using model repository and returns model_artifact_path\n\twhen trainer calls get model from its adapter then request goes through p2p connection then in client p2p node adapter it calls the transfer model handler and get the path then sends it to p2p node and p2p-node send file to trainer\n\n        trainer -> |(trainer_p2p_node_adapter) -> send request to p2p-node   |(trainer p2p-node)                     -> (client p2p-node)|(client_p2p_node_adapter) calls the cammand handler and get path | -> client\n                   |                           <- return path                | save file and return saved file path  <-     send file    |                          send path to p2p-node                  | <-\n\n\n1-3- get shard -> it connects to client_node_id\n\ttrainer sends\n\t    model_id,\n            model_version,\n            data_set_id,\n            shard_id,\n\tand get returned path\n\tvia adapter to p2p node\n\t\n\tclient in application has transfer_shard command with \n            model_id,\n            model_version,\n            data_set_id,\n            shard_id,\n\n\tin its handler it will look up shard via training shard repository and returns the artifact_path\n\twhen trainer calls get shard from its adapter then request goes through p2p connection then in client p2p node adapter it calls the transfer shard handler and get the path then sends it to p2p node and p2p-node send file to trainer\n\n        trainer -> |(trainer_p2p_node_adapter) -> send request to p2p-node   |(trainer p2p-node)                     -> (client p2p-node)|(client_p2p_node_adapter) calls the cammand handler and get path | -> client\n                   |                           <- return path                | save file and return saved file path  <-     send file    |                          send path to p2p-node                  | <-\n\n1-4- send update -> it connects to client_node_id\n\ttrainer sends\n\t\ttraining_result\n\t\tupdate artifact path\n\twith no return\n\tvia adapter to p2p-node\n\n\tclient in application has Update_Model command with\n\t\ttraining_result\n\t\tupdate artifact path\n\n\tin its handler it will find the training shard via training shard repository with data from training result then updates it and and set update_artifact_path and status.                                                                                     \n\ttrainer -> |(trainer_p2p_node_adapter) -> send request to p2p-node   |(trainer p2p-node)  send training_result and send update file  -> (client p2p-node) save update file and send training_result and path to saved update file|(client_p2p_node_adapter) calls the update model cammand handler | -> client\n\n\np2p-node grpc api interface and its transfer protocol and Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py and Client/infrastructure/adapter/client_p2p_node_adapter.py must changed or updated or created so these 4 functionality work correctly as described\nin any file saving existing file must be overritten\nany file saving in client and trainer happens in working directory. p2p-node knows the working direcory via its environmental variable\nthe hole process must have proper logging and compelete tracablity of flow through logs\np2p node grpc address in both trainer and client p2p node adapters come from env via config manager\nnote taht adapters are different for client and trainer but p2p node is one module for all the functionalities\n\n-----------------\n2- get node id in p2p node adapter\n\ntrainer and client p2p node adapter has one common method : get_p2p_node_id()\nit connects to p2p-node via grpc api and get the node id of p2p-node \n\nboth client in application/commands/ and trainer in application/trainer_commands/ has a set_node_id_command\nthis command takes no argument and in its handler calls the p2p node adapter get p2p node id and then set the p2p node id in state to returning value\nif any part in this process goes wrong exception must raise\n\nboth client and trainer in their main.py app in startup time must call this command handler. this comes first in starting both of them and if it fails stop the application from running in both console cli adn gui with proper error message\n\n\n--------------------\n3- start training handler\n\nstart training handler in trainer application\\coordiantor_commands\\ now must do it's desired functionality\n\nthis handler works in this order\n\n3-1- use trainer_p2p_node_adapter and get training task from client_node_id to get training task from client\n3-2- if required model and version exists in working directory skip. else use trainer_p2p_node_adapter and get model from client_node_id to get model from client and get returend path\n3-3- use trainer_p2p_node_adapter and get sahrd from client_node_id to get shard from client and get returned path\n3-4- use training_orchestrator and train the model and get the training_reuslt\n3-5- use trainer_p2p_node_adapter and send update to client_node_id \n3-6- if send was successfull then remove the shard file and update file (keep the model file)\n\neach step should have proper logging and tracablity\n\n---------------------\n4- trainer presentation\n\nin trainer/application/state.py add a new state varible is_training with false as default value and when training handler start to execute make it true and with it finishes make it false again\n\nin console_ui.py in persentaiotn if is_traing is false show waiting for task and when its true it must show training steps and its result\nin gui/ when is_training is false make create a wait screen and when its training show the steps that are going through and loading (make it beautiful maybe use animation)\n------------------\n\n5- containerizaton \n\tupdate docker file of trainer and client for env var and volumes if needed\n\tin client create a docker compose file that first runs a p2p node and when it was up then runs client application and connect client to local p2p node. do not expose the p2p-node out \n\tin trainer create a docker compose file that first runs a p2p node and when it was up then runs trainer application and connect client to local p2p node. do not expose the p2p-node out \n\n---------------\n6- update p2p-node / trainer / client / coordinator readme about new functionality and instructions for run with cmd / docker / docker compose\n\n---------------\n\n7- Test in samples/\n\nin samples create full_distributed_training_test/\nthe goal is to mimik a real work senario via docker one coordiantor and one realy in public network and client and 2 trainer with thair p2p-node sidcars behind NAT and client submit a task\n\ncreate data_generator.py that creates a simple model with a dataset with 50 samples and training config then export them as pt2 and pt and json\n\ncreate a docker compose file and inside it \n\tcreate 3 network simulating networks behind NAT\n\tfirst c\n\tsecond t1\n\tthird t2\n\t1- run bootstrap-realy via docker\n\t2- run coordinator via docker\n\tthese are in public network and must expose required ports\n\t3- in network c run a p2p node via docker but dont expose it in this network run a client via docker and set up envs to connect to its p2p-node coordiantor and relay and working directory\n\t4- mount pt and pt2 and json file inside client\n\t5- in t1 and t2 network each of them create a p2p node via docker and don't expose it and run a trainer in each and set envs for correct settings and conneciton to relay and coordinator\n\ncreate setup.py that runs the docker compose with proper logging and check if services are working\n\ncreate test.py taht goes inside the client and submit the training task of created model\n\nat the end model must be submited and saved in client and task in the coordinator and scheduler assigns one shard to each trainer then trainers using p2p-node must communicate with client and get thair training taks, model copy and shard and start training and when finished send updates to client and updates saved in client working direcoty status of training shards in client db must be updated\n\ncreate a verify.py to verify that test was working correctly"

## Clarifications

### Session 2026-09-08

- Q: How should the Client handle a `get_training_task` request if the requested shard is already marked as `training` or `completed`? (FR-009) → A: Always accept the request and overwrite the assignment regardless of current status (Option C).
- Q: If sending the trained model update to the Client fails (`send_update`), how should the Trainer handle the local shard and update artifact files? (FR-019) → A: Retain both shard and update files on disk, log the failure details, and reset `is_training` to False (Option A).
- Q: When Trainer checks whether the base model exists locally in its working directory, how should it verify presence and integrity? (FR-019) → A: Verify file existence only; skip download if the file path exists (Option B).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - P2P Node Identity Retrieval and Fail-Fast Startup Guard (Priority: P1)

As a distributed client or trainer application operator, I want each node to automatically query its attached Go `p2p-node` sidecar upon application boot to retrieve its unique peer identifier and record it in application state, so that invalid or unreachable sidecars fail immediately with actionable diagnostic feedback before entering the command loop or GUI presentation.

**Why this priority**: Foundational connectivity precondition. All P2P operations, peer-to-peer handshakes, and scheduling dispatches depend on a healthy local `p2p-node` sidecar with a verified peer identity.

**Independent Test**: Launch Client or Trainer with `p2p-node` offline; verify startup halts immediately with code 1 and an explicit error log. Launch with healthy `p2p-node`; verify peer identifier is retrieved, stored in application state, and logged cleanly.

**Acceptance Scenarios**:

1. **Given** a healthy `p2p-node` sidecar running on the configured gRPC endpoint, **When** Client or Trainer application executes its startup sequence in `main.py`, **Then** the application triggers `set_node_id_command` as its very first action.
2. **Given** `set_node_id_command` executes, **When** it queries the P2P adapter's `get_p2p_node_id()` method, **Then** the adapter issues a gRPC call to `p2p-node`, retrieves the sidecar's node identifier string, and stores it in application state (`ClientState` / `TrainerState`).
3. **Given** an unreachable, misconfigured, or erroring `p2p-node` sidecar, **When** `set_node_id_command` is invoked during startup, **Then** an exception is raised, caught by `main.py`, a human-readable fatal error message is emitted to stderr/console, and process execution terminates cleanly without loading GUI or console interactive loops.

---

### User Story 2 - P2P Training Task Retrieval and Shard State Transition (Priority: P1)

As an assigned Trainer node, I want to request the complete training task specification from the authoritative Client node over the direct P2P network using my assigned task parameters (`model_id`, `model_version`, `data_set_id`, `shard_id`), so that I receive the training configuration JSON and hyper-parameters while the Client transitions the corresponding shard record to `training` status.

**Why this priority**: Critical data-plane handshake. Connects control-plane task dispatching (`StartTrainingCommand`) to authoritative data-plane execution without involving the Coordinator in configuration or checkpoint transport.

**Independent Test**: Send a get-training-task request from Trainer adapter to Client adapter via their connected `p2p-node` sidecars. Verify Client command handler validates the shard and model records, loads configuration, transitions shard status to `training`, records `trainer_node_id`, and returns a structured `TrainingTask` model to the Trainer.

**Acceptance Scenarios**:

1. **Given** Trainer receives a `StartTrainingCommand` containing `client_node_id`, `model_id`, `model_version`, `data_set_id`, and `shard_id`, **When** Trainer initiates step 1 of training via `trainer_p2p_node_adapter.get_training_task()`, **Then** the request is forwarded across the P2P network to the target Client node.
2. **Given** Client receives the incoming training task query via its `p2p-node` sidecar, **When** dispatched to `client_p2p_node_adapter`, **Then** it invokes the Client's `get_training_task_command` handler.
3. **Given** `get_training_task_command` handler executes in Client, **When** resolving the task, **Then** it queries `ModelRepository` for model metadata, loads the referenced training configuration JSON from disk, queries `TrainingShardRepository` for shard details, updates the shard's `trainer_node_id` and sets `status` to `training` in SQLite, and returns a compiled `TrainingTask` model envelope.
4. **Given** the compiled `TrainingTask` model, **When** sent back across P2P to the Trainer, **Then** `trainer_p2p_node_adapter` receives and unpacks the `TrainingTask` object, ready for orchestrator execution.

---

### User Story 3 - P2P Model Checkpoint Retrieval with Local Cache Bypass (Priority: P1)

As a Trainer node, I want to check my local working directory for existing model checkpoint artifacts before downloading, and if absent, request and stream the base model file from the Client over P2P, overwriting any corrupt or partial files, so that unnecessary network transfers are eliminated while ensuring model availability.

**Why this priority**: Core bandwidth optimization and precondition for model fine-tuning. Base models can be hundreds of megabytes or gigabytes; avoiding redundant downloads across tasks saves time and network resources.

**Independent Test**: Invoke `get_model` when the file already exists in Trainer working directory; verify transfer is skipped and existing path returned. Delete local file and re-invoke; verify Client's `transfer_model` command handler resolves `model_artifact_path`, streams the checkpoint via P2P chunk transfer, saves the file in Trainer's working directory, and returns the valid local path.

**Acceptance Scenarios**:

1. **Given** Trainer prepares to train a model version that is already present in its local working directory, **When** step 2 executes, **Then** Trainer skips P2P model transfer and immediately uses the local path.
2. **Given** Trainer does not have the specified model version in its working directory, **When** step 2 executes, **Then** Trainer adapter calls `get_model(client_node_id, model_id, model_version)` over P2P.
3. **Given** the request arrives at Client, **When** handled by Client's `transfer_model` command handler, **Then** the handler retrieves `model_artifact_path` from `ModelRepository` and provides the path to `p2p-node` for streaming.
4. **Given** the file is streamed across P2P to Trainer's `p2p-node`, **When** received, **Then** the sidecar writes the file into Trainer's designated working directory (overwriting existing content if present) and returns the verified local file path to `trainer_p2p_node_adapter`.

---

### User Story 4 - P2P Dataset Shard Retrieval and Local Ingestion (Priority: P1)

As a Trainer node, I want to fetch my assigned dataset shard file from the Client over P2P using shard identifiers (`model_id`, `model_version`, `data_set_id`, `shard_id`), saving the shard in my working directory, so that local training has the exact training samples assigned by the Coordinator.

**Why this priority**: Precondition for local fine-tuning. Dataset shards are partitioned per trainer and must be securely streamed directly from the owning Client.

**Independent Test**: Issue a `get_shard` request from Trainer to Client. Verify Client's `transfer_shard` command handler looks up the shard artifact in `TrainingShardRepository`, streams the `.pt` shard via P2P, and saves it into Trainer's working directory with write overwrite enabled.

**Acceptance Scenarios**:

1. **Given** Trainer initiates step 3 of training, **When** calling `trainer_p2p_node_adapter.get_shard(client_node_id, model_id, model_version, data_set_id, shard_id)`, **Then** the request reaches Client via P2P.
2. **Given** Client receives the shard request, **When** `transfer_shard` command handler runs, **Then** it queries `TrainingShardRepository` using the composite key, extracts `artifact_path`, and passes the file to Client's `p2p-node`.
3. **Given** P2P streaming commences, **When** data arrives at Trainer's `p2p-node`, **Then** the shard file is written to Trainer's working directory (overwriting any previous file) and the local filesystem path is returned to Trainer.

---

### User Story 5 - Local Model Training, Update Transmission, and Ephemeral Cleanup (Priority: P1)

As a Trainer node, I want to execute local fine-tuning using `TrainingOrchestrator`, transmit the resulting weights update delta and `TrainingResult` metadata back to Client over P2P, and upon confirmed delivery, purge the ephemeral shard and update files while preserving the base model artifact, so that Client receives updates and Trainer disk space is reclaimed cleanly.

**Why this priority**: Completes the core data-plane distributed training lifecycle. Updates Client persistence, closes the training loop for the assigned shard, and prevents unbounded disk growth on Trainer nodes.

**Independent Test**: Execute training in Trainer using valid model and shard files. Verify `TrainingOrchestrator` generates `TrainingResult` and safetensors delta. Call `trainer_p2p_node_adapter.send_update()`. Verify Client receives update file in working directory, updates `TrainingShard` in SQLite with `update_artifact_path` and `completed` status. Assert Trainer successfully removes local shard and update files while leaving the base model artifact intact.

**Acceptance Scenarios**:

1. **Given** model and shard files are staged in Trainer working directory, **When** `TrainingOrchestrator.run()` executes, **Then** training completes and yields a `TrainingResult` DTO and delta artifact.
2. **Given** training completes, **When** Trainer calls `trainer_p2p_node_adapter.send_update(client_node_id, training_result, update_artifact_path)`, **Then** Trainer's `p2p-node` streams the update delta file and transmits the `TrainingResult` payload to Client's `p2p-node`.
3. **Given** Client's `p2p-node` receives the update, **When** the file is saved into Client's working directory (overwriting if needed), **Then** Client adapter invokes `update_model` command handler with the `TrainingResult` and saved update artifact path.
4. **Given** `update_model` command handler executes in Client, **When** updating SQLite, **Then** it locates the matching `TrainingShard` in `TrainingShardRepository`, updates `update_artifact_path`, records metrics, and transitions `status` to `completed`.
5. **Given** successful confirmation of update delivery, **When** Trainer completes the workflow, **Then** Trainer immediately deletes the ephemeral dataset shard file and update artifact file from its working directory, but retains the base model artifact file.

---

### User Story 6 - Real-Time Trainer State Presentation and Progress Telemetry (Priority: P2)

As a Trainer node operator, I want real-time visibility into the training execution lifecycle via a dedicated `is_training` state flag in `TrainerState`, reflecting "waiting for task" when idle and structured execution steps / progress bars in console CLI and GUI presentation, so that node activity is immediately observable.

**Why this priority**: Operator transparency and usability. Operators running CLI or GUI need distinct, non-blocking visual feedback distinguishing between waiting for Coordinator assignments and executing multi-step P2P training workflows.

**Independent Test**: Inspect `trainer_state.is_training` before, during, and after task execution. Verify console UI prints waiting message when False, and prints step-by-step progress when True. Verify GUI displays a waiting screen when False and transition/loading animations during active training.

**Acceptance Scenarios**:

1. **Given** `TrainerState` in Trainer application, **When** initialized, **Then** `is_training` property defaults to `False`.
2. **Given** `StartTrainingHandler` begins execution, **When** task processing starts, **Then** `is_training` is set to `True`.
3. **Given** `StartTrainingHandler` completes or fails, **When** execution terminates, **Then** `is_training` is reset to `False`.
4. **Given** Trainer runs in Console UI mode, **When** `is_training` is `False`, **Then** the terminal displays a clear "Waiting for task..." indicator; **When** `is_training` is `True`, **Then** it prints ordered step-by-step progress logs and training metrics.
5. **Given** Trainer runs in Desktop GUI mode, **When** `is_training` is `False`, **Then** it displays an idle wait screen; **When** `is_training` is `True`, **Then** it renders active step progress and visual loading indicators.

---

### User Story 7 - Standardized Sidecar Containerization & Isolation (Priority: P2)

As a DevOps or systems engineer, I want Dockerfiles and Docker Compose profiles for Client and Trainer that bundle each application with its local `p2p-node` sidecar running on isolated internal networks without exposing the sidecar's gRPC port to the host or other containers, so that deployments are fully reproducible, secure, and self-contained.

**Why this priority**: Compliance with Constitution Principle I, II, and III. `p2p-node` must strictly expose its gRPC control API to localhost/sidecar internal consumers, while libp2p network ports handle external traffic.

**Independent Test**: Build and start Client and Trainer Docker Compose stacks; verify `p2p-node` starts first, healthy sidecar connection is established by Python application, and sidecar gRPC port is unreachable from outside the private container network.

**Acceptance Scenarios**:

1. **Given** Client Docker Compose configuration, **When** launched via `docker compose up`, **Then** the `p2p-node` sidecar container initializes first and enters a healthy state before Client starts.
2. **Given** Trainer Docker Compose configuration, **When** launched via `docker compose up`, **Then** the `p2p-node` sidecar container initializes first and enters a healthy state before Trainer starts.
3. **Given** both Compose stacks, **When** inspected, **Then** the `p2p-node` gRPC port (50051) is bound strictly internally between the application and sidecar and is NOT published to the host network.
4. **Given** container execution, **When** files are downloaded or saved, **Then** persistent volumes are mounted for working directories and database storage.

---

### User Story 8 - Full Distributed Training Multi-Node End-to-End Test Suite (Priority: P3)

As a validation engineer or developer, I want a comprehensive automated test sample in `samples/full_distributed_training_test/` that uses Docker Compose to orchestrate 1 Coordinator, 1 Bootstrap Relay, 1 Client (in NAT network `c`), and 2 Trainers (in NAT networks `t1` and `t2`), generates a synthetic model and 50-sample dataset, submits a training task, and verifies complete distributed P2P execution and database convergence, so that end-to-end multi-node training reliability is proven per Constitution Principle VII.

**Why this priority**: Mandatory quality gate (Constitution Principle VII). Validates real NAT traversal, DCUtR hole punching, P2P task negotiation, weight streaming, and status updates across isolated virtual networks.

**Independent Test**: Execute `python setup.py`, `python test.py`, and `python verify.py` in `samples/full_distributed_training_test/`. Verify 0 errors, full task completion across 2 trainers, and verified database/file outputs.

**Acceptance Scenarios**:

1. **Given** `data_generator.py`, **When** executed, **Then** it creates a canonical PyTorch model (`.pt2`), a 50-sample dataset (`.pt`), and a valid `training_config.json`.
2. **Given** `docker-compose.yml` in `samples/full_distributed_training_test/`, **When** configured, **Then** it creates 3 distinct isolated NAT networks (`c`, `t1`, `t2`) and 1 public network containing the Bootstrap Relay and Coordinator.
3. **Given** `setup.py`, **When** executed, **Then** it boots all containers via Docker Compose, streams startup logs, and confirms all services are healthy and responsive.
4. **Given** `test.py`, **When** executed, **Then** it submits the generated model and dataset inside the Client container, initiating task partitioning and Coordinator registration.
5. **Given** the test run completes, **When** `verify.py` inspects the environment, **Then**:
   - Coordinator scheduler assigned 1 shard each to Trainer 1 and Trainer 2.
   - Both Trainers fetched tasks, model artifacts, and shards over P2P from Client.
   - Both Trainers performed local training and uploaded delta updates over P2P to Client.
   - Client SQLite database shows all training shards updated to `completed` with saved `update_artifact_path`.
   - Ephemeral shards are cleaned up on Trainers, and base models are preserved.

---

### Edge Cases

- **Sidecar Unavailability on Boot**: What happens if the `p2p-node` binary crashes or its gRPC port is not listening when Client or Trainer starts? The `set_node_id_command` handler catches the connection timeout/failure, raises a dedicated `P2PNodeUnavailableError`, logs an actionable message ("Failed to connect to local p2p-node sidecar at <address>"), and terminates the application with exit code 1.
- **Client Offline or Unreachable during Training Fetch**: What happens if a Trainer is assigned a task by the Coordinator, but the Client node is unreachable over P2P (e.g., relay disconnection or NAT punch timeout)? The Trainer adapter attempts connection with a configurable timeout (30s). Upon failure, it logs the error, marks the task execution as failed, resets `is_training` to `False`, and emits an error log without crashing the Trainer process.
- **Base Model File Presence Check**: When verifying whether the base model exists locally in step 2, Trainer checks filesystem path existence. If the file path exists on disk, download is skipped; if absent, Trainer downloads the checkpoint from the Client over P2P.
- **Concurrent Shard Requests from Multiple Trainers**: How does Client handle concurrent requests from Trainer 1 and Trainer 2 for different shards simultaneously? The Client's `p2p-node` handles concurrent libp2p streams asynchronously, and Client database operations utilize scoped SQLite connections with busy timeouts (`busy_timeout = 5000`) and transaction locking to prevent database locked errors.
- **P2P Update Stream Interruption**: What happens if the network drops while Trainer is streaming the trained update safetensors to Client? Trainer's adapter catches the transfer failure, retains the local update artifact and shard for diagnostic inspection or retry, logs the failure, and does NOT delete the local files.
- **Existing File Conflict in Working Directory**: What happens if a file with the same name already exists in the destination working directory when receiving a model, shard, or update? Per specification, all file save operations in both Client and Trainer `p2p-node` sidecars MUST overwrite existing files cleanly (`O_TRUNC` / overwrite mode).
- **Ephemeral Shard Cleanup Failure**: What happens if deleting the temporary shard or update file fails on Trainer (e.g. file lock or permissions error)? The error is logged as a non-fatal warning, ensuring the training result report remains valid and does not fail the completed training cycle.
- **Re-request of Shard in Training or Completed State**: If a Trainer issues `get_training_task` for a shard that is already marked as `training` or `completed`, the Client unconditionally accepts the request, updates `trainer_node_id` with the requesting trainer, resets `status` to `training`, and returns the task envelope.

## Requirements *(mandatory)*

### Functional Requirements

#### P2P Node Adapter & Sidecar Integration (Data Plane)
- **FR-001**: System MUST provide a Go `p2p-node` sidecar service exposing a localhost gRPC API that supports node identity query, P2P connection establishment, and bidirectional file and message transfer.
- **FR-002**: System MUST provide a `TrainerP2PNodeAdapter` in `Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py` interfacing with the local `p2p-node` sidecar via gRPC.
- **FR-003**: System MUST provide a `ClientP2PNodeAdapter` in `Client/infrastructure/adapters/client_p2p_node_adapter.py` interfacing with the local `p2p-node` sidecar via gRPC.
- **FR-004**: System MUST resolve the `p2p-node` gRPC endpoint address from environment variables (`P2P_NODE_GRPC_ADDRESS` / `P2P_GRPC_PORT`) via centralized `ConfigManager` in both Client and Trainer.
- **FR-005**: Both `TrainerP2PNodeAdapter` and `ClientP2PNodeAdapter` MUST implement a common method `get_p2p_node_id() -> str` that queries the local sidecar for its libp2p peer ID.
- **FR-006**: Both Client (`Client/application/commands/`) and Trainer (`Trainer/application/trainer_commands/`) MUST implement a `SetNodeIdCommand` and handler that calls `get_p2p_node_id()` and updates the application state (`client_node_id` / `p2p_node_id`).
- **FR-007**: Both Client and Trainer `main.py` entry points MUST invoke `SetNodeIdCommand` as the very first operation during boot, terminating execution immediately with exit code 1 and an explicit error log if the call fails.

#### Four Core P2P Transfer Functionalities
- **FR-008**: System MUST support `get_training_task` initiated from Trainer to Client over P2P, transmitting `model_id`, `model_version`, `data_set_id`, and `shard_id`, and returning a compiled `TrainingTask` model envelope.
- **FR-009**: Client application MUST implement `GetTrainingTaskCommand` and handler which queries `ModelRepository` for model metadata, loads the referenced training configuration JSON, queries `TrainingShardRepository` for shard details, updates the shard's `trainer_node_id`, unconditionally transitions `status` to `training` in SQLite (even if previously `training` or `completed`), and returns the constructed `TrainingTask` model.
- **FR-010**: System MUST support `get_model` initiated from Trainer to Client over P2P, transmitting `model_id` and `model_version`, streaming the model checkpoint artifact over libp2p, saving it in Trainer's working directory, and returning the local file path.
- **FR-011**: Client application MUST implement `TransferModelCommand` and handler which looks up the requested model in `ModelRepository`, retrieves `model_artifact_path`, and passes the path to the P2P transfer subsystem.
- **FR-012**: System MUST support `get_shard` initiated from Trainer to Client over P2P, transmitting `model_id`, `model_version`, `data_set_id`, and `shard_id`, streaming the dataset shard file over libp2p, saving it in Trainer's working directory, and returning the local file path.
- **FR-013**: Client application MUST implement `TransferShardCommand` and handler which looks up the shard in `TrainingShardRepository`, retrieves `artifact_path`, and passes the path to the P2P transfer subsystem.
- **FR-014**: System MUST support `send_update` initiated from Trainer to Client over P2P, streaming the trained weights update artifact and transmitting the `TrainingResult` metadata to Client with no return value expected.
- **FR-015**: Client application MUST implement `UpdateModelCommand` and handler which receives `TrainingResult` and the local path to the saved update artifact, locates the matching `TrainingShard` in `TrainingShardRepository`, and updates `update_artifact_path`, metrics, and transitions `status` to `completed`.
- **FR-016**: All file saving operations performed by `p2p-node` in both Client and Trainer MUST write into their respective working directories as specified by the `WORKING_DIR` environment variable.
- **FR-017**: All file saving operations MUST overwrite existing files if a file with the identical name already exists in the target directory.
- **FR-018**: All P2P transfer and negotiation flows MUST emit structured, traceable log messages detailing transfer identifiers, bytes transferred, and transition states.

#### Trainer Execution Lifecycle & Presentation
- **FR-019**: `StartTrainingHandler` in Trainer application MUST execute the following exact sequence:
  1. Retrieve `TrainingTask` from Client via `trainer_p2p_node_adapter.get_training_task()`.
  2. Check if the required base model artifact path exists in the working directory; if the file exists on disk, skip download; if absent, download via `trainer_p2p_node_adapter.get_model()`.
  3. Retrieve dataset shard via `trainer_p2p_node_adapter.get_shard()`.
  4. Execute model training using `TrainingOrchestrator`, obtaining a `TrainingResult` and update artifact.
  5. Transmit update artifact and `TrainingResult` to Client via `trainer_p2p_node_adapter.send_update()`.
  6. Upon successful send, remove the local dataset shard file and update artifact file, while keeping the base model artifact file; if sending the update fails, retain both the shard and update files on disk for diagnostics, log the failure details, and do not remove them.
- **FR-020**: `TrainerState` in `Trainer/application/state.py` MUST maintain an `is_training` boolean property initialized to `False`.
- **FR-021**: `StartTrainingHandler` MUST set `is_training` to `True` before beginning step 1 and reset `is_training` to `False` upon completion or termination.
- **FR-022**: Trainer `console_ui.py` MUST display a "waiting for task" message when `is_training` is `False`, and print real-time training steps and execution results when `is_training` is `True`.
- **FR-023**: Trainer Desktop GUI MUST present a dedicated wait/idle screen when `is_training` is `False`, and display step progress and loading animations when `is_training` is `True`.

#### Containerization & Isolation
- **FR-024**: Client and Trainer Dockerfiles MUST be updated to support necessary runtime dependencies, working directory mounts, and environment configurations.
- **FR-025**: Client MUST provide a `docker-compose.yml` that boots `p2p-node` first, waits for healthy initialization, and launches Client connected to the local sidecar without publishing `p2p-node` gRPC to the host.
- **FR-026**: Trainer MUST provide a `docker-compose.yml` that boots `p2p-node` first, waits for healthy initialization, and launches Trainer connected to the local sidecar without publishing `p2p-node` gRPC to the host.

#### Documentation
- **FR-027**: Documentation in `p2p-node/README.md`, `Trainer/README.md`, `Client/README.md`, and `Coordinator/README.md` MUST be updated with detailed instructions for running via CLI, Docker, and Docker Compose.

#### Multi-Node Distributed Verification Sample
- **FR-028**: System MUST include a self-contained test suite in `samples/full_distributed_training_test/` simulating a production distributed training network.
- **FR-029**: `samples/full_distributed_training_test/data_generator.py` MUST generate a canonical PyTorch model (`.pt2`), a 50-sample dataset (`.pt`), and `training_config.json`.
- **FR-030**: `samples/full_distributed_training_test/docker-compose.yml` MUST configure 3 simulated NAT networks (`c`, `t1`, `t2`), 1 public network with Coordinator and Bootstrap Relay, 1 Client container with internal sidecar in `c`, and 2 Trainer containers with internal sidecars in `t1` and `t2`.
- **FR-031**: `samples/full_distributed_training_test/setup.py` and `test.py` MUST boot services, confirm health, and trigger training submission from inside the Client container.
- **FR-032**: `samples/full_distributed_training_test/verify.py` MUST verify task assignment across both trainers, successful P2P file transfers, training execution, update ingestion in Client, and database status transitions to `completed`.

### Key Entities

- **P2PNodeDescriptor**: Represents the network identity and status of a `p2p-node` sidecar instance, including `peer_id`, listen multiaddresses, reachability status, and gRPC endpoint.
- **TrainingTaskEnvelope**: Structured DTO (`TrainingTask`) encapsulating task identity (`training_task_id`), model specification (`baseline_model_id`, `baseline_model_version`), dataset coordinates (`data_set_id`, `data_set_shard_id`), training type, and hyper-parameter configurations.
- **ModelEntity**: Persistent Client record tracking top-level model metadata (`model_id`, `model_type`, `model_version`, `dataset_id`, `model_artifact_path`, `training_config_path`).
- **TrainingShardRecord**: Persistent Client record tracking individual shard lifecycle, including composite key (`model_id`, `model_version`, `dataset_id`, `shard_id`), local `artifact_path`, `sample_count`, `status` (`created`, `ready`, `training`, `completed`, `failed`), assigned `trainer_node_id`, and `update_artifact_path`.
- **TrainingResultPackage**: DTO and binary payload encapsulating local training outputs, metrics (loss, epochs), execution timing, and safetensors delta weight updates.
- **TrainerExecutionState**: In-memory state machine in Trainer tracking connectivity, registration ID, `is_training` boolean flag, and active assigned task IDs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of P2P file transfers (models, shards, updates) complete with verified SHA256 integrity and zero byte loss across NAT boundaries.
- **SC-002**: Trainer model download is bypassed 100% of the time when a valid matching model checkpoint already exists in the local working directory.
- **SC-003**: 100% of startup attempts with an unreachable or malfunctioning `p2p-node` sidecar fail fast within 5 seconds, displaying a descriptive diagnostic error message and exiting with code 1.
- **SC-004**: 100% of ephemeral dataset shard and update artifact files are deleted from the Trainer working directory upon successful update confirmation, while 100% of base model checkpoints are retained.
- **SC-005**: Shard status in Client SQLite database transitions accurately from `ready` → `training` (with `trainer_node_id` populated) → `completed` (with `update_artifact_path` populated) for 100% of processed tasks.
- **SC-006**: Both Trainer and Client sidecar gRPC endpoints remain completely unexposed to external public networks in Docker Compose configurations.
- **SC-007**: The full multi-node distributed test suite in `samples/full_distributed_training_test/` executes end-to-end and passes all verification assertions across 2 concurrent trainers without human intervention.
- **SC-008**: All state transitions and P2P communication steps emit structured log entries providing full end-to-end traceability from task assignment through update storage.

## Assumptions

- **P2P Relay & NAT Traversal**: Direct peer-to-peer data plane communication utilizes libp2p DCUtR hole punching coordinated via the Go Bootstrap Relay service.
- **Working Directory Isolation**: In multi-container environments, each container (Client, Trainer 1, Trainer 2) operates in an isolated filesystem with its own dedicated working directory mount.
- **Localhost gRPC Transport**: Python applications communicate with their respective local Go `p2p-node` sidecars over loopback TCP (or internal container bridge network) via gRPC.
- **Database Concurrency**: The Client SQLite database uses standard transaction scoping and busy timeouts to handle concurrent read/write queries from multiple worker threads without deadlock.
- **Safe Delta Storage**: Model weight updates are serialized in safetensors format to ensure secure, framework-compatible weight aggregation.
