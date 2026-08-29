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

Once the setup is complete, you can run the transfer manually by acting as both the Owner and the Requester in separate terminals.

### Step 1: Create a test file in Node A
Because the Go nodes are running in Docker, the file must exist inside Node A's container so its Go backend can read it.
```powershell
docker compose exec node-a sh -c "echo 'Hello from TrainSwarm Node A!' > /tmp/test_file.txt"
```

### Step 2: Start the Owner (Node A)
In a new terminal (with the virtual environment activated), start the owner script. This script listens for incoming requests on Node A and instructs it to serve `/tmp/test_file.txt`.
```powershell
.\venv\Scripts\Activate.ps1
python owner.py 50051 /tmp/test_file.txt
```
**Important:** The script will output Node A's `Node ID` (Peer ID). Copy this ID for the next step. Leave this script running.

### Step 3: Start the Requester (Node B)
In another terminal (with the virtual environment activated), run the requester script to instruct Node B to dial Node A and pull the file. Replace `<node-a-owner-peer-id>` with the ID you copied above.
```powershell
.\venv\Scripts\Activate.ps1
python requester.py 50052 <node-a-owner-peer-id> test_file.txt localhost
```

## How to Verify Success
1. **Logs**: You should see logs indicating a successful file request message sent from Node B, and Node A's Owner script acknowledging the request and pushing the file.
2. **Hole Punching**: The receiver logs may print `🎉 Connection upgraded to direct (Hole punch successful!)` if the simulated NAT permitted a direct connection upgrade over DCUtR.
3. **File Contents**: Verify the file was securely downloaded and saved inside Node B's container:
```powershell
docker compose exec node-b cat /received_test_file.txt
```
You should see the message: `Hello from TrainSwarm Node A!`

When you are done, clean up the environment:
```powershell
.\stop.ps1
```
