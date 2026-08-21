"""FastAPI Web Application for the TrainSwarm Bootstrap Relay service."""

import sys
import json
from dataclasses import asdict
from typing import Optional, List, Dict, Any

from config import config
from models import (
    RegisterPeerRequest,
    RegisterPeerResponse,
    PeerItem,
    SendRelayMessageRequest,
    RelayInboxResponse,
)
from registry import registry

try:
    from fastapi import FastAPI, HTTPException, status
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def create_app():
    if not HAS_FASTAPI:
        return None

    app = FastAPI(
        title="TrainSwarm Bootstrap Relay",
        description="Control-plane peer registry and DCUtR relay service for TrainSwarm.",
        version="1.0.0",
    )

    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "service": "TrainSwarm-Bootstrap"}

    @app.post("/api/peers/register")
    async def register_peer(request: Dict[str, Any]):
        node_id = request.get("nodeId")
        role = request.get("role")
        endpoint = request.get("endpoint")

        if not node_id or not str(node_id).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="nodeId is required and cannot be empty.",
            )
        if not role or role not in ("trainer", "client"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="role must be either 'trainer' or 'client'.",
            )

        relay_address = f"http://{config.host}:{config.port}"
        response = registry.register_peer(
            node_id=str(node_id).strip(),
            role=role,
            endpoint=endpoint,
            relay_address=relay_address,
        )
        return asdict(response)

    @app.get("/api/peers")
    async def list_peers():
        peers = registry.list_peers()
        return [asdict(p) for p in peers]

    @app.post("/api/relay/send")
    async def send_relay_message(request: Dict[str, Any]):
        source_peer_id = request.get("sourcePeerId")
        target_peer_id = request.get("targetPeerId")
        payload = request.get("payload")

        if not source_peer_id or not target_peer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sourcePeerId and targetPeerId are required.",
            )

        msg = registry.enqueue_message(
            source_peer_id=str(source_peer_id),
            target_peer_id=str(target_peer_id),
            payload=payload,
        )
        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target peer '{target_peer_id}' not found in registry.",
            )

        return {"messageId": msg.messageId, "status": "enqueued"}

    @app.get("/api/relay/inbox/{peer_id}")
    async def get_relay_inbox(peer_id: str):
        peer = registry.get_peer(peer_id)
        if peer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Peer '{peer_id}' not found in registry.",
            )

        messages = registry.drain_inbox(peer_id)
        return {
            "peerId": peer_id,
            "messages": [asdict(m) for m in messages],
        }

    return app


# Standard library HTTP Server Fallback (runs if fastapi/uvicorn is not yet installed)
def run_stdlib_server(host: str, port: int):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse

    class RelayHTTPHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, data: Any):
            body = json.dumps(data).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")

            if path == "/api/health":
                self._send_json(200, {"status": "healthy", "service": "TrainSwarm-Bootstrap"})
            elif path == "/api/peers":
                peers = registry.list_peers()
                self._send_json(200, [asdict(p) for p in peers])
            elif path.startswith("/api/relay/inbox/"):
                peer_id = path.split("/")[-1]
                peer = registry.get_peer(peer_id)
                if not peer:
                    self._send_json(404, {"detail": f"Peer '{peer_id}' not found."})
                else:
                    messages = registry.drain_inbox(peer_id)
                    self._send_json(200, {"peerId": peer_id, "messages": [asdict(m) for m in messages]})
            else:
                self._send_json(404, {"detail": "Not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")

            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                self._send_json(400, {"detail": "Invalid JSON"})
                return

            if path == "/api/peers/register":
                node_id = data.get("nodeId")
                role = data.get("role")
                endpoint = data.get("endpoint")
                if not node_id or role not in ("trainer", "client"):
                    self._send_json(400, {"detail": "nodeId and valid role are required."})
                    return
                resp = registry.register_peer(
                    node_id=str(node_id).strip(),
                    role=role,
                    endpoint=endpoint,
                    relay_address=f"http://{host}:{port}",
                )
                self._send_json(200, asdict(resp))
            elif path == "/api/relay/send":
                source = data.get("sourcePeerId")
                target = data.get("targetPeerId")
                payload = data.get("payload")
                if not source or not target:
                    self._send_json(400, {"detail": "sourcePeerId and targetPeerId are required."})
                    return
                msg = registry.enqueue_message(source, target, payload)
                if not msg:
                    self._send_json(404, {"detail": f"Target peer '{target}' not found."})
                else:
                    self._send_json(200, {"messageId": msg.messageId, "status": "enqueued"})
            else:
                self._send_json(404, {"detail": "Not found"})

        def log_message(self, format, *args):
            # Clean logging
            print(f"[Bootstrap] {self.address_string()} - {format % args}")

    server = HTTPServer((host, port), RelayHTTPHandler)
    print(f"[Bootstrap] Serving HTTP relay on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Bootstrap] Shutting down...")
        server.server_close()


def main():
    if HAS_FASTAPI:
        app = create_app()
        uvicorn.run(app, host=config.host, port=config.port)
    else:
        run_stdlib_server(host=config.host, port=config.port)


if __name__ == "__main__":
    main()

