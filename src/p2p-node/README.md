# TrainSwarm `p2p-node` Sidecar

The `p2p-node` is a high-performance Go microservice that serves as a private data-plane sidecar for TrainSwarm Clients and Trainers. It manages libp2p peer identities, relays traffic over Circuit Relay v2, handles NAT traversal / hole punching, and streams training models, dataset shards, and trained weights deltas directly between peers.

## Architecture

```
+-------------------------------------------------------------------------+
|                              p2p-node                                   |
|                                                                         |
|  +---------------------------+       +-------------------------------+  |
|  |       gRPC API Server     |       |    Transfer & Stream Manager  |  |
|  |      (Port 50051 TCP)     |       |       (go-libp2p streams)     |  |
|  +-------------^-------------+       +---------------^---------------+  |
|                |                                     |                  |
+----------------|-------------------------------------|------------------+
                 | gRPC                                | Libp2p (TCP/QUIC)
                 v                                     v
       Local Application (Client/Trainer)       Remote Peer / Circuit Relay v2
```

## Libp2p Protocols

| Protocol ID | Description | Direction |
|-------------|-------------|-----------|
| `/trainswarm/task/1.0.0` | Query training task envelope specification | Trainer $\rightarrow$ Client |
| `/trainswarm/model/1.0.0` | Stream baseline model checkpoint (`.pt2`) | Trainer $\rightarrow$ Client |
| `/trainswarm/shard/1.0.0` | Stream assigned dataset shard (`.pt`) | Trainer $\rightarrow$ Client |
| `/trainswarm/update/1.0.0` | Transmit trained weights delta (`.safetensors`) + `TrainingResult` metadata | Trainer $\rightarrow$ Client |

## gRPC Service Contract (`P2PNode`)

Defined in `p2p.proto` / `p2pv1`:

- `GetNodeInfo(GetNodeInfoRequest) returns (GetNodeInfoResponse)`: Returns local libp2p peer ID and relay multiaddresses.
- `GetTrainingTask(TrainingTaskRequest) returns (TrainingTaskResponse)`: Sends task query to remote client peer.
- `GetModel(ModelTransferRequest) returns (FileTransferResponse)`: Downloads base model checkpoint and saves to `WORKING_DIR`.
- `GetShard(ShardTransferRequest) returns (FileTransferResponse)`: Downloads assigned shard and saves to `WORKING_DIR`.
- `SendUpdate(UpdateTransferRequest) returns (UpdateTransferResponse)`: Streams local update weights delta and metadata to client.
- `ServeClientRequests(stream ClientActionResponse) returns (stream ClientActionRequest)`: Bidirectional stream connecting local Client application to dispatch inbound P2P transfer requests.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RELAY_HOST` | Hostname or IP of the bootstrap relay | `127.0.0.1` |
| `RELAY_PORT` | P2P listening port of the relay | `4001` |
| `RELAY_HTTP_PORT` | HTTP port of the relay for peer discovery | `8090` |
| `P2P_PORT` | Local libp2p listening port | `9000` |
| `GRPC_PORT` | Local gRPC management port | `50051` |
| `WORKING_DIR` | Directory where transferred files are staged/saved | `.` |
| `IDENTITY_PATH` | Path to save/load libp2p private key | `/tmp/p2p_node.key` |

## Building & Running

### From Source
```bash
go build -o p2pd ./cmd/p2pd
./p2pd
```

### Via Docker
```bash
docker build -t trainswarm/p2p-node .
docker run -d \
  -e RELAY_HOST=relay \
  -e WORKING_DIR=/artifacts \
  -v trainer-artifacts:/artifacts \
  trainswarm/p2p-node
```
