"""
Canonical PyTorch model aggregation adapter package.
"""

from .canonical_torch_aggregator import CanonicalTorchAggregator
from distributed_training_engine.model_type import ModelType
from distributed_training_engine.aggregation.aggregator_adapter_registery import (
    AggregatorAdapterRegistery,
)

# Register under ModelType.CANONICAL_TORCH
AggregatorAdapterRegistery.Register(ModelType.CANONICAL_TORCH, CanonicalTorchAggregator)

__all__ = ["CanonicalTorchAggregator"]
