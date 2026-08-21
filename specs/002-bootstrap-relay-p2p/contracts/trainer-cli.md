# Trainer Console CLI Contract

## Overview

The Trainer application is an interactive console REPL application that connects to the Bootstrap Relay on startup, manages local node state, queries peer discovery information, and displays status to the operator.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRAINER_NODE_ID` | No | `trainer-node-01` | String identifier for this trainer node. |
| `BOOTSTRAP_URL` | No | `http://localhost:6000` | Address of the Bootstrap Relay service. |
| `COORDINATOR_URL` | No | `http://localhost:5000` | Address of the Coordinator API. |
| `REQUEST_TIMEOUT_SECONDS` | No | `5.0` | HTTP request timeout in seconds. |

---

## Interactive Interface

### Startup Banner
```text
========================================
       TrainSwarm Trainer Console       
========================================
Node ID:         trainer-node-01
Peer ID:         e1f2a3b4-5678-4abc-9def-0123456789ab
Bootstrap URL:   http://localhost:6000
Coordinator URL: http://localhost:5000
Relay Status:    CONNECTED
========================================
```

### Menu Options
```text
Commands:
  1. View Node & Network Status
  2. Reconnect to Bootstrap Relay
  3. List Discovered Peers
  4. Check Coordinator Status
  5. Exit
```

### Command Behavior & Responses

#### Option 1: View Node & Network Status
Outputs detailed local state:
```text
----------------------------------------
Trainer Node Status:
  Node ID:         trainer-node-01
  Peer ID:         e1f2a3b4-5678-4abc-9def-0123456789ab
  Bootstrap URL:   http://localhost:6000
  Coordinator URL: http://localhost:5000
  Relay Status:    CONNECTED
----------------------------------------
```

#### Option 2: Reconnect to Bootstrap Relay
Attempts re-registration with the Bootstrap relay:
```text
[INFO] Connecting to Bootstrap Relay at http://localhost:6000...
[SUCCESS] Registered with Bootstrap Relay! Assigned Peer ID: e1f2a3b4-5678-4abc-9def-0123456789ab
```
*On connection error:*
```text
[ERROR] Failed to connect to Bootstrap Relay at http://localhost:6000: Connection refused.
```

#### Option 3: List Discovered Peers
Queries `/api/peers` on Bootstrap relay and lists peers:
```text
----------------------------------------
Discovered Peers in Swarm (2):
  - [client] client-node-dev (Peer ID: c9d8e7f6-5432-4cba-8fed-9876543210fe)
  - [trainer] trainer-node-01 (Peer ID: e1f2a3b4-5678-4abc-9def-0123456789ab) [Self]
----------------------------------------
```

#### Option 4: Check Coordinator Status
Pings `/api/health` or `/api/sessions` on Coordinator:
```text
[INFO] Coordinator at http://localhost:5000 is reachable.
```

#### Option 5: Exit
Exits application cleanly with status 0.