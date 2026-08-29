package transfer

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"
	"time"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	"p2p-node/internal/api/p2pv1"
)

const ProtocolID = "/trainswarm/file/1.0.0"
const RequestProtocolID = "/trainswarm/request/1.0.0"

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

type Manager struct {
	host             host.Host
	pendingTransfers map[string]*PendingIncoming
	mu               sync.Mutex
	EventCallback    func(*p2pv1.NodeEvent)
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
	m := &Manager{
		host:             h,
		pendingTransfers: make(map[string]*PendingIncoming),
		EventCallback:    eventCb,
	}
	h.SetStreamHandler(ProtocolID, m.handleIncomingStream)
	h.SetStreamHandler(RequestProtocolID, m.handleFileRequestStream)
	return m
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
		return fmt.Errorf("failed to open source file: %w", err)
	}
	defer f.Close()

	s, err := m.host.NewStream(ctx, p, ProtocolID)
	if err != nil {
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

	m.EventCallback(&p2pv1.NodeEvent{
		Type: p2pv1.EventType_EVENT_FILE_REQUESTED,
		PeerId: s.Conn().RemotePeer().String(),
		Message: req.FileName,
	})
}

func (m *Manager) RequestFile(ctx context.Context, p peer.ID, fileName string) error {
	fmt.Printf("[Transfer Manager] Dialing peer %s to request file '%s'\n", p.String(), fileName)
	s, err := m.host.NewStream(ctx, p, RequestProtocolID)
	if err != nil {
		fmt.Printf("[Transfer Manager] NewStream failed: %v\n", err)
		return err
	}
	defer s.Close()

	msg := RequestWireMsg{FileName: fileName}
	return json.NewEncoder(s).Encode(msg)
}

