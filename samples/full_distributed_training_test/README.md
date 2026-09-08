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

## Running the Test Suite

### Step 1: Environment Setup
Launches the full multi-node stack (Relay, Coordinator, Client + Sidecar, 2 Trainers + Sidecars) and monitors health:
```bash
python setup.py
```
*(In Docker environments, runs `docker compose up --build -d`. In non-Docker environments, runs the equivalent topology locally via background processes).*

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
Clean up containers and background processes:
```bash
python setup.py --stop
```
