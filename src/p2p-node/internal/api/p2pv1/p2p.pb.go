package p2pv1

import (
	"context"
	"google.golang.org/grpc"
)

// --- Enums ---

type Reachability int32
const (
	Reachability_REACHABILITY_UNKNOWN Reachability = 0
	Reachability_REACHABILITY_PUBLIC Reachability = 1
	Reachability_REACHABILITY_PRIVATE Reachability = 2
	Reachability_REACHABILITY_RELAY_ONLY Reachability = 3
)

type ConnectionState int32
const (
	ConnectionState_STATE_DISCONNECTED ConnectionState = 0
	ConnectionState_STATE_CONNECTING ConnectionState = 1
	ConnectionState_STATE_RELAY_CONNECTED ConnectionState = 2
	ConnectionState_STATE_PUNCHING ConnectionState = 3
	ConnectionState_STATE_DIRECT_CONNECTED ConnectionState = 4
	ConnectionState_STATE_FAILED ConnectionState = 5
)

type EventType int32
const (
	EventType_EVENT_UNKNOWN EventType = 0
	EventType_EVENT_PEER_CONNECTED EventType = 1
	EventType_EVENT_PEER_DISCONNECTED EventType = 2
	EventType_EVENT_CONNECTION_UPGRADED_TO_DIRECT EventType = 3
	EventType_EVENT_HOLE_PUNCH_FAILED EventType = 4
	EventType_EVENT_TRANSFER_REQUESTED EventType = 5
	EventType_EVENT_TRANSFER_STARTED EventType = 6
	EventType_EVENT_TRANSFER_PROGRESS EventType = 7
	EventType_EVENT_TRANSFER_COMPLETED EventType = 8
	EventType_EVENT_TRANSFER_FAILED EventType = 9
	EventType_EVENT_TRANSFER_CANCELLED EventType = 10
)

// --- Messages ---

type GetNodeInfoRequest struct {}

type GetNodeInfoResponse struct {
	PeerId string
	ListenAddresses []string
	RelayAddresses []string
	Reachability Reachability
	GrpcApiVersion string
}

type ConnectRequest struct {
	PeerId string
	Multiaddrs []string
	TimeoutMs int32
}

type ConnectResponse struct {
	ConnectionId string
	PeerId string
	State ConnectionState
	Transport string
	Direct bool
	RelayAddress string
	Error string
}

type DisconnectRequest struct {
	PeerId string
}

type DisconnectResponse struct {
	Success bool
}

type GetConnectionStatusRequest struct {
	PeerId string
}

type GetConnectionStatusResponse struct {
	PeerId string
	ConnectionId string
	State ConnectionState
	Direct bool
	Transport string
	RemoteAddresses []string
	ConnectedAt int64
	LastActivity int64
}

type WatchEventsRequest struct {}

type TransferMetadata struct {
	FileName string
	FileSize int64
	Sha256 string
}

type NodeEvent struct {
	Type EventType
	PeerId string
	TransferId string
	Message string
	Metadata *TransferMetadata
}

type SendFileRequest struct {
	TransferId string
	PeerId string
	FileName string
	FileSize int64
	Sha256 string
	SourcePath string
	Overwrite bool
}

type AcceptFileRequest struct {
	TransferId string
	DestinationPath string
	Overwrite bool
}

type TransferEvent struct {
	TransferId string
	State EventType
	BytesTransferred int64
	TotalBytes int64
	SpeedBps int64
	Progress float32
	Error string
}

type CancelTransferRequest struct {
	TransferId string
}

type CancelTransferResponse struct {
	Success bool
}

type GetTransferStatusRequest struct {
	TransferId string
}

type TransferStatusResponse struct {
	TransferId string
	State EventType
	BytesTransferred int64
	TotalBytes int64
}

// --- GRPC Client/Server ---

type P2PNodeServer interface {
	GetNodeInfo(context.Context, *GetNodeInfoRequest) (*GetNodeInfoResponse, error)
	Connect(context.Context, *ConnectRequest) (*ConnectResponse, error)
	Disconnect(context.Context, *DisconnectRequest) (*DisconnectResponse, error)
	GetConnectionStatus(context.Context, *GetConnectionStatusRequest) (*GetConnectionStatusResponse, error)
	WatchEvents(*WatchEventsRequest, P2PNode_WatchEventsServer) error
	SendFile(*SendFileRequest, P2PNode_SendFileServer) error
	AcceptFile(*AcceptFileRequest, P2PNode_AcceptFileServer) error
	CancelTransfer(context.Context, *CancelTransferRequest) (*CancelTransferResponse, error)
	GetTransferStatus(context.Context, *GetTransferStatusRequest) (*TransferStatusResponse, error)
}

type UnimplementedP2PNodeServer struct {}

func (UnimplementedP2PNodeServer) GetNodeInfo(context.Context, *GetNodeInfoRequest) (*GetNodeInfoResponse, error) {
	return nil, nil
}
func (UnimplementedP2PNodeServer) Connect(context.Context, *ConnectRequest) (*ConnectResponse, error) {
	return nil, nil
}
func (UnimplementedP2PNodeServer) Disconnect(context.Context, *DisconnectRequest) (*DisconnectResponse, error) {
	return nil, nil
}
func (UnimplementedP2PNodeServer) GetConnectionStatus(context.Context, *GetConnectionStatusRequest) (*GetConnectionStatusResponse, error) {
	return nil, nil
}
func (UnimplementedP2PNodeServer) WatchEvents(*WatchEventsRequest, P2PNode_WatchEventsServer) error {
	return nil
}
func (UnimplementedP2PNodeServer) SendFile(*SendFileRequest, P2PNode_SendFileServer) error {
	return nil
}
func (UnimplementedP2PNodeServer) AcceptFile(*AcceptFileRequest, P2PNode_AcceptFileServer) error {
	return nil
}
func (UnimplementedP2PNodeServer) CancelTransfer(context.Context, *CancelTransferRequest) (*CancelTransferResponse, error) {
	return nil, nil
}
func (UnimplementedP2PNodeServer) GetTransferStatus(context.Context, *GetTransferStatusRequest) (*TransferStatusResponse, error) {
	return nil, nil
}

func RegisterP2PNodeServer(s *grpc.Server, srv P2PNodeServer) {}

type P2PNode_WatchEventsServer interface {
	Send(*NodeEvent) error
	grpc.ServerStream
}
type P2PNode_SendFileServer interface {
	Send(*TransferEvent) error
	grpc.ServerStream
}
type P2PNode_AcceptFileServer interface {
	Send(*TransferEvent) error
	grpc.ServerStream
}
