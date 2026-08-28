# Quickstart & Validation: Bootstrap Relay Server

## Prerequisites
- Docker installed
- Ports `4001` (TCP) and `4001` (UDP) available on the host machine.

## 1. Build the Docker Image
```bash
cd src/bootstrap-relay
docker build -t trainswarm/bootstrap-relay:latest .
```

## 2. Run the Service
Create a local directory for the persistent identity:
```bash
mkdir -p /tmp/relay-identity
```

Run the container:
```bash
docker run -d \
  --name ts-relay \
  -p 4001:4001/tcp \
  -p 4001:4001/udp \
  -v /tmp/relay-identity:/data \
  -e P2P_RELAY_LISTEN_TCP="/ip4/0.0.0.0/tcp/4001" \
  -e P2P_RELAY_LISTEN_QUIC="/ip4/0.0.0.0/udp/4001/quic-v1" \
  -e P2P_RELAY_IDENTITY_PATH="/data/identity.key" \
  -e P2P_RELAY_MAX_RESERVATIONS=128 \
  -e P2P_RELAY_MAX_CIRCUITS=16 \
  -e P2P_RELAY_MAX_RELAYED_BYTES=10485760 \
  -e P2P_RELAY_MAX_RELAY_DURATION="2m" \
  -e P2P_RELAY_LOG_LEVEL="debug" \
  trainswarm/bootstrap-relay:latest
```

## 3. Validation Scenarios

### Scenario 1: Identity Generation & Logging
1. Check the logs:
   ```bash
   docker logs ts-relay
   ```
2. **Expected Output**:
   - `level=info msg="Generating new Ed25519 identity" path="/data/identity.key"`
   - `level=info msg="Relay started" peer_id="12D3KooW..."`
   - `level=info msg="Listening on" addr="/ip4/0.0.0.0/tcp/4001"`
   - `level=info msg="Listening on" addr="/ip4/0.0.0.0/udp/4001/quic-v1"`

### Scenario 2: Identity Persistence
1. Stop and restart the container:
   ```bash
   docker restart ts-relay
   ```
2. Check the logs again.
3. **Expected Output**:
   - `level=info msg="Loaded existing identity" path="/data/identity.key"`
   - The `peer_id` MUST be identical to the previous run.

### Scenario 3: Accepting P2P Connections
1. Use an external tool like `go-libp2p`'s `ping` or `grpcurl` equivalent for libp2p, or wait for the Python sidecar to attempt a connection.
2. The operational logs will reflect `circuit established` once a private node reserves a slot.
