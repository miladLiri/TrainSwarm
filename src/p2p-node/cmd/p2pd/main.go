package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"p2p-node/internal/api"
	"p2p-node/internal/node"
)

func main() {
	keyPath := flag.String("key", "identity.key", "Path to libp2p private key file")
	p2pPort := flag.Int("p2p-port", 9000, "Port for P2P connections")
	grpcPort := flag.Int("grpc-port", 50051, "Port for localhost gRPC API")
	relayHost := flag.String("relay-host", os.Getenv("RELAY_HOST"), "IP or hostname of the relay server to fetch PeerID from")
	relayPort := flag.String("relay-port", "4001", "TCP port of the relay server")
	flag.Parse()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	log.Println("Starting p2pd...")

	// Load or generate identity
	priv, err := node.LoadOrGenerateIdentity(*keyPath)
	if err != nil {
		log.Fatalf("Failed to initialize identity: %v", err)
	}

	// Create libp2p host
	p2pNode, err := node.NewNode(ctx, priv, *p2pPort)
	if err != nil {
		log.Fatalf("Failed to create p2p node: %v", err)
	}
	defer p2pNode.Host.Close()

	log.Printf("P2P Node ID: %s", p2pNode.Host.ID().String())
	for _, addr := range p2pNode.Host.Addrs() {
		log.Printf("Listening on: %s/p2p/%s", addr.String(), p2pNode.Host.ID().String())
	}

	relayAddr := ""
	if *relayHost != "" {
		var relayPeerID string
		for i := 0; i < 30; i++ {
			resp, err := http.Get(fmt.Sprintf("http://%s:80/peerid", *relayHost))
			if err == nil {
				body, err := io.ReadAll(resp.Body)
				resp.Body.Close()
				if err == nil && len(body) > 0 {
					relayPeerID = strings.TrimSpace(string(body))
					break
				}
			}
			log.Printf("Waiting for relay HTTP API at %s:80...", *relayHost)
			time.Sleep(2 * time.Second)
		}
		if relayPeerID == "" {
			log.Fatalf("Failed to fetch relay peer ID from %s:80 after retries", *relayHost)
		}

		prefix := "/dns4"
		if net.ParseIP(*relayHost) != nil {
			prefix = "/ip4"
		}
		relayAddr = fmt.Sprintf("%s/%s/tcp/%s/p2p/%s", prefix, *relayHost, *relayPort, relayPeerID)
		log.Printf("Constructed Relay Multiaddr: %s", relayAddr)
	}

	if relayAddr != "" {
		if err := node.ReserveRelaySlot(ctx, p2pNode.Host, relayAddr); err != nil {
			log.Printf("Warning: failed to reserve slot on relay %s: %v", relayAddr, err)
		} else {
			log.Printf("Successfully reserved slot on relay %s", relayAddr)
		}
	}

	// Create event bus and gRPC server
	eventBus := api.NewEventBus()
	server := api.NewServer(p2pNode, eventBus)

	// Run server in goroutine
	errCh := make(chan error, 1)
	go func() {
		if err := server.Start(*grpcPort); err != nil {
			errCh <- err
		}
	}()

	// Wait for shutdown signal or error
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-errCh:
		log.Fatalf("Server error: %v", err)
	case <-sigCh:
		log.Println("Shutting down...")
	}
}
