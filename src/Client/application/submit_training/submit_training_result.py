"""Result DTO for the Submit Training application use case."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SubmitTrainingResult:
    """Structured response detailing submission outcome and registered task IDs."""

    success: bool
    model_id: Optional[str] = None
    dataset_id: Optional[str] = None
    shard_count: Optional[int] = None
    training_task_ids: Optional[List[str]] = None
    recommended_samples_per_shard: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary matching JSON contract."""
        return {
            "success": self.success,
            "model_id": self.model_id,
            "dataset_id": self.dataset_id,
            "shard_count": self.shard_count,
            "training_task_ids": self.training_task_ids,
            "recommended_samples_per_shard": self.recommended_samples_per_shard,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SubmitTrainingResult:
        """Construct SubmitTrainingResult from a dictionary."""
        return cls(
            success=bool(data.get("success", False)),
            model_id=data.get("model_id"),
            dataset_id=data.get("dataset_id"),
            shard_count=int(data["shard_count"]) if data.get("shard_count") is not None else None,
            training_task_ids=data.get("training_task_ids"),
            recommended_samples_per_shard=int(data["recommended_samples_per_shard"]) if data.get("recommended_samples_per_shard") is not None else None,
            error=data.get("error"),
        )
