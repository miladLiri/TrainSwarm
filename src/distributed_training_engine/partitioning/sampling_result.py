"""
Sampling result model representing representative dataset sample metadata.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class SamplingResult:
    """
    Metadata describing the extracted representative sample artifact.
    """
    datasetId: str
    samplePath: str
    sampleCount: int = 1

    @property
    def dataset_id(self) -> str:
        return self.datasetId

    @property
    def sample_path(self) -> str:
        return self.samplePath

    @property
    def sample_count(self) -> int:
        return self.sampleCount

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to wire dictionary."""
        return {
            "datasetId": self.datasetId,
            "samplePath": self.samplePath,
            "sampleCount": self.sampleCount,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SamplingResult:
        """Construct from dictionary."""
        return cls(
            datasetId=data.get("datasetId") or data.get("dataset_id", ""),
            samplePath=data.get("samplePath") or data.get("sample_path", ""),
            sampleCount=int(data.get("sampleCount", data.get("sample_count", 1))),
        )
