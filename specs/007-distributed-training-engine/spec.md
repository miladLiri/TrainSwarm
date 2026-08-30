# Feature Specification: Distributed Training Engine

**Feature Branch**: `007-distributed-training-engine`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "Distributed Training Engine - Implement a Python distributed training engine responsible for executing one training task. The engine must be extensible to support multiple training types through adapters, while keeping the orchestration lifecycle independent from model/training-type-specific implementation. The first and only supported training type in this specification is canonical_torch. The engine must be located under /src."

## Clarifications

### Session 2026-08-30

- Q: What naming convention and artifact structure should CanonicalTorchAdapter.save_result() use for the locally trained output checkpoint artifact in the working directory? → A: `trained_<task_id>.pt2` re-exported as PyTorch 2 exported program via `torch.export.save()`.
- Q: What neural network architecture should samples/training_test/setup.py generate for the canonical .pt2 exported model and matching .pt dataset shard? → A: Lightweight Multi-Layer Perceptron (MLP) (e.g., 2-layer Linear network with float32 input shape `[10, 4]` and target `[10, 1]`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Execution of Canonical PyTorch Training Task (Priority: P1)

As a Trainer node worker in the TrainSwarm cluster, I want to execute a single, locally dispatched training task using a canonical PyTorch model (.pt2) and dataset shard (.pt), so that I can train the model weights locally and emit a newly trained model checkpoint artifact (`trained_<task_id>.pt2`) and execution metrics without mutating input files or assuming global aggregation ownership.

**Why this priority**: Core execution capability of the data plane trainer. Without local task execution, no training workload can be performed on the swarm.

**Independent Test**: Provide a working directory containing an exported PyTorch 2 canonical program (`checkpoint-001.pt2`) and dataset shard (`shard-001.pt`), along with a `TrainingTask` JSON configuration specifying `canonical_torch` training parameters. Invoke `TrainingOrchestrator`, verify that the model trains for the specified epochs/steps, weights update, output checkpoint artifact (`trained_<task_id>.pt2`) is produced in the working directory via `torch.export.save()`, and a valid `TrainingResult` is returned with execution metrics.

**Acceptance Scenarios**:

1. **Given** a valid `TrainingTask` with type `canonical_torch`, a working directory with `checkpoint-001.pt2` and `shard-001.pt`, **When** `TrainingOrchestrator.run(task, working_dir)` is executed, **Then** the orchestrator resolves `CanonicalTorchAdapter`, executes the complete lifecycle (`validate`, `prepare`, `train`, `save_result`), outputs a new local checkpoint artifact (`trained_<task_id>.pt2`), leaves input files unmodified, and returns a `TrainingResult` containing training steps, epochs completed, final loss, and output artifact path.
2. **Given** a training task with `max_steps` set to an integer smaller than the total steps across all epochs, **When** training is executed, **Then** the training loop halts precisely when the optimizer step count reaches `max_steps`, updating the scheduler and saving the resulting model state.
3. **Given** a training task with `gradient_accumulation_steps` > 1 and `max_grad_norm` configured, **When** training batches are processed, **Then** loss is scaled by accumulation steps, gradients are accumulated across batches, clipped to `max_grad_norm` before `optimizer.step()`, scheduler stepped after optimizer update, and the final remaining incomplete accumulation group is processed cleanly.

---

### User Story 2 - Pre-Flight Task, Model, and Dataset Validation (Priority: P2)

As an operator and orchestrator, I want rigorous pre-flight validation of task schemas, configuration parameters, model contracts, and dataset shard files before training starts, so that misconfigurations, corrupted files, and schema incompatibilities fail fast with actionable, descriptive error messages without leaving corrupted artifacts or half-executed state.

**Why this priority**: Critical for operational reliability and debuggability in distributed worker execution. Failures must be explicit and occur before any compute or optimization steps begin.

**Independent Test**: Supply malformed task DTOs, unsupported training types, negative batch sizes/learning rates, missing checkpoint/shard files, dataset shards with mismatched tensor dimensions or non-float32 dtypes, or non-canonical model files. Verify that `validate()` or `prepare()` raises explicit, categorized exceptions detailing the failure cause.

**Acceptance Scenarios**:

1. **Given** a `TrainingTask` with missing required fields (e.g. empty `task_id` or null `training` block) or negative hyperparameters (`batch_size = -1`, `epochs = 0`), **When** `validate()` is called, **Then** validation fails immediately before reading files or starting training.
2. **Given** a dataset shard `.pt` file where tensor `x` and `y` have mismatched batch dimensions or non-`torch.float32` dtype, **When** dataset validation runs during `prepare()`, **Then** a dataset contract validation error is raised indicating the shape/dtype discrepancy.
3. **Given** a requested checkpoint file or shard file that does not exist in the working directory, **When** `validate()` executes, **Then** an explicit missing artifact error is raised identifying the expected file path and artifact ID.

---

### User Story 3 - Extensible Component Registries (Priority: P3)

As a developer extending the training framework, I want modular registries for training adapters, optimizers, schedulers, and loss criteria with strongly typed parameter DTOs, so that new algorithms and components can be added without modifying the core `TrainingOrchestrator` lifecycle or the `CanonicalTorchAdapter` training loop.

**Why this priority**: Enables clean architectural separation and future extensibility (e.g., adding Transformer adapters or new PyTorch optimizers/schedulers) while enforcing strict dependency boundaries.

**Independent Test**: Register a supported optimizer (e.g. `AdamW` or `SGD`), scheduler (e.g. `CosineAnnealingLR`, `LinearLR`, `StepLR`, `ExponentialLR`, `ConstantLR`), or criterion (e.g. `MSELoss`, `L1Loss`, `SmoothL1Loss`, `CrossEntropyLoss`, `BCEWithLogitsLoss`) through their respective registries with validated parameter DTOs, verify correct PyTorch instance construction and training execution.

**Acceptance Scenarios**:

1. **Given** a task specifying `optimizer: { "type": "AdamW", "parameters": { "learning_rate": 0.001, "weight_decay": 0.01 } }`, **When** `OptimizerRegistry.create(...)` is invoked, **Then** parameters are validated into `AdamWParameters` DTO and an instantiated `torch.optim.AdamW` object is bound to model parameters.
2. **Given** a task specifying `loss: { "type": "CrossEntropyLoss", "parameters": {} }`, **When** `CriterionRegistry.create(...)` is invoked, **Then** parameters are validated into `CrossEntropyLossParameters` DTO and a `torch.nn.CrossEntropyLoss` instance is returned.
3. **Given** a task specifying an unknown or unsupported training type, optimizer, scheduler, or loss type, **When** registry lookup occurs, **Then** a descriptive registry resolution error is thrown listing the unsupported key.

---

### User Story 4 - End-to-End Verification Sample and Tracing (Priority: P4)

As a developer or QA engineer, I want a runnable sample test suite (`setup.py`, `train.py`, and `README.md`) under `samples/training_test/` along with structured tracing logs, so that I can generate sample artifacts, run a single training step end-to-end, and inspect the operational log flow.

**Why this priority**: Mandatory per project constitution (active execution verification, zero mocks, runnable artifacts).

**Independent Test**: Execute `python samples/training_test/setup.py` to generate `checkpoint-001.pt2` (a 2-layer MLP) and `shard-001.pt` (10 samples of float32 tensors with shapes `[10, 4]` and `[10, 1]`), then execute `python samples/training_test/train.py` to run `TrainingOrchestrator`, verify zero errors, inspect console/structured logs for each lifecycle phase, and confirm the generated `trained_<task_id>.pt2` result artifact.

**Acceptance Scenarios**:

1. **Given** the `samples/training_test/setup.py` script, **When** executed, **Then** it creates a canonical 2-layer MLP PyTorch model, exports it to `checkpoint-001.pt2` format, creates a 10-entry canonical `x`/`y` tensor dataset shard (`x` shape `[10, 4]`, `y` shape `[10, 1]`) saved as `shard-001.pt`, and writes both to the sample directory.
2. **Given** the generated sample files and `samples/training_test/train.py`, **When** executed, **Then** it constructs a `TrainingTask`, runs `TrainingOrchestrator`, logs step-by-step lifecycle progress (`validate` -> `prepare` -> `train` -> `save_result`), exports `trained_<task_id>.pt2`, and outputs the final loss and metrics cleanly.

---

### Edge Cases

- **Incomplete Gradient Accumulation**: When dataset length / batch size leaves a final remainder batch that does not align with `gradient_accumulation_steps`, the final partial accumulation group must execute an optimizer step and zero gradients without dropping gradient information.
- **Both `epochs` and `max_steps` Configured**: Training must gracefully terminate whichever threshold is satisfied first (early exit upon reaching `max_steps` mid-epoch or completion of all `epochs`).
- **Gradient Clipping with Zero or Null Threshold**: When `max_grad_norm` is `null`, gradient clipping is bypassed; when specified (> 0.0), `torch.nn.utils.clip_grad_norm_` is applied before `optimizer.step()`.
- **Reproducibility with Random Seed**: When `seed` is provided in `CanonicalTorchTrainingConfig`, seed states for Python `random`, `numpy` (if installed), `torch.manual_seed`, and `torch.cuda.manual_seed_all` (if CUDA is available) must be established before DataLoader initialization and training execution.
- **Device Availability Fallback**: Automatically select `cuda` if `torch.cuda.is_available()` is true, otherwise fallback to `cpu`, transferring model module and batch tensors to the chosen device.
- **Immutable Input Artifacts**: Neither input checkpoint `.pt2` nor dataset shard `.pt` may be modified, overwritten, or locked on disk during or after training execution.
- **Output Artifact Naming Collision Avoidance**: Generated locally trained output checkpoint artifact must be saved as `trained_<task_id>.pt2` via `torch.export.save()` in the working directory, guaranteeing no overwrite of `<checkpoint_version>.pt2`.

## Requirements *(mandatory)*

### Functional Requirements

#### Architecture & Orchestration
- **FR-001**: System MUST place the distributed training engine under `src/distributed_training_engine/` and follow the modular package hierarchy specified in the design.
- **FR-002**: `TrainingOrchestrator` MUST be training-type agnostic, delegating all training-specific behaviors exclusively to `TrainingAdapter` implementations without inspecting type-specific configuration fields or using conditional branching on model types.
- **FR-003**: `TrainingOrchestrator` MUST resolve adapter instances via `TrainingAdapterRegistry` using the task `type` (`ModelType`).
- **FR-004**: `TrainingOrchestrator` MUST construct the resolved adapter by passing `TrainingTask` and the resolved `working_directory` path.
- **FR-005**: `TrainingOrchestrator` MUST execute the adapter lifecycle in strict sequential order: `validate()` -> `prepare()` -> `train()` -> `save_result()`, returning the produced `TrainingResult`.
- **FR-006**: `TrainingAdapter` MUST be an abstract base class defining the four core lifecycle methods: `validate()`, `prepare()`, `train()`, and `save_result()`.

#### Model & Dataset Contracts (`canonical_torch`)
- **FR-007**: `CanonicalTorchAdapter` MUST support models exported as PyTorch 2 program files in `.pt2` format, loaded via `torch.export.load(path)` and unwrapped via `loaded_program.module()`.
- **FR-008**: The canonical model MUST accept a single argument `x` of type `torch.Tensor` with `dtype=torch.float32` and return output tensors compatible with PyTorch criteria.
- **FR-009**: Canonical dataset shards MUST be `.pt` files loaded via `torch.load(path, weights_only=True)` containing a dictionary with keys `"x"` and `"y"`.
- **FR-010**: Dataset tensors `"x"` and `"y"` MUST both be `torch.Tensor` with `dtype=torch.float32`, sharing the identical leading dimension (number of samples).
- **FR-011**: `prepare()` MUST package the dataset tensors into `torch.utils.data.TensorDataset` and construct a `torch.utils.data.DataLoader` using the configured `batch_size` and `shuffle` settings.

#### Registries & Strongly Typed Parameter DTOs
- **FR-012**: `OptimizerRegistry` MUST map optimizer string identifiers to typed parameter DTOs and construct PyTorch optimizers. Initial supported optimizers MUST include `AdamW` (`AdamWParameters`) and `SGD` (`SGDParameters`). `learning_rate` MUST be validated as an optimizer parameter.
- **FR-013**: `SchedulerRegistry` MUST map scheduler string identifiers to typed parameter DTOs and construct PyTorch learning rate schedulers. Initial supported schedulers MUST include `ConstantLR`, `LinearLR`, `StepLR`, `ExponentialLR`, and `CosineAnnealingLR` with corresponding parameter DTOs.
- **FR-014**: `CriterionRegistry` MUST map loss string identifiers to typed parameter DTOs and construct PyTorch loss criteria. Initial supported criteria MUST include `MSELoss`, `L1Loss`, `SmoothL1Loss`, `CrossEntropyLoss`, and `BCEWithLogitsLoss` with corresponding parameter DTOs.
- **FR-015**: Registries MUST reject arbitrary unvalidated parameter dictionaries and throw descriptive errors when unsupported types or invalid parameter fields are encountered.

#### Training Loop & Execution Semantics
- **FR-016**: `CanonicalTorchAdapter.train()` MUST execute the autograd training loop in `model.train()` mode on the detected hardware device (`cuda` if available, else `cpu`).
- **FR-017**: All model parameters and input/target batch tensors MUST be placed on the execution device using single-precision (`torch.float32`).
- **FR-018**: When `seed` is specified, random number generators for Python, NumPy (if present), PyTorch CPU, and CUDA MUST be seeded before execution.
- **FR-019**: `train()` MUST scale batch loss by `1.0 / gradient_accumulation_steps` before invoking `loss.backward()`.
- **FR-020**: When `max_grad_norm` is provided, gradients MUST be clipped via `torch.nn.utils.clip_grad_norm_` prior to `optimizer.step()`.
- **FR-021**: The configured scheduler (if present) MUST be stepped immediately following `optimizer.step()`, followed by `optimizer.zero_grad()`.
- **FR-022**: Optimizer step count (`max_steps`) MUST count actual optimizer updates rather than batch iterations. Training MUST stop when `max_steps` is reached or when all `epochs` have completed.
- **FR-023**: The final incomplete gradient accumulation group at the end of training/dataset iteration MUST perform an optimizer step and gradient zeroing.

#### Artifacts, Results & Ownership
- **FR-024**: `save_result()` MUST save the locally trained model as a PyTorch 2 exported program (`.pt2`) to an artifact named `trained_<task_id>.pt2` in the working directory using `torch.export.save()`, without overwriting the input `<checkpoint_version>.pt2`.
- **FR-025**: The engine MUST NOT label or designate the output artifact as the next global checkpoint version, leaving global versioning and aggregation to the aggregator service.
- **FR-026**: `save_result()` MUST return a `TrainingResult` DTO populated with `task_id`, `input_checkpoint_version`, `output_checkpoint_path`, `training_steps`, `epochs_completed`, `final_loss`, and `metrics`.
- **FR-027**: Input checkpoint (`<checkpoint_version>.pt2`) and dataset shard (`<dataset_shard_id>.pt`) files MUST be treated as immutable read-only inputs.

#### Pre-Flight Validation & Error Handling
- **FR-028**: `validate()` MUST execute prior to training and verify:
  - Non-empty `task_id`, `session_id`, `type`, `checkpoint_version`, and `dataset_shard_id`.
  - Positive numeric values for `batch_size`, `epochs`, and `gradient_accumulation_steps`.
  - Non-negative/positive values for `max_steps` and `max_grad_norm` when non-null.
  - Valid integer for `seed`.
  - Existence of `<checkpoint_version>.pt2` and `<dataset_shard_id>.pt` in the working directory.
  - Successful validation of optimizer, scheduler, and criterion configuration blocks against their respective registry schemas.
- **FR-029**: Validation errors and runtime failures MUST raise specific, actionable domain exceptions without swallowing stack traces or silently continuing execution.

#### Observability & Verification Harness
- **FR-030**: All orchestrator and adapter lifecycle transitions (`validate`, `prepare`, `train`, `save_result`) and per-epoch/per-step metrics MUST be logged using structured Python logging (`logging` module).
- **FR-031**: The system MUST provide `samples/training_test/setup.py`, `samples/training_test/train.py`, and `samples/training_test/README.md` to demonstrate end-to-end canonical 2-layer MLP export (`[10, 4]` input, `[10, 1]` target), dataset creation, orchestrator execution, and result verification.

### Key Entities

- **`TrainingTask`**: Top-level DTO representing a training task dispatch. Attributes: `task_id` (str), `session_id` (str), `type` (`ModelType` or str), `checkpoint_version` (str), `dataset_shard_id` (str), `training` (polymorphic dict / type-specific config).
- **`ModelType`**: Enumeration discriminator for training types. Initial member: `CANONICAL_TORCH = "canonical_torch"`.
- **`CanonicalTorchTrainingConfig`**: Strongly typed configuration for `canonical_torch`. Attributes: `batch_size` (int), `shuffle` (bool), `epochs` (int), `gradient_accumulation_steps` (int), `max_steps` (Optional[int]), `max_grad_norm` (Optional[float]), `seed` (Optional[int]), `optimizer` (OptimizerConfig), `scheduler` (Optional[SchedulerConfig]), `loss` (LossConfig).
- **`OptimizerConfig` & `OptimizerParameters`**: Generic wrapper specifying optimizer `type` (str) and typed parameters (e.g. `AdamWParameters`, `SGDParameters`).
- **`SchedulerConfig` & `SchedulerParameters`**: Generic wrapper specifying scheduler `type` (str) and typed parameters (e.g. `CosineAnnealingLRParameters`, `StepLRParameters`, `LinearLRParameters`, `ExponentialLRParameters`, `ConstantLRParameters`).
- **`LossConfig` & `CriterionParameters`**: Generic wrapper specifying loss `type` (str) and typed parameters (e.g. `MSELossParameters`, `L1LossParameters`, `SmoothL1LossParameters`, `CrossEntropyLossParameters`, `BCEWithLogitsLossParameters`).
- **`TrainingResult`**: Result DTO returned after execution. Attributes: `task_id` (str), `input_checkpoint_version` (str), `output_checkpoint_path` (str), `training_steps` (int), `epochs_completed` (int), `final_loss` (float), `metrics` (dict).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Successful end-to-end execution of a canonical PyTorch training task produces a verified loss reduction and updated model artifact (`trained_<task_id>.pt2`) in under 5 seconds for sample tasks.
- **SC-002**: 100% of invalid task configurations, missing files, corrupted shards, or unsupported components are caught during pre-flight validation before compute or training allocation begins.
- **SC-003**: 0% mutation of input checkpoint (`.pt2`) and dataset shard (`.pt`) files across all execution paths.
- **SC-004**: Adding a new optimizer, scheduler, or criterion to the registry requires 0 modifications to the core training loop or orchestrator lifecycle.
- **SC-005**: All lifecycle transitions, training progress, and execution milestones are logged with structured context (task ID, session ID, epoch, step, loss).
- **SC-006**: Sample verification suite (`samples/training_test/setup.py` and `train.py`) executes cleanly with exit code 0 and verifies complete contract compliance.

## Assumptions

- Training tasks are executed locally on the worker host with PyTorch 2.x installed.
- Input checkpoint files in `.pt2` format are valid PyTorch 2 exported programs (`torch.export.ExportedProgram`) whose `.module()` accepts a single `torch.float32` tensor.
- Precision for the canonical torch contract is fixed at `torch.float32` (no AMP/FP16/BF16/quantization in this initial version).
- Network transfer of checkpoints/shards, assignment orchestration, and global federated averaging/aggregation are handled outside of this local engine component by other TrainSwarm services (Coordinator, Client/Aggregator, P2P sidecar).
- Hardware execution automatically uses CUDA if available, falling back to CPU.
