package relay

import (
	"context"
	"fmt"

	"bootstrap-relay/internal/config"
	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/crypto"
	"github.com/libp2p/go-libp2p/core/host"
)

func NewHost(ctx context.Context, priv crypto.PrivKey, cfg *config.Config) (host.Host, error) {
	listenAddrs := []string{cfg.ListenTCP}
	if cfg.ListenQUIC != "" {
		listenAddrs = append(listenAddrs, cfg.ListenQUIC)
	}

	opts := []libp2p.Option{
		libp2p.Identity(priv),
		libp2p.ListenAddrStrings(listenAddrs...),
		// The identify protocol is enabled by default in go-libp2p, but we can explicitly state it
		// NATPortMap is disabled because this is a public server and shouldn't use UPnP
	}

	h, err := libp2p.New(opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create libp2p host: %w", err)
	}

	return h, nil
}
