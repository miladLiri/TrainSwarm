package transfer

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/multiformats/go-multiaddr"
	"p2p-node/internal/api/p2pv1"
)

const ProtocolID = "/trainswarm/file/1.0.0"
const RequestProtocolID = "/trainswarm/request/1.0.0"

const (
	TaskProtocolID   = "/trainswarm/task/1.0.0"
	ModelProtocolID  = "/trainswarm/model/1.0.0"
	ShardProtocolID  = "/trainswarm/shard/1.0.0"
	UpdateProtocolID = "/trainswarm/update/1.0.0"
)

// Wire Messages
type TransferRequest struct {
	FileName string `json:"file_name"`
	FileSize int64  `json:"file_size"`
	SHA256   string `json:"sha256"`
}

type RequestWireMsg struct {
	FileName string `json:"file_name"`
}

type TransferResponse struct {
	Accepted bool   `json:"accepted"`
	Reason   string `json:"reason"`
}

// P2P Workflow Wire Messages
type TaskWireReq struct {
	ModelID      string `json:"model_id"`
	ModelVersion string `json:"model_version"`
	DataSetID    string `json:"data_set_id"`
	ShardID      string `json:"shard_id"`
}

type TaskWireResp struct {
	Success          bool   `json:"success"`
	Error            string `json:"error,omitempty"`
	TrainingTaskJSON string `json:"training_task_json,omitempty"`
}

type ModelWireReq struct {
	ModelID      string `json:"model_id"`
	ModelVersion string `json:"model_version"`
}

type ShardWireReq struct {
	ModelID      string `json:"model_id"`
	ModelVersion string `json:"model_version"`
	DataSetID    string `json:"data_set_id"`
	ShardID      string `json:"shard_id"`
}

type FileWireHeader struct {
	Success  bool   `json:"success"`
	Error    string `json:"error,omitempty"`
	FileName string `json:"file_name,omitempty"`
	FileSize int64  `json:"file_size,omitempty"`
}

type UpdateWireReq struct {
	TrainingResultJSON string `json:"training_result_json"`
	FileName           string `json:"file_name"`
	FileSize           int64  `json:"file_size"`
}

type UpdateWireResp struct {
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
}

type Manager struct {
	host             host.Host
	workingDir       string
	relayPeerIDFunc  func() string
	pendingTransfers map[string]*PendingIncoming
	mu               sync.Mutex
	EventCallback    func(*p2pv1.NodeEvent)
	ClientDispatcher func(ctx context.Context, req *p2pv1.ClientActionRequest) (*p2pv1.ClientActionResponse, error)
}

type PendingIncoming struct {
	Stream   network.Stream
	Metadata TransferRequest
	AcceptCh chan AcceptDecision
}

type AcceptDecision struct {
	Accepted bool
	DestPath string
	Overwrite bool
	Progress chan *p2pv1.TransferEvent
}

func NewManager(h host.Host, eventCb func(*p2pv1.NodeEvent)) *Manager {
	return NewManagerWithConfig(h, ".", nil, eventCb)
}

func NewManagerWithConfig(h host.Host, workingDir string, relayPeerIDFunc func() string, eventCb func(*p2pv1.NodeEvent)) *Manager {
	if workingDir == "" {
		workingDir = "."
	}
	m := &Manager{
		host:             h,
		workingDir:       workingDir,
		relayPeerIDFunc:  relayPeerIDFunc,
		pendingTransfers: make(map[string]*PendingIncoming),
		EventCallback:    eventCb,
	}
	h.SetStreamHandler(ProtocolID, m.handleIncomingStream)
	h.SetStreamHandler(RequestProtocolID, m.handleFileRequestStream)
	h.SetStreamHandler(TaskProtocolID, m.handleTaskStream)
	h.SetStreamHandler(ModelProtocolID, m.handleModelStream)
	h.SetStreamHandler(ShardProtocolID, m.handleShardStream)
	h.SetStreamHandler(UpdateProtocolID, m.handleUpdateStream)
	return m
}

func (m *Manager) SetWorkingDir(dir string) {
	if dir != "" {
		m.workingDir = dir
	}
}

func (m *Manager) SetRelayPeerIDFunc(fn func() string) {
	m.relayPeerIDFunc = fn
}

func (m *Manager) SetClientDispatcher(fn func(ctx context.Context, req *p2pv1.ClientActionRequest) (*p2pv1.ClientActionResponse, error)) {
	m.ClientDispatcher = fn
}

func (m *Manager) ensurePeerAddr(pid peer.ID) {
	if m.relayPeerIDFunc != nil {
		relayPeerID := m.relayPeerIDFunc()
		if relayPeerID != "" && len(m.host.Peerstore().Addrs(pid)) == 0 {
			circuitAddr, err := multiaddr.NewMultiaddr(
				fmt.Sprintf("/p2p/%s/p2p-circuit", relayPeerID),
			)
			if err == nil {
				m.host.Peerstore().AddAddr(pid, circuitAddr, time.Hour)
			}
		}
	}
}

func (m *Manager) handleIncomingStream(s network.Stream) {
	defer func() {
		// We do not close the stream immediately unless rejected or done
	}()

	// 1. Read Request
	var req TransferRequest
	decoder := json.NewDecoder(s)
	if err := decoder.Decode(&req); err != nil {
		s.Reset()
		return
	}

	transferID := fmt.Sprintf("in-%s-%d", s.Conn().RemotePeer().String(), time.Now().UnixNano())

	pending := &PendingIncoming{
		Stream:   s,
		Metadata: req,
		AcceptCh: make(chan AcceptDecision, 1),
	}

	m.mu.Lock()
	m.pendingTransfers[transferID] = pending
	m.mu.Unlock()

	// 2. Emit Event
	if m.EventCallback != nil {
		m.EventCallback(&p2pv1.NodeEvent{
			Type:       p2pv1.EventType_EVENT_TRANSFER_REQUESTED,
			PeerId:     s.Conn().RemotePeer().String(),
			TransferId: transferID,
			Metadata: &p2pv1.TransferMetadata{
				FileName: req.FileName,
				FileSize: req.FileSize,
				Sha256:   req.SHA256,
			},
		})
	}

	// 3. Wait for AcceptFile or timeout
	timer := time.NewTimer(30 * time.Second) // 30s for Python app to accept
	var decision AcceptDecision

	select {
	case decision = <-pending.AcceptCh:
		timer.Stop()
	case <-timer.C:
		m.rejectStream(transferID, s, "Timeout waiting for accept")
		return
	}

	if !decision.Accepted {
		m.rejectStream(transferID, s, "Rejected by application")
		return
	}

	// Remove from pending
	m.mu.Lock()
	delete(m.pendingTransfers, transferID)
	m.mu.Unlock()

	// Send Accept
	encoder := json.NewEncoder(s)
	_ = encoder.Encode(TransferResponse{Accepted: true})

	// Do file transfer reading
	m.doReceiveFile(transferID, s, decision.DestPath, decision.Overwrite, decision.Progress, req)
}

func (m *Manager) rejectStream(transferID string, s network.Stream, reason string) {
	m.mu.Lock()
	delete(m.pendingTransfers, transferID)
	m.mu.Unlock()

	encoder := json.NewEncoder(s)
	_ = encoder.Encode(TransferResponse{Accepted: false, Reason: reason})
	s.Close()
}

func (m *Manager) AcceptFile(transferID, destPath string, overwrite bool, progress chan *p2pv1.TransferEvent) error {
	m.mu.Lock()
	pending, ok := m.pendingTransfers[transferID]
	m.mu.Unlock()

	if !ok {
		return fmt.Errorf("transfer ID not found or expired")
	}

	pending.AcceptCh <- AcceptDecision{
		Accepted:  true,
		DestPath:  destPath,
		Overwrite: overwrite,
		Progress:  progress,
	}
	return nil
}

func (m *Manager) doReceiveFile(transferID string, s network.Stream, destPath string, overwrite bool, progress chan *p2pv1.TransferEvent, req TransferRequest) {
	defer s.Close()
	defer close(progress)

	flags := os.O_CREATE | os.O_WRONLY
	if overwrite {
		flags |= os.O_TRUNC
	} else {
		flags |= os.O_EXCL
	}

	f, err := os.OpenFile(destPath, flags, 0644)
	if err != nil {
		progress <- &p2pv1.TransferEvent{
			TransferId: transferID,
			State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
			Error:      fmt.Sprintf("Failed to open file: %v", err),
		}
		s.Reset()
		return
	}
	defer f.Close()

	progress <- &p2pv1.TransferEvent{
		TransferId: transferID,
		State:      p2pv1.EventType_EVENT_TRANSFER_STARTED,
		TotalBytes: req.FileSize,
	}

	buf := make([]byte, 32*1024)
	var written int64 = 0
	lastReport := time.Now()

	for {
		n, err := s.Read(buf)
		if n > 0 {
			if _, werr := f.Write(buf[:n]); werr != nil {
				progress <- &p2pv1.TransferEvent{
					TransferId: transferID,
					State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
					Error:      fmt.Sprintf("Disk write error: %v", werr),
				}
				s.Reset()
				return
			}
			written += int64(n)

			if time.Since(lastReport) > 500*time.Millisecond {
				progress <- &p2pv1.TransferEvent{
					TransferId:       transferID,
					State:            p2pv1.EventType_EVENT_TRANSFER_PROGRESS,
					BytesTransferred: written,
					TotalBytes:       req.FileSize,
					Progress:         float32(written) / float32(req.FileSize),
				}
				lastReport = time.Now()
			}
		}

		if err != nil {
			if err == io.EOF {
				break
			}
			progress <- &p2pv1.TransferEvent{
				TransferId: transferID,
				State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
				Error:      fmt.Sprintf("Network read error: %v", err),
			}
			s.Reset()
			return
		}
	}

	progress <- &p2pv1.TransferEvent{
		TransferId:       transferID,
		State:            p2pv1.EventType_EVENT_TRANSFER_COMPLETED,
		BytesTransferred: written,
		TotalBytes:       req.FileSize,
		Progress:         1.0,
	}
}

func (m *Manager) CancelTransfer(transferID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	pending, ok := m.pendingTransfers[transferID]
	if !ok {
		return fmt.Errorf("transfer ID not found")
	}
	pending.AcceptCh <- AcceptDecision{Accepted: false}
	return nil
}

func (m *Manager) GetTransferStatus(transferID string) (*p2pv1.TransferStatusResponse, error) {
	// Simple MVP implementation: just check if it's in pending. Real status tracking requires a separate struct.
	m.mu.Lock()
	defer m.mu.Unlock()
	_, ok := m.pendingTransfers[transferID]
	if ok {
		return &p2pv1.TransferStatusResponse{
			TransferId: transferID,
			State:      p2pv1.EventType_EVENT_TRANSFER_REQUESTED,
		}, nil
	}
	return nil, fmt.Errorf("transfer ID not found or already completed/failed")
}

func (m *Manager) SendFile(ctx context.Context, p peer.ID, transferID, sourcePath, fileName string, fileSize int64, sha256 string, progress chan *p2pv1.TransferEvent) error {
	defer close(progress)

	f, err := os.Open(sourcePath)
	if err != nil {
		progress <- &p2pv1.TransferEvent{TransferId: transferID, State: p2pv1.EventType_EVENT_TRANSFER_FAILED, Error: err.Error()}
		return fmt.Errorf("failed to open source file: %w", err)
	}
	defer f.Close()

	s, err := m.host.NewStream(network.WithUseTransient(ctx, "send-file"), p, ProtocolID)
	if err != nil {
		progress <- &p2pv1.TransferEvent{TransferId: transferID, State: p2pv1.EventType_EVENT_TRANSFER_FAILED, Error: err.Error()}
		return fmt.Errorf("failed to open stream: %w", err)
	}
	defer s.Close()

	// 1. Send Request
	req := TransferRequest{
		FileName: fileName,
		FileSize: fileSize,
		SHA256:   sha256,
	}
	encoder := json.NewEncoder(s)
	if err := encoder.Encode(req); err != nil {
		s.Reset()
		return fmt.Errorf("failed to send metadata: %w", err)
	}

	// 2. Read Response
	var resp TransferResponse
	decoder := json.NewDecoder(s)
	if err := decoder.Decode(&resp); err != nil {
		s.Reset()
		return fmt.Errorf("failed to read response: %w", err)
	}

	if !resp.Accepted {
		s.Close()
		return fmt.Errorf("peer rejected transfer: %s", resp.Reason)
	}

	progress <- &p2pv1.TransferEvent{
		TransferId: transferID,
		State:      p2pv1.EventType_EVENT_TRANSFER_STARTED,
		TotalBytes: fileSize,
	}

	// 3. Send Data
	buf := make([]byte, 32*1024)
	var sent int64 = 0
	lastReport := time.Now()

	for {
		n, err := f.Read(buf)
		if n > 0 {
			if _, werr := s.Write(buf[:n]); werr != nil {
				progress <- &p2pv1.TransferEvent{
					TransferId: transferID,
					State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
					Error:      fmt.Sprintf("Network write error: %v", werr),
				}
				s.Reset()
				return nil
			}
			sent += int64(n)

			if time.Since(lastReport) > 500*time.Millisecond {
				progress <- &p2pv1.TransferEvent{
					TransferId:       transferID,
					State:            p2pv1.EventType_EVENT_TRANSFER_PROGRESS,
					BytesTransferred: sent,
					TotalBytes:       fileSize,
					Progress:         float32(sent) / float32(fileSize),
				}
				lastReport = time.Now()
			}
		}

		if err != nil {
			if err == io.EOF {
				break
			}
			progress <- &p2pv1.TransferEvent{
				TransferId: transferID,
				State:      p2pv1.EventType_EVENT_TRANSFER_FAILED,
				Error:      fmt.Sprintf("Disk read error: %v", err),
			}
			s.Reset()
			return nil
		}
	}

	progress <- &p2pv1.TransferEvent{
		TransferId:       transferID,
		State:            p2pv1.EventType_EVENT_TRANSFER_COMPLETED,
		BytesTransferred: sent,
		TotalBytes:       fileSize,
		Progress:         1.0,
	}

	return nil
}

func (m *Manager) handleFileRequestStream(s network.Stream) {
	defer s.Close()

	var req RequestWireMsg
	if err := json.NewDecoder(s).Decode(&req); err != nil {
		fmt.Printf("[Transfer Manager] Failed to decode RequestWireMsg: %v\n", err)
		return
	}

	fmt.Printf("[Transfer Manager] Received file request for '%s' from peer %s\n", req.FileName, s.Conn().RemotePeer())

	if m.EventCallback != nil {
		m.EventCallback(&p2pv1.NodeEvent{
			Type: p2pv1.EventType_EVENT_FILE_REQUESTED,
			PeerId: s.Conn().RemotePeer().String(),
			Message: req.FileName,
		})
	}
}

func (m *Manager) RequestFile(ctx context.Context, p peer.ID, fileName string) error {
	fmt.Printf("[Transfer Manager] Dialing peer %s to request file '%s'\n", p.String(), fileName)
	s, err := m.host.NewStream(network.WithUseTransient(ctx, "request-file"), p, RequestProtocolID)
	if err != nil {
		fmt.Printf("[Transfer Manager] NewStream failed: %v\n", err)
		return err
	}
	defer s.Close()
	fmt.Printf("[Transfer Manager] Successfully opened Request stream to %s\n", p.String())

	msg := RequestWireMsg{FileName: fileName}
	err = json.NewEncoder(s).Encode(msg)
	fmt.Printf("[Transfer Manager] Sent file request message: %v\n", err)
	return err
}

// --- Inbound Handlers (Client Side) ---

func (m *Manager) handleTaskStream(s network.Stream) {
	defer s.Close()
	var req TaskWireReq
	if err := json.NewDecoder(s).Decode(&req); err != nil {
		_ = json.NewEncoder(s).Encode(TaskWireResp{Success: false, Error: fmt.Sprintf("decode error: %v", err)})
		return
	}

	if m.ClientDispatcher == nil {
		_ = json.NewEncoder(s).Encode(TaskWireResp{Success: false, Error: "client application dispatcher not configured"})
		return
	}

	actionReq := &p2pv1.ClientActionRequest{
		RequestId:     uuid.NewString(),
		ActionType:    p2pv1.ClientActionType_ACTION_GET_TRAINING_TASK,
		TrainerPeerId: s.Conn().RemotePeer().String(),
		ModelId:       req.ModelID,
		ModelVersion:  req.ModelVersion,
		DatasetId:     req.DataSetID,
		ShardId:       req.ShardID,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := m.ClientDispatcher(ctx, actionReq)
	if err != nil {
		_ = json.NewEncoder(s).Encode(TaskWireResp{Success: false, Error: err.Error()})
		return
	}

	if !resp.Success {
		_ = json.NewEncoder(s).Encode(TaskWireResp{Success: false, Error: resp.Error})
		return
	}

	_ = json.NewEncoder(s).Encode(TaskWireResp{
		Success:          true,
		TrainingTaskJSON: resp.TrainingTaskJson,
	})
}

func (m *Manager) handleModelStream(s network.Stream) {
	defer s.Close()
	var req ModelWireReq
	if err := json.NewDecoder(s).Decode(&req); err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("decode error: %v", err)})
		return
	}

	if m.ClientDispatcher == nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: "client application dispatcher not configured"})
		return
	}

	actionReq := &p2pv1.ClientActionRequest{
		RequestId:     uuid.NewString(),
		ActionType:    p2pv1.ClientActionType_ACTION_TRANSFER_MODEL,
		TrainerPeerId: s.Conn().RemotePeer().String(),
		ModelId:       req.ModelID,
		ModelVersion:  req.ModelVersion,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := m.ClientDispatcher(ctx, actionReq)
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: err.Error()})
		return
	}

	if !resp.Success {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: resp.Error})
		return
	}

	f, err := os.Open(resp.FilePath)
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("failed to open model file: %v", err)})
		return
	}
	defer f.Close()

	fi, err := f.Stat()
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("failed to stat model file: %v", err)})
		return
	}

	header := FileWireHeader{
		Success:  true,
		FileName: filepath.Base(resp.FilePath),
		FileSize: fi.Size(),
	}

	if err := json.NewEncoder(s).Encode(header); err != nil {
		return
	}

	buf := make([]byte, 64*1024)
	_, _ = io.CopyBuffer(s, f, buf)
}

func (m *Manager) handleShardStream(s network.Stream) {
	defer s.Close()
	var req ShardWireReq
	if err := json.NewDecoder(s).Decode(&req); err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("decode error: %v", err)})
		return
	}

	if m.ClientDispatcher == nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: "client application dispatcher not configured"})
		return
	}

	actionReq := &p2pv1.ClientActionRequest{
		RequestId:     uuid.NewString(),
		ActionType:    p2pv1.ClientActionType_ACTION_TRANSFER_SHARD,
		TrainerPeerId: s.Conn().RemotePeer().String(),
		ModelId:       req.ModelID,
		ModelVersion:  req.ModelVersion,
		DatasetId:     req.DataSetID,
		ShardId:       req.ShardID,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := m.ClientDispatcher(ctx, actionReq)
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: err.Error()})
		return
	}

	if !resp.Success {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: resp.Error})
		return
	}

	f, err := os.Open(resp.FilePath)
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("failed to open shard file: %v", err)})
		return
	}
	defer f.Close()

	fi, err := f.Stat()
	if err != nil {
		_ = json.NewEncoder(s).Encode(FileWireHeader{Success: false, Error: fmt.Sprintf("failed to stat shard file: %v", err)})
		return
	}

	header := FileWireHeader{
		Success:  true,
		FileName: filepath.Base(resp.FilePath),
		FileSize: fi.Size(),
	}

	if err := json.NewEncoder(s).Encode(header); err != nil {
		return
	}

	buf := make([]byte, 64*1024)
	_, _ = io.CopyBuffer(s, f, buf)
}

func (m *Manager) handleUpdateStream(s network.Stream) {
	defer s.Close()
	var req UpdateWireReq
	if err := json.NewDecoder(s).Decode(&req); err != nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: fmt.Sprintf("decode error: %v", err)})
		return
	}

	if m.ClientDispatcher == nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: "client application dispatcher not configured"})
		return
	}

	if err := os.MkdirAll(m.workingDir, 0755); err != nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: fmt.Sprintf("failed to create working dir: %v", err)})
		return
	}

	fileName := filepath.Base(req.FileName)
	if fileName == "" || fileName == "." {
		fileName = fmt.Sprintf("update_%d.safetensors", time.Now().UnixNano())
	}
	savePath := filepath.Join(m.workingDir, fileName)

	f, err := os.OpenFile(savePath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: fmt.Sprintf("failed to open destination file: %v", err)})
		return
	}

	_, err = io.CopyN(f, s, req.FileSize)
	f.Close()
	if err != nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: fmt.Sprintf("failed to read update stream: %v", err)})
		return
	}

	actionReq := &p2pv1.ClientActionRequest{
		RequestId:          uuid.NewString(),
		ActionType:         p2pv1.ClientActionType_ACTION_UPDATE_MODEL,
		TrainerPeerId:      s.Conn().RemotePeer().String(),
		TrainingResultJson: req.TrainingResultJSON,
		SavedUpdatePath:    savePath,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	resp, err := m.ClientDispatcher(ctx, actionReq)
	if err != nil {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: err.Error()})
		return
	}

	if !resp.Success {
		_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: false, Error: resp.Error})
		return
	}

	_ = json.NewEncoder(s).Encode(UpdateWireResp{Success: true})
}

// --- Outbound Methods (Trainer Side) ---

func (m *Manager) GetTrainingTask(ctx context.Context, p peer.ID, modelID, modelVersion, datasetID, shardID string) (string, error) {
	m.ensurePeerAddr(p)
	s, err := m.host.NewStream(network.WithUseTransient(ctx, "get-training-task"), p, TaskProtocolID)
	if err != nil {
		return "", fmt.Errorf("failed to open stream: %w", err)
	}
	defer s.Close()

	req := TaskWireReq{
		ModelID:      modelID,
		ModelVersion: modelVersion,
		DataSetID:    datasetID,
		ShardID:      shardID,
	}
	if err := json.NewEncoder(s).Encode(req); err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}

	var resp TaskWireResp
	if err := json.NewDecoder(s).Decode(&resp); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	if !resp.Success {
		return "", fmt.Errorf("client returned error: %s", resp.Error)
	}

	return resp.TrainingTaskJSON, nil
}

func (m *Manager) GetModel(ctx context.Context, p peer.ID, modelID, modelVersion string) (string, error) {
	m.ensurePeerAddr(p)
	s, err := m.host.NewStream(network.WithUseTransient(ctx, "get-model"), p, ModelProtocolID)
	if err != nil {
		return "", fmt.Errorf("failed to open stream: %w", err)
	}
	defer s.Close()

	req := ModelWireReq{
		ModelID:      modelID,
		ModelVersion: modelVersion,
	}
	if err := json.NewEncoder(s).Encode(req); err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}

	var header FileWireHeader
	if err := json.NewDecoder(s).Decode(&header); err != nil {
		return "", fmt.Errorf("failed to decode file header: %w", err)
	}

	if !header.Success {
		return "", fmt.Errorf("client failed to transfer model: %s", header.Error)
	}

	if err := os.MkdirAll(m.workingDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create working dir: %w", err)
	}

	fileName := filepath.Base(header.FileName)
	if fileName == "" || fileName == "." {
		fileName = fmt.Sprintf("%s_%s.pt2", modelID, modelVersion)
	}
	destPath := filepath.Join(m.workingDir, fileName)

	f, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to open local destination file: %w", err)
	}
	defer f.Close()

	_, err = io.CopyN(f, s, header.FileSize)
	if err != nil && err != io.EOF {
		return "", fmt.Errorf("failed to download model bytes: %w", err)
	}

	return destPath, nil
}

func (m *Manager) GetShard(ctx context.Context, p peer.ID, modelID, modelVersion, datasetID, shardID string) (string, error) {
	m.ensurePeerAddr(p)
	s, err := m.host.NewStream(network.WithUseTransient(ctx, "get-shard"), p, ShardProtocolID)
	if err != nil {
		return "", fmt.Errorf("failed to open stream: %w", err)
	}
	defer s.Close()

	req := ShardWireReq{
		ModelID:      modelID,
		ModelVersion: modelVersion,
		DataSetID:    datasetID,
		ShardID:      shardID,
	}
	if err := json.NewEncoder(s).Encode(req); err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}

	var header FileWireHeader
	if err := json.NewDecoder(s).Decode(&header); err != nil {
		return "", fmt.Errorf("failed to decode file header: %w", err)
	}

	if !header.Success {
		return "", fmt.Errorf("client failed to transfer shard: %s", header.Error)
	}

	if err := os.MkdirAll(m.workingDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create working dir: %w", err)
	}

	fileName := filepath.Base(header.FileName)
	if fileName == "" || fileName == "." {
		fileName = fmt.Sprintf("%s_%s.pt", datasetID, shardID)
	}
	destPath := filepath.Join(m.workingDir, fileName)

	f, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to open local destination file: %w", err)
	}
	defer f.Close()

	_, err = io.CopyN(f, s, header.FileSize)
	if err != nil && err != io.EOF {
		return "", fmt.Errorf("failed to download shard bytes: %w", err)
	}

	return destPath, nil
}

func (m *Manager) SendUpdate(ctx context.Context, p peer.ID, trainingResultJSON, updateArtifactPath string) error {
	m.ensurePeerAddr(p)

	f, err := os.Open(updateArtifactPath)
	if err != nil {
		return fmt.Errorf("failed to open update artifact: %w", err)
	}
	defer f.Close()

	fi, err := f.Stat()
	if err != nil {
		return fmt.Errorf("failed to stat update artifact: %w", err)
	}

	s, err := m.host.NewStream(network.WithUseTransient(ctx, "send-update"), p, UpdateProtocolID)
	if err != nil {
		return fmt.Errorf("failed to open stream: %w", err)
	}
	defer s.Close()

	req := UpdateWireReq{
		TrainingResultJSON: trainingResultJSON,
		FileName:           filepath.Base(updateArtifactPath),
		FileSize:           fi.Size(),
	}
	if err := json.NewEncoder(s).Encode(req); err != nil {
		return fmt.Errorf("failed to send update metadata: %w", err)
	}

	buf := make([]byte, 64*1024)
	if _, err := io.CopyBuffer(s, f, buf); err != nil {
		return fmt.Errorf("failed to stream update bytes: %w", err)
	}

	var resp UpdateWireResp
	if err := json.NewDecoder(s).Decode(&resp); err != nil {
		return fmt.Errorf("failed to read update response: %w", err)
	}

	if !resp.Success {
		return fmt.Errorf("client failed to process update: %s", resp.Error)
	}

	return nil
}

