"""UpdateModelCommand data transfer object."""

from dataclasses import dataclass

try:
    from distributed_training_engine.training import TrainingResult
except ImportError:
    try:
        from distributed_training_engine import TrainingResult
    except ImportError:
        pass


@dataclass
class UpdateModelCommand:
    """Inbound request from Trainer transmitting completed TrainingResult and saved update artifact path."""
    trainer_node_id: str
    training_result: TrainingResult
    saved_update_artifact_path: str
