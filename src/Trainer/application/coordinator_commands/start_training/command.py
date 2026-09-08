"""Command models and envelope for StartTraining coordinator command."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class CommandType(str, Enum):
    StartTraining = "StartTraining"


@dataclass(frozen=True)
class CommandEnvelope:
    id: str
    type: str
    data: str  # Raw UTF-8 JSON payload string


@dataclass(frozen=True)
class StartTrainingCommand:
    client_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartTrainingCommand":
        client_node_id = data.get("clientNodeId") or data.get("client_node_id")
        model_id = data.get("modelId") or data.get("model_id")
        model_version = data.get("modelVersion") or data.get("model_version")
        data_set_id = data.get("dataSetId") or data.get("data_set_id") or data.get("datasetId") or data.get("dataset_id")
        shard_id = data.get("shardId") or data.get("shard_id")

        missing = []
        if not client_node_id:
            missing.append("client_node_id")
        if not model_id:
            missing.append("model_id")
        if not model_version:
            missing.append("model_version")
        if not data_set_id:
            missing.append("data_set_id")
        if not shard_id:
            missing.append("shard_id")

        if missing:
            raise ValueError(f"Missing required fields for StartTrainingCommand: {missing}. Received: {data}")

        return cls(
            client_node_id=str(client_node_id),
            model_id=str(model_id),
            model_version=str(model_version),
            data_set_id=str(data_set_id),
            shard_id=str(shard_id),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clientNodeId": self.client_node_id,
            "modelId": self.model_id,
            "modelVersion": self.model_version,
            "dataSetId": self.data_set_id,
            "shardId": self.shard_id,
        }
