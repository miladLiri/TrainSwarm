"""TransferShardCommand data transfer object."""

from dataclasses import dataclass


@dataclass
class TransferShardCommand:
    """Inbound request from Trainer to fetch dataset shard file path."""
    trainer_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str
