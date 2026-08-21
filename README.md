# TrainSwarm
Decentralized Infrastructure for Collaborative Fine-Tuning of Transformers

## System Overview

TrainSwarm coordinates distributed transformer fine-tuning across a swarm of trainer nodes:
- **Coordinator** (`src/Coordinator`): Control-plane .NET 10 Web API managing sessions, registrations, and trainer assignments.
- **Client** (`src/Client`): Data-plane Python console application managing session initiation, checkpoint coordination, and aggregation.
- **Trainer**: Data-plane Python console application performing local PyTorch fine-tuning.
- **Bootstrap**: Control-plane Python web application serving peer discovery and DCUtR relay communication.

---

## Running the Services

### 1. Coordinator Service (.NET)

Prerequisites: [.NET 10 SDK](https://dotnet.microsoft.com/)

```powershell
cd src/Coordinator
dotnet run --project TrainSwarm.Coordinator.Api
```

The Coordinator API will listen on `http://localhost:5000`.

### 2. Client Console Application (Python)

Prerequisites: Python 3.11+

```bash
cd src/Client

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run Client console REPL
python main.py
```

### 3. Running Client in Docker

```bash
cd src/Client
docker build -t trainswarm-client .
docker run -it --rm -e COORDINATOR_URL="http://host.docker.internal:5000" trainswarm-client
```

