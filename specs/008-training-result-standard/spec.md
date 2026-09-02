# Feature Specification: Training Result Standard & Delta Artifacts

**Feature Branch**: `008-training-result-standard`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "in distributed training engine make some changes are needed: 1 - in training/training_task_model: task_id -> training_task_id, session_id -> remove, baseline_model_id : str added, checkpoint_version -> baseline_model_version, data_set_id : str added, data_set_shard_id : str added. Contract update: name of model pt2 file should use this convention: <baseline_model_id>_<baseline_model_version>.pt2, name of dataset shard pt file should use this convention: <data_set_id>_<data_set_shard_id>.pt. 2 - training result delta artifact: After training is completed, the trainer in the save result MUST calculate the model delta against the exact immutable baseModelVersion used for the task by subtracting each tensor in the original base model state_dict from the corresponding tensor in the trained model state_dict (delta[name] = trained[name] - base[name]). The resulting delta MUST contain the same tensor names and compatible shapes as the base model and MUST be saved as a separate artifact file, preferably in a tensor-only format such as .safetensors. The artifact MUST be written to the trainer's task workspace directory. Name of delta artifact is <baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>. 3 - training result model: update TrainingResult Contract in distributed_training_engine/training/training_result with fields trainingTaskId, baseModelId, baseModelVersion, datasetId, datasetShardId, samplesTrained, metrics, execution (startedAt, completedAt, durationMs), delta. 4 - distributed training engine must adapt to contract and functionality changes in this specification. 5 - samples/training test setup and train file must be updated according to changes in contracts and functionality changes and instead of saving trained model it should save delta artifact; create a verify.py file that loads both base model and delta file then apply delta on model parameters then evaluate the result. 6 - keep the implementation clear, easy to read and maintainable."

## Clarifications

### Session 2026-09-02
- Q: Should the delta artifact filename strictly include the `.safetensors` extension when written to disk? (FR-010) → A: Strictly include the `.safetensors` extension (`<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors`).
- Q: What exact metadata fields and casing should the `delta` sub-object in the serialized `TrainingResult` contain? (FR-006) → A: Standardize on camelCase keys: `filename`, `path`, `format`, `tensorCount`, and `sizeBytes` with snake_case property access in Python.
- Q: How should `samples/training_test/verify.py` locate input artifacts and determine verification success? (FR-020) → A: Hardcode standard sample filenames in the sample directory, validating numerical reconstruction parity and loss reduction (exit code 0 on success, non-zero on failure).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Model Delta Calculation and Safetensors Artifact Export (Priority: P1)

As a Trainer node in the distributed swarm, I want to compute a model parameter delta (`delta = trained_weights - base_weights`) against the baseline model upon finishing training, and save this delta as a lightweight `.safetensors` artifact in my workspace rather than re-exporting the entire trained model, so that parameter updates are compact, secure, and ready for decentralized peer-to-peer transmission and serverless aggregation.

**Why this priority**: Core architectural shift from transferring heavy full-model checkpoints to lightweight weight deltas. This minimizes bandwidth consumption and standardizes the aggregation contract across the data plane.

**Independent Test**: Provide a working directory containing a baseline PyTorch model (`<baseline_model_id>_<baseline_model_version>.pt2`) and dataset shard (`<data_set_id>_<data_set_shard_id>.pt`). Execute the training workflow for a specified number of steps. Verify that the output artifact produced is a `.safetensors` file named `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors`, containing exactly the difference tensors (`trained - base`) for all model parameters with identical names and shapes, without mutating the baseline model file.

**Acceptance Scenarios**:

1. **Given** a valid baseline model file `<baseline_model_id>_<baseline_model_version>.pt2` and dataset shard `<data_set_id>_<data_set_shard_id>.pt`, **When** the training workflow executes to completion, **Then** a separate delta artifact named `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors` is saved in the workspace directory containing `delta[tensor_name] = trained_tensor - base_tensor`.
2. **Given** a completed training run where model parameters were updated during optimization, **When** the delta tensor values are inspected, **Then** each tensor in the delta artifact has the identical key name, dimensions, and `float32` data type as the base model, and non-zero differences reflect the applied gradient updates.
3. **Given** a training task with 0 training steps or where optimizer weights remain unchanged, **When** delta generation runs, **Then** the resulting delta artifact contains all parameter keys with zero-valued tensors matching the parameter shapes.
4. **Given** the delta calculation phase, **When** the base model is read to compute differences, **Then** the original baseline `.pt2` file on disk remains completely unmodified.

---

### User Story 2 - Standardized Training Task and Result Contracts (Priority: P2)

As a developer and coordinator operator, I want standardized `TrainingTask` and `TrainingResult` contract models with explicit baseline model, dataset shard, execution telemetry, and delta references, with `session_id` eliminated, so that task dispatch and result reporting have precise, unambiguous schema envelopes across control and data planes.

**Why this priority**: Standardizes the data contract across all services, removing deprecated fields (`session_id`) and introducing explicit baseline model IDs, baseline model versions, dataset IDs, and dataset shard IDs.

**Independent Test**: Instantiate `TrainingTask` and `TrainingResult` using JSON representations and Python DTO constructors. Validate envelope constraints, field presence, serialization round-trips, and rejection of invalid or malformed payloads.

**Acceptance Scenarios**:

1. **Given** a task payload with fields `training_task_id`, `baseline_model_id`, `baseline_model_version`, `data_set_id`, `data_set_shard_id`, `type`, and `training`, **When** deserialized into `TrainingTask`, **Then** the object validates successfully and provides typed access to all fields.
2. **Given** a task payload missing any required identifier (e.g. empty `training_task_id` or missing `baseline_model_id`), **When** envelope validation executes, **Then** an explicit validation error is raised identifying the missing or invalid field.
3. **Given** a completed training run, **When** `TrainingResult` is generated, **Then** it contains `trainingTaskId`, `baseModelId`, `baseModelVersion`, `datasetId`, `datasetShardId`, `samplesTrained`, `metrics` (generic dictionary including loss), `execution` (containing `startedAt`, `completedAt`, `durationMs`), and `delta` (containing artifact name and metadata).
4. **Given** a `TrainingResult` object, **When** converted to JSON or dictionary format, **Then** the field naming follows the standardized schema structure.

---

### User Story 3 - Standalone Delta Verification Tooling (Priority: P3)

As a validation engineer or downstream aggregator, I want a standalone verification tool (`verify.py`) that loads a baseline model and a generated delta artifact, applies the delta to reconstruct the trained model, and evaluates model predictions against sample data, so that delta correctness and model convergence can be validated without re-running the entire training loop.

**Why this priority**: Essential verification mechanism required to ensure mathematical correctness of delta generation and reconstructibility of trained models from deltas.

**Independent Test**: Run `python samples/training_test/verify.py` after training. Verify that the script successfully loads `<baseline_model_id>_<baseline_model_version>.pt2`, reads `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors`, applies the parameter updates (`reconstructed = base + delta`), executes forward evaluation on the dataset shard, and confirms lower loss compared to the baseline model.

**Acceptance Scenarios**:

1. **Given** a valid base model `.pt2` file and matching `.safetensors` delta file, **When** `verify.py` is executed, **Then** it applies parameter deltas to the base model, runs evaluation against the dataset shard, outputs baseline loss vs trained loss, and exits with code 0.
2. **Given** a delta file with mismatched parameter shapes or missing tensor names relative to the base model, **When** `verify.py` attempts reconstruction, **Then** it reports an explicit tensor compatibility error and exits with a non-zero code.
3. **Given** a verified reconstructed model, **When** evaluated on the training dataset shard, **Then** its loss matches the final loss recorded in the training result execution metrics.

---

### User Story 4 - Updated End-to-End Sample and Setup Workflow (Priority: P4)

As a developer getting started with the engine, I want `samples/training_test/setup.py`, `samples/training_test/train.py`, and `samples/training_test/verify.py` updated to follow the new artifact naming conventions and delta workflow, so that I can set up sample data, train, and verify in three simple CLI commands.

**Why this priority**: Guarantees runnable, reproducible verification artifacts in accordance with project constitution quality gates (active execution verification, zero mocks).

**Independent Test**: Sequentially execute `python samples/training_test/setup.py`, `python samples/training_test/train.py`, and `python samples/training_test/verify.py`. Verify that all three execute cleanly without warnings or errors, producing the expected baseline artifacts, delta artifact, and verification report.

**Acceptance Scenarios**:

1. **Given** `samples/training_test/setup.py`, **When** executed, **Then** it creates `<baseline_model_id>_<baseline_model_version>.pt2` (e.g. `base_model_v1.pt2`) and `<data_set_id>_<data_set_shard_id>.pt` (e.g. `dataset1_shard1.pt`) under the sample directory.
2. **Given** generated sample artifacts, **When** `samples/training_test/train.py` is executed, **Then** it runs `TrainingOrchestrator`, produces `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors` in the workspace, and logs execution timing and training metrics.
3. **Given** generated base, shard, and delta files, **When** `samples/training_test/verify.py` is executed, **Then** it loads base model and delta, computes reconstructed weights, runs inference on the shard, and confirms loss reduction.

---

### Edge Cases

- **Mismatched Delta and Base Model Keys**: If a delta artifact contains keys not present in the base model `state_dict`, or lacks keys present in the base model, delta application must fail with an explicit descriptive error.
- **Incompatible Tensor Shapes or Dtypes**: If a delta tensor shape differs from the corresponding base model tensor, difference calculation or delta reconstruction must fail immediately before any weights are mutated.
- **In-Place Weight Mutation Prevention**: When computing the delta (`delta[name] = trained[name] - base[name]`), the adapter must ensure that base model weights captured at the start of training were not modified in-place during optimization.
- **Zero Update (No-Op Training)**: When training runs for 0 epochs or 0 steps, the delta must still be saved with all tensors equal to 0.0, maintaining identical tensor shapes and keys.
- **Missing Baseline Model or Dataset Shard**: If either `<baseline_model_id>_<baseline_model_version>.pt2` or `<data_set_id>_<data_set_shard_id>.pt` is absent from the working directory during validation, an explicit `MissingArtifactError` must be raised before training begins.
- **Execution Timestamp Integrity**: Execution timestamps (`startedAt`, `completedAt`) must be recorded in UTC ISO-8601 format, and `durationMs` must be a non-negative integer representing elapsed wall-clock milliseconds.
- **File Overwrites in Workspace**: If a delta artifact with the same name already exists in the task workspace, saving the new delta must atomically replace it cleanly without leaving partial or corrupted files.

## Requirements *(mandatory)*

### Functional Requirements

#### 1. Training Task Model Contract (`training_task_model.py`)
- **FR-001**: `TrainingTask` model MUST contain the following envelope fields:
  - `training_task_id` (`str`): Unique identifier for the training task.
  - `baseline_model_id` (`str`): Identifier of the base model to train.
  - `baseline_model_version` (`str`): Immutable version of the base model.
  - `data_set_id` (`str`): Identifier of the dataset assigned to the task.
  - `data_set_shard_id` (`str`): Identifier of the specific dataset shard.
  - `type` (`str`): Identifier of the training adapter type (e.g., `canonical_torch`).
  - `training` (`Dict[str, Any]`): Type-specific training hyperparameter dictionary.
- **FR-002**: `TrainingTask` MUST NOT contain the deprecated `session_id` field.
- **FR-003**: `TrainingTask.validate_envelope()` MUST enforce that `training_task_id`, `baseline_model_id`, `baseline_model_version`, `data_set_id`, `data_set_shard_id`, and `type` are non-empty strings, and `training` is a dictionary.
- **FR-004**: Baseline model artifact file MUST follow the naming convention: `<baseline_model_id>_<baseline_model_version>.pt2`.
- **FR-005**: Dataset shard artifact file MUST follow the naming convention: `<data_set_id>_<data_set_shard_id>.pt`.

#### 2. Training Result Model Contract (`training_result.py`)
- **FR-006**: `TrainingResult` contract MUST contain exactly the following logical fields:
  - `trainingTaskId` (`str`): Uniquely identifies the training task that produced this result (MUST match task `training_task_id`).
  - `baseModelId` (`str`): Identifies the model trained (MUST match task `baseline_model_id`).
  - `baseModelVersion` (`str`): Identifies the exact model version used as the delta baseline (MUST match task `baseline_model_version`).
  - `datasetId` (`str`): Identifies the dataset used for the task (MUST match task `data_set_id`).
  - `datasetShardId` (`str`): Identifies the specific dataset shard used (MUST match task `data_set_shard_id`).
  - `samplesTrained` (`int`): Actual number of training samples processed across all epochs/steps contributing to the model update.
  - `metrics` (`Dict[str, Any]`): Generic, algorithm-agnostic dictionary of training metrics (e.g. `loss`, `tokensPerSecond`, `loss_history`).
  - `execution` (`Dict[str, Any]` or typed DTO): Execution timing containing `startedAt` (ISO-8601 UTC string), `completedAt` (ISO-8601 UTC string), and `durationMs` (integer elapsed milliseconds).
  - `delta` (`Dict[str, Any]` or typed DTO): Delta artifact metadata containing `filename` (`str`), `path` (`str`), `format` (`str`, e.g. `"safetensors"`), `tensorCount` (`int`), and `sizeBytes` (`int`), serialized with camelCase wire keys and accessible via snake_case properties in Python.
- **FR-007**: `TrainingResult` MUST provide serialization methods (`to_dict()`, `to_json()`) and deserialization methods (`from_dict()`, `from_json()`) supporting camelCase contract keys and snake_case Python property access.

#### 3. Model Delta Artifact Calculation & Safetensors Export
- **FR-008**: Upon training completion, the adapter in `save_result()` MUST calculate parameter deltas by subtracting the original baseline model `state_dict` from the trained model `state_dict`: `delta[name] = trained_tensor[name] - base_tensor[name]`.
- **FR-009**: The delta tensors MUST retain the identical parameter names, dimensions, and data type (`torch.float32`) as the baseline model parameters.
- **FR-010**: The model delta MUST be saved as a separate artifact file in `.safetensors` format using the strict naming convention: `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors`.
- **FR-011**: The delta artifact MUST be written directly to the trainer's task workspace directory without mutating or deleting input baseline or dataset files.
- **FR-012**: The adapter MUST NOT export a full `.pt2` trained model as the primary result artifact, replacing full model export with the delta artifact.

#### 4. Distributed Training Engine Adaptations
- **FR-013**: `CanonicalTorchAdapter` and `TrainingOrchestrator` MUST be updated to accept and process the revised `TrainingTask` contract.
- **FR-014**: `CanonicalTorchAdapter.validate()` MUST verify the existence of `<baseline_model_id>_<baseline_model_version>.pt2` and `<data_set_id>_<data_set_shard_id>.pt` in the working directory.
- **FR-015**: `CanonicalTorchAdapter.prepare()` MUST capture or preserve the baseline model `state_dict` before any training or optimizer steps modify model weights in-memory.
- **FR-016**: `CanonicalTorchAdapter.train()` MUST track total `samples_trained` (number of dataset items processed across all batches and epochs).
- **FR-017**: `TrainingOrchestrator` MUST record execution start time before running the adapter lifecycle and execution completion time after saving the result, computing `durationMs`.

#### 5. Sample & Verification Tooling (`samples/training_test/`)
- **FR-018**: `samples/training_test/setup.py` MUST be updated to generate a baseline PyTorch model saved as `<baseline_model_id>_<baseline_model_version>.pt2` (e.g. `base_model_v1.pt2`) and a dataset shard saved as `<data_set_id>_<data_set_shard_id>.pt` (e.g. `dataset1_shard1.pt`).
- **FR-019**: `samples/training_test/train.py` MUST construct a `TrainingTask` conforming to the updated contract, execute `TrainingOrchestrator`, log lifecycle transitions and execution metrics, and produce the delta `.safetensors` artifact.
- **FR-020**: `samples/training_test/verify.py` MUST be created with hardcoded sample artifact paths in the sample directory (`base_model_v1.pt2`, `dataset1_shard1.pt`, `base_model_v1_dataset1_shard1.safetensors`) to:
  - Load the baseline model `<baseline_model_id>_<baseline_model_version>.pt2`.
  - Load the delta artifact `<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors`.
  - Apply delta weights to base model parameters: `reconstructed[name] = base[name] + delta[name]`.
  - Verify parameter reconstruction parity against in-memory/expected tensors.
  - Load the dataset shard and evaluate baseline loss vs reconstructed model loss.
  - Confirm loss improvement or match with training result metrics, exiting with code 0 on success and non-zero on failure.
- **FR-021**: `samples/training_test/README.md` MUST be updated to document the updated artifact names, training workflow, and verification steps.

#### 6. Maintainability & Code Quality
- **FR-022**: All models, adapters, and scripts MUST have clear type annotations, structured logging, and docstrings.
- **FR-023**: All exceptions raised during task validation, artifact loading, training execution, or delta saving MUST be explicit custom exceptions inheriting from domain error types.

### Key Entities

- **`TrainingTask`**: Updated DTO representing a task dispatch. Key attributes: `training_task_id` (str), `baseline_model_id` (str), `baseline_model_version` (str), `data_set_id` (str), `data_set_shard_id` (str), `type` (str), `training` (dict).
- **`TrainingResult`**: Updated DTO representing the result of training. Key attributes: `training_task_id` (str), `base_model_id` (str), `base_model_version` (str), `dataset_id` (str), `dataset_shard_id` (str), `samples_trained` (int), `metrics` (dict), `execution` (ExecutionInfo/dict), `delta` (DeltaInfo/dict).
- **`ExecutionInfo`**: Telemetry DTO capturing execution timing. Key attributes: `started_at` (str ISO-8601 UTC), `completed_at` (str ISO-8601 UTC), `duration_ms` (int).
- **`DeltaArtifactInfo`**: Metadata descriptor for the delta file. Key attributes: `filename` (str), `path` (str), `format` (str, e.g. "safetensors"), `tensor_count`/`tensorCount` (int), `size_bytes`/`sizeBytes` (int).
- **`CanonicalTorchAdapter`**: PyTorch adapter executing local training, state snapshotting, difference calculation, and safetensors export.
- **`DeltaVerification`**: Logic in `verify.py` responsible for loading base models, loading deltas, reconstructing parameter states (`base + delta`), and evaluating metrics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Generated delta artifacts (`.safetensors`) reduce output artifact size by at least 60% compared to full `.pt2` exported model programs for identical model architectures.
- **SC-002**: Mathematical reconstruction of trained model parameters (`reconstructed = base + delta`) achieves 100% numerical parity with in-memory trained model parameters within floating-point epsilon ($< 10^{-6}$).
- **SC-003**: 100% of invalid task configurations, missing files, or mismatched baseline/delta tensors are detected and rejected during pre-flight validation or loading with actionable error messages.
- **SC-004**: 0% mutation of input baseline model (`.pt2`) and dataset shard (`.pt`) files across all training and verification paths.
- **SC-005**: All training lifecycle transitions, execution timings (`startedAt`, `completedAt`, `durationMs`), sample counts (`samplesTrained`), and metrics are recorded and serialized in compliance with the `TrainingResult` contract.
- **SC-006**: End-to-end sample scripts (`setup.py`, `train.py`, `verify.py`) execute sequentially with exit code 0 and demonstrate verified loss reduction.

## Assumptions

- Python environment has `safetensors` library installed (`safetensors.torch.save_file` and `safetensors.torch.load_file`).
- Input baseline model files are PyTorch 2 exported programs (`.pt2`) whose underlying module parameters are extractable via `.state_dict()` or module weights.
- Dataset shard files (`.pt`) contain dictionaries with `"x"` and `"y"` tensors in float32.
- Delta tensors are stored in single-precision (`torch.float32`) matching model parameters.
- Timestamps use UTC timezone formatted as ISO-8601 strings (e.g. `2026-09-02T10:20:00Z`).
- Aggregation, global checkpoint updating, and peer-to-peer distribution of delta files are handled by coordinating services (Client/Aggregator and Coordinator) and are outside the scope of this local engine specification.
