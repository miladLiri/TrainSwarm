package node

import (
	"context"
	"fmt"

	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/crypto"
	"github.com/libp2p/go-libp2p/core/host"
)

// Node represents the P2P sidecar node.
type Node struct {
	Host host.Host
}

// NewNode creates a new libp2p host with the given private key and port.
func NewNode(ctx context.Context, priv crypto.PrivKey, port int) (*Node, error) {
	// TCP and QUIC listeners
	listenAddrs := libp2p.ListenAddrStrings(
		fmt.Sprintf("/ip4/0.0.0.0/tcp/%d", port),
		fmt.Sprintf("/ip4/0.0.0.0/udp/%d/quic-v1", port),
	)

	h, err := libp2p.New(
		libp2p.Identity(priv),
		listenAddrs,
		libp2p.DefaultTransports,
		libp2p.DefaultSecurity,
		libp2p.DefaultMuxers,
		// NATPortMap attempts to open ports using UPnP/NAT-PMP
		libp2p.NATPortMap(),
		// Enable AutoNAT as a client
		libp2p.EnableNATService(),
		// Enable DCUtR (hole punching)
		libp2p.EnableHolePunching(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create libp2p host: %w", err)
	}

	return &Node{Host: h}, nil
}
