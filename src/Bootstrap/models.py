"""Data models and schemas for the Bootstrap Relay service."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RegisterPeerRequest:
    nodeId: str
    role: str  # "trainer" or "client"
    endpoint: Optional[str] = None


@dataclass
class RegisterPeerResponse:
    peerId: str
    nodeId: str
    role: str
    relayAddress: str
    registeredAt: str


@dataclass
class PeerItem:
    peerId: str
    nodeId: str
    role: str
    endpoint: Optional[str] = None
    lastSeenAt: str = field(default_factory=get_utc_now_iso)


@dataclass
class SendRelayMessageRequest:
    sourcePeerId: str
    targetPeerId: str
    payload: Any


@dataclass
class RelayMessage:
    messageId: str
    sourcePeerId: str
    targetPeerId: str
    payload: Any
    timestamp: str = field(default_factory=get_utc_now_iso)


@dataclass
class RelayInboxResponse:
    peerId: str
    messages: List[Dict[str, Any]] = field(default_factory=list)

