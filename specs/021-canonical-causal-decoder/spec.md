# Feature Specification: Canonical Causal Decoder Model

**Feature Branch**: `021-canonical-causal-decoder`

**Created**: 2026-09-13

**Status**: Draft
**Input**: User description: "Canonical Causal Decoder Model"

## Clarifications

### Session 2026-09-13

- Q: How should the compressed model archive format and file extension be validated and handled across the client, trainer, and aggregator? → A: Accept both `.tar.gz` and `.gz` transparently via `tarfile` in gzip decompression mode, saving newly published versions as `.gz` (Option A).
- Q: Where should CanonicalCausalDecoderTrainer unpack the model archive during the prepare() phase, and how should unpacked directories be managed? → A: Extract to a dedicated subfolder (`model_unpacked/`) and load via resolved path to `model` and `tokenizer`, retaining them until task completion (Option A).
- Q: How should setup.py obtain the TinyStories-1M model and dataset artifacts if the execution environment is offline or Hugging Face Hub is unreachable? → A: Directly download model (`roneneldan/TinyStories-1M`) and dataset (`roneneldan/TinyStories`) from Hugging Face Hub, requiring internet access for test setup.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Training Execution with Hugging Face Causal LM (Priority: P1)

As a Trainer node in the distributed cluster, I want to execute local fine-tuning on an assigned tokenized dataset shard using Hugging Face `AutoModelForCausalLM` and `Trainer` via a concrete `CanonicalCausalDecoderTrainer` adapter, so that transformer decoder models are trained locally and weight updates are extracted as parameter deltas (`.safetensors`).

**Why this priority**: Core execution capability of the feature. Without the trainer adapter, Trainer nodes cannot validate, prepare, fine-tune, or extract deltas for causal language models.

**Independent Test**: Load a valid compressed causal decoder model archive (`.gz`) containing model and tokenizer weights, an assigned `.pt` dataset shard with `input_ids`, `attention_mask`, and `labels`, and a `CanonicalCausalDecoderTrainingConfig`. Run the 4-phase lifecycle (`validate()`, `prepare()`, `train()`, `save_result()`). Verify that fine-tuning executes without errors, base model files remain unmodified, and a valid `.safetensors` update artifact containing parameter deltas ($\Delta W = W_{\text{trained}} - W_{\text{base}}$) is produced alongside a populated `TrainingResult`.

**Acceptance Scenarios**:

1. **Given** a `TrainingTask` targeting `canonical_causal_decoder`, **When** `validate()` is called, **Then** it validates task envelope fields, deserializes `CanonicalCausalDecoderTrainingConfig`, verifies the model archive (`.gz`) exists and unpacks to valid `model/` and `tokenizer/` directories, verifies the `.pt` dataset shard exists, and raises explicit domain exceptions (`MissingArtifactError`, `InvalidTaskConfigurationError`) on validation failures.
2. **Given** validated task inputs, **When** `prepare()` is called, **Then** it resolves the execution device (`cuda` if available, otherwise `cpu`), unpacks the model archive into a dedicated subfolder (`model_unpacked/`) inside `self.working_directory`, loads `AutoModelForCausalLM` from `model/` and `AutoTokenizer` from `tokenizer/`, validates the dataset shard schema (`input_ids`, `attention_mask`, `labels`), captures an immutable in-memory snapshot of all trainable base parameters, constructs Hugging Face `TrainingArguments`, and initializes `Trainer` without performing any gradient update step.
3. **Given** prepared state, **When** `train()` is called, **Then** it invokes Hugging Face `Trainer.train()` to optimize the causal language model loss on the assigned shard, honors configured termination criteria (`epochs`, `max_steps`), and records execution metrics.
4. **Given** completed training, **When** `save_result()` is called, **Then** it computes parameter deltas ($\Delta W = W_{\text{trained}} - W_{\text{base}}$) for every trainable parameter, validates delta names, shapes, and dtypes against the baseline, serializes them into a `.safetensors` artifact named `{base_model_id}_{version}_{dataset_id}_{shard_id}.safetensors`, and returns a populated `TrainingResult` containing samples trained, metrics, and artifact references.

---

### User Story 2 - Causal Language Model Dataset Partitioning & Sampling (Priority: P2)

As a Client or Aggregator preparing a distributed training job, I want to extract a representative smoke-test sample and divide a tokenized causal dataset into balanced `.pt` shards using `CanonicalCausalDecoderPartitioner`, so that individual shards can be distributed to trainer nodes without altering token sequences or training semantics.

**Why this priority**: Essential data-plane prerequisite. Without partitioning, the client cannot perform smoke tests or deliver correctly sized shards to trainers.

**Independent Test**: Provide a source dataset `.pt` file containing `input_ids`, `attention_mask`, and `labels`. Invoke `CreateSample()` to produce `<dataset_id>_sample.pt`, then invoke `CreateShards(shardSampleSize)` to produce numbered shard files `<dataset_id>_<shard_id>.pt`. Confirm each shard preserves tensor keys, shapes, sample alignment, and token values.

**Acceptance Scenarios**:

1. **Given** a valid tokenized dataset `.pt` file, **When** `CreateSample()` is called, **Then** it extracts a representative sample containing `input_ids`, `attention_mask`, and `labels`, and saves it as `<dataset_id>_sample.pt` in the designated sample output directory.
2. **Given** a target shard sample size, **When** `CreateShards(shardSampleSize)` is called, **Then** it slices the dataset into sequential shards containing at most `shardSampleSize` samples per shard, saving each as `<dataset_id>_<shard_id>.pt` in the shards output directory.
3. **Given** generated shards, **When** tensors are inspected, **Then** `input_ids`, `attention_mask`, and `labels` within every shard have matching sample counts (batch dimension) and compatible tensor dtypes.
4. **Given** an invalid dataset missing required keys or with mismatched tensor lengths, **When** partitioning is attempted, **Then** the partitioner rejects the dataset with an explicit descriptive validation error.

---

### User Story 3 - Model Update Aggregation & Version Generation (Priority: P3)

As an Aggregator node, I want to validate trainer update deltas, compute sample-weighted Federated Averaging, and publish a new model version archive via `CanonicalCausalDecoderAggregator`, so that parameter updates from all trainers are synthesized into an updated causal decoder model.

**Why this priority**: Core distributed learning closure. Without aggregation, multi-trainer updates cannot be combined into a consolidated new model version.

**Independent Test**: Provide a base model archive and two valid `.safetensors` updates with known sample counts ($n_1, n_2$). Execute `LoadDelta()`, `ValidateDelta()`, `Aggregate()`, and `CreateNewVersion()`. Verify that the aggregated delta matches the mathematical weighted average $\Delta W_{\text{avg}} = \sum \frac{n_i}{N} \Delta W_i$, the base model parameters are updated ($W_{\text{new}} = W_{\text{base}} + \Delta W_{\text{avg}}$), the tokenizer is carried forward unchanged, and the new version is atomically written as a valid `.gz` archive containing `model/` and `tokenizer/`.

**Acceptance Scenarios**:

1. **Given** a list of trainer update references in `AggregationRequest`, **When** `LoadDelta()` is executed, **Then** it deserializes each `.safetensors` update artifact into memory without error.
2. **Given** loaded updates, **When** `ValidateDelta()` is executed, **Then** it verifies that all update parameter names match parameters in the base model, tensor shapes and dtypes match, samples trained is greater than zero, and all deltas share identical model ID and base version.
3. **Given** validated deltas, **When** `Aggregate()` is executed, **Then** it calculates sample-weighted Federated Averaging across all updates independently of specific Transformer architecture architectures (GPT, Llama, Qwen, etc.).
4. **Given** aggregated deltas, **When** `CreateNewVersion()` is executed, **Then** it applies updates to the base model parameters ($W_{\text{new}} = W_{\text{base}} + \Delta W_{\text{avg}}$), packages the resulting `model/` directory alongside the untouched `tokenizer/` directory into a `.gz` archive atomically, and returns an `AggregationResult` describing the published version.

---

### User Story 4 - Engine Registration & Open-Closed Principle Compliance (Priority: P4)

As a system architect, I want the canonical causal decoder adapter suite registered with the distributed training engine without modifying model-agnostic abstractions or control/data-plane services outside of the adapter and presentation layers, so that the Open-Closed Principle is strictly preserved.

**Why this priority**: Architectural integrity requirement mandated by repository standards and user instructions. Adding new model types must not regress or mutate existing model-agnostic workflows.

**Independent Test**: Register `ModelType.CANONICAL_CAUSAL_DECODER = "canonical_causal_decoder"` in `model_type.py`, and register the trainer, partitioner, and aggregator classes in their respective registries. Verify that `TrainerAdapterRegistery.get()`, `PartitionerAdapterRegistery.Get()`, and `AggregatorAdapterRegistery.Get()` resolve the causal decoder adapters correctly, while existing `canonical_torch` registrations remain unchanged.

**Acceptance Scenarios**:

1. **Given** `model_type.py`, **When** inspected, **Then** `ModelType` enum contains `CANONICAL_CAUSAL_DECODER = "canonical_causal_decoder"` alongside `CANONICAL_TORCH = "canonical_torch"`.
2. **Given** `TrainerAdapterRegistery`, `PartitionerAdapterRegistery`, and `AggregatorAdapterRegistery`, **When** queried with `CANONICAL_CAUSAL_DECODER`, **Then** each returns the corresponding canonical causal decoder adapter class.
3. **Given** existing engine core abstractions (`TrainingOrchestrator`, `PartitioningOrchestrator`, `AggregationOrchestrator`, data models, Coordinator, Trainer, and Client core services), **When** inspected, **Then** zero model-specific causal decoder logic or branching is introduced outside of `adapters/canonical_causal_decoder/` and presentation layers.

---

### User Story 5 - Dynamic Model Type Selection in Client GUI and Console UI (Priority: P5)

As a Client application user, I want the submit training interface in both GUI and Console UI to prompt for `model_type` first and dynamically present the appropriate artifact file pickers and hyperparameter input fields, so that I can configure and submit either `canonical_torch` or `canonical_causal_decoder` training tasks intuitively.

**Why this priority**: User interface usability and contract compliance. Users must be able to select the model type and configure model-specific hyperparameters in both GUI and CLI environments.

**Independent Test**: Launch the GUI and change Model Engine Type dropdown from `canonical_torch` to `canonical_causal_decoder`. Confirm that artifact pickers update to accept `.gz` archives for models and `.pt` for datasets, and parameter fields switch to Hugging Face Trainer arguments (`learning_rate`, `batch_size`, `epochs`, `max_steps`, `weight_decay`, `gradient_accumulation_steps`, `max_grad_norm`, `scheduler_type`, `warmup_steps`, `warmup_ratio`, `fp16`, `bf16`, `shuffle`, `seed`). Run CLI `submit-training` with `--model-type canonical_causal_decoder` and assert appropriate argument handling.

**Acceptance Scenarios**:

1. **Given** the Client GUI "Submit Training" tab, **When** rendered, **Then** the first interactive field is the "Model Engine Type" dropdown containing `canonical_torch` and `canonical_causal_decoder`.
2. **Given** `canonical_causal_decoder` is selected in GUI, **When** the form updates, **Then** the model artifact picker requests a `.gz` archive, dataset picker requests a `.pt` file, and training parameter inputs display fields for `CanonicalCausalDecoderTrainingConfig`.
3. **Given** `canonical_torch` is selected in GUI, **When** the form updates, **Then** the artifact pickers request `.pt2` and `.pt` files, and training parameter inputs display optimizer, criterion, and scheduler dropdowns.
4. **Given** the Client CLI `submit-training` command, **When** invoked with `--model-type canonical_causal_decoder`, **Then** `--model-path` accepts the `.gz` archive, `--dataset-path` accepts the `.pt` dataset, and `--training-config` accepts the causal decoder JSON configuration file.

---

### User Story 6 - Non-Containerized End-to-End Verification Test with TinyStories-1M (Priority: P6)

As a developer or QA engineer, I want an end-to-end verification sample in `samples/canonical_causal_decoder_training_test/` using TinyStories-1M, running Coordinator, Relay, Client, and 2 Trainers natively without Docker, so that the complete multi-node causal decoder lifecycle (setup, submission, P2P file transfer, distributed training, aggregation, perplexity validation, and cleanup) is verified per Constitution Principles VI and VII.

**Why this priority**: Non-negotiable quality gate mandated by the Constitution (Principle VI: Real Functional Implementations, Principle VII: Executable Correctness). Proves the entire system works end-to-end in real execution without mocks.

**Independent Test**: Execute `setup.py` to start background services and prepare TinyStories-1M artifacts, run `submit.py` to submit and coordinate distributed training across 2 trainers, run `verify.py` to calculate validation loss and perplexity across version 0 and version 1, and run `clean.py` to cleanly terminate processes and purge test directories.

**Acceptance Scenarios**:

1. **Given** `samples/canonical_causal_decoder_training_test/setup.py`, **When** executed, **Then** it starts Coordinator, Relay, Client (with p2p sidecar), and 2 Trainers (with p2p sidecars) as background processes with dedicated working directories, and downloads TinyStories-1M (`roneneldan/TinyStories-1M`) and dataset (`roneneldan/TinyStories`) directly from Hugging Face Hub, preparing the `.gz` model archive and `.pt` dataset partitioned into training and small validation sets.
2. **Given** `submit.py`, **When** executed, **Then** it submits the training task via Client CLI, executes local smoke testing, partitions the dataset into 2 shards, persists records, and sends tasks to Coordinator; Coordinator schedules 1 shard to each of the 2 trainers; trainers pull artifacts, execute local fine-tuning using Hugging Face Trainer, and push `.safetensors` delta updates to Client; Client aggregates updates and publishes version 1 `.gz` model artifact.
3. **Given** `verify.py`, **When** executed, **Then** it evaluates base version 0 and aggregated version 1 on the hold-out validation dataset, reports loss and perplexity for both, and verifies model improvement.
4. **Given** `clean.py`, **When** executed, **Then** it terminates all background services cleanly and removes temporary artifacts and directories.

---

### Edge Cases

- **Corrupted Model Archive**: What happens if the uploaded `.gz` model archive is corrupt or lacks either the `model/` or `tokenizer/` subdirectory? `validate()` fails immediately with `MissingArtifactError` or `InvalidModelArchiveError` before starting preparation.
- **Mismatched Dataset Keys**: What happens if the dataset shard `.pt` file contains arbitrary keys or is missing `labels`? `prepare()` and `CreateShards()` reject the dataset with `InvalidDatasetContractError`.
- **Unequal Batch Lengths**: What happens if `input_ids`, `attention_mask`, and `labels` have mismatched tensor dimensions or lengths? Dataset validation raises a `TensorDimensionMismatchError`.
- **Partial Trainer Completion**: What happens if only 1 out of 2 trainers finishes training? Aggregator aggregates available updates if minimum quorum requirements are met, or reports a clear failure state.
- **Empty Delta File or Zero Trained Samples**: What happens if a trainer produces a delta file with 0 samples trained? `ValidateDelta()` rejects the update with `InvalidUpdateError` before aggregation.
- **Mixed Precision Availability**: What happens if `fp16` or `bf16` is requested on hardware without CUDA support? The trainer falls back to CPU/FP32 or logs a warning/raises an explicit error based on configuration strictness.
- **Atomic Model Publishing**: What happens if model serialization is interrupted during `CreateNewVersion()`? The new version archive must be written to a temporary file and atomically renamed to prevent publishing partially written archives.

## Requirements *(mandatory)*

### Functional Requirements

#### Core Adapter Suite Structure
- **FR-001**: System MUST create the adapter suite under `src/distributed_training_engine/adapters/canonical_causal_decoder/` structured into `training/`, `partitioning/`, and `aggregation/` packages.
- **FR-002**: `training/canonical_causal_decoder_config.py` MUST provide `CanonicalCausalDecoderTrainingConfig` validating the following configuration attributes: `seed` (int, default 42), `batch_size` (int, default 2), `epochs` (int, default 1), `max_steps` (Optional[int], default None), `learning_rate` (float, default 5e-5), `weight_decay` (float, default 0.01), `gradient_accumulation_steps` (int, default 1), `max_grad_norm` (Optional[float], default 1.0), `scheduler_type` (str, default "linear"), `warmup_steps` (int, default 0), `warmup_ratio` (float, default 0.0), `fp16` (bool, default False), `bf16` (bool, default False), and `shuffle` (bool, default True).

#### Trainer Adapter
- **FR-003**: `training/canonical_causal_decoder_trainer.py` MUST implement `TrainerAdapter` with the 4-phase lifecycle: `validate()`, `prepare()`, `train()`, and `save_result()`.
- **FR-004**: `validate()` MUST inspect the incoming `TrainingTask` envelope, deserialize `CanonicalCausalDecoderTrainingConfig`, verify the model archive (`.gz` or `.tar.gz`) exists and contains `model/` and `tokenizer/` directories (transparently unarchived via `tarfile` in gzip mode), and verify the `.pt` dataset shard exists.
- **FR-005**: `prepare()` MUST resolve target device (`cuda` if available, otherwise `cpu`), unpack the model archive into a dedicated `model_unpacked/` subfolder inside `self.working_directory`, load `AutoModelForCausalLM` from `model_unpacked/model` and `AutoTokenizer` from `model_unpacked/tokenizer`, validate canonical dataset keys (`input_ids`, `attention_mask`, `labels`), capture an immutable parameter snapshot, construct Hugging Face `TrainingArguments`, and initialize `Trainer`.
- **FR-006**: `train()` MUST invoke Hugging Face `Trainer.train()` on the assigned dataset shard and track execution metrics.
- **FR-007**: `save_result()` MUST compute parameter deltas $\Delta W = W_{\text{trained}} - W_{\text{base}}$ for all trainable parameters, serialize them into a `.safetensors` update artifact `{base_model_id}_{version}_{dataset_id}_{shard_id}.safetensors`, and return a populated `TrainingResult`. Original baseline and shard files MUST remain unmodified.

#### Partitioner Adapter
- **FR-008**: `partitioning/canonical_causal_decoder_partitioner.py` MUST implement `PartitionerAdapter` providing `CreateSample() -> SamplingResult` and `CreateShards(shardSampleSize: int) -> PartitioningResult`.
- **FR-009**: `CreateSample()` MUST extract a representative training sample conforming to `{"input_ids": ..., "attention_mask": ..., "labels": ...}` and persist it as `<dataset_id>_sample.pt`.
- **FR-010**: `CreateShards(shardSampleSize)` MUST chunk the tokenized dataset into sequential shards of at most `shardSampleSize` samples each, persisting each shard as `<dataset_id>_<shard_id>.pt` containing canonical keys and matching sample counts.

#### Aggregator Adapter
- **FR-011**: `aggregation/canonical_causal_decoder_aggregator.py` MUST implement `AggregatorAdapter` providing `LoadDelta()`, `ValidateDelta()`, `Aggregate()`, and `CreateNewVersion() -> AggregationResult`.
- **FR-012**: `LoadDelta()` MUST deserialize trainer-produced `.safetensors` parameter updates into memory.
- **FR-013**: `ValidateDelta()` MUST verify that parameter names exist in the base model, tensor shapes and dtypes match, samples trained is positive, and all updates share the identical base model ID and version.
- **FR-014**: `Aggregate()` MUST compute sample-weighted Federated Averaging: $\Delta W_{\text{avg}} = \sum \frac{n_i}{N} \Delta W_i$, operating independently of specific Transformer architectures.
- **FR-015**: `CreateNewVersion()` MUST apply aggregated deltas to base model parameters ($W_{\text{new}} = W_{\text{base}} + \Delta W_{\text{avg}}$), preserve the tokenizer unchanged, and package the result atomically into a new `.gz` model archive (gzipped tar archive).

#### Engine Registration & Open-Closed Principle
- **FR-016**: `ModelType` enum in `src/distributed_training_engine/model_type.py` MUST include `CANONICAL_CAUSAL_DECODER = "canonical_causal_decoder"`.
- **FR-017**: `TrainerAdapterRegistery`, `PartitionerAdapterRegistery`, and `AggregatorAdapterRegistery` MUST register the canonical causal decoder adapters.
- **FR-018**: All engine core orchestrators, data models, and abstractions outside of `adapters/` and presentation layers MUST remain completely unchanged.

#### Presentation Changes
- **FR-019**: Client GUI "Submit Training" tab MUST present `Model Engine Type` as the first selectable input, dynamically displaying file selectors (.gz/.tar.gz model, .pt dataset for causal decoder; .pt2 model, .pt dataset for canonical torch) and model-specific training parameter fields.
- **FR-020**: Client Console UI CLI MUST accept `--model-type` as the primary configuration selector and parse the corresponding paths and training config.

#### Verification & Test Sample
- **FR-021**: `samples/canonical_causal_decoder_training_test/` MUST be created containing `setup.py`, `submit.py`, `verify.py`, and `clean.py`.
- **FR-022**: `setup.py` MUST launch Coordinator, Relay, Client, and 2 Trainers natively as background processes with isolated working directories, and directly download TinyStories-1M (`roneneldan/TinyStories-1M`) and dataset (`roneneldan/TinyStories`) from Hugging Face Hub, preparing the `.gz` model archive and `.pt` dataset split into training and validation sets.
- **FR-023**: `submit.py` MUST execute Client training submission, orchestrating smoke testing, partitioning into 2 shards, task dispatch, trainer execution, update transfer, and version 1 aggregation.
- **FR-024**: `verify.py` MUST evaluate validation loss and perplexity on version 0 and version 1 models using the hold-out validation set.
- **FR-025**: `clean.py` MUST terminate all running test processes and purge test directories.

### Key Entities

- **CanonicalCausalDecoderModelArchive**: Gzip-compressed tar archive (`.gz` or `.tar.gz`) containing `model/` (Hugging Face transformer weights and config) and `tokenizer/` (Hugging Face tokenizer files).
- **CanonicalCausalDecoderDataset**: PyTorch dictionary file (`.pt`) containing tensors `input_ids`, `attention_mask`, and `labels` with aligned first dimensions (sample count).
- **CanonicalCausalDecoderDelta**: Safetensors dictionary file (`.safetensors`) mapping parameter names to parameter delta tensors: $\Delta W = W_{\text{trained}} - W_{\text{base}}$.
- **CanonicalCausalDecoderTrainingConfig**: Strongly-typed configuration entity encapsulating hyperparameters passed to Hugging Face `TrainingArguments`.
- **ModelType**: Enumeration designating supported model types: `CANONICAL_TORCH` and `CANONICAL_CAUSAL_DECODER`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 4-phase lifecycle (`validate`, `prepare`, `train`, `save_result`) executes cleanly on Trainer nodes without crashing or altering baseline artifact files.
- **SC-002**: Generated `.safetensors` update artifacts match parameter names, shapes, and dtypes of the base model with zero missing or superfluous parameters.
- **SC-003**: Federated Averaging aggregation calculation produces exact mathematically weighted parameter updates ($\Delta W_{\text{avg}} = \sum \frac{n_i}{N} \Delta W_i$) across all participating trainers.
- **SC-004**: Client GUI dynamically swaps between `canonical_torch` and `canonical_causal_decoder` form layouts within 100ms of user selection.
- **SC-005**: All core engine modules outside of `adapters/` and presentation layers remain 100% compliant with the Open-Closed Principle (0 modifications to model-agnostic engine orchestrators).
- **SC-006**: The end-to-end test in `samples/canonical_causal_decoder_training_test/` executes to completion with exit code 0, demonstrating measurable perplexity improvement between version 0 and version 1 on the TinyStories-1M validation set.

## Assumptions

- **Archive Format**: Model archives are compressed tar archives (`.tar.gz` or `.gz`) loadable via Python's standard `tarfile` module and extractable to directory paths consumed by Hugging Face `from_pretrained`.
- **Hugging Face Libraries**: Environment contains compatible versions of `transformers`, `torch`, and `safetensors`.
- **TinyStories-1M Availability**: The test environment has internet connectivity to download `roneneldan/TinyStories-1M` model and `roneneldan/TinyStories` dataset from Hugging Face Hub during test setup.
- **Local Native Execution**: In adherence to Constitution Principle VII, all test processes in `samples/canonical_causal_decoder_training_test/` run as native CLI processes without requiring Docker containers.
