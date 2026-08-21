# TrainSwarm
Decentralized Infrastructure for Collaborative Fine-Tuning of Transformers

## System Overview

TrainSwarm coordinates distributed transformer fine-tuning across a swarm of trainer nodes:
- **Coordinator** (`src/Coordinator`): Control-plane .NET 10 Web API managing sessions, registrations, and trainer assignments (`http://localhost:5000`).
- **Bootstrap** (`src/Bootstrap`): Control-plane Python web application serving DCUtR peer registry and relay messaging (`http://localhost:6000`).
- **Trainer** (`src/Trainer`): Data-plane Python console application performing local PyTorch fine-tuning with presentation-independent architecture.
- **Client** (`src/Client`): Data-plane Python console application managing session initiation, checkpoint coordination, and aggregation.

---

## Running the Services

### 1. Coordinator Service (.NET 10)

Prerequisites: [.NET 10 SDK](https://dotnet.microsoft.com/)

```powershell
cd src/Coordinator
dotnet run --project TrainSwarm.Coordinator.Api
```
The Coordinator API listens on `http://localhost:5000`.

---

### 2. Bootstrap Relay Service (Python FastAPI)

Prerequisites: Python 3.11+

```bash
cd src/Bootstrap
pip install -r requirements.txt
python main.py
```
The Bootstrap Relay service listens on `http://localhost:6000`.

**Run in Docker:**
```bash
cd src/Bootstrap
docker build -t trainswarm-bootstrap .
docker run -p 6000:6000 --name ts-bootstrap trainswarm-bootstrap
```

---

### 3. Trainer Console Application (Python)

Prerequisites: Python 3.11+

```bash
cd src/Trainer
pip install -r requirements.txt
cp .env.example .env
python main.py
```

**Run in Docker:**
```bash
cd src/Trainer
docker build -t trainswarm-trainer .
docker run -it --rm -e BOOTSTRAP_URL="http://host.docker.internal:6000" trainswarm-trainer
```

---

### 4. Client Console Application (Python)

Prerequisites: Python 3.11+

```bash
cd src/Client
pip install -r requirements.txt
cp .env.example .env
python main.py
```

**Run in Docker:**
```bash
cd src/Client
docker build -t trainswarm-client .
docker run -it --rm -e COORDINATOR_URL="http://host.docker.internal:5000" -e BOOTSTRAP_URL="http://host.docker.internal:6000" trainswarm-client
```


