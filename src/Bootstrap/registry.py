"""Thread-safe in-memory peer registry and relay message store."""

import threading
import uuid
from typing import Dict, List, Optional, Any
from collections import defaultdict
from models import (
    PeerItem,
    RegisterPeerResponse,
    RelayMessage,
    get_utc_now_iso,
)


class PeerRegistry:
    """Thread-safe in-memory store for active peers and relayed message inboxes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._peers: Dict[str, PeerItem] = {}  # peerId -> PeerItem
        self._node_id_to_peer_id: Dict[str, str] = {}  # nodeId -> peerId
        self._inboxes: Dict[str, List[RelayMessage]] = defaultdict(list)  # peerId -> [RelayMessage]

    def register_peer(
        self,
        node_id: str,
        role: str,
        endpoint: Optional[str] = None,
        relay_address: str = "http://localhost:6000",
    ) -> RegisterPeerResponse:
        """Registers a node or updates an existing registration, assigning a peer ID."""
        with self._lock:
            now = get_utc_now_iso()
            
            # Check if this nodeId is already registered
            if node_id in self._node_id_to_peer_id:
                peer_id = self._node_id_to_peer_id[node_id]
                peer_item = self._peers[peer_id]
                peer_item.role = role
                peer_item.endpoint = endpoint
                peer_item.lastSeenAt = now
                registered_at = peer_item.lastSeenAt
            else:
                peer_id = str(uuid.uuid4())
                peer_item = PeerItem(
                    peerId=peer_id,
                    nodeId=node_id,
                    role=role,
                    endpoint=endpoint,
                    lastSeenAt=now,
                )
                self._peers[peer_id] = peer_item
                self._node_id_to_peer_id[node_id] = peer_id
                registered_at = now

            return RegisterPeerResponse(
                peerId=peer_id,
                nodeId=node_id,
                role=role,
                relayAddress=relay_address,
                registeredAt=registered_at,
            )

    def list_peers(self) -> List[PeerItem]:
        """Returns all currently registered active peers."""
        with self._lock:
            return list(self._peers.values())

    def get_peer(self, peer_id: str) -> Optional[PeerItem]:
        """Looks up a peer by peerId."""
        with self._lock:
            return self._peers.get(peer_id)

    def enqueue_message(
        self,
        source_peer_id: str,
        target_peer_id: str,
        payload: Any,
    ) -> Optional[RelayMessage]:
        """Enqueues a message for a target peer. Returns None if target is not registered."""
        with self._lock:
            if target_peer_id not in self._peers:
                return None

            msg_id = str(uuid.uuid4())
            msg = RelayMessage(
                messageId=msg_id,
                sourcePeerId=source_peer_id,
                targetPeerId=target_peer_id,
                payload=payload,
                timestamp=get_utc_now_iso(),
            )
            self._inboxes[target_peer_id].append(msg)
            return msg

    def drain_inbox(self, peer_id: str) -> List[RelayMessage]:
        """Retrieves and clears all queued messages for a given peer."""
        with self._lock:
            messages = self._inboxes.pop(peer_id, [])
            # Touch last seen
            if peer_id in self._peers:
                self._peers[peer_id].lastSeenAt = get_utc_now_iso()
            return messages


# Global singleton instance
registry = PeerRegistry()

