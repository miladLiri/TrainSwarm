"""GetTrainingTaskCommand data transfer object."""

from dataclasses import dataclass


@dataclass
class GetTrainingTaskCommand:
    """Inbound request from Trainer to fetch training task envelope."""
    trainer_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str
