# Interface Contract: Aggregator Adapter & Orchestration

**Module**: `distributed_training_engine.aggregation`  
**Feature**: `010-distributed-training-aggregation`  
**Status**: Stable

---

## 1. `AggregatorAdapter` (Abstract Base Class)

Defined in `src/distributed_training_engine/aggregation/aggregator_adapter.py`.  
Model-agnostic abstract base class for all framework-specific aggregator adapters.

```python
class AggregatorAdapter(ABC):
    """
    Model-agnostic abstract contract for federated model delta aggregation.
    Concrete adapters implement reading, validating, averaging, and serializing model artifacts.
    """

    def __init__(self, request: AggregationRequest) -> None:
        """
        Initialize the aggregator adapter with an immutable AggregationRequest.
        """
        self.request = request

    @abstractmethod
    def LoadDelta(self) -> None:
        """
        Open and load all delta artifacts specified in self.request.updates.

        Raises:
            DeltaAccessError: If any delta file is missing or unreadable.
            DeltaFormatError: If any delta file is corrupted or cannot be deserialized.
        """
        pass

    @abstractmethod
    def ValidateDelta(self) -> None:
        """
        Validate all loaded deltas against the base model schema and verify target output paths.

        Validation Checks:
            1. Target artifact `<modelId>_<newVersion>.pt2` does not already exist.
            2. Base model artifact exists and can be loaded.
            3. All deltas contain valid tensors matching base model keys, shapes, and dtypes.
            4. All updates have samplesTrained > 0.

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
        Perform sample-weighted Federated Averaging across all loaded deltas to compute
        a single aggregated parameter delta.

        Invariants:
            - Σ(samplesTrained_i * delta_i) / Σ(samplesTrained_i) computed per tensor.
            - Deltas are NEVER applied sequentially to the base model.
            - Base model file on disk is never modified.

        Raises:
            AggregationOperationError: If mathematical calculation fails.
        """
        pass

    @abstractmethod
    def CreateNewVersion(self) -> AggregationResult:
        """
        Apply the aggregated delta to the base model, atomically persist the resulting model
        version, and return the operation result.

        Invariants:
            - New model is written to a temporary file first before atomic rename.
            - Temporary file is unlinked on serialization failure.
            - Returned AggregationResult reflects the published model version.

        Returns:
            AggregationResult: Metadata descriptor for the newly created model.

        Raises:
            ModelSerializationError: If saving the new model artifact fails.
        """
        pass
```

---

## 2. `AggregatorAdapterRegistry`

Defined in `src/distributed_training_engine/aggregation/aggregator_adapter_registery.py`.  
Registry mapping `ModelType` enum values to concrete `AggregatorAdapter` implementations.

```python
class AggregatorAdapterRegistry:
    """Registry maintaining mappings between ModelType and AggregatorAdapter classes."""

    @classmethod
    def Register(cls, model_type: ModelType, adapter_class: Type[AggregatorAdapter]) -> None:
        """Register an aggregator adapter class for a specific model type."""
        pass

    @classmethod
    def Get(cls, model_type: ModelType) -> Type[AggregatorAdapter]:
        """
        Retrieve the registered aggregator adapter class for a model type.

        Raises:
            AggregatorAdapterNotFoundError: If no adapter is registered for the requested ModelType.
            UnsupportedModelTypeError: If model_type is invalid.
        """
        pass
```

---

## 3. `AggregationOrchestrator`

Defined in `src/distributed_training_engine/aggregation/aggregation_orchecstrator.py`.  
Lifecycle coordinator for model aggregation. Contains zero framework-specific logic.

```python
class AggregationOrchestrator:
    """
    Orchestrates the lifecycle of model aggregation across participating trainers.
    Resolves adapters through the registry and drives the sequential aggregation flow.
    """

    def __init__(self, model_type: ModelType) -> None:
        """
        Initialize the orchestrator with the target model type.
        Resolves the corresponding adapter class from AggregatorAdapterRegistry.
        """
        self.model_type = model_type
        self.adapter_class = AggregatorAdapterRegistry.Get(model_type)

    def aggregate(self, request: AggregationRequest) -> AggregationResult:
        """
        Execute the full aggregation lifecycle:
        1. adapter = self.adapter_class(request)
        2. adapter.LoadDelta()
        3. adapter.ValidateDelta()
        4. adapter.Aggregate()
        5. result = adapter.CreateNewVersion()
        6. return result

        Returns:
            AggregationResult: Summary of the published model version.
        """
        pass
```
