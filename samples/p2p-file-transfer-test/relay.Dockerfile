FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY src/bootstrap-relay/ ./src/bootstrap-relay/
WORKDIR /app/src/bootstrap-relay
RUN go mod download
RUN go build -o /app/relay ./cmd/relay

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/relay .
CMD ["./relay"]
