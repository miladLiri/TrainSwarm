"""
Training result DTO for the distributed training engine.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ExecutionInfo:
    """
    Execution timing and duration telemetry.
    """
    started_at: str
    completed_at: str
    duration_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "durationMs": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionInfo:
        if not isinstance(data, dict):
            return cls(started_at="", completed_at="", duration_ms=0)
        started_at = str(data.get("startedAt") or data.get("started_at") or "")
        completed_at = str(data.get("completedAt") or data.get("completed_at") or "")
        duration_ms = int(data.get("durationMs") or data.get("duration_ms") or 0)
        return cls(
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )


@dataclass
class DeltaArtifactInfo:
    """
    Metadata describing the exported safetensors model delta artifact.
    """
    filename: str
    path: str
    format: str = "safetensors"
    tensor_count: int = 0
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "path": self.path,
            "format": self.format,
            "tensorCount": self.tensor_count,
            "sizeBytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DeltaArtifactInfo:
        if not isinstance(data, dict):
            return cls(filename="", path="")
        filename = str(data.get("filename") or "")
        path = str(data.get("path") or "")
        fmt = str(data.get("format") or "safetensors")
        tensor_count = int(data.get("tensorCount") or data.get("tensor_count") or 0)
        size_bytes = int(data.get("sizeBytes") or data.get("size_bytes") or 0)
        return cls(
            filename=filename,
            path=path,
            format=fmt,
            tensor_count=tensor_count,
            size_bytes=size_bytes,
        )


@dataclass
class TrainingResult:
    """
    Result returned upon completion of a local training task.
    """
    training_task_id: str
    base_model_id: str
    base_model_version: str
    dataset_id: str
    dataset_shard_id: str
    samples_trained: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution: ExecutionInfo = field(default_factory=lambda: ExecutionInfo(started_at="", completed_at="", duration_ms=0))
    delta: DeltaArtifactInfo = field(default_factory=lambda: DeltaArtifactInfo(filename="", path=""))

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TrainingResult to a camelCase wire dictionary."""
        return {
            "trainingTaskId": self.training_task_id,
            "baseModelId": self.base_model_id,
            "baseModelVersion": self.base_model_version,
            "datasetId": self.dataset_id,
            "datasetShardId": self.dataset_shard_id,
            "samplesTrained": self.samples_trained,
            "metrics": self.metrics,
            "execution": self.execution.to_dict() if isinstance(self.execution, ExecutionInfo) else self.execution,
            "delta": self.delta.to_dict() if isinstance(self.delta, DeltaArtifactInfo) else self.delta,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrainingResult:
        """Construct a TrainingResult from a dictionary supporting camelCase and snake_case keys."""
        if not isinstance(data, dict):
            raise TypeError("TrainingResult payload must be a dictionary.")

        training_task_id = str(data.get("trainingTaskId") or data.get("training_task_id") or "")
        base_model_id = str(data.get("baseModelId") or data.get("base_model_id") or "")
        base_model_version = str(data.get("baseModelVersion") or data.get("base_model_version") or "")
        dataset_id = str(data.get("datasetId") or data.get("dataset_id") or data.get("data_set_id") or "")
        dataset_shard_id = str(data.get("datasetShardId") or data.get("dataset_shard_id") or data.get("data_set_shard_id") or "")
        samples_trained = int(data.get("samplesTrained") or data.get("samples_trained") or 0)
        metrics = data.get("metrics") or {}

        execution_raw = data.get("execution") or {}
        execution = ExecutionInfo.from_dict(execution_raw) if isinstance(execution_raw, dict) else execution_raw

        delta_raw = data.get("delta") or {}
        delta = DeltaArtifactInfo.from_dict(delta_raw) if isinstance(delta_raw, dict) else delta_raw

        return cls(
            training_task_id=training_task_id,
            base_model_id=base_model_id,
            base_model_version=base_model_version,
            dataset_id=dataset_id,
            dataset_shard_id=dataset_shard_id,
            samples_trained=samples_trained,
            metrics=metrics,
            execution=execution,
            delta=delta,
        )

    @classmethod
    def from_json(cls, json_str: str) -> TrainingResult:
        """Construct a TrainingResult from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the TrainingResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

