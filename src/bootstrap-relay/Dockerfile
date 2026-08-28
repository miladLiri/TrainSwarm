FROM golang:1.26-alpine AS builder

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

ENTRYPOINT ["bootstrap-relay"]
