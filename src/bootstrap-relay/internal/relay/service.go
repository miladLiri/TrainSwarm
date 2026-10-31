package relay

import (
	"fmt"
	"log"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	circuitv2 "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
	"bootstrap-relay/internal/config"
)

func NewRelayService(h host.Host, cfg *config.Config) (*circuitv2.Relay, error) {
	resources := circuitv2.DefaultResources()
	
	// Apply limits from config
	resources.MaxReservations = cfg.MaxReservations
	resources.MaxCircuits = cfg.MaxCircuits

	var opts []circuitv2.Option
	if cfg.MaxRelayedBytes <= 0 {
		// Disable per-circuit data limits for large model and dataset transfers
		resources.Limit = nil
		opts = append(opts, circuitv2.WithResources(resources), circuitv2.WithInfiniteLimits())
		log.Printf("level=info msg=\"Circuit relay initialized with infinite data limits\"")
	} else {
		if resources.Limit == nil {
			resources.Limit = circuitv2.DefaultLimit()
		}
		resources.Limit.Data = cfg.MaxRelayedBytes
		if cfg.MaxRelayDuration > 0 {
			resources.Limit.Duration = cfg.MaxRelayDuration
		}
		opts = append(opts, circuitv2.WithResources(resources))
		log.Printf("level=info msg=\"Circuit relay initialized with limits\" max_relayed_bytes=%d max_duration=%v", cfg.MaxRelayedBytes, cfg.MaxRelayDuration)
	}

	r, err := circuitv2.New(h, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create circuit relay v2: %w", err)
	}

	// Attach basic logging hooks via network notifications
	h.Network().Notify(&network.NotifyBundle{
		ConnectedF: func(n network.Network, c network.Conn) {
			log.Printf("level=debug msg=\"Connected\" peer_id=\"%s\" remote_addr=\"%s\"", c.RemotePeer(), c.RemoteMultiaddr())
		},
		DisconnectedF: func(n network.Network, c network.Conn) {
			log.Printf("level=debug msg=\"Disconnected\" peer_id=\"%s\"", c.RemotePeer())
		},
	})

	return r, nil
}
