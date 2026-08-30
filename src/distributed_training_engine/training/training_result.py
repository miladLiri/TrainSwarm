"""
Training result DTO for the distributed training engine.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class TrainingResult:
    """
    Result returned upon completion of a local training task.
    """
    task_id: str
    input_checkpoint_version: str
    output_checkpoint_path: str
    training_steps: int
    epochs_completed: int
    final_loss: float
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TrainingResult to a dictionary."""
        return {
            "task_id": self.task_id,
            "input_checkpoint_version": self.input_checkpoint_version,
            "output_checkpoint_path": self.output_checkpoint_path,
            "training_steps": self.training_steps,
            "epochs_completed": self.epochs_completed,
            "final_loss": self.final_loss,
            "metrics": self.metrics,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the TrainingResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
