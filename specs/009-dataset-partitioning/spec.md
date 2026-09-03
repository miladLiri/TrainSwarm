# Feature Specification: Distributed Training Engine — Partitioning Module and Folder Structure

**Feature Branch**: `009-dataset-partitioning`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Refactor the distributed_training_engine to introduce a dedicated partitioning module responsible for converting an input dataset into training shards whose size is provided. The partitioning implementation MUST be model-agnostic at the abstraction level and MUST use a model-specific partitioner adapter selected through the adapter registry."
## Clarifications

### Session 2026-09-03

- Q: How should the shardId be generated and represented for shards produced by CanonicalTorchPartitioner? → A: Full UUID string (e.g., `uuid4`), writing shard files as `<datasetId>_<shardId>.pt`.
- Q: How should CreateSample() handle the scenario where a representative sample file (<dataset_id>_sample.pt) already exists in sampleOutputDirectory? → A: Overwrite the existing sample artifact atomically (idempotent sample generation).
- Q: What exact condition in shardsOutputDirectory should trigger an ExistingShardConflictError? → A: Fail if shardsOutputDirectory is non-empty (strict empty-directory requirement).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dataset Partitioning into Shards by Sample Count (Priority: P1)

As a Trainer node or Client node operator in the TrainSwarm data plane, I want to partition a full training dataset into fixed-size shards based on a target sample count, so that distributed workers can be assigned balanced, manageable slices of training data for localized PyTorch training tasks.

**Why this priority**: Core functional capability of the partitioning subsystem. Without the ability to divide raw datasets into discrete, serialized training shards, distributed training tasks cannot be dispatched or executed across worker nodes.

**Independent Test**: Provide an input dataset file (e.g., a PyTorch tensor dataset with 5,000 samples) and a target shard sample size of 2,250 samples. Instantiate `PartitioningOrchestrator` with a `PartitioningRequest` pointing to input and output directories, and call `CreateShards(2250)`. Verify that exactly three shards are generated in the output directory (`shard 0` with 2,250 samples, `shard 1` with 2,250 samples, and `shard 2` with 500 samples), named according to `<dataset_id>_<shard_id>.pt`, with no samples dropped or duplicated, and that a `PartitioningResult` object is returned detailing all generated shards.

**Acceptance Scenarios**:

1. **Given** a valid dataset containing 5,000 samples and a target `shardSampleSize` of 2,250, **When** `PartitioningOrchestrator.CreateShards(2250)` is executed, **Then** the dataset is sliced into three shards (2,250, 2,250, and 500 samples respectively), each serialized to the configured output directory with naming `<datasetId>_<shardId>.pt`, leaving the final partial shard intact.
2. **Given** a target `shardSampleSize` that evenly divides the dataset (e.g., 5,000 samples with `shardSampleSize` = 2,500), **When** `CreateShards(2500)` is executed, **Then** exactly two shards of 2,500 samples each are created without any empty trailing shard.
3. **Given** a target `shardSampleSize` larger than the total dataset size (e.g., dataset size = 1,000, `shardSampleSize` = 5,000), **When** `CreateShards(5000)` is executed, **Then** a single shard containing all 1,000 samples is produced and saved.
4. **Given** a completed partitioning operation, **When** `PartitioningResult` is inspected, **Then** it contains the correct `datasetId`, `shardCount`, and a list of `PartitionedShard` descriptors with matching `shardId`, `sampleCount`, and `artifactPath`.

---

### User Story 2 - Representative Dataset Sampling (Priority: P2)

As an orchestrator coordinating cluster training jobs, I want to extract a representative single-sample artifact from an input dataset prior to full partitioning, so that the training orchestrator can validate tensor schemas, shapes, and data types before committing to full cluster dispatch.

**Why this priority**: Required for pre-flight task validation and dry-run execution. Enables early detection of schema mismatches between model architectures and input data without reading or slicing the entire dataset.

**Independent Test**: Provide a valid canonical PyTorch dataset file at `datasetPath`. Invoke `PartitioningOrchestrator.GetSample()`. Verify that a sample artifact named `<dataset_id>_sample.pt` is generated in `sampleOutputDirectory`, formatted identically to the representation expected by `CanonicalTorchTrainer`, and that a `SamplingResult` instance is returned with the sample artifact path and metadata.

**Acceptance Scenarios**:

1. **Given** a valid dataset at `datasetPath`, **When** `PartitioningOrchestrator.GetSample()` is executed, **Then** the underlying partitioner adapter opens the dataset, extracts one representative sample (the first sample), persists it as `<dataset_id>_sample.pt` in `sampleOutputDirectory`, and returns a `SamplingResult` referencing the artifact.
2. **Given** an invalid or empty dataset file with 0 samples, **When** `GetSample()` is executed, **Then** an explicit `DatasetFormatError` is raised indicating that a sample cannot be extracted from an empty dataset.
3. **Given** an existing sample artifact in the sample output directory, **When** `GetSample()` is executed, **Then** the existing sample artifact is replaced atomically without raising a conflict error, ensuring idempotent pre-flight sampling.

---

### User Story 3 - Model-Agnostic Abstraction and Adapter Registry (Priority: P3)

As a developer extending the distributed training engine, I want a model-agnostic partitioning abstraction (`PartitionerAdapter`) and registry (`PartitionerAdapterRegistry`) decoupled from model-specific serialization logic, so that future frameworks (e.g., ONNX, TensorFlow, HuggingFace) can be added without modifying the core partitioning orchestration lifecycle.

**Why this priority**: Architectural boundary requirement. Guarantees separation of concerns between workflow coordination and concrete framework dataset formats.

**Independent Test**: Register a custom or mock-free concrete partitioner adapter for a new `ModelType` in `PartitionerAdapterRegistry`. Instantiate `PartitioningOrchestrator` with that `ModelType`, and verify that the orchestrator resolves and delegates to the registered adapter without branching on model type. Verify that querying an unregistered `ModelType` raises a dedicated `PartitionerAdapterNotFoundError`.

**Acceptance Scenarios**:

1. **Given** a registered `ModelType.CANONICAL_TORCH`, **When** `PartitionerAdapterRegistry.Get(ModelType.CANONICAL_TORCH)` is called, **Then** the registry returns the `CanonicalTorchPartitioner` class or configured factory.
2. **Given** an unregistered or unsupported `ModelType`, **When** `PartitionerAdapterRegistry.Get(unsupported_type)` is called, **Then** an explicit `PartitionerAdapterNotFoundError` is raised.
3. **Given** `PartitioningOrchestrator`, **When** it initializes, **Then** it resolves the adapter solely through `PartitionerAdapterRegistry` using the `model_type` provided in `PartitioningRequest`, containing zero framework-specific dataset parsing logic.

---

### User Story 4 - Package Reorganization and Regression Safety (Priority: P4)

As a developer maintaining the `distributed_training_engine`, I want the package reorganized into dedicated `training/`, `partitioning/`, `aggregation/`, and `adapters/` hierarchies, so that engine subsystems have clear modular boundaries while preserving existing training capabilities and backward compatibility.

**Why this priority**: Structural integrity and maintainability. Reorganizing existing code to the target layout prevents architectural drift and prepares the codebase for upcoming aggregation and partitioning workflows.

**Independent Test**: Inspect the directory structure under `src/distributed_training_engine/`. Confirm that `model_type.py` resides at the package root, existing training files are organized under `training/` (with `trainer_adapter.py`, `trainer_adapter_registery.py`, `training_orchecstrator.py`), blank placeholder modules exist under `aggregation/`, partitioning files exist under `partitioning/`, and canonical torch adapters are structured under `adapters/canonical_torch/` (`training/`, `aggragation/`, `partitioning/`). Execute existing sample training scripts (`samples/training_test/train.py` and `verify.py`) to confirm zero regressions in training behavior.

**Acceptance Scenarios**:

1. **Given** the reorganized `src/distributed_training_engine/`, **When** Python imports are resolved, **Then** existing training symbols are importable from `distributed_training_engine` and `distributed_training_engine.training` without broken imports.
2. **Given** the sample training test in `samples/training_test/`, **When** `train.py` and `verify.py` are executed, **Then** training completes successfully, delta artifacts are created, and mathematical verification passes.
3. **Given** future aggregation modules under `src/distributed_training_engine/aggregation/` and `src/distributed_training_engine/adapters/canonical_torch/aggragation/`, **When** inspected, **Then** files exist as placeholders ready for future feature implementation.

---

### Edge Cases

- **Existing Output Conflict**: If the configured `shardsOutputDirectory` is non-empty (contains any existing files or subdirectories), calling `CreateShards()` MUST fail fast with an `ExistingShardConflictError` rather than silently overwriting or mixing old and new shards.
- **Output Directory Auto-Creation**: If `shardsOutputDirectory` or `sampleOutputDirectory` does not exist on disk, the partitioner MUST create the directory tree automatically with proper permissions.
- **Invalid Sample Size**: If `shardSampleSize` is less than or equal to 0, or is not an integer, the orchestrator/adapter MUST raise an `InvalidShardSampleSizeError` immediately before reading the dataset.
- **Empty Dataset**: If the source dataset file exists but contains 0 samples, partitioning MUST fail with an explicit `DatasetFormatError` indicating an empty dataset cannot be partitioned.
- **Missing Dataset File**: If `datasetPath` does not exist or is unreadable, an explicit `DatasetAccessError` MUST be raised with the missing path and dataset ID.
- **Corrupted or Unreadable Samples**: If any sample within the dataset cannot be deserialized, decoded, or sliced, the operation MUST fail with `DatasetFormatError` immediately; it MUST NOT silently skip unreadable samples or emit incomplete shards.
- **Non-Integral Shard Remainders**: When the total sample count is not an exact multiple of `shardSampleSize`, the trailing samples MUST form a valid final shard whose `sampleCount` equals the remainder (`sample_count % shardSampleSize`). The final shard MUST NOT be discarded.
- **Duplicate Shard Identifiers**: Shard identifiers within a single dataset partitioning run MUST be strictly unique across all generated shards.
- **Existing Sample Artifact Overwrite**: Unlike shard generation which strictly fails upon collisions with existing shards, `CreateSample()` atomically replaces an existing sample file (`<dataset_id>_sample.pt`) to ensure idempotent inspection and pre-flight validation.
- **External Path Confinement**: Shards and samples MUST NOT be written outside the specified output directories under any circumstance (path traversal prevention).

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Package Structure & Reorganization
- **FR-001**: System MUST reorganize `src/distributed_training_engine/` into the following package layout:
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
      ├── aggregation/ (placeholders for future implementation)
      │   ├── exceptions.py
      │   ├── aggregator_adapter_registery.py
      │   ├── aggregator_adapter.py
      │   ├── aggregation_request.py
      │   ├── aggregation_result.py
      │   └── aggregation_orchecstrator.py
      │
      ├── partitioning/
      │   ├── exceptions.py
      │   ├── partitioner_adapter_registery.py
      │   ├── partitioner_adapter.py
      │   ├── partitioning_request.py
      │   ├── sampling_result.py
      │   ├── partitioning_result.py
      │   └── partitioning_orchecstrator.py
      │
      └── adapters/
          └── canonical_torch/
              ├── training/
              │   ├── canonical_torch_trainer.py
              │   ├── canonical_torch_config.py
              │   ├── criterion_registry.py
              │   ├── optimizer_registry.py
              │   ├── scheduler_registry.py
              │   ├── criteria/
              │   ├── optimizers/
              │   └── schedulers/
              │
              ├── aggragation/ (placeholder for future implementation)
              │   └── canonical_torch_aggregator.py
              │
              └── partitioning/
                  └── canonical_torch_partitioner.py
  ```
- **FR-002**: Existing training functionality MUST be preserved without redesigning existing training classes/logic. Package exports in `distributed_training_engine/__init__.py` and `training/__init__.py` MUST provide backward-compatible aliases where appropriate.
- **FR-003**: Placeholders under `aggregation/` and `adapters/canonical_torch/aggragation/` MUST be created as blank files or minimal stubs reserved for future implementation.

#### 2. Partitioning Abstraction (`partitioner_adapter.py`)
- **FR-004**: System MUST define an abstract base class `PartitionerAdapter` in `partitioning/partitioner_adapter.py`.
- **FR-005**: `PartitionerAdapter.__init__` MUST receive a `PartitioningRequest` containing:
  - `model_type` (`ModelType` enum)
  - `datasetPath` (`str` or `Path`)
  - `shardsOutputDirectory` (`str` or `Path`)
  - `sampleOutputDirecotry` (`str` or `Path`)
  - `datasetId` (`str`)
- **FR-006**: `PartitionerAdapter` MUST declare exactly two primary abstract operations:
  - `CreateSample() -> SamplingResult`
  - `CreateShards(shardSampleSize: int) -> PartitioningResult`
- **FR-007**: `PartitionerAdapter` MUST be strictly model-agnostic and MUST NOT contain framework-specific dataset parsing or serialization code.

#### 3. Partitioning Request & Result Models
- **FR-008**: System MUST define `PartitioningRequest` in `partitioning/partitioning_request.py` encapsulating `model_type`, `datasetPath`, `shardsOutputDirectory`, `sampleOutputDirecotry`, and `datasetId`, with validation enforcing non-empty strings, valid enum instances, and non-empty paths.
- **FR-009**: System MUST define `SamplingResult` in `partitioning/sampling_result.py` containing:
  - `datasetId` (`str`): Identifier of the sampled dataset.
  - `samplePath` (`str`): Absolute or canonical path to the generated sample artifact.
  - `sampleCount` (`int`): Number of samples extracted (default: 1).
- **FR-010**: System MUST define `PartitioningResult` and `PartitionedShard` in `partitioning/partitioning_result.py`:
  - `PartitioningResult`:
    - `datasetId` (`str`): Identifier of the partitioned dataset.
    - `shardCount` (`int`): Total count of shards produced.
    - `shards` (`List[PartitionedShard]`): List of partitioned shard metadata descriptors.
  - `PartitionedShard`:
    - `shardId` (`str`): Unique UUID string identifier of the shard within the dataset.
    - `sampleCount` (`int`): Number of training samples contained in the shard.
    - `artifactPath` (`str`): File path to the persisted shard artifact.

#### 4. Partitioner Adapter Registry (`partitioner_adapter_registery.py`)
- **FR-011**: System MUST define `PartitionerAdapterRegistry` in `partitioning/partitioner_adapter_registery.py` mapping `ModelType` values to `PartitionerAdapter` implementations.
- **FR-012**: `PartitionerAdapterRegistry` MUST expose `Register(modelType: ModelType, partitioner_class: Type[PartitionerAdapter])` and `Get(modelType: ModelType) -> Type[PartitionerAdapter]`.
- **FR-013**: Requesting an unregistered or unknown `ModelType` via `Get()` MUST raise `PartitionerAdapterNotFoundError`.
- **FR-014**: The registry MUST NOT contain dataset-specific or model-specific partitioning logic.

#### 5. Partitioning Orchestrator (`partitioning_orchecstrator.py`)
- **FR-015**: System MUST define `PartitioningOrchestrator` in `partitioning/partitioning_orchecstrator.py`.
- **FR-016**: `PartitioningOrchestrator.__init__` MUST receive a `PartitioningRequest` instance and resolve the corresponding `PartitionerAdapter` class via `PartitionerAdapterRegistry`.
- **FR-017**: `PartitioningOrchestrator` MUST expose `GetSample() -> SamplingResult` which invokes `CreateSample()` on the resolved adapter instance.
- **FR-018**: `PartitioningOrchestrator` MUST expose `CreateShards(shardSampleSize: int) -> PartitioningResult` which validates `shardSampleSize` and invokes `CreateShards()` on the resolved adapter instance.
- **FR-019**: `PartitioningOrchestrator` MUST NOT contain framework-specific dataset parsing or serialization logic.

#### 6. Canonical Torch Partitioner (`canonical_torch_partitioner.py`)
- **FR-020**: System MUST implement `CanonicalTorchPartitioner` in `adapters/canonical_torch/partitioning/canonical_torch_partitioner.py` inheriting from `PartitionerAdapter`.
- **FR-021**: `CanonicalTorchPartitioner` MUST be registered under `ModelType.CANONICAL_TORCH` in `PartitionerAdapterRegistry`.
- **FR-022**: `CanonicalTorchPartitioner.CreateSample()` MUST open the PyTorch dataset at `datasetPath`, extract the first sample, save it as `<dataset_id>_sample.pt` in `sampleOutputDirecotry`, and return a `SamplingResult`. The sample format MUST match the tensor dictionary structure (`{"x": ..., "y": ...}`) expected by `CanonicalTorchTrainer`. If a sample file already exists at the target path, `CreateSample()` MUST atomically overwrite it (ensuring idempotent sampling).
- **FR-023**: `CanonicalTorchPartitioner.CreateShards(shardSampleSize)` MUST iterate through the dataset in deterministic order, group samples into shards of at most `shardSampleSize` samples, serialize each shard as a PyTorch file named `<datasetId>_<shardId>.pt` in `shardsOutputDirectory`, and return a `PartitioningResult`.
- **FR-024**: Each generated shard MUST have a unique `shardId` within the dataset generated as a random full UUID string (e.g., `str(uuid.uuid4())`), and duplicate shard IDs MUST NOT occur.
- **FR-025**: The final partial shard MUST be serialized and preserved if remaining samples exist; it MUST NOT be discarded.
- **FR-026**: If `shardsOutputDirectory` is non-empty (contains any existing files or subdirectories), `CreateShards()` MUST fail and raise `ExistingShardConflictError`.
- **FR-027**: `CanonicalTorchPartitioner` MUST create output directories if they do not already exist.

#### 7. Error Handling & Subsystem Boundaries (`exceptions.py`)
- **FR-028**: System MUST define explicit exceptions in `partitioning/exceptions.py` inheriting from a base `PartitioningError`:
  - `InvalidPartitioningConfigurationError`
  - `InvalidShardSampleSizeError`
  - `DatasetAccessError`
  - `DatasetFormatError`
  - `ShardSerializationError`
  - `OutputDirectoryError`
  - `ExistingShardConflictError`
  - `UnsupportedModelTypeError`
  - `PartitionerAdapterNotFoundError`
  - `PartitioningOperationError`
- **FR-029**: Exception messages MUST include contextual diagnostic information: `datasetId`, relevant file paths, and the failing operation.
- **FR-030**: Partitioner adapters MUST NOT silently skip unreadable or corrupted samples; encountering an invalid sample MUST raise `DatasetFormatError`.
- **FR-031**: Partitioning subsystem MUST NOT perform model training, select a trainer, communicate with trainers, perform aggregation, create model versions, maintain a dataset cache, or cache shards outside the configured directories.

#### 8. Traceability and Logging
- **FR-032**: Partitioning workflow coordinator and adapters MUST emit structured descriptive logs at each lifecycle step (request validation, adapter resolution, dataset opening, sample extraction, shard boundary slicing, serialization, and result construction).

### Key Entities *(include if feature involves data)*

- **`PartitioningRequest`**: Configuration payload containing `model_type`, `datasetPath`, `shardsOutputDirectory`, `sampleOutputDirecotry`, and `datasetId`.
- **`SamplingResult`**: Output descriptor containing `datasetId`, `samplePath`, and `sampleCount`.
- **`PartitionedShard`**: Metadata for an individual generated shard containing `shardId` (UUID string), `sampleCount`, and `artifactPath`.
- **`PartitioningResult`**: Overall operation result containing `datasetId`, `shardCount`, and a list of `PartitionedShard` instances.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of samples from a valid input dataset are partitioned into shards without sample loss or duplication, with the final partial shard preserved intact.
- **SC-002**: Generated shard artifacts strictly adhere to the naming format `<datasetId>_<shardId>.pt` and are stored exclusively within the configured `shardsOutputDirectory`.
- **SC-003**: Representative sample artifacts strictly adhere to the naming format `<dataset_id>_sample.pt` and are stored exclusively within the configured `sampleOutputDirecotry`.
- **SC-004**: 100% of non-empty `shardsOutputDirectory` scenarios trigger an explicit `ExistingShardConflictError` without mutating or overwriting existing files.
- **SC-005**: All error scenarios (invalid configuration, negative sample size, missing dataset, unreadable samples, unknown model type) raise explicit, categorized exceptions with zero silent failures.
- **SC-006**: Existing training workflows and sample verification tests (`samples/training_test/train.py` and `verify.py`) execute with 100% pass rate following folder restructuring and file renaming.

## Assumptions

- Target datasets for `CanonicalTorchPartitioner` are stored as PyTorch serialized `.pt` files containing tensor mappings (e.g. `{"x": tensor, "y": tensor}`) with matching batch dimensions along dimension 0.
- Shard IDs in `CanonicalTorchPartitioner` are generated as random full UUID strings (e.g. `str(uuid.uuid4())`), guaranteeing uniqueness and adhering to the `<datasetId>_<shardId>.pt` naming convention.
- In Python, module naming in the file tree follows the user's explicit specification: `trainer_adapter_registery.py`, `partitioner_adapter_registery.py`, `partitioning_orchecstrator.py`, and `training_orchecstrator.py`.
- Aggregation files under `src/distributed_training_engine/aggregation/` and `src/distributed_training_engine/adapters/canonical_torch/aggragation/` are scaffolding placeholders reserved for upcoming features and do not require functional logic in this phase.
- Verification follows the repository constitution: no mocks, active execution verification via Python execution and sample tooling.
