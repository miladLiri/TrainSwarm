package nat

import (
	"context"
	"fmt"
	"time"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/client"
)

// SetupRelayClient connects to a relay and ensures the reservation is maintained.
func SetupRelayClient(ctx context.Context, h host.Host, relayInfo peer.AddrInfo) error {
	if err := h.Connect(ctx, relayInfo); err != nil {
		return fmt.Errorf("failed to connect to relay: %w", err)
	}

	reservation, err := client.Reserve(ctx, h, relayInfo)
	if err != nil {
		return fmt.Errorf("failed to reserve slot on relay: %w", err)
	}

	// Background refresh loop (every 2 minutes, max 5 retries on failure)
	go func() {
		retries := 0
		for {
			select {
			case <-ctx.Done():
				return
			// The reservation has an expiration, we refresh slightly before
			case <-time.After(time.Until(reservation.Expiration) - 1*time.Minute):
				res, err := client.Reserve(ctx, h, relayInfo)
				if err != nil {
					retries++
					if retries > 5 {
						return // Max retries exceeded
					}
					// Exponential backoff
					time.Sleep(time.Duration(1<<retries) * time.Second)
				} else {
					reservation = res
					retries = 0
				}
			}
		}
	}()

	return nil
}
