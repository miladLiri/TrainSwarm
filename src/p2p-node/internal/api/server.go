package api

import (
	"context"
	"fmt"
	"net"
	"log"

	"google.golang.org/grpc"
	p2pv1 "p2p-node/internal/api/p2pv1"
	"p2p-node/internal/node"
)

type Server struct {
	p2pv1.UnimplementedP2PNodeServer
	node     *node.Node
	eventBus *EventBus
}

func NewServer(n *node.Node, eb *EventBus) *Server {
	return &Server{
		node:     n,
		eventBus: eb,
	}
}

// Start serves the gRPC API on 127.0.0.1.
func (s *Server) Start(port int) error {
	lis, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
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
	// Not fully implemented parsing multiaddrs in this mock
	return &p2pv1.ConnectResponse{
		ConnectionId: "conn-123",
		PeerId:       req.PeerId,
		State:        p2pv1.ConnectionState_STATE_DIRECT_CONNECTED,
		Direct:       true,
	}, nil
}

func (s *Server) Disconnect(ctx context.Context, req *p2pv1.DisconnectRequest) (*p2pv1.DisconnectResponse, error) {
	return &p2pv1.DisconnectResponse{Success: true}, nil
}

func (s *Server) SendFile(req *p2pv1.SendFileRequest, stream p2pv1.P2PNode_SendFileServer) error {
	return nil
}

func (s *Server) AcceptFile(req *p2pv1.AcceptFileRequest, stream p2pv1.P2PNode_AcceptFileServer) error {
	return nil
}

func (s *Server) CancelTransfer(ctx context.Context, req *p2pv1.CancelTransferRequest) (*p2pv1.CancelTransferResponse, error) {
	return &p2pv1.CancelTransferResponse{Success: true}, nil
}

func (s *Server) GetTransferStatus(ctx context.Context, req *p2pv1.GetTransferStatusRequest) (*p2pv1.TransferStatusResponse, error) {
	return &p2pv1.TransferStatusResponse{}, nil
}

func (s *Server) GetConnectionStatus(ctx context.Context, req *p2pv1.GetConnectionStatusRequest) (*p2pv1.GetConnectionStatusResponse, error) {
	return &p2pv1.GetConnectionStatusResponse{}, nil
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
