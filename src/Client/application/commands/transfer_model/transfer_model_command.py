"""TransferModelCommand data transfer object."""

from dataclasses import dataclass


@dataclass
class TransferModelCommand:
    """Inbound request from Trainer to fetch base model checkpoint path."""
    trainer_node_id: str
    model_id: str
    model_version: str
