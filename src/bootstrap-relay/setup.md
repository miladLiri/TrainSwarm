# Setup & Run Instructions

## Prerequisites
- Docker installed
- Host ports `4001` TCP/UDP available

## Build
```bash
docker build -t trainswarm/bootstrap-relay:latest .
```

## Run
Create a directory to store the identity key persistently:
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
