import grpc
import p2p_pb2
import p2p_pb2_grpc
import sys
import time
import urllib.request

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

def run():
    if len(sys.argv) < 5:
        print("Usage: python sender.py <port> <target_peer_id> <file_path> <relay_host>")
        sys.exit(1)
        
    port = sys.argv[1]
    target_peer_id = sys.argv[2]
    file_path = sys.argv[3]
    relay_host = sys.argv[4]
    
    # Fetch relay peer ID
    print(f"[Sender] Fetching relay peer ID from http://{relay_host}:80/peerid...")
    req = urllib.request.urlopen(f"http://{relay_host}:80/peerid")
    relay_peer_id = req.read().decode('utf-8').strip()
    print(f"[Sender] Relay Peer ID: {relay_peer_id}")
    
    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p2p_pb2_grpc.P2PNodeStub(channel)
    
    print(f"[Sender] Connected to Node A gRPC on localhost:{port}")
    
    # Target address via relay
    relay_addr = f"/dns4/{relay_host}/tcp/4001/p2p/{relay_peer_id}/p2p-circuit/p2p/{target_peer_id}"
    print(f"[Sender] Connecting to Node B via relay circuit: {relay_addr}")
    
    try:
        connect_res = stub.Connect(p2p_pb2.ConnectRequest(
            peer_id=target_peer_id,
            addresses=[relay_addr],
            timeout_seconds=30
        ))
        print(f"[Sender] Connect initiated. Success: {connect_res.success}")
    except grpc.RpcError as e:
        print(f"[Sender] Failed to connect: {e}")
        return

    # Wait a bit for connection and potential hole punch
    print("[Sender] Waiting 5 seconds for connection stabilization and hole punch...")
    time.sleep(5)
    
    try:
        status = stub.GetConnectionStatus(p2p_pb2.GetConnectionStatusRequest(peer_id=target_peer_id))
        print(f"[Sender] Connection State: {p2p_pb2.ConnectionState.Name(status.state)}")
    except grpc.RpcError as e:
        print(f"[Sender] Could not get status: {e}")
    
    print(f"[Sender] Sending file {file_path}...")
    try:
        transfer_stream = stub.SendFile(p2p_pb2.SendFileRequest(
            peer_id=target_peer_id,
            file_path=file_path
        ))
        for progress in transfer_stream:
            print(f"[Sender] Progress: {progress.bytes_transferred} bytes")
        print("[Sender] Transfer completed successfully!")
    except grpc.RpcError as e:
        print(f"[Sender] File transfer error: {e}")

if __name__ == '__main__':
    run()
