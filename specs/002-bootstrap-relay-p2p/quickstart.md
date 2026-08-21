# Quickstart & Validation Guide: Bootstrap Relay and P2P Communication

## Overview

This guide provides end-to-end validation scenarios for verifying the Bootstrap Relay service, Trainer node, and Client integration.

---

## Prerequisites

- Python 3.11+
- .NET 10 SDK (for Coordinator)
- Docker (optional for container testing)

---

## Scenario 1: Launch Bootstrap Relay & Verify Endpoints

### 1. Start Bootstrap Service
```bash
cd src/Bootstrap
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
*Expected output*:
```text
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:6000 (Press CTRL+C to quit)
```

### 2. Verify Health & Empty Peer List
```bash
curl http://localhost:6000/api/health
# Response: {"status":"healthy","service":"TrainSwarm-Bootstrap"}

curl http://localhost:6000/api/peers
# Response: []
```

---

## Scenario 2: Start Trainer Node & Verify Relay Registration

### 1. Launch Trainer Console
```bash
cd src/Trainer
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 2. Expected Startup Banner
```text
========================================
       TrainSwarm Trainer Console       
========================================
Node ID:         trainer-node-01
Peer ID:         [Assigned UUID]
Bootstrap URL:   http://localhost:6000
Coordinator URL: http://localhost:5000
Relay Status:    CONNECTED
========================================
```

### 3. Check Discovered Peers from Trainer Console
Select menu option `3` (List Discovered Peers):
```text
----------------------------------------
Discovered Peers in Swarm (1):
  - [trainer] trainer-node-01 (Peer ID: [Assigned UUID]) [Self]
----------------------------------------
```

---

## Scenario 3: Connect Client & Verify Multi-Peer Discovery

### 1. Launch Client Console
```bash
cd src/Client
python main.py
```

### 2. Check Peers on Bootstrap Relay
```bash
curl http://localhost:6000/api/peers
```
*Expected response contains both Client and Trainer peers:*
```json
[
  {
    "peerId": "[Trainer UUID]",
    "nodeId": "trainer-node-01",
    "role": "trainer"
  },
  {
    "peerId": "[Client UUID]",
    "nodeId": "client-node-dev",
    "role": "client"
  }
]
```

---

## Scenario 4: Build & Run Docker Containers

### 1. Build and Run Bootstrap Container
```bash
cd src/Bootstrap
docker build -t trainswarm-bootstrap .
docker run -d -p 6000:6000 --name ts-bootstrap trainswarm-bootstrap
```

### 2. Build and Run Trainer Container
```bash
cd src/Trainer
docker build -t trainswarm-trainer .
docker run -it --rm -e BOOTSTRAP_URL="http://host.docker.internal:6000" trainswarm-trainer
```