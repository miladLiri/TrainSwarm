package tests

import (
	"context"
	"testing"
	"time"

	"p2p-node/internal/node"
)

func TestConnection_E2E(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 1. Create two nodes
	privA, _ := node.LoadOrGenerateIdentity("temp_a.key")
	privB, _ := node.LoadOrGenerateIdentity("temp_b.key")

	nodeA, _ := node.NewNode(ctx, privA, 0) // OS picks port
	nodeB, _ := node.NewNode(ctx, privB, 0)
	
	defer nodeA.Host.Close()
	defer nodeB.Host.Close()

	// 2. Connect them
	peerInfo := nodeB.Host.Peerstore().PeerInfo(nodeB.Host.ID())
	err := nodeA.Host.Connect(ctx, peerInfo)
	if err != nil {
		t.Fatalf("Failed to connect directly: %v", err)
	}

	// Wait for event or check connection
	conns := nodeA.Host.Network().ConnsToPeer(nodeB.Host.ID())
	if len(conns) == 0 {
		t.Fatal("Expected active connection")
	}
}
