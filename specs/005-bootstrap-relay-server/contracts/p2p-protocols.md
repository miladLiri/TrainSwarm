# Interfaces & Contracts: Bootstrap Relay Server

The Bootstrap Relay Server exposes no custom HTTP or gRPC APIs. Its entire network interface is strictly standard go-libp2p multiplexed streams.

## 1. LibP2P Identify Protocol
- **Protocol ID**: `/ipfs/id/1.0.0`
- **Purpose**: Expose the server's public key, PeerID, and observed listening multiaddresses.
- **Contract**: Handled implicitly by `go-libp2p` base host.

## 2. Circuit Relay v2 (Hop)
- **Protocol ID**: `/libp2p/circuit/relay/0.2.0/hop`
- **Purpose**: Allow peers to reserve slots and request a circuit to a destination peer.
- **Messages**: 
  - `RESERVE` (allocates a slot on the relay)
  - `CONNECT` (requests a proxy stream to another node)
- **Contract**: Strict adherence to the standard `go-libp2p` relay service. DCUtR messages traverse inside these established circuits opaquely.
