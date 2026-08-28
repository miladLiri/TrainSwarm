package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"p2p-node/internal/api"
	"p2p-node/internal/node"
)

func main() {
	keyPath := flag.String("key", "identity.key", "Path to libp2p private key file")
	p2pPort := flag.Int("p2p-port", 9000, "Port for P2P connections")
	grpcPort := flag.Int("grpc-port", 50051, "Port for localhost gRPC API")
	relayAddr := flag.String("relay", "", "Optional multiaddress of a relay to connect and reserve a slot on")
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

	if *relayAddr != "" {
		if err := node.ReserveRelaySlot(ctx, p2pNode.Host, *relayAddr); err != nil {
			log.Printf("Warning: failed to reserve slot on relay %s: %v", *relayAddr, err)
		} else {
			log.Printf("Successfully reserved slot on relay %s", *relayAddr)
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
