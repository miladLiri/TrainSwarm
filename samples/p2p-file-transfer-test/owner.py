import grpc
import p2p_pb2
import p2p_pb2_grpc
import sys
import os

sys.stdout.reconfigure(line_buffering=True)

def run():
    if len(sys.argv) < 3:
        print("Usage: python owner.py <port> <file_path> [--get-peer-id]")
        sys.exit(1)
        
    port = sys.argv[1]
    file_path = sys.argv[2]
    
    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p2p_pb2_grpc.P2PNodeStub(channel)
    
    if len(sys.argv) >= 4 and sys.argv[3] == "--get-peer-id":
        try:
            info = stub.GetNodeInfo(p2p_pb2.GetNodeInfoRequest(), timeout=2)
            print(info.peer_id, end="")
            sys.exit(0)
        except grpc.RpcError:
            sys.exit(1)

    info = stub.GetNodeInfo(p2p_pb2.GetNodeInfoRequest(), timeout=5)
    print(f"[Owner] Connected to Node gRPC on localhost:{port}")
    print(f"[Owner] Node ID: {info.peer_id}")
    print(f"[Owner] Hosting file: {file_path}")
    print(f"[Owner] Waiting for requests...")
    
    try:
        events = stub.WatchEvents(p2p_pb2.WatchEventsRequest())
        for event in events:
            if event.type == p2p_pb2.EVENT_FILE_REQUESTED:
                print(f"[Owner] Peer {event.peer_id} requested file: {event.message}")
                if event.message == os.path.basename(file_path) or event.message == file_path:
                    print(f"[Owner] Sending file {file_path} to requester...")
                    try:
                        transfer_stream = stub.SendFile(p2p_pb2.SendFileRequest(
                            peer_id=event.peer_id,
                            file_path=file_path
                        ))
                        for progress in transfer_stream:
                            print(f"[Owner] Upload Progress: {progress.bytes_transferred} bytes")
                        print("[Owner] File sent successfully!")
                        break # exit after one transfer
                    except grpc.RpcError as e:
                        print(f"[Owner] Error sending file: {e}")
                else:
                    print(f"[Owner] Requested file not found: {event.message}")
    except grpc.RpcError as e:
        print(f"[Owner] gRPC Error: {e}")

if __name__ == '__main__':
    run()
