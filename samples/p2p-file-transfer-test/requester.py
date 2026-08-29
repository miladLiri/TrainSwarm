import grpc
import p2p_pb2
import p2p_pb2_grpc
import sys
import time
import threading
import os

sys.stdout.reconfigure(line_buffering=True)

def run():
    if len(sys.argv) < 4:
        print("Usage: python requester.py <port> <owner_peer_id> <file_name>")
        sys.exit(1)

    port = sys.argv[1]
    owner_peer_id = sys.argv[2]
    file_name = sys.argv[3]

    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p2p_pb2_grpc.P2PNodeStub(channel)

    print(f"[Requester] Connected to Node gRPC on localhost:{port}")

    transfer_done = threading.Event()
    transfer_failed = threading.Event()

    def watch_events():
        try:
            events = stub.WatchEvents(p2p_pb2.WatchEventsRequest())
            for event in events:
                if event.type == p2p_pb2.EVENT_CONNECTION_UPGRADED_TO_DIRECT:
                    print("[Requester] 🎉 Connection upgraded to direct (Hole punch successful!)")
                elif event.type == p2p_pb2.EVENT_TRANSFER_REQUESTED:
                    print(f"[Requester] Incoming file transfer requested! ID: {event.transfer_id}")
                    try:
                        dest = f"received_{event.metadata.file_name}"
                        progress_stream = stub.AcceptFile(p2p_pb2.AcceptFileRequest(
                            transfer_id=event.transfer_id,
                            destination_path=dest
                        ))
                        for progress in progress_stream:
                            if progress.total_bytes > 0:
                                pct = (progress.bytes_transferred / progress.total_bytes) * 100
                                print(f"[Requester] Download Progress: {progress.bytes_transferred}/{progress.total_bytes} bytes ({pct:.1f}%)")
                            else:
                                print(f"[Requester] Download Progress: {progress.bytes_transferred} bytes")
                        print(f"[Requester] ✅ Transfer completed successfully!")
                        transfer_done.set()
                        return
                    except grpc.RpcError as e:
                        print(f"[Requester] Error accepting file: {e}")
                        transfer_failed.set()
                        return
        except grpc.RpcError as e:
            if not transfer_done.is_set():
                print(f"[Requester] Event stream error: {e}")

    watcher_thread = threading.Thread(target=watch_events, daemon=True)
    watcher_thread.start()

    # Give watcher thread a moment to subscribe
    time.sleep(1)

    print(f"[Requester] Connecting to Owner {owner_peer_id}...")
    try:
        resp = stub.Connect(p2p_pb2.ConnectRequest(
            peer_id=owner_peer_id,
            timeout_ms=30000
        ))
        if resp.state == p2p_pb2.STATE_FAILED:
            print(f"[Requester] Failed to connect: {resp.error}")
            sys.exit(1)
        print(f"[Requester] Connected successfully to {owner_peer_id}")
    except grpc.RpcError as e:
        print(f"[Requester] gRPC Connect error: {e}")
        sys.exit(1)

    # Allow brief moment for peer route stabilization
    time.sleep(2)

    print(f"[Requester] Requesting file '{file_name}' from Owner...")
    try:
        stub.RequestFile(p2p_pb2.RequestFileRequest(
            peer_id=owner_peer_id,
            file_name=file_name
        ), timeout=30)
        print(f"[Requester] File request sent! Waiting for transfer to complete...")
    except grpc.RpcError as e:
        print(f"[Requester] Failed to request file: {e}")
        sys.exit(1)

    # Wait up to 60 seconds for file transfer to finish
    if transfer_done.wait(timeout=60):
        print("[Requester] Finished successfully.")
        sys.exit(0)
    elif transfer_failed.is_set():
        print("[Requester] Transfer failed.")
        sys.exit(1)
    else:
        print("[Requester] Timeout waiting for file transfer.")
        sys.exit(1)

if __name__ == '__main__':
    run()
