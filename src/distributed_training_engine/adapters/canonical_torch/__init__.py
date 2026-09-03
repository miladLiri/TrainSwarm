"""
Canonical PyTorch adapter suite.
"""

from .training import CanonicalTorchTrainer, CanonicalTorchAdapter
from .partitioning import CanonicalTorchPartitioner
from .aggragation import CanonicalTorchAggregator

__all__ = [
    "CanonicalTorchTrainer",
    "CanonicalTorchAdapter",
    "CanonicalTorchPartitioner",
    "CanonicalTorchAggregator",
]
