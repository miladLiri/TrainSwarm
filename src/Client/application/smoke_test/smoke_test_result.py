"""Result DTO for the Smoke Test application use case."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SmokeTestResult:
    """Structured outcome record of a smoke test execution containing timing, throughput, and shard sizing."""

    success: bool
    sample_count: int
    training_time_seconds: Optional[float] = None
    samples_per_second: Optional[float] = None
    shard_training_time_limit_seconds: Optional[float] = None
    estimated_samples_per_shard: Optional[int] = None
    recommended_samples_per_shard: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "success": self.success,
            "sample_count": self.sample_count,
            "training_time_seconds": self.training_time_seconds,
            "samples_per_second": self.samples_per_second,
            "shard_training_time_limit_seconds": self.shard_training_time_limit_seconds,
            "estimated_samples_per_shard": self.estimated_samples_per_shard,
            "recommended_samples_per_shard": self.recommended_samples_per_shard,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SmokeTestResult:
        """Construct a SmokeTestResult from a dictionary."""
        return cls(
            success=bool(data.get("success", False)),
            sample_count=int(data.get("sample_count", 0)),
            training_time_seconds=float(data["training_time_seconds"]) if data.get("training_time_seconds") is not None else None,
            samples_per_second=float(data["samples_per_second"]) if data.get("samples_per_second") is not None else None,
            shard_training_time_limit_seconds=float(data["shard_training_time_limit_seconds"]) if data.get("shard_training_time_limit_seconds") is not None else None,
            estimated_samples_per_shard=int(data["estimated_samples_per_shard"]) if data.get("estimated_samples_per_shard") is not None else None,
            recommended_samples_per_shard=int(data["recommended_samples_per_shard"]) if data.get("recommended_samples_per_shard") is not None else None,
            error=data.get("error"),
        )
