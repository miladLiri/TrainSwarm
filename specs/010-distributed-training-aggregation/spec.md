# Feature Specification: Distributed Training Engine — Aggregation Module

**Feature Branch**: `010-distributed-training-aggregation`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Introduce a model-agnostic aggregation subsystem into distributed_training_engine that collects the completed training updates for a federated-training round, loads and validates the delta artifacts produced by trainers, performs weighted Federated Averaging, and creates the next model version by applying the aggregated delta to the immutable base model."

## Clarifications

### Session 2026-09-03

- Q: How should CanonicalTorchAggregator verify that a loaded delta artifact belongs to the expected model ID and base model version? → A: Do not verify model ID or base version from the delta file or filename; model compatibility is validated strictly by matching tensor keys, shapes, and dtypes against the base model state dict.
- Q: How should CanonicalTorchAggregator handle non-floating point tensors or integer tracking buffers during weighted Federated Averaging? → A: Apply weighted FedAvg to floating-point tensors; for integer buffers, round the weighted average to the nearest integer and cast back to the native integer dtype.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Model-Agnostic Weighted Federated Averaging Aggregation (Priority: P1)

As a Client or Aggregator node operator in the TrainSwarm data plane, I want to collect completed trainer updates for a federated training round, compute a weighted Federated Average across valid parameter deltas, apply the combined delta to an immutable base model, and persist the next model version, so that the global model improves iteratively without centralizing raw training data or worker gradients.

**Why this priority**: P1 is the foundational capability of the aggregation subsystem. Without model aggregation and new version publication, federated learning rounds cannot complete or advance to subsequent training iterations.

**Independent Test**: Provide an immutable base model artifact (e.g. `gpt2_0.pt2`), and two or more valid delta artifacts produced by trainer nodes with known `samplesTrained` counts (e.g. Delta A with 10 samples and Delta B with 40 samples). Construct an `AggregationRequest` and invoke `AggregationOrchestrator.aggregate()`. Verify that weighted Federated Averaging produces an exact mathematical combination (`0.2 * Delta A + 0.8 * Delta B`), applies the aggregated delta to the base model weights, atomically saves `gpt2_1.pt2` in `newVersionOutputDirectory`, and returns an `AggregationResult` detailing the new version and update count.

**Acceptance Scenarios**:

1. **Given** a valid base model version `V` and `N` valid trainer update deltas with varying `samplesTrained` counts, **When** `AggregationOrchestrator` executes the aggregation lifecycle, **Then** all deltas are combined using weighted Federated Averaging proportional to `samplesTrained`, applied to the base model state, and saved as `<modelId>_<newVersion>.pt2`.
2. **Given** multiple updates with identical `samplesTrained` counts, **When** aggregation executes, **Then** each delta contributes equally (simple average) to the aggregated delta.
3. **Given** a completed aggregation, **When** the returned `AggregationResult` is inspected, **Then** it contains `modelId`, `baseModelVersion`, `newModelVersion`, `updatesCount` matching the number of aggregated deltas, and the canonical `modelPath` of the published model artifact.
4. **Given** an aggregation operation, **When** deltas are applied, **Then** the base model file remains completely unmodified on disk (strict immutability).

---

### User Story 2 - Delta Loading and Comprehensive Pre-Aggregation Validation (Priority: P2)

As an aggregation orchestrator, I want to strictly load and validate all referenced delta artifacts against the base model schema before performing mathematical averaging, so that corrupt, mismatched, or out-of-order trainer deltas fail fast without corrupting global model state or generating invalid model versions.

**Why this priority**: Guarantees system integrity and the "all-or-nothing" architectural invariant. Partial aggregations or incorporating corrupted deltas can irreversibly diverge the global model.

**Independent Test**: Supply an `AggregationRequest` containing one delta artifact that has mismatched tensor shapes, missing parameter keys, non-positive `samplesTrained`, or an unreadable file path. Run `AggregationOrchestrator.aggregate()`. Verify that the orchestrator aborts execution immediately during `ValidateDelta()`, raises the specific exception (`TensorCompatibilityError`, `InvalidUpdateError`, or `DeltaAccessError`), and produces zero new model artifacts.

**Acceptance Scenarios**:

1. **Given** an update referencing a non-existent, unreadable, or corrupted delta file, **When** `LoadDelta()` executes, **Then** the aggregator fails fast with `DeltaAccessError` or `DeltaFormatError` and halts the aggregation flow.
2. **Given** a delta containing tensor keys that do not match the base model state dict (missing required keys or containing unexpected keys), **When** `ValidateDelta()` executes, **Then** validation fails with `TensorCompatibilityError`.
3. **Given** a delta whose tensor shapes or dtypes do not match corresponding base model tensors, **When** `ValidateDelta()` executes, **Then** validation fails with `TensorCompatibilityError`.
4. **Given** an update whose `samplesTrained` is less than or equal to zero, **When** `ValidateDelta()` executes, **Then** validation fails with `InvalidUpdateError`.
5. **Given** any validation failure across any delta in the request, **When** validation completes, **Then** no delta calculations take place and no model version is created or published.

---

### User Story 3 - Model-Agnostic Abstraction and Adapter Registry (Priority: P3)

As a developer extending the distributed training engine, I want a model-agnostic `AggregatorAdapter` abstraction and an `AggregatorAdapterRegistry` decoupled from framework-specific serialization, so that future model frameworks (e.g. ONNX, SafeTensors-only, HuggingFace) can be added without modifying the core aggregation orchestration lifecycle.

**Why this priority**: Architectural boundary requirement. Enforces clean separation between lifecycle coordination (orchestration) and framework-specific tensor mathematics and file serialization.

**Independent Test**: Register a concrete adapter class for a model type in `AggregatorAdapterRegistry`. Instantiate `AggregationOrchestrator` with an `AggregationRequest` containing that `ModelType`, and verify that the orchestrator resolves and instantiates the adapter passing the request to its constructor. Verify that querying an unregistered `ModelType` raises a dedicated `AggregatorAdapterNotFoundError`.

**Acceptance Scenarios**:

1. **Given** `ModelType.CANONICAL_TORCH` registered in `AggregatorAdapterRegistry`, **When** `AggregatorAdapterRegistry.Get(ModelType.CANONICAL_TORCH)` is called, **Then** the registry returns `CanonicalTorchAggregator`.
2. **Given** an unregistered or unsupported `ModelType`, **When** `AggregatorAdapterRegistry.Get(unsupported_type)` is called, **Then** an explicit `AggregatorAdapterNotFoundError` is raised.
3. **Given** `AggregatorAdapter`, **When** inspected, **Then** its abstract interface methods (`LoadDelta`, `ValidateDelta`, `Aggregate`, `CreateNewVersion`) contain zero framework-specific types (no `torch.Tensor`, `ExportedProgram`, or `state_dict`).
4. **Given** `AggregationOrchestrator`, **When** executing, **Then** it manages only lifecycle sequencing and adapter resolution, containing zero tensor mathematics or model mutation logic.

---

### User Story 4 - Atomic Model Creation and Version Protection (Priority: P4)

As a cluster coordinator managing model checkpoints, I want new model versions to be serialized to a temporary file before being atomically moved to their destination filename, and I want attempts to overwrite existing versions to fail fast, so that consumers never observe half-written model files and model history remains immutable.

**Why this priority**: Prevents race conditions, corrupted downloads by downstream trainer nodes, and accidental overwrites of historical model checkpoints.

**Independent Test**: (1) Attempt an aggregation where the target artifact `<modelId>_<newVersion>.pt2` already exists in `newVersionOutputDirectory`, and verify it fails fast during validation with `ExistingModelVersionConflictError`. (2) Execute a normal aggregation and verify that serialization writes to a temporary file first before atomically renaming to `<modelId>_<newVersion>.pt2`.

**Acceptance Scenarios**:

1. **Given** an aggregation request where `<modelId>_<newVersion>.pt2` already exists in `newVersionOutputDirectory`, **When** validation executes, **Then** an explicit `ExistingModelVersionConflictError` is raised immediately before loading or computing deltas.
2. **Given** a successful aggregation calculation, **When** `CreateNewVersion()` executes, **Then** the model is serialized to a temporary file in the target directory, verified to exist and be readable, and atomically renamed to the final version filename.
3. **Given** an unexpected failure during model serialization, **When** the error occurs, **Then** the temporary file is cleaned up and no incomplete model file with the target version name is left on disk.

---

### User Story 5 - End-to-End Distributed Training and Aggregation Verification Suite (Priority: P5)

As an engineer verifying the engine, I want a complete, runnable sample test suite under `samples/distributed_training_test/` demonstrating setup, partitioning, multi-trainer execution, aggregation, and verification, so that the entire distributed training lifecycle can be tested end-to-end without mocks.

**Why this priority**: Fulfills Constitution Principle VII (Mandatory Post-Change Quality Gate) and User Requirement 30 by delivering a real, working, zero-mock pipeline that validates compilability, executability, and functional correctness.

**Independent Test**: Run `python setup.py`, `python partition.py`, `python train.py`, `python aggregate.py`, and `python verify.py` sequentially in `samples/distributed_training_test/`. Verify that:
1. `setup.py` creates `model_0.pt2` and a 50-sample dataset `dataset.pt`.
2. `partition.py` partitions the dataset into 5 shards of 10 samples each.
3. `train.py` executes 5 training tasks producing 5 `.safetensors` delta files.
4. `aggregate.py` aggregates the 5 deltas into `model_1.pt2`.
5. `verify.py` loads both `model_0.pt2` and `model_1.pt2`, evaluates their loss on the dataset, and confirms that `model_1.pt2` demonstrates measurable loss reduction.

**Acceptance Scenarios**:

1. **Given** `samples/distributed_training_test/setup.py`, **When** executed, **Then** it exports a canonical PyTorch model as `.pt2` and a 50-sample dataset as `.pt`.
2. **Given** `samples/distributed_training_test/partition.py`, **When** executed, **Then** it uses `PartitioningOrchestrator` to generate 5 shards of 10 samples each.
3. **Given** `samples/distributed_training_test/train.py`, **When** executed, **Then** it executes 5 training tasks using `TrainingOrchestrator` / `CanonicalTorchTrainer` in parallel, outputting 5 valid delta files.
4. **Given** `samples/distributed_training_test/aggregate.py`, **When** executed, **Then** it creates an `AggregationRequest` from the 5 deltas and invokes `AggregationOrchestrator`, successfully publishing `model_1.pt2`.
5. **Given** `samples/distributed_training_test/verify.py`, **When** executed, **Then** it verifies that both model versions evaluate cleanly and that `model_1.pt2` achieves a lower loss than `model_0.pt2`.

---

### Edge Cases

- **Existing Model Version Collision**: If `<modelId>_<newVersion>.pt2` already exists in `newVersionOutputDirectory`, aggregation MUST fail fast during the validation phase with `ExistingModelVersionConflictError`.
- **Target Output Directory Missing**: If `newVersionOutputDirectory` does not exist on disk, the aggregator MUST create the directory tree automatically before saving.
- **Empty Updates List**: If `updates` list in `AggregationRequest` is empty, aggregation MUST fail immediately with `InvalidAggregationRequestError`.
- **Zero or Negative Samples Trained**: If any update has `samplesTrained <= 0`, aggregation MUST fail fast with `InvalidUpdateError`.
- **Missing or Corrupted Delta File**: If any delta path specified in `updates` is missing, unreadable, or corrupted, aggregation MUST fail with `DeltaAccessError` or `DeltaFormatError`; skipping deltas is strictly prohibited.
- **Missing or Unexpected Tensors**: If any delta omits tensors present in the base model state dict or includes unexpected extra tensors, validation MUST raise `TensorCompatibilityError`.
- **Shape or Dtype Mismatch**: If tensor shapes or dtypes in any delta differ from the base model tensors, validation MUST raise `TensorCompatibilityError`.
- **Base Model Not Found**: If `baseModelPath` does not exist or cannot be deserialized as an exported program, aggregation MUST raise `BaseModelAccessError` or `BaseModelLoadError`.
- **Arbitrary Directory Searches Prohibited**: The aggregator MUST strictly load only the delta paths specified in the `AggregationRequest` and MUST NOT scan directories for unreferenced files.
- **Sequential Application Prohibited**: Deltas MUST NOT be sequentially applied to base weights; all deltas MUST be combined simultaneously via weighted FedAvg before applying to the base model.
- **Base Model Immutability**: The base model file on disk MUST NOT be modified or overwritten under any circumstances.
- **Partial Write Prevention**: If serialization of the new model version fails or is interrupted, no partial file named `<modelId>_<newVersion>.pt2` can remain on disk.
- **Path Traversal Prevention**: Artifact output paths MUST be validated to remain strictly within the configured output directory.

---

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Package Structure & Naming Compliance
- **FR-001**: System MUST provide the aggregation subsystem inside `src/distributed_training_engine/` adhering to the exact required layout:
  ```text
  src/
  └── distributed_training_engine/
      ├── model_type.py
      │
      ├── training/
      │   ├── exceptions.py
      │   ├── trainer_adapter_registery.py
      │   ├── trainer_adapter.py
      │   ├── training_task_model.py
      │   ├── training_result.py
      │   └── training_orchecstrator.py
      │
      ├── aggregation/
      │   ├── exceptions.py
      │   ├── aggregator_adapter_registery.py
      │   ├── aggregator_adapter.py
      │   ├── aggregation_request.py
      │   ├── aggregation_result.py
      │   └── aggregation_orchestrator.py
      │
      ├── partitioning/
      │   ├── exceptions.py
      │   ├── partitioner_adapter_registery.py
      │   ├── partitioner_adapter.py
      │   ├── partitioning_result.py
      │   └── partitioning_orchecstrator.py
      │
      └── adapters/
          └── canonical_torch/
              ├── training/
              │   ├── canonical_torch_trainer.py
              │   └── ...
              │
              ├── aggragation/
              │   └── canonical_torch_aggregator.py
              │
              └── partitioning/
                  └── canonical_torch_partitioner.py
  ```
  *(Note: Exact file/directory spellings specified by contract: `aggregator_adapter_registery.py`, `aggregation_orchestrator.py`, and `adapters/canonical_torch/aggragation/canonical_torch_aggregator.py`).*
- **FR-002**: Existing training and partitioning behavior MUST NOT be redesigned, broken, or regressed by the aggregation implementation.

#### 2. Aggregator Adapter Abstraction (`aggregator_adapter.py`)
- **FR-003**: System MUST define `AggregatorAdapter` in `aggregation/aggregator_adapter.py` as an abstract base class.
- **FR-004**: `AggregatorAdapter.__init__` MUST receive an `AggregationRequest` instance as its constructor parameter and retain it as immutable context.
- **FR-005**: `AggregatorAdapter` MUST declare the following abstract lifecycle operations:
  - `LoadDelta() -> None`
  - `ValidateDelta() -> None`
  - `Aggregate() -> None`
  - `CreateNewVersion() -> AggregationResult`
- **FR-006**: `AggregatorAdapter` MUST be model-agnostic and MUST NOT contain framework-specific types (e.g. `torch.Tensor`, `ExportedProgram`, or `state_dict`).

#### 3. Aggregation Request & Result Models
- **FR-007**: System MUST define `AggregationRequest` and `ModelUpdate` in `aggregation/aggregation_request.py`.
- **FR-008**: `AggregationRequest` MUST contain:
  - `modelId` (`str`): Unique identifier of the model.
  - `baseModelVersion` (`int`): Base model version number that deltas were trained against.
  - `baseModelPath` (`str` or `Path`): Path to the immutable base model artifact.
  - `newVersion` (`int`): Target version number for the aggregated model.
  - `newVersionOutputDirectory` (`str` or `Path`): Target directory where the new model will be saved.
  - `updates` (`List[ModelUpdate]`): List of completed trainer update records.
- **FR-009**: `ModelUpdate` MUST contain:
  - `samplesTrained` (`int`): Number of training samples processed for this update (must be > 0).
  - `deltaPath` (`str` or `Path`): Path to the serialized delta artifact.
- **FR-010**: System MUST define `AggregationResult` in `aggregation/aggregation_result.py` containing:
  - `modelId` (`str`): Model identifier.
  - `baseModelVersion` (`int`): Base model version aggregated from.
  - `newModelVersion` (`int`): Newly created model version.
  - `updatesCount` (`int`): Total count of updates included in the aggregation.
  - `modelPath` (`str`): Absolute or canonical path to the published model artifact.

#### 4. Aggregator Adapter Registry (`aggregator_adapter_registery.py`)
- **FR-011**: System MUST define `AggregatorAdapterRegistry` in `aggregation/aggregator_adapter_registery.py` mapping `ModelType` values to `AggregatorAdapter` implementations.
- **FR-012**: `AggregatorAdapterRegistry` MUST expose:
  - `Register(modelType: ModelType, aggregator_class: Type[AggregatorAdapter])`
  - `Get(modelType: ModelType) -> Type[AggregatorAdapter]`
- **FR-013**: Querying an unregistered `ModelType` MUST raise `AggregatorAdapterNotFoundError`.
- **FR-014**: The registry MUST NOT contain model-specific or framework-specific aggregation mathematics.

#### 5. Aggregation Orchestrator (`aggregation_orchestrator.py`)
- **FR-015**: System MUST define `AggregationOrchestrator` in `aggregation/aggregation_orchestrator.py`.
- **FR-016**: `AggregationOrchestrator` MUST coordinate the aggregation lifecycle in strict sequential order:
  1. Receive `AggregationRequest` and `ModelType`.
  2. Resolve the concrete adapter class from `AggregatorAdapterRegistry`.
  3. Instantiate the adapter with `AggregationRequest`.
  4. Invoke `adapter.LoadDelta()`.
  5. Invoke `adapter.ValidateDelta()`.
  6. Invoke `adapter.Aggregate()`.
  7. Invoke `adapter.CreateNewVersion()`.
  8. Return `AggregationResult`.
- **FR-017**: `AggregationOrchestrator` MUST NOT implement tensor mathematics, model delta computation, or direct file serialization.

#### 6. Canonical PyTorch Aggregator (`canonical_torch_aggregator.py`)
- **FR-018**: System MUST implement `CanonicalTorchAggregator` in `adapters/canonical_torch/aggragation/canonical_torch_aggregator.py` inheriting from `AggregatorAdapter`.
- **FR-019**: `CanonicalTorchAggregator` MUST be registered under `ModelType.CANONICAL_TORCH` in `AggregatorAdapterRegistry`.
- **FR-020**: `LoadDelta()` MUST load each delta file from `ModelUpdate.deltaPath` using SafeTensors deserialization (`safetensors.torch.load_file`).
- **FR-021**: `ValidateDelta()` MUST validate that:
  - Target model file `<modelId>_<newVersion>.pt2` does not already exist in `newVersionOutputDirectory`.
  - Base model at `baseModelPath` exists and can be loaded via `torch.export.load`.
  - Every delta can be loaded and contains tensors.
  - Every delta tensor key matches the base model state dict exactly (no missing, no unexpected keys).
  - Every delta tensor shape and dtype matches the corresponding base model tensor.
  - Every update has `samplesTrained > 0`.
  - The aggregator does NOT inspect or verify model ID or version from the delta filename or metadata; compatibility is validated strictly by matching tensor keys, shapes, and dtypes against the base model state dict.
- **FR-022**: `Aggregate()` MUST perform weighted Federated Averaging across all loaded deltas:
  $$\text{aggregatedDelta}[k] = \frac{\sum_{i} (\text{samplesTrained}_i \times \text{delta}_i[k])}{\sum_{i} \text{samplesTrained}_i}$$
  computed independently for each model tensor $k$. For floating-point tensors, the weighted average is maintained in floating point precision; for integer or non-floating point buffers (e.g., tracking counters), the weighted average is rounded to the nearest integer and cast back to the tensor's native integer dtype.
- **FR-023**: `Aggregate()` MUST NOT sequentially apply deltas to base model weights.
- **FR-024**: `CreateNewVersion()` MUST:
  - Reconstruct new weights: $\text{newState}[k] = \text{baseState}[k] + \text{aggregatedDelta}[k]$.
  - Update base model exported program module state.
  - Serialize the new model using `torch.export.save` to a temporary file in `newVersionOutputDirectory`.
  - Verify the temporary file exists and is non-empty.
  - Atomically rename the temporary file to `<modelId>_<newVersion>.pt2`.
  - Leave the base model artifact untouched.
  - Return `AggregationResult`.

#### 7. Exceptions & Error Handling (`exceptions.py`)
- **FR-025**: System MUST define explicit exceptions in `aggregation/exceptions.py` inheriting from `AggregationError`:
  - `UnsupportedModelTypeError`
  - `AggregatorAdapterNotFoundError`
  - `InvalidAggregationRequestError`
  - `DeltaAccessError`
  - `DeltaFormatError`
  - `TensorCompatibilityError`
  - `InvalidBaseModelVersionError`
  - `InconsistentModelIdError`
  - `InvalidUpdateError`
  - `BaseModelAccessError`
  - `BaseModelLoadError`
  - `AggregationOperationError`
  - `ExistingModelVersionConflictError`
  - `ModelSerializationError`
- **FR-026**: Exception messages MUST include diagnostic context: model ID, version, file paths, tensor names, and expected/actual values.
- **FR-027**: Aggregation MUST operate under an all-or-nothing guarantee: if any delta fails validation or loading, or if aggregation fails, zero new model versions are created or published.

#### 8. Traceability and Logging
- **FR-028**: Aggregation orchestrator and adapters MUST emit structured logs at every lifecycle stage: request receipt, adapter resolution, delta loading, validation checks, FedAvg calculation progress, atomic serialization, and final result output.

#### 9. Runnable Test Suite (`samples/distributed_training_test/`)
- **FR-029**: System MUST provide a complete end-to-end distributed training test suite under `samples/distributed_training_test/` containing:
  - `setup.py`: Generates base model `.pt2` (CNN model) and a 50-sample dataset `.pt`.
  - `partition.py`: Partitions the dataset into 5 shards of 10 samples each using `PartitioningOrchestrator`.
  - `train.py`: Trains 5 models in parallel over the 5 shards using `TrainingOrchestrator`, outputting 5 `.safetensors` delta files.
  - `aggregate.py`: Collects the 5 deltas and invokes `AggregationOrchestrator`, publishing a new `.pt2` model version.
  - `verify.py`: Evaluates baseline model vs aggregated model on the dataset, verifying loss improvement.
  - `README.md`: Explains test workflow and execution commands.
- **FR-030**: All test scripts MUST be executable and pass with exit code 0 without mock implementations.

---

### Key Entities *(include if feature involves data)*

- **`AggregationRequest`**: Input payload containing `modelId`, `baseModelVersion`, `baseModelPath`, `newVersion`, `newVersionOutputDirectory`, and a collection of `ModelUpdate` entries.
- **`ModelUpdate`**: Single trainer update record containing `samplesTrained` (weighting factor) and `deltaPath` (path to delta artifact).
- **`AggregationResult`**: Immutable result descriptor returned upon successful aggregation, containing `modelId`, `baseModelVersion`, `newModelVersion`, `updatesCount`, and `modelPath`.
- **`AggregatorAdapter`**: Model-agnostic abstract base class defining the four core aggregation lifecycle methods.
- **`CanonicalTorchAggregator`**: Concrete adapter implementing SafeTensors delta loading, parameter schema validation, tensor-wise weighted FedAvg, and atomic `.pt2` model creation.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid trainer updates in an aggregation request are mathematically aggregated using sample-weighted Federated Averaging without sample loss or equal-weight distortion.
- **SC-002**: 100% of invalid, unreadable, missing, or mismatched deltas trigger immediate failure during validation before any model calculation or mutation occurs (zero partial aggregations).
- **SC-003**: 100% of target version conflicts (`<modelId>_<newVersion>.pt2` already exists) are rejected during validation, preventing accidental overwrites.
- **SC-004**: Base model artifacts remain 100% immutable and bit-for-bit identical before and after aggregation runs.
- **SC-005**: All published model artifacts are written atomically, ensuring no half-written or corrupted artifacts are accessible to downstream consumers upon serialization failure.
- **SC-006**: The end-to-end sample suite in `samples/distributed_training_test/` executes successfully from setup through verification with 100% pass rate, demonstrating measurable loss reduction on the aggregated model.
- **SC-007**: Existing training and partitioning tests and modules execute with zero regressions.

---

## Assumptions

- Deltas produced by `CanonicalTorchTrainer` are serialized as `.safetensors` files containing parameter difference tensors: $\Delta = \theta_{\text{trained}} - \theta_{\text{base}}$.
- The canonical PyTorch base model is an exported program artifact saved as `.pt2` via `torch.export.save`.
- Weighted FedAvg computes independent weighted averages per tensor; optimizer states (e.g. Adam momentum buffers) are not transferred or aggregated in basic FedAvg unless explicitly included in deltas.
- Python module and file naming adheres strictly to the repository conventions: `aggregator_adapter_registery.py`, `aggregation_orchestrator.py`, and `adapters/canonical_torch/aggragation/canonical_torch_aggregator.py`.
- In accordance with TrainSwarm Constitution Principle V and VII: no mocks or stubs are used; real working implementations and executable verification scripts are mandatory.
