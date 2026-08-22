package nat

import (
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/p2p/protocol/holepunch"
)

// EnableDCUtR starts the hole-punching service on the host.
func EnableDCUtR(h host.Host) (*holepunch.Service, error) {
	// go-libp2p EnableHolePunching is usually passed as an option in libp2p.New,
	// but we can also manually initialize the service if needed.
	// We'll assume libp2p.EnableHolePunching() is set in node.go
	return holepunch.NewService(h)
}
