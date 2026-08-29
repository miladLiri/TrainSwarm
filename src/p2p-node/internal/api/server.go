package api

import (
	"context"
	"fmt"
	"net"
	"log"
	"time"

	"github.com/multiformats/go-multiaddr"
	"github.com/libp2p/go-libp2p/core/peer"

	"google.golang.org/grpc"
	p2pv1 "p2p-node/internal/api/p2pv1"
	"p2p-node/internal/node"
	"p2p-node/internal/transfer"
)

type Server struct {
	p2pv1.UnimplementedP2PNodeServer
	node            *node.Node
	eventBus        *EventBus
	transferManager *transfer.Manager
}

func NewServer(n *node.Node, eb *EventBus) *Server {
	tm := transfer.NewManager(n.Host, func(ev *p2pv1.NodeEvent) {
		eb.Broadcast(ev)
	})
	return &Server{
		node:            n,
		eventBus:        eb,
		transferManager: tm,
	}
}

// Start serves the gRPC API on 0.0.0.0.
func (s *Server) Start(port int) error {
	lis, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", port))
	if err != nil {
		return fmt.Errorf("failed to listen: %w", err)
	}

	grpcServer := grpc.NewServer()
	p2pv1.RegisterP2PNodeServer(grpcServer, s)

	log.Printf("Starting gRPC server on %s", lis.Addr().String())
	return grpcServer.Serve(lis)
}

func (s *Server) GetNodeInfo(ctx context.Context, req *p2pv1.GetNodeInfoRequest) (*p2pv1.GetNodeInfoResponse, error) {
	var listenAddrs []string
	for _, addr := range s.node.Host.Addrs() {
		listenAddrs = append(listenAddrs, addr.String())
	}

	return &p2pv1.GetNodeInfoResponse{
		PeerId:         s.node.Host.ID().String(),
		ListenAddresses: listenAddrs,
		Reachability:   p2pv1.Reachability_REACHABILITY_UNKNOWN,
		GrpcApiVersion: "v1",
	}, nil
}

func (s *Server) Connect(ctx context.Context, req *p2pv1.ConnectRequest) (*p2pv1.ConnectResponse, error) {
	fmt.Printf("[gRPC API] Connect: Peer=%s, Multiaddrs=%v\n", req.PeerId, req.Multiaddrs)
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return nil, fmt.Errorf("invalid peer ID: %w", err)
	}

	var maddrs []multiaddr.Multiaddr
	for _, a := range req.Multiaddrs {
		ma, err := multiaddr.NewMultiaddr(a)
		if err == nil {
			maddrs = append(maddrs, ma)
		}
	}

	addrInfo := peer.AddrInfo{
		ID:    pid,
		Addrs: maddrs,
	}

	// Wait up to timeout_ms
	dialCtx := ctx
	if req.TimeoutMs > 0 {
		var cancel context.CancelFunc
		dialCtx, cancel = context.WithTimeout(ctx, time.Duration(req.TimeoutMs)*time.Millisecond)
		defer cancel()
	}

	if err := s.node.Host.Connect(dialCtx, addrInfo); err != nil {
		return &p2pv1.ConnectResponse{
			ConnectionId: "",
			PeerId:       req.PeerId,
			State:        p2pv1.ConnectionState_STATE_FAILED,
			Error:        err.Error(),
		}, nil
	}

	return &p2pv1.ConnectResponse{
		ConnectionId: fmt.Sprintf("%s-%s", s.node.Host.ID().String(), req.PeerId),
		PeerId:       req.PeerId,
		State:        p2pv1.ConnectionState_STATE_DIRECT_CONNECTED, // Simplification for MVP
		Direct:       true,
	}, nil
}

func (s *Server) Disconnect(ctx context.Context, req *p2pv1.DisconnectRequest) (*p2pv1.DisconnectResponse, error) {
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return nil, fmt.Errorf("invalid peer ID: %w", err)
	}

	err = s.node.Host.Network().ClosePeer(pid)
	return &p2pv1.DisconnectResponse{Success: err == nil}, err
}

func (s *Server) SendFile(req *p2pv1.SendFileRequest, stream p2pv1.P2PNode_SendFileServer) error {
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return fmt.Errorf("invalid peer ID: %w", err)
	}

	progressCh := make(chan *p2pv1.TransferEvent, 100)
	
	go func() {
		err := s.transferManager.SendFile(stream.Context(), pid, req.TransferId, req.SourcePath, req.FileName, req.FileSize, req.Sha256, progressCh)
		if err != nil {
			progressCh <- &p2pv1.TransferEvent{
				TransferId: req.TransferId,
				State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
				Error:      err.Error(),
			}
			close(progressCh)
		}
	}()

	for ev := range progressCh {
		if err := stream.Send(ev); err != nil {
			return err
		}
	}

	return nil
}

func (s *Server) AcceptFile(req *p2pv1.AcceptFileRequest, stream p2pv1.P2PNode_AcceptFileServer) error {
	progressCh := make(chan *p2pv1.TransferEvent, 100)
	
	if err := s.transferManager.AcceptFile(req.TransferId, req.DestinationPath, req.Overwrite, progressCh); err != nil {
		return err
	}

	for ev := range progressCh {
		if err := stream.Send(ev); err != nil {
			return err
		}
	}

	return nil
}

func (s *Server) CancelTransfer(ctx context.Context, req *p2pv1.CancelTransferRequest) (*p2pv1.CancelTransferResponse, error) {
	err := s.transferManager.CancelTransfer(req.TransferId)
	if err != nil {
		return &p2pv1.CancelTransferResponse{Success: false}, err
	}
	return &p2pv1.CancelTransferResponse{Success: true}, nil
}

func (s *Server) GetTransferStatus(ctx context.Context, req *p2pv1.GetTransferStatusRequest) (*p2pv1.TransferStatusResponse, error) {
	resp, err := s.transferManager.GetTransferStatus(req.TransferId)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

func (s *Server) GetConnectionStatus(ctx context.Context, req *p2pv1.GetConnectionStatusRequest) (*p2pv1.GetConnectionStatusResponse, error) {
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return nil, fmt.Errorf("invalid peer ID: %w", err)
	}

	conns := s.node.Host.Network().ConnsToPeer(pid)
	if len(conns) == 0 {
		return &p2pv1.GetConnectionStatusResponse{
			PeerId: req.PeerId,
			State:  p2pv1.ConnectionState_STATE_DISCONNECTED,
		}, nil
	}

	c := conns[0]
	return &p2pv1.GetConnectionStatusResponse{
		PeerId: req.PeerId,
		ConnectionId: c.ID(),
		State:  p2pv1.ConnectionState_STATE_DIRECT_CONNECTED,
		Direct: true,
		Transport: "tcp", // Simplified
		RemoteAddresses: []string{c.RemoteMultiaddr().String()},
		ConnectedAt: time.Now().Unix(), // Simplified
		LastActivity: time.Now().Unix(), // Simplified
	}, nil
}

func (s *Server) WatchEvents(req *p2pv1.WatchEventsRequest, stream p2pv1.P2PNode_WatchEventsServer) error {
	ch := s.eventBus.Subscribe()
	defer s.eventBus.Unsubscribe(ch)

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case event := <-ch:
			if err := stream.Send(event); err != nil {
				return err
			}
		}
	}
}

func (s *Server) RequestFile(ctx context.Context, req *p2pv1.RequestFileRequest) (*p2pv1.RequestFileResponse, error) {
	p, err := peer.Decode(req.PeerId)
	if err != nil {
		return nil, fmt.Errorf("invalid peer id: %w", err)
	}

	err = s.transferManager.RequestFile(ctx, p, req.FileName)
	if err != nil {
		return nil, err
	}

	return &p2pv1.RequestFileResponse{Success: true}, nil
}
