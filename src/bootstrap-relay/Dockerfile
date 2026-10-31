FROM golang:alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bootstrap-relay ./cmd/relay

FROM alpine:latest
RUN apk --no-cache add ca-certificates
COPY --from=builder /bootstrap-relay /usr/local/bin/bootstrap-relay

# Expose standard go-libp2p ports
EXPOSE 4001/tcp
EXPOSE 4001/udp
EXPOSE 8090/tcp

# Runtime environment defaults for containerized relay
ENV P2P_RELAY_LISTEN_TCP="/ip4/0.0.0.0/tcp/4001"
ENV P2P_RELAY_LISTEN_QUIC="/ip4/0.0.0.0/udp/4001/quic-v1"
ENV P2P_RELAY_LISTEN_HTTP="8090"
ENV P2P_RELAY_IDENTITY_PATH="/data/relay.key"
ENV P2P_RELAY_LOG_LEVEL="info"

RUN mkdir -p /data
VOLUME ["/data"]

ENTRYPOINT ["bootstrap-relay"]
