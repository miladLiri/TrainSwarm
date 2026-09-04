"""CreateTrainingTaskDto data transfer object for Coordinator API."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class CreateTrainingTaskDto:
    """Data transfer object representing a request to create training tasks on the Coordinator."""

    client_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id_list: List[str]

    def __post_init__(self) -> None:
        """Validate all fields are present, non-empty, and conform to constraints."""
        if not isinstance(self.client_node_id, str) or not self.client_node_id.strip():
            raise ValueError("client_node_id is required and cannot be empty or whitespace")

        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id is required and cannot be empty or whitespace")

        if not isinstance(self.model_version, str) or not self.model_version.strip():
            raise ValueError("model_version is required and cannot be empty or whitespace")

        if not isinstance(self.data_set_id, str) or not self.data_set_id.strip():
            raise ValueError("data_set_id is required and cannot be empty or whitespace")

        if not isinstance(self.shard_id_list, (list, tuple)):
            raise ValueError("shard_id_list must be a non-empty list of strings")

        if len(self.shard_id_list) == 0:
            raise ValueError("shard_id_list must contain at least one shard ID")

        for i, shard_id in enumerate(self.shard_id_list):
            if not isinstance(shard_id, str) or not shard_id.strip():
                raise ValueError(f"shard_id at index {i} cannot be empty or whitespace")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize DTO to camelCase JSON dictionary matching Coordinator API contract."""
        return {
            "clientNodeId": self.client_node_id.strip(),
            "modelId": self.model_id.strip(),
            "modelVersion": self.model_version.strip(),
            "dataSetId": self.data_set_id.strip(),
            "shardIdList": [s.strip() for s in self.shard_id_list],
        }
