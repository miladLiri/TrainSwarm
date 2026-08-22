package api

import (
	"sync"
	
	p2pv1 "p2p-node/internal/api/p2pv1"
)

// EventBus is a simple thread-safe pub/sub for NodeEvent messages.
type EventBus struct {
	mu          sync.RWMutex
	subscribers map[chan *p2pv1.NodeEvent]struct{}
}

func NewEventBus() *EventBus {
	return &EventBus{
		subscribers: make(map[chan *p2pv1.NodeEvent]struct{}),
	}
}

// Subscribe returns a channel that receives newly broadcast events.
func (eb *EventBus) Subscribe() chan *p2pv1.NodeEvent {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	ch := make(chan *p2pv1.NodeEvent, 100)
	eb.subscribers[ch] = struct{}{}
	return ch
}

// Unsubscribe removes the channel from the bus.
func (eb *EventBus) Unsubscribe(ch chan *p2pv1.NodeEvent) {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	delete(eb.subscribers, ch)
	close(ch)
}

// Broadcast sends an event to all subscribers.
func (eb *EventBus) Broadcast(event *p2pv1.NodeEvent) {
	eb.mu.RLock()
	defer eb.mu.RUnlock()
	
	for ch := range eb.subscribers {
		select {
		case ch <- event:
		default:
			// Drop event if subscriber is full
		}
	}
}
