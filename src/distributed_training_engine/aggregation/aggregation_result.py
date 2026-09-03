"""
Aggregation result DTO encapsulating the outcome of a successful aggregation round.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class AggregationResult:
    """
    Result descriptor returned upon successful model aggregation and version publishing.
    """
    modelId: str
    baseModelVersion: int
    newModelVersion: int
    updatesCount: int
    modelPath: str

    @property
    def model_id(self) -> str:
        return self.modelId

    @property
    def base_model_version(self) -> int:
        return self.baseModelVersion

    @property
    def new_model_version(self) -> int:
        return self.newModelVersion

    @property
    def updates_count(self) -> int:
        return self.updatesCount

    @property
    def model_path(self) -> str:
        return self.modelPath

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AggregationResult:
        return cls(
            modelId=data.get("modelId") or data.get("model_id", ""),
            baseModelVersion=int(data.get("baseModelVersion") if "baseModelVersion" in data else data.get("base_model_version", 0)),
            newModelVersion=int(data.get("newModelVersion") if "newModelVersion" in data else data.get("new_model_version", 0)),
            updatesCount=int(data.get("updatesCount") if "updatesCount" in data else data.get("updates_count", 0)),
            modelPath=data.get("modelPath") or data.get("model_path", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modelId": self.modelId,
            "baseModelVersion": self.baseModelVersion,
            "newModelVersion": self.newModelVersion,
            "updatesCount": self.updatesCount,
            "modelPath": self.modelPath,
        }
