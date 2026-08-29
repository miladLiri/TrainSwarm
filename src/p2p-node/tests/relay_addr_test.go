package tests

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
	"github.com/multiformats/go-multiaddr"
	"p2p-node/internal/node"
	"p2p-node/internal/transfer"
)

func TestRelayAndNewStream_E2E(t *testing.T) {
	os.Setenv("GOLOG_LOG_LEVEL", "debug")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 1. Create a Relay Node
	relayHost, err := libp2p.New(
		libp2p.ListenAddrStrings("/ip4/127.0.0.1/tcp/0"),
		libp2p.EnableRelayService(),
	)
	if err != nil {
		t.Fatalf("Failed to create relay host: %v", err)
	}
	defer relayHost.Close()

	_, err = relay.New(relayHost)
	if err != nil {
		t.Fatalf("Failed to instantiate relay: %v", err)
	}

	relayAddrStr := fmt.Sprintf("%s/p2p/%s", relayHost.Addrs()[0], relayHost.ID())
	t.Logf("Relay listening on %s", relayAddrStr)

	tempDir := t.TempDir()

	// 2. Create Node A (Owner / Receiver of stream)
	privA, _ := node.LoadOrGenerateIdentity(tempDir + "/temp_a.key")
	nodeA, err := node.NewNode(ctx, privA, 0)
	if err != nil {
		t.Fatalf("Failed to create node A: %v", err)
	}
	defer nodeA.Host.Close()

	relayID_A, err := node.ReserveRelaySlot(ctx, nodeA.Host, relayAddrStr)
	if err != nil {
		t.Fatalf("Node A failed to reserve relay slot: %v", err)
	}
	nodeA.RelayPeerID = relayID_A

	// Register stream handlers on Node A
	managerA := transfer.NewManager(nodeA.Host, nil)
	_ = managerA

	// 3. Create Node B (Requester / Caller of NewStream)
	privB, _ := node.LoadOrGenerateIdentity(tempDir + "/temp_b.key")
	nodeB, err := node.NewNode(ctx, privB, 0)
	if err != nil {
		t.Fatalf("Failed to create node B: %v", err)
	}
	defer nodeB.Host.Close()

	relayID_B, err := node.ReserveRelaySlot(ctx, nodeB.Host, relayAddrStr)
	if err != nil {
		t.Fatalf("Node B failed to reserve relay slot: %v", err)
	}
	nodeB.RelayPeerID = relayID_B

	// 4. Connect Node B to Node A via Circuit Address
	// Correct circuit address for target Node A is /p2p/<relayID>/p2p-circuit (or with /ip4/...)
	circuitAddr, err := multiaddr.NewMultiaddr(fmt.Sprintf("/p2p/%s/p2p-circuit", relayHost.ID()))
	if err != nil {
		t.Fatalf("Failed to create circuit addr: %v", err)
	}

	addrInfoA := peer.AddrInfo{
		ID:    nodeA.Host.ID(),
		Addrs: []multiaddr.Multiaddr{circuitAddr},
	}

	t.Logf("Node B dialing Node A via AddrInfo: ID=%s Addrs=%v", addrInfoA.ID, addrInfoA.Addrs)
	if err := nodeB.Host.Connect(ctx, addrInfoA); err != nil {
		t.Fatalf("Node B failed to connect to Node A: %v", err)
	}
	t.Logf("Node B successfully connected to Node A via relay circuit!")

	connsB := nodeB.Host.Network().ConnsToPeer(nodeA.Host.ID())
	t.Logf("Node B conns to Node A count: %d", len(connsB))
	for i, c := range connsB {
		t.Logf("  node B conn[%d]: Local=%s Remote=%s", i, c.LocalMultiaddr(), c.RemoteMultiaddr())
	}

	connsA := nodeA.Host.Network().ConnsToPeer(nodeB.Host.ID())
	t.Logf("Node A conns to Node B count: %d", len(connsA))
	for i, c := range connsA {
		t.Logf("  node A conn[%d]: Local=%s Remote=%s", i, c.LocalMultiaddr(), c.RemoteMultiaddr())
	}

	managerB := transfer.NewManager(nodeB.Host, nil)

	t.Logf("Node B calling managerB.RequestFile...")
	err = managerB.RequestFile(ctx, nodeA.Host.ID(), "test_file.txt")
	if err != nil {
		t.Fatalf("managerB.RequestFile failed: %v", err)
	}
	t.Logf("managerB.RequestFile SUCCEEDED!")
}
