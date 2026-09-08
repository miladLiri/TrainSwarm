"""Trainer P2P node adapter connecting to local Go p2p-node over localhost gRPC."""

from abc import ABC, abstractmethod
import json
import logging
import os
from typing import Optional

import grpc

try:
    from distributed_training_engine.training import TrainingTask, TrainingResult
except ImportError:
    try:
        from distributed_training_engine import TrainingTask, TrainingResult
    except ImportError:
        pass

from .p2p_pb2 import (
    GetNodeInfoRequest,
    GetTrainingTaskRequest,
    GetModelRequest,
    GetShardRequest,
    SendUpdateRequest,
)
from .p2p_pb2_grpc import P2PNodeStub

logger = logging.getLogger("trainswarm.trainer.p2p_adapter")


class P2PNodeConnectionError(Exception):
    """Raised when communication with the local p2p-node fails."""
    pass


class P2PTransferError(Exception):
    """Raised when a P2P transfer operation fails."""
    pass


class ITrainerP2PNodeAdapter(ABC):
    """Adapter for Trainer communication with the local Go p2p-node sidecar."""

    @abstractmethod
    def get_p2p_node_id(self) -> str:
        """Query local p2p-node sidecar via gRPC GetNodeInfo and return its libp2p peer ID."""
        pass

    @abstractmethod
    def get_training_task(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
        data_set_id: str,
        shard_id: str,
    ) -> TrainingTask:
        """Connect to client_node_id via p2p-node and fetch the TrainingTask envelope."""
        pass

    @abstractmethod
    def get_model(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
    ) -> str:
        """Request and stream base model checkpoint from client_node_id over P2P."""
        pass

    @abstractmethod
    def get_shard(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
        data_set_id: str,
        shard_id: str,
    ) -> str:
        """Request and stream dataset shard file from client_node_id over P2P."""
        pass

    @abstractmethod
    def send_update(
        self,
        client_node_id: str,
        training_result: TrainingResult,
        update_artifact_path: str,
    ) -> None:
        """Stream trained weights delta and transmit TrainingResult metadata to client_node_id over P2P."""
        pass


class TrainerP2PNodeAdapter(ITrainerP2PNodeAdapter):
    """gRPC client implementation communicating with localhost Go p2p-node sidecar."""

    def __init__(self, target: Optional[str] = None, timeout: float = 60.0) -> None:
        grpc_host = os.getenv("P2P_GRPC_HOST", "127.0.0.1")
        grpc_port = os.getenv("P2P_GRPC_PORT", os.getenv("GRPC_PORT", "50051"))
        self.target = target or f"{grpc_host}:{grpc_port}"
        self.timeout = timeout
        self._channel = None
        self._stub = None

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

    def get_training_task(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
        data_set_id: str,
        shard_id: str,
    ) -> TrainingTask:
        stub = self._get_stub()
        try:
            req = GetTrainingTaskRequest(
                client_peer_id=client_node_id,
                model_id=model_id,
                model_version=str(model_version),
                data_set_id=data_set_id,
                shard_id=str(shard_id),
            )
            resp = stub.GetTrainingTask(req, timeout=self.timeout)
            if not resp.success:
                raise P2PTransferError(f"Failed to get training task from {client_node_id}: {resp.error}")
            
            task_dict = json.loads(resp.training_task_json)
            if hasattr(TrainingTask, "from_dict"):
                return TrainingTask.from_dict(task_dict)
            return TrainingTask(**task_dict)
        except grpc.RpcError as e:
            raise P2PTransferError(f"gRPC error fetching training task: {e}") from e
        except Exception as e:
            if isinstance(e, P2PTransferError):
                raise
            raise P2PTransferError(f"Unexpected error fetching training task: {e}") from e

    def get_model(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
    ) -> str:
        stub = self._get_stub()
        try:
            req = GetModelRequest(
                client_peer_id=client_node_id,
                model_id=model_id,
                model_version=str(model_version),
            )
            resp = stub.GetModel(req, timeout=self.timeout)
            if not resp.success:
                raise P2PTransferError(f"Failed to get model from {client_node_id}: {resp.error}")
            return resp.local_file_path
        except grpc.RpcError as e:
            raise P2PTransferError(f"gRPC error fetching model: {e}") from e
        except Exception as e:
            if isinstance(e, P2PTransferError):
                raise
            raise P2PTransferError(f"Unexpected error fetching model: {e}") from e

    def get_shard(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
        data_set_id: str,
        shard_id: str,
    ) -> str:
        stub = self._get_stub()
        try:
            req = GetShardRequest(
                client_peer_id=client_node_id,
                model_id=model_id,
                model_version=str(model_version),
                data_set_id=data_set_id,
                shard_id=str(shard_id),
            )
            resp = stub.GetShard(req, timeout=self.timeout)
            if not resp.success:
                raise P2PTransferError(f"Failed to get shard from {client_node_id}: {resp.error}")
            return resp.local_file_path
        except grpc.RpcError as e:
            raise P2PTransferError(f"gRPC error fetching shard: {e}") from e
        except Exception as e:
            if isinstance(e, P2PTransferError):
                raise
            raise P2PTransferError(f"Unexpected error fetching shard: {e}") from e

    def send_update(
        self,
        client_node_id: str,
        training_result: TrainingResult,
        update_artifact_path: str,
    ) -> None:
        stub = self._get_stub()
        try:
            if hasattr(training_result, "to_dict"):
                result_json = json.dumps(training_result.to_dict())
            elif hasattr(training_result, "__dict__"):
                result_json = json.dumps(training_result.__dict__)
            else:
                result_json = str(training_result)

            req = SendUpdateRequest(
                client_peer_id=client_node_id,
                training_result_json=result_json,
                update_artifact_path=str(update_artifact_path),
            )
            resp = stub.SendUpdate(req, timeout=self.timeout)
            if not resp.success:
                raise P2PTransferError(f"Failed to send update to {client_node_id}: {resp.error}")
        except grpc.RpcError as e:
            raise P2PTransferError(f"gRPC error sending update: {e}") from e
        except Exception as e:
            if isinstance(e, P2PTransferError):
                raise
            raise P2PTransferError(f"Unexpected error sending update: {e}") from e

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None
