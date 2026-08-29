import grpc
import p2p_pb2
import p2p_pb2_grpc
import sys
import time
import urllib.request
import threading
import os

sys.stdout.reconfigure(line_buffering=True)

def run():
    if len(sys.argv) < 5:
        print("Usage: python requester.py <port> <owner_peer_id> <file_name> <relay_http_host> [relay_p2p_host]")
        print("  relay_http_host  - hostname to fetch relay peer ID via HTTP (e.g. localhost)")
        print("  relay_p2p_host   - hostname the Go node uses to dial the relay (e.g. 'relay' for Docker). Defaults to relay_http_host.")
        sys.exit(1)

    port = sys.argv[1]
    owner_peer_id = sys.argv[2]
    file_name = sys.argv[3]
    relay_http_host = sys.argv[4]
    # relay_p2p_host is the hostname that the Go node (inside Docker) uses to reach the relay.
    # When running in Docker, this must be the Docker service name "relay", not "localhost".
    relay_p2p_host = sys.argv[5] if len(sys.argv) >= 6 else relay_http_host

    print(f"[Requester] Fetching relay peer ID from http://{relay_http_host}:8090/peerid...")
    req = urllib.request.urlopen(f"http://{relay_http_host}:8090/peerid")
    relay_peer_id = req.read().decode('utf-8').strip()
    print(f"[Requester] Relay peer ID: {relay_peer_id}")

    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p2p_pb2_grpc.P2PNodeStub(channel)

    print(f"[Requester] Connected to Node gRPC on localhost:{port}")

    # Build the circuit relay address using the P2P hostname (resolvable from inside Docker)
    relay_addr = f"/dns4/{relay_p2p_host}/tcp/4001/p2p/{relay_peer_id}/p2p-circuit/p2p/{owner_peer_id}"
    print(f"[Requester] Connecting to Owner via relay circuit: {relay_addr}")
    
    try:
        stub.Connect(p2p_pb2.ConnectRequest(
            peer_id=owner_peer_id,
            multiaddrs=[relay_addr],
            timeout_ms=30000
        ))
    except grpc.RpcError as e:
        print(f"[Requester] Failed to connect: {e}")
        return

    # Wait for connection stabilization and hole-punch
    time.sleep(10)
    
    def watch_events():
        try:
            events = stub.WatchEvents(p2p_pb2.WatchEventsRequest())
            for event in events:
                if event.type == p2p_pb2.EVENT_CONNECTION_UPGRADED_TO_DIRECT:
                    print("[Requester] 🎉 Connection upgraded to direct (Hole punch successful!)")
                elif event.type == p2p_pb2.EVENT_TRANSFER_REQUESTED:
                    print(f"[Requester] Incoming file transfer requested! ID: {event.transfer_id}")
                    try:
                        progress_stream = stub.AcceptFile(p2p_pb2.AcceptFileRequest(
                            transfer_id=event.transfer_id,
                            destination_path=f"received_{event.metadata.file_name}"
                        ))
                        for progress in progress_stream:
                            print(f"[Requester] Download Progress: {progress.bytes_transferred} bytes")
                        print(f"[Requester] Transfer completed successfully!")
                        os._exit(0)
                    except grpc.RpcError as e:
                        print(f"[Requester] Error accepting file: {e}")
        except grpc.RpcError:
            pass

    t = threading.Thread(target=watch_events, daemon=True)
    t.start()

    print(f"[Requester] Requesting file '{file_name}' from Owner...")
    try:
        stub.RequestFile(p2p_pb2.RequestFileRequest(
            peer_id=owner_peer_id,
            file_name=file_name
        ), timeout=30)
    except grpc.RpcError as e:
        print(f"[Requester] Failed to request file: {e}")

    time.sleep(30)
    print("[Requester] Timeout waiting for file transfer.")
    os._exit(1)

if __name__ == '__main__':
    run()
