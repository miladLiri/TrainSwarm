"""SetNodeIdCommand data transfer object for Client."""

from dataclasses import dataclass


@dataclass
class SetNodeIdCommand:
    """Instructs the application to query local p2p-node and record its peer ID."""
    pass
