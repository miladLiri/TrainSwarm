FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY src/p2p-node/ ./src/p2p-node/
WORKDIR /app/src/p2p-node
RUN go mod download
RUN go build -o /app/p2pd ./cmd/p2pd

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/p2pd .
CMD ["./p2pd"]
