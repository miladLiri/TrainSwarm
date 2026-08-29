# P2P File Transfer Test (NAT Simulation)

This sample demonstrates how the TrainSwarm P2P infrastructure facilitates file transfers between two peers behind different NATs. 

## Architecture

The test spins up 3 Docker containers to simulate a realistic internet scenario:
1. **Relay (`public-internet`)**: The bootstrap relay acts as a central discovery point.
2. **Node A (`nat-a`)**: A p2p sidecar node running in its own isolated bridge network (simulating NAT A).
3. **Node B (`nat-b`)**: A p2p sidecar node running in its own isolated bridge network (simulating NAT B).

Since Node A and Node B are on different networks, they cannot connect to each other directly using internal IP addresses. They both connect outbound to the Relay using the Docker host's IP (`host.docker.internal`). 

The test runs two Python scripts on your host:
- `owner.py`: Connects to Node A's gRPC API (`localhost:50051`), listens for requests, and pushes the requested file.
- `requester.py`: Connects to Node B's gRPC API (`localhost:50052`), dials Node A (the owner) using its `/p2p-circuit` relay address, and requests a file.

Behind the scenes, `go-libp2p` orchestrates a DCUtR (Direct Connection Upgrade through Relay) hole punch. If successful, the connection is upgraded to direct P2P. If the simulated NAT is too restrictive, it falls back to streaming the file via the relay circuit.

## Requirements
- Docker and Docker Compose
- Python 3.10+

## How to Run

First, run the setup script to start the necessary Docker containers and compile the gRPC stubs:

```powershell
.\setup.ps1
```

Once the setup is complete, determine Node A's Peer ID (the Owner), and use it to run the transfer test:

```powershell
.\test_transfer.ps1 -PeerId <node-a-owner-peer-id>
```

If you want to keep the Docker containers running after the test to inspect logs manually:
```powershell
.\test_transfer.ps1 -PeerId <node-b-peer-id> -KeepEnv
```

## How to Verify Success
1. **Logs**: You should see both Sender and Receiver logs output progress bytes.
2. **Hole Punching**: The receiver logs will print `🎉 Connection upgraded to direct (Hole punch successful!)` if the simulated NAT permitted a direct connection upgrade.
3. **File Contents**: The script will verify that `received_test_file.txt` matches the original `test_file.txt`. A green `✅ SUCCESS!` message will appear.
