package node

import (
	"context"
	"fmt"
	"time"

	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/crypto"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/multiformats/go-multiaddr"
	"github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/client"
)

func ReserveRelaySlot(ctx context.Context, h host.Host, relayAddr string) (peer.ID, error) {
	ma, err := multiaddr.NewMultiaddr(relayAddr)
	if err != nil {
		return "", fmt.Errorf("invalid relay multiaddr: %w", err)
	}

	relayInfo, err := peer.AddrInfoFromP2pAddr(ma)
	if err != nil {
		return "", fmt.Errorf("invalid relay AddrInfo: %w", err)
	}

	if err := h.Connect(ctx, *relayInfo); err != nil {
		return "", fmt.Errorf("failed to connect to relay: %w", err)
	}

	reservation, err := client.Reserve(ctx, h, *relayInfo)
	if err != nil {
		return "", fmt.Errorf("failed to reserve slot: %w", err)
	}

	// Simple background refresh
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case <-time.After(time.Until(reservation.Expiration) - 1*time.Minute):
				res, err := client.Reserve(ctx, h, *relayInfo)
				if err == nil {
					reservation = res
				} else {
					time.Sleep(30 * time.Second) // backoff
				}
			}
		}
	}()

	return relayInfo.ID, nil
}

// Node represents the P2P sidecar node.
type Node struct {
	Host        host.Host
	RelayPeerID peer.ID // peer ID of the relay this node is connected to, if any
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
		// Enable Relay (Circuit Relay v2 client)
		libp2p.EnableRelay(),
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
