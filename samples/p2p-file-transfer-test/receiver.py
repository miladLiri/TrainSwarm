import grpc
import p2p_pb2
import p2p_pb2_grpc
import sys
import time

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

def run():
    if len(sys.argv) < 3:
        print("Usage: python receiver.py <port> <node_b_id>")
        sys.exit(1)
        
    port = sys.argv[1]
    node_b_id = sys.argv[2]
    
    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = p2p_pb2_grpc.P2PNodeStub(channel)
    
    print(f"[Receiver] Connected to Node B gRPC on localhost:{port}")
    print(f"[Receiver] Waiting for events...")
    
    # Watch events
    try:
        events = stub.WatchEvents(p2p_pb2.WatchEventsRequest())
        
        for event in events:
            if event.type == p2p_pb2.EVENT_TRANSFER_REQUESTED:
                print(f"[Receiver] Incoming file transfer requested! ID: {event.transfer_id}, File: {event.transfer_metadata.file_name} ({event.transfer_metadata.file_size} bytes)")
                
                # Accept file
                accept_req = p2p_pb2.AcceptFileRequest(
                    transfer_id=event.transfer_id,
                    destination_path=f"received_{event.transfer_metadata.file_name}"
                )
                
                try:
                    progress_stream = stub.AcceptFile(accept_req)
                    for progress in progress_stream:
                        print(f"[Receiver] Progress: {progress.bytes_transferred}/{event.transfer_metadata.file_size} bytes")
                    print(f"[Receiver] Transfer {event.transfer_id} completed successfully!")
                except grpc.RpcError as e:
                    print(f"[Receiver] Error accepting file: {e}")
                
                break # Exit after one transfer for the test
            elif event.type == p2p_pb2.EVENT_CONNECTION_UPGRADED_TO_DIRECT:
                print("[Receiver] 🎉 Connection upgraded to direct (Hole punch successful!)")
            elif event.type == p2p_pb2.EVENT_HOLE_PUNCH_FAILED:
                print("[Receiver] ⚠️ Hole punch failed. Falling back to relay circuit...")
            else:
                print(f"[Receiver] Event: {p2p_pb2.EventType.Name(event.type)}")
    except grpc.RpcError as e:
        print(f"[Receiver] gRPC Error: {e}")

if __name__ == '__main__':
    run()
