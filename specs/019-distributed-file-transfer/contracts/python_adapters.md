# Python P2P Node Adapter Contracts

**Feature**: `019-distributed-file-transfer` | **Phase**: 1 | **Date**: 2026-09-08

## 1. `TrainerP2PNodeAdapter` Interface

Located at: `src/Trainer/infrastructure/adapters/trainer_p2p_node_adapter.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from distributed_training_engine import TrainingTask, TrainingResult

class ITrainerP2PNodeAdapter(ABC):
    """Adapter for Trainer communication with the local Go p2p-node sidecar."""

    @abstractmethod
    def get_p2p_node_id(self) -> str:
        """Query local p2p-node sidecar via gRPC GetNodeInfo and return its libp2p peer ID.
        
        Raises:
            P2PNodeConnectionError: If the sidecar is unreachable or reports an error.
        """
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
        """Connect to client_node_id via p2p-node and fetch the TrainingTask envelope.
        
        Raises:
            P2PTransferError: If the transfer fails or peer rejects the request.
        """
        pass

    @abstractmethod
    def get_model(
        self,
        client_node_id: str,
        model_id: str,
        model_version: str,
    ) -> str:
        """Request and stream base model checkpoint from client_node_id over P2P.
        
        Saves the file into the Trainer's working directory, overwriting existing files.
        Returns:
            str: Local filesystem path to the saved model checkpoint.
            
        Raises:
            P2PTransferError: If transfer fails.
        """
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
        """Request and stream dataset shard file from client_node_id over P2P.
        
        Saves the file into the Trainer's working directory, overwriting existing files.
        Returns:
            str: Local filesystem path to the saved shard file.
            
        Raises:
            P2PTransferError: If transfer fails.
        """
        pass

    @abstractmethod
    def send_update(
        self,
        client_node_id: str,
        training_result: TrainingResult,
        update_artifact_path: str,
    ) -> None:
        """Stream trained weights delta and transmit TrainingResult metadata to client_node_id over P2P.
        
        Raises:
            P2PTransferError: If transmission fails.
        """
        pass
```

---

## 2. `ClientP2PNodeAdapter` Interface

Located at: `src/Client/infrastructure/adapters/client_p2p_node_adapter.py`

```python
from abc import ABC, abstractmethod

class IClientP2PNodeAdapter(ABC):
    """Adapter for Client communication with the local Go p2p-node sidecar."""

    @abstractmethod
    def get_p2p_node_id(self) -> str:
        """Query local p2p-node sidecar via gRPC GetNodeInfo and return its libp2p peer ID.
        
        Raises:
            P2PNodeConnectionError: If the sidecar is unreachable or reports an error.
        """
        pass

    @abstractmethod
    def start_listening(self) -> None:
        """Establish long-lived bidirectional streaming RPC (ServeClientRequests) with p2p-node.
        
        Dispatches inbound libp2p requests to application command handlers:
        - ACTION_GET_TRAINING_TASK -> GetTrainingTaskCommandHandler
        - ACTION_TRANSFER_MODEL    -> TransferModelCommandHandler
        - ACTION_TRANSFER_SHARD    -> TransferShardCommandHandler
        - ACTION_UPDATE_MODEL      -> UpdateModelCommandHandler
        """
        pass

    @abstractmethod
    def stop_listening(self) -> None:
        """Terminate the background inbound request streaming connection."""
        pass
```
