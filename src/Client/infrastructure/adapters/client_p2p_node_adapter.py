"""Client P2P node adapter connecting to local Go p2p-node over localhost gRPC."""

from abc import ABC, abstractmethod
import json
import logging
import os
import queue
import threading
import time
from typing import Callable, Dict, Optional

import grpc

try:
    from distributed_training_engine.training import TrainingResult
except ImportError:
    try:
        from distributed_training_engine import TrainingResult
    except ImportError:
        pass

from .p2p_pb2 import (
    ClientActionRequest,
    ClientActionResponse,
    ClientActionType,
    GetNodeInfoRequest,
)
from .p2p_pb2_grpc import P2PNodeStub

logger = logging.getLogger("trainswarm.client.p2p_adapter")


class P2PNodeConnectionError(Exception):
    """Raised when communication with the local p2p-node fails."""
    pass


class IClientP2PNodeAdapter(ABC):
    """Adapter for Client communication with the local Go p2p-node sidecar."""

    @abstractmethod
    def get_p2p_node_id(self) -> str:
        """Query local p2p-node sidecar via gRPC GetNodeInfo and return its libp2p peer ID."""
        pass

    @abstractmethod
    def start_listening(self) -> None:
        """Establish long-lived bidirectional streaming RPC (ServeClientRequests) with p2p-node."""
        pass

    @abstractmethod
    def stop_listening(self) -> None:
        """Terminate the background inbound request streaming connection."""
        pass


class ClientP2PNodeAdapter(IClientP2PNodeAdapter):
    """Client adapter connecting to Go p2p-node sidecar over localhost gRPC."""

    def __init__(
        self,
        target: Optional[str] = None,
        get_training_task_handler: Optional[Callable] = None,
        transfer_model_handler: Optional[Callable] = None,
        transfer_shard_handler: Optional[Callable] = None,
        update_model_handler: Optional[Callable] = None,
    ) -> None:
        grpc_host = os.getenv("P2P_GRPC_HOST", "127.0.0.1")
        grpc_port = os.getenv("P2P_GRPC_PORT", os.getenv("GRPC_PORT", "50051"))
        self.target = target or f"{grpc_host}:{grpc_port}"

        self.get_training_task_handler = get_training_task_handler
        self.transfer_model_handler = transfer_model_handler
        self.transfer_shard_handler = transfer_shard_handler
        self.update_model_handler = update_model_handler

        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[P2PNodeStub] = None
        self._listening: bool = False
        self._listener_thread: Optional[threading.Thread] = None
        self._response_queue: queue.Queue = queue.Queue()

    def _get_stub(self) -> P2PNodeStub:
        if self._stub is None:
            self._channel = grpc.insecure_channel(self.target)
            self._stub = P2PNodeStub(self._channel)
        return self._stub

    def get_p2p_node_id(self) -> str:
        """Query local p2p-node sidecar via gRPC GetNodeInfo and return its libp2p peer ID."""
        stub = self._get_stub()
        try:
            req = GetNodeInfoRequest()
            resp = stub.GetNodeInfo(req, timeout=5.0)
            if not resp.peer_id:
                raise P2PNodeConnectionError("p2p-node returned empty peer_id")
            logger.info("Retrieved P2P node ID from sidecar: %s", resp.peer_id)
            return resp.peer_id
        except grpc.RpcError as e:
            raise P2PNodeConnectionError(f"Failed to connect to local p2p-node at {self.target}: {e}") from e
        except Exception as e:
            if isinstance(e, P2PNodeConnectionError):
                raise
            raise P2PNodeConnectionError(f"Error querying p2p-node at {self.target}: {e}") from e

    def start_listening(self) -> None:
        """Start listening for inbound client actions from p2p-node in a background daemon thread."""
        if self._listening:
            return
        self._listening = True
        self._listener_thread = threading.Thread(
            target=self._run_listen_loop,
            name="ClientP2PNodeListener",
            daemon=True,
        )
        self._listener_thread.start()
        logger.info("Started Client P2P node inbound request listener.")

    def stop_listening(self) -> None:
        """Stop listening for inbound requests."""
        self._listening = False
        # Push None to unblock generator
        self._response_queue.put(None)
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        logger.info("Stopped Client P2P node inbound request listener.")

    def _response_generator(self):
        # Yield an initial handshake message so gRPC establishes the bidirectional stream immediately
        yield ClientActionResponse(request_id="client-init", success=True)
        while self._listening:
            item = self._response_queue.get()
            if item is None:
                break
            yield item

    def _run_listen_loop(self) -> None:
        """Main loop managing connection and stream with p2p-node ServeClientRequests."""
        while self._listening:
            try:
                channel = grpc.insecure_channel(self.target)
                stub = P2PNodeStub(channel)
                logger.info("Connecting to ServeClientRequests stream at %s...", self.target)

                # Send requests from queue, receive requests from p2p-node
                inbound_stream = stub.ServeClientRequests(self._response_generator())

                for action_req in inbound_stream:
                    if not self._listening:
                        break
                    # Handle each inbound action
                    self._dispatch_action(action_req)

            except grpc.RpcError as e:
                if not self._listening:
                    break
                logger.warning("ServeClientRequests stream disconnected: %s. Reconnecting in 2s...", e)
                time.sleep(2.0)
            except Exception as e:
                if not self._listening:
                    break
                logger.error("Unexpected error in ServeClientRequests loop: %s. Retrying in 2s...", e, exc_info=True)
                time.sleep(2.0)

    def _dispatch_action(self, req: ClientActionRequest) -> None:
        """Process an inbound ClientActionRequest and push ClientActionResponse to response queue."""
        logger.info(
            "Received inbound P2P action: request_id=%s, action_type=%s, trainer_peer_id=%s",
            req.request_id,
            req.action_type,
            req.trainer_peer_id,
        )
        try:
            if req.action_type == ClientActionType.ACTION_GET_TRAINING_TASK:
                if not self.get_training_task_handler:
                    raise RuntimeError("GetTrainingTaskCommandHandler not registered")
                task = self.get_training_task_handler.handle(
                    trainer_node_id=req.trainer_peer_id,
                    model_id=req.model_id,
                    model_version=req.model_version,
                    data_set_id=req.dataset_id,
                    shard_id=req.shard_id,
                )
                task_json = json.dumps(task.to_dict()) if hasattr(task, "to_dict") else json.dumps(task)
                self._response_queue.put(ClientActionResponse(
                    request_id=req.request_id,
                    success=True,
                    training_task_json=task_json,
                ))

            elif req.action_type == ClientActionType.ACTION_TRANSFER_MODEL:
                if not self.transfer_model_handler:
                    raise RuntimeError("TransferModelCommandHandler not registered")
                file_path = self.transfer_model_handler.handle(
                    trainer_node_id=req.trainer_peer_id,
                    model_id=req.model_id,
                    model_version=req.model_version,
                )
                self._response_queue.put(ClientActionResponse(
                    request_id=req.request_id,
                    success=True,
                    file_path=file_path,
                ))

            elif req.action_type == ClientActionType.ACTION_TRANSFER_SHARD:
                if not self.transfer_shard_handler:
                    raise RuntimeError("TransferShardCommandHandler not registered")
                file_path = self.transfer_shard_handler.handle(
                    trainer_node_id=req.trainer_peer_id,
                    model_id=req.model_id,
                    model_version=req.model_version,
                    data_set_id=req.dataset_id,
                    shard_id=req.shard_id,
                )
                self._response_queue.put(ClientActionResponse(
                    request_id=req.request_id,
                    success=True,
                    file_path=file_path,
                ))

            elif req.action_type == ClientActionType.ACTION_UPDATE_MODEL:
                if not self.update_model_handler:
                    raise RuntimeError("UpdateModelCommandHandler not registered")
                # Parse TrainingResult
                result_dict = json.loads(req.training_result_json)
                if hasattr(TrainingResult, "from_dict"):
                    result = TrainingResult.from_dict(result_dict)
                else:
                    result = TrainingResult(**result_dict)
                
                self.update_model_handler.handle(
                    trainer_node_id=req.trainer_peer_id,
                    training_result=result,
                    saved_update_artifact_path=req.saved_update_path,
                )
                self._response_queue.put(ClientActionResponse(
                    request_id=req.request_id,
                    success=True,
                ))
            else:
                raise ValueError(f"Unsupported action type: {req.action_type}")

        except Exception as e:
            logger.error("Failed to execute P2P inbound action %s: %s", req.request_id, e, exc_info=True)
            self._response_queue.put(ClientActionResponse(
                request_id=req.request_id,
                success=False,
                error=str(e),
            ))

    def close(self) -> None:
        self.stop_listening()
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None
