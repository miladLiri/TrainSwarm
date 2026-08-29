# Validation Quickstart: Go P2P Sidecar

This guide provides steps to validate the Go P2P sidecar executable in a simulated network environment. 

## Prerequisites

1. **Go 1.21+** installed (`go version`)
2. `grpcurl` installed to interact with the localhost gRPC API without needing to write a Python client immediately.
3. Access to a public libp2p Circuit Relay v2 node (or run a local one).

## 1. Build and Run Sidecars

Build the sidecar executable:
```bash
cd src/p2p-node
go build -o p2pd.exe ./cmd/p2pd
```

Open two terminal windows to represent Node A (Sender) and Node B (Receiver).

**Terminal 1 (Node A):**
```bash
./p2pd.exe --port 5001 --grpc-port 9001 --identity ./nodeA.key
```

**Terminal 2 (Node B):**
```bash
./p2pd.exe --port 5002 --grpc-port 9002 --identity ./nodeB.key
```

## 2. Inspect Node Info

Use `grpcurl` to get Node B's PeerID and listening addresses:
```bash
grpcurl -plaintext localhost:9002 p2p.v1.P2PNode/GetNodeInfo
```
*Note the returned `peer_id` and `relay_addresses` (or `listen_addresses` if testing locally without a relay).*

## 3. Establish Connection & Observe DCUtR

Subscribe to events on Node A to watch the connection upgrade process:
```bash
grpcurl -plaintext localhost:9001 p2p.v1.P2PNode/WatchEvents
```

In a new terminal, tell Node A to connect to Node B:
```bash
grpcurl -plaintext -d '{"peer_id": "<NODE_B_PEER_ID>"}' localhost:9001 p2p.v1.P2PNode/Connect
```

**Expected Event Output (Node A's WatchEvents stream):**
1. `EVENT_PEER_CONNECTED`
2. `EVENT_CONNECTION_UPGRADED_TO_DIRECT` (shortly after, as DCUtR hole punches in the background)

## 4. Test File Transfer

Create a dummy 100MB file on Node A:
```bash
# Windows
fsutil file createnew testfile.dat 104857600
# Linux/macOS
dd if=/dev/urandom of=testfile.dat bs=1M count=100
```

Subscribe to events on Node B to receive incoming transfer requests:
```bash
grpcurl -plaintext localhost:9002 p2p.v1.P2PNode/WatchEvents
```

From Node A, initiate the file send:
```bash
grpcurl -plaintext -d '{
  "transfer_id": "tx-1234",
  "peer_id": "<NODE_B_PEER_ID>",
  "file_name": "testfile.dat",
  "file_size": 104857600,
  "sha256": "<hash>",
  "source_path": "./testfile.dat"
}' localhost:9001 p2p.v1.P2PNode/SendFile
```

Node B's event stream will emit `EVENT_TRANSFER_REQUESTED`.
Accept the file on Node B:
```bash
grpcurl -plaintext -d '{
  "transfer_id": "tx-1234",
  "destination_path": "./received_testfile.dat",
  "overwrite": false
}' localhost:9002 p2p.v1.P2PNode/AcceptFile
```

Both Node A's `SendFile` stream and Node B's `AcceptFile` stream will output `EVENT_TRANSFER_PROGRESS` followed by `EVENT_TRANSFER_COMPLETED`.

Verify `received_testfile.dat` matches `testfile.dat` exactly.

### Alternative: Pull / Request Workflow
Alternatively, Node B can explicitly request a file from Node A:
```bash
grpcurl -plaintext -d '{"peer_id": "<NODE_A_PEER_ID>", "file_name": "testfile.dat"}' localhost:9002 p2p.v1.P2PNode/RequestFile
```
Node A's `WatchEvents` stream emits `EVENT_FILE_REQUESTED`, allowing Node A to initiate `SendFile`.
