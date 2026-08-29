FROM golang:1.26-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /p2pd ./cmd/p2pd

FROM alpine:latest
RUN apk --no-cache add ca-certificates
COPY --from=builder /p2pd /usr/local/bin/p2pd

# Expose standard go-libp2p ports and gRPC port
EXPOSE 9000/tcp
EXPOSE 9000/udp
EXPOSE 50051/tcp

ENTRYPOINT ["p2pd"]
