# P2P File Transfer Test (NAT Simulation)

This sample demonstrates how the TrainSwarm P2P infrastructure facilitates file transfers between two peers behind different NATs. 

## Architecture

The test spins up 3 Docker containers to simulate a realistic internet scenario:
1. **Relay (`public-internet`)**: The bootstrap relay acts as a central discovery point.
2. **Node A (`nat-a`)**: A p2p sidecar node running in its own isolated bridge network (simulating NAT A).
3. **Node B (`nat-b`)**: A p2p sidecar node running in its own isolated bridge network (simulating NAT B).

Since Node A and Node B are on different networks, they cannot connect to each other directly using internal IP addresses. They both connect outbound to the Relay using the Docker host's IP (`host.docker.internal`). 

The test runs two Python scripts on your host:
- `receiver.py`: Connects to Node B's gRPC API (`localhost:50052`), subscribes to events, and auto-accepts incoming file transfers.
- `sender.py`: Connects to Node A's gRPC API (`localhost:50051`), dials Node B using its `/p2p-circuit` relay address, and streams a sample file.

Behind the scenes, `go-libp2p` orchestrates a DCUtR (Direct Connection Upgrade through Relay) hole punch. If successful, the connection is upgraded to direct P2P. If the simulated NAT is too restrictive, it falls back to streaming the file via the relay circuit.

## Requirements
- Docker and Docker Compose
- Python 3.10+

## How to Run

Execute the test script from a PowerShell terminal:

```powershell
.\run_test.ps1
```

If you want to keep the Docker containers running after the test to inspect logs manually:
```powershell
.\run_test.ps1 -KeepEnv
```

## How to Verify Success
1. **Logs**: You should see both Sender and Receiver logs output progress bytes.
2. **Hole Punching**: The receiver logs will print `🎉 Connection upgraded to direct (Hole punch successful!)` if the simulated NAT permitted a direct connection upgrade.
3. **File Contents**: The script will verify that `received_test_file.txt` matches the original `test_file.txt`. A green `✅ SUCCESS!` message will appear.
