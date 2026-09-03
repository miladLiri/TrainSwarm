"""
Model-agnostic aggregator adapter abstract base class.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .aggregation_request import AggregationRequest
    from .aggregation_result import AggregationResult


class AggregatorAdapter(ABC):
    """
    Model-agnostic abstract base class for federated model delta aggregation adapters.
    Concrete adapters implement loading deltas, validating tensor schemas, computing
    weighted Federated Averaging, and publishing new model versions.
    """

    def __init__(self, request: "AggregationRequest") -> None:
        """
        Initialize the aggregator adapter with an immutable AggregationRequest.

        Args:
            request: Configuration payload containing model ID, versions, base model path,
                     output directory, and trainer update references.
        """
        self.request = request

    @abstractmethod
    def LoadDelta(self) -> None:
        """
        Load all delta artifacts specified in request.updates into memory.

        Raises:
            DeltaAccessError: If a specified delta file does not exist or cannot be read.
            DeltaFormatError: If a delta artifact is corrupted or cannot be deserialized.
        """
        pass

    @abstractmethod
    def ValidateDelta(self) -> None:
        """
        Validate all loaded delta artifacts against the base model schema and verify
        that the target output version artifact does not already exist.

        Raises:
            ExistingModelVersionConflictError: If target model version already exists.
            BaseModelAccessError: If base model path does not exist.
            BaseModelLoadError: If base model cannot be loaded.
            TensorCompatibilityError: If tensor keys, shapes, or dtypes mismatch.
            InvalidUpdateError: If samplesTrained <= 0.
        """
        pass

    @abstractmethod
    def Aggregate(self) -> None:
        """
        Compute sample-weighted Federated Averaging across all valid loaded deltas.
        Produces a single combined parameter delta without modifying the base model on disk.

        Raises:
            AggregationOperationError: If calculation fails.
        """
        pass

    @abstractmethod
    def CreateNewVersion(self) -> "AggregationResult":
        """
        Apply the aggregated delta to the base model, atomically serialize the resulting
        model artifact, and return the operation result descriptor.

        Returns:
            AggregationResult: Metadata descriptor for the published model version.

        Raises:
            ModelSerializationError: If model serialization or file atomic rename fails.
        """
        pass
