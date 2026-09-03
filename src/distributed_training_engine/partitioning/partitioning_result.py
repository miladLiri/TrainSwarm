"""
Result models for dataset partitioning operations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PartitionedShard:
    """
    Metadata describing an individual generated dataset shard.
    """
    shardId: str
    sampleCount: int
    artifactPath: str

    @property
    def shard_id(self) -> str:
        return self.shardId

    @property
    def sample_count(self) -> int:
        return self.sampleCount

    @property
    def artifact_path(self) -> str:
        return self.artifactPath

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to wire dictionary."""
        return {
            "shardId": self.shardId,
            "sampleCount": self.sampleCount,
            "artifactPath": self.artifactPath,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PartitionedShard:
        """Construct PartitionedShard from dictionary."""
        return cls(
            shardId=str(data.get("shardId") or data.get("shard_id", "")),
            sampleCount=int(data.get("sampleCount", data.get("sample_count", 0))),
            artifactPath=str(data.get("artifactPath") or data.get("artifact_path", "")),
        )


@dataclass
class PartitioningResult:
    """
    Complete result returned by the partitioning operation.
    """
    datasetId: str
    shardCount: int
    shards: List[PartitionedShard] = field(default_factory=list)

    @property
    def dataset_id(self) -> str:
        return self.datasetId

    @property
    def shard_count(self) -> int:
        return self.shardCount

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to wire dictionary matching specification format."""
        return {
            "datasetId": self.datasetId,
            "shardCount": self.shardCount,
            "shards": [s.to_dict() for s in self.shards],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PartitioningResult:
        """Construct PartitioningResult from dictionary."""
        shards_raw = data.get("shards", [])
        return cls(
            datasetId=str(data.get("datasetId") or data.get("dataset_id", "")),
            shardCount=int(data.get("shardCount", data.get("shard_count", len(shards_raw)))),
            shards=[PartitionedShard.from_dict(s) if isinstance(s, dict) else s for s in shards_raw],
        )
