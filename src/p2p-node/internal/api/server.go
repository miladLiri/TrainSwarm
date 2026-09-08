package api

import (
	"context"
	"fmt"
	"log"
	"net"
	"sync"
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
	clientStreamMu  sync.Mutex
	clientStream    p2pv1.P2PNode_ServeClientRequestsServer
	pendingActions  map[string]chan *p2pv1.ClientActionResponse
}

func NewServer(n *node.Node, eb *EventBus) *Server {
	return NewServerWithWorkingDir(n, eb, ".")
}

func NewServerWithWorkingDir(n *node.Node, eb *EventBus, workingDir string) *Server {
	s := &Server{
		node:           n,
		eventBus:       eb,
		pendingActions: make(map[string]chan *p2pv1.ClientActionResponse),
	}
	tm := transfer.NewManagerWithConfig(n.Host, workingDir, func() string {
		if n.RelayPeerID != "" {
			return n.RelayPeerID.String()
		}
		return ""
	}, func(ev *p2pv1.NodeEvent) {
		eb.Broadcast(ev)
	})
	tm.SetClientDispatcher(s.DispatchClientAction)
	s.transferManager = tm
	return s
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

	var relayAddrs []string
	if s.node.RelayPeerID != "" {
		relayAddrs = append(relayAddrs, fmt.Sprintf("/p2p/%s/p2p-circuit/p2p/%s", s.node.RelayPeerID, s.node.Host.ID().String()))
	}

	return &p2pv1.GetNodeInfoResponse{
		PeerId:          s.node.Host.ID().String(),
		ListenAddresses: listenAddrs,
		RelayAddresses:  relayAddrs,
		Reachability:    p2pv1.Reachability_REACHABILITY_UNKNOWN,
		GrpcApiVersion:  "v1",
	}, nil
}

func (s *Server) ensurePeerAddr(pid peer.ID) {
	if s.node.RelayPeerID != "" && len(s.node.Host.Peerstore().Addrs(pid)) == 0 {
		circuitAddr, err := multiaddr.NewMultiaddr(
			fmt.Sprintf("/p2p/%s/p2p-circuit", s.node.RelayPeerID),
		)
		if err == nil {
			s.node.Host.Peerstore().AddAddr(pid, circuitAddr, time.Hour)
		}
	}
}

func (s *Server) Connect(ctx context.Context, req *p2pv1.ConnectRequest) (*p2pv1.ConnectResponse, error) {
	fmt.Printf("[gRPC API] Connect: Peer=%s\n", req.PeerId)
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return nil, fmt.Errorf("invalid peer ID: %w", err)
	}

	var maddrs []multiaddr.Multiaddr
	if s.node.RelayPeerID != "" {
		circuitAddr, err := multiaddr.NewMultiaddr(
			fmt.Sprintf("/p2p/%s/p2p-circuit", s.node.RelayPeerID),
		)
		if err == nil {
			fmt.Printf("[gRPC API] Connect: Routing via internal relay circuit: %s\n", circuitAddr)
			maddrs = append(maddrs, circuitAddr)
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
	fmt.Printf("[gRPC API] SendFile: Peer=%s, File=%s\n", req.PeerId, req.SourcePath)
	pid, err := peer.Decode(req.PeerId)
	if err != nil {
		return fmt.Errorf("invalid peer ID: %w", err)
	}

	s.ensurePeerAddr(pid)

	progressCh := make(chan *p2pv1.TransferEvent, 100)
	
	go func() {
		s.transferManager.SendFile(stream.Context(), pid, req.TransferId, req.SourcePath, req.FileName, req.FileSize, req.Sha256, progressCh)
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

	s.ensurePeerAddr(p)

	err = s.transferManager.RequestFile(ctx, p, req.FileName)
	if err != nil {
		return nil, err
	}

	return &p2pv1.RequestFileResponse{Success: true}, nil
}

func (s *Server) DispatchClientAction(ctx context.Context, req *p2pv1.ClientActionRequest) (*p2pv1.ClientActionResponse, error) {
	s.clientStreamMu.Lock()
	if s.clientStream == nil {
		s.clientStreamMu.Unlock()
		return nil, fmt.Errorf("client application is not connected to p2p-node via ServeClientRequests")
	}
	respCh := make(chan *p2pv1.ClientActionResponse, 1)
	s.pendingActions[req.RequestId] = respCh
	stream := s.clientStream
	s.clientStreamMu.Unlock()

	defer func() {
		s.clientStreamMu.Lock()
		delete(s.pendingActions, req.RequestId)
		s.clientStreamMu.Unlock()
	}()

	if err := stream.Send(req); err != nil {
		return nil, fmt.Errorf("failed to send action request to client application: %w", err)
	}

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case resp := <-respCh:
		return resp, nil
	}
}

func (s *Server) ServeClientRequests(stream p2pv1.P2PNode_ServeClientRequestsServer) error {
	s.clientStreamMu.Lock()
	s.clientStream = stream
	s.clientStreamMu.Unlock()

	defer func() {
		s.clientStreamMu.Lock()
		if s.clientStream == stream {
			s.clientStream = nil
		}
		s.clientStreamMu.Unlock()
	}()

	for {
		resp, err := stream.Recv()
		if err != nil {
			return err
		}
		s.clientStreamMu.Lock()
		ch, exists := s.pendingActions[resp.RequestId]
		s.clientStreamMu.Unlock()
		if exists && ch != nil {
			select {
			case ch <- resp:
			default:
			}
		}
	}
}

func (s *Server) GetTrainingTask(ctx context.Context, req *p2pv1.GetTrainingTaskRequest) (*p2pv1.GetTrainingTaskResponse, error) {
	pid, err := peer.Decode(req.ClientPeerId)
	if err != nil {
		return &p2pv1.GetTrainingTaskResponse{Success: false, Error: fmt.Sprintf("invalid client peer id: %v", err)}, nil
	}
	s.ensurePeerAddr(pid)

	taskJSON, err := s.transferManager.GetTrainingTask(ctx, pid, req.ModelId, req.ModelVersion, req.DataSetId, req.ShardId)
	if err != nil {
		return &p2pv1.GetTrainingTaskResponse{Success: false, Error: err.Error()}, nil
	}
	return &p2pv1.GetTrainingTaskResponse{Success: true, TrainingTaskJson: taskJSON}, nil
}

func (s *Server) GetModel(ctx context.Context, req *p2pv1.GetModelRequest) (*p2pv1.GetModelResponse, error) {
	pid, err := peer.Decode(req.ClientPeerId)
	if err != nil {
		return &p2pv1.GetModelResponse{Success: false, Error: fmt.Sprintf("invalid client peer id: %v", err)}, nil
	}
	s.ensurePeerAddr(pid)

	localPath, err := s.transferManager.GetModel(ctx, pid, req.ModelId, req.ModelVersion)
	if err != nil {
		return &p2pv1.GetModelResponse{Success: false, Error: err.Error()}, nil
	}
	return &p2pv1.GetModelResponse{Success: true, LocalFilePath: localPath}, nil
}

func (s *Server) GetShard(ctx context.Context, req *p2pv1.GetShardRequest) (*p2pv1.GetShardResponse, error) {
	pid, err := peer.Decode(req.ClientPeerId)
	if err != nil {
		return &p2pv1.GetShardResponse{Success: false, Error: fmt.Sprintf("invalid client peer id: %v", err)}, nil
	}
	s.ensurePeerAddr(pid)

	localPath, err := s.transferManager.GetShard(ctx, pid, req.ModelId, req.ModelVersion, req.DataSetId, req.ShardId)
	if err != nil {
		return &p2pv1.GetShardResponse{Success: false, Error: err.Error()}, nil
	}
	return &p2pv1.GetShardResponse{Success: true, LocalFilePath: localPath}, nil
}

func (s *Server) SendUpdate(ctx context.Context, req *p2pv1.SendUpdateRequest) (*p2pv1.SendUpdateResponse, error) {
	pid, err := peer.Decode(req.ClientPeerId)
	if err != nil {
		return &p2pv1.SendUpdateResponse{Success: false, Error: fmt.Sprintf("invalid client peer id: %v", err)}, nil
	}
	s.ensurePeerAddr(pid)

	err = s.transferManager.SendUpdate(ctx, pid, req.TrainingResultJson, req.UpdateArtifactPath)
	if err != nil {
		return &p2pv1.SendUpdateResponse{Success: false, Error: err.Error()}, nil
	}
	return &p2pv1.SendUpdateResponse{Success: true}, nil
}

