# Full Distributed Training Multi-Node NAT Verification Test

This sample validates end-to-end distributed training across isolated nodes behind simulated NAT networks communicating via peer-to-peer data transfers over a libp2p Circuit Relay v2.

## Topology

```
+-----------------------------------------------------------------------------------+
|                               Public Network                                      |
|                                                                                   |
|    +-----------------------------+        +----------------------------------+    |
|    |     Bootstrap Relay         |        |           Coordinator            |    |
|    | (go-libp2p circuit relay v2)|        | (.NET ASP.NET REST & gRPC API)   |    |
|    +-----------------------------+        +----------------------------------+    |
+-------------------^---------------------------------------^-----------------------+
                    | (Circuit Relay v2)                    |
       +------------+------------+                          | (Task Scheduling)
       |                         |                          |
+------v-------------+  +--------v-----------+  +-----------v--------+
|    NAT Network c   |  |   NAT Network t1   |  |   NAT Network t2   |
|                    |  |                    |  |                    |
| +----------------+ |  | +----------------+ |  | +----------------+ |
| |   Client App   | |  | | Trainer 1 App  | |  | | Trainer 2 App  | |
| +-------^--------+ |  | +-------^--------+ |  | +-------^--------+ |
|         | gRPC     |  |         | gRPC     |  |         | gRPC     |
| +-------v--------+ |  | +-------v--------+ |  | +-------v--------+ |
| |  Client Sidecar| |  | |Trainer 1 Sidecar| | | |Trainer 2 Sidecar| |
| |   (p2p-node)   | |  | |   (p2p-node)   | |  | |   (p2p-node)   | |
| +----------------+ |  | +----------------+ |  | +----------------+ |
+--------------------+  +--------------------+  +--------------------+
```

## Running Without Docker (Native Local Execution)

For local development or environments without Docker / Docker Compose installed, run the automated all-in-one runner:

```bash
cd samples/full_distributed_training_test
python run_local.py
```

This script:
1. Verifies test artifacts exist (or generates them via `data_generator.py`).
2. Cleans up lingering processes on ports 4001, 8090, 8080, 8081, 50051-50053, 9001-9003.
3. Launches all 8 services in background processes with independent working directories:
   - **Bootstrap Relay**: Port 4001 (P2P), Port 8090 (Health HTTP)
   - **Coordinator**: Port 8080 (REST HTTP), Port 8081 (gRPC)
   - **Client p2p-node**: Port 9001 (P2P), Port 50051 (gRPC)
   - **Trainer 1 p2p-node**: Port 9002 (P2P), Port 50052 (gRPC)
   - **Trainer 2 p2p-node**: Port 9003 (P2P), Port 50053 (gRPC)
   - **Client daemon**: Connects to 50051 and listens for inbound P2P transfers
   - **Trainer 1**: Connects to Coordinator & sidecar 50052
   - **Trainer 2**: Connects to Coordinator & sidecar 50053
4. Submits the training task with `OVERRIDE_SHARD_SIZE=25` (2 shards).
5. Monitors Client SQLite database (`training.db`) until all shards reach `completed`.
6. Asserts artifact presence, trainer assignments, and ephemeral file purge.
7. Automatically tears down all background processes and cleans up.

---

## Running With Docker Compose

### Step 1: Environment Setup
Launches the full multi-node stack in isolated Docker containers:
```bash
python setup.py
```

### Step 2: Submit Training Task
Submits a canonical `.pt2` model checkpoint and 50-sample dataset partitioned into 2 shards:
```bash
python test.py
```

### Step 3: Verify Results
Monitors and verifies that:
1. Both shards transition to `completed` in Client SQLite (`training.db`).
2. Both shards have `trainer_node_id` populated with distinct trainer IDs.
3. Update delta `.safetensors` files exist in Client's working directory.
4. Ephemeral `.pt` shards and `.safetensors` updates are deleted from Trainers while retaining the base model in cache.
```bash
python verify.py
```

### Step 4: Teardown
Clean up containers:
```bash
python setup.py --stop
```
