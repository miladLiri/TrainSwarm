# Adapter Interface Contracts: Canonical Causal Decoder Model

**Feature Branch**: `021-canonical-causal-decoder`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Trainer Adapter Contract

### Class Signature
```python
class CanonicalCausalDecoderTrainer(TrainerAdapter):
    def __init__(self, task: TrainingTask, working_directory: Path) -> None: ...
    def validate(self) -> None: ...
    def prepare(self) -> None: ...
    def train(self) -> None: ...
    def save_result(self) -> TrainingResult: ...
```

### Phase Specifications

#### `validate(self) -> None`
- **Preconditions**: `self.task` is populated; `self.working_directory` exists.
- **Actions**:
  1. Calls `self.task.validate_envelope()`.
  2. Parses `self.task.training` using `CanonicalCausalDecoderTrainingConfig.from_dict()`.
  3. Verifies that the model archive exists at `self.working_directory / self.task.model.artifact_path` (or absolute path) and has extension `.gz` or `.tar.gz`.
  4. Inspects the tar archive to verify it contains `model/` and `tokenizer/` directories without extracting.
  5. Verifies the dataset shard `.pt` file exists.
- **Errors Raised**:
  - `MissingArtifactError`: If model archive or dataset shard file does not exist.
  - `InvalidTaskConfigurationError`: If config validation fails or archive layout is corrupt.

#### `prepare(self) -> None`
- **Preconditions**: `validate()` has succeeded.
- **Actions**:
  1. Resolves device: `cuda` if available, else `cpu`.
  2. Extracts the model archive into `self.working_directory / "model_unpacked"`.
  3. Loads model via `AutoModelForCausalLM.from_pretrained(unpacked_model_path)`.
  4. Loads tokenizer via `AutoTokenizer.from_pretrained(unpacked_tokenizer_path)`.
  5. Loads dataset shard `.pt` file; validates `input_ids`, `attention_mask`, and `labels` tensors.
  6. Snapshots baseline parameters: `{name: p.detach().clone().cpu() for name, p in model.named_parameters() if p.requires_grad}`.
  7. Instantiates Hugging Face `TrainingArguments` and `Trainer`.
- **Postconditions**: Model and Trainer initialized; zero gradient updates performed.

#### `train(self) -> None`
- **Preconditions**: `prepare()` has succeeded.
- **Actions**:
  1. Invokes `self.hf_trainer.train()`.
  2. Tracks loss, epoch progression, step count, and execution duration.
- **Postconditions**: Model weights updated in-memory; metrics tracked.

#### `save_result(self) -> TrainingResult`
- **Preconditions**: `train()` has succeeded.
- **Actions**:
  1. For each parameter in `self.baseline_parameters`:
     $$\Delta W[p] = (W_{\text{trained}}[p].detach().cpu() - W_{\text{base}}[p]).contiguous()$$
  2. Validates delta tensor shape and dtype against baseline.
  3. Serializes deltas to `{base_model_id}_{version}_{dataset_id}_{shard_id}.safetensors` via `safetensors.torch.save_file`.
  4. Preserves original model archive and dataset shard files unmodified.
  5. Returns populated `TrainingResult` DTO.

---

## 2. Partitioner Adapter Contract

### Class Signature
```python
class CanonicalCausalDecoderPartitioner(PartitionerAdapter):
    def __init__(self, request: PartitioningRequest) -> None: ...
    def CreateSample(self) -> SamplingResult: ...
    def CreateShards(self, shardSampleSize: int) -> PartitioningResult: ...
```

### Methods

#### `CreateSample(self) -> SamplingResult`
- Slices $K = \min(2, N)$ samples from the source dataset.
- Saves tensor dict to `self.request.sampleOutputDirecotry / f"{dataset_id}_sample.pt"`.
- Returns `SamplingResult(datasetId=..., samplePath=..., sampleCount=K, metadata=...)`.

#### `CreateShards(self, shardSampleSize: int) -> PartitioningResult`
- Slices tokenized dataset into chunks of at most `shardSampleSize` samples along dimension 0.
- Saves each shard to `self.request.shardsOutputDirectory / f"{dataset_id}_{shard_id}.pt"`.
- Returns `PartitioningResult(datasetId=..., totalSamples=N, shardCount=M, shards=[...])`.

---

## 3. Aggregator Adapter Contract

### Class Signature
```python
class CanonicalCausalDecoderAggregator(AggregatorAdapter):
    def __init__(self, request: AggregationRequest) -> None: ...
    def LoadDelta(self) -> None: ...
    def ValidateDelta(self) -> None: ...
    def Aggregate(self) -> None: ...
    def CreateNewVersion(self) -> AggregationResult: ...
```

### Methods

#### `LoadDelta(self) -> None`
- Deserializes each `.safetensors` file referenced in `self.request.updates` via `safetensors.torch.load_file(..., device="cpu")`.

#### `ValidateDelta(self) -> None`
- Verifies target output version archive does not already exist.
- Unpacks base model archive, verifies base parameters match update tensor keys, shapes, and dtypes.
- Verifies every update has `samplesTrained > 0` and matching base model ID and version.

#### `Aggregate(self) -> None`
- Calculates sample-weighted FedAvg across all updates:
  $$\Delta W_{\text{avg}}[k] = \sum_{i=1}^{M} \frac{n_i}{N} \Delta W_i[k]$$

#### `CreateNewVersion(self) -> AggregationResult`
- Applies $\Delta W_{\text{avg}}$ to base model weights: $W_{\text{new}} = W_{\text{base}} + \Delta W_{\text{avg}}$.
- Saves updated model weights to temporary directory via `save_pretrained()`.
- Copies tokenizer directory unchanged from base model.
- Packages into a temporary `.tar.gz` archive, then atomically renames to `{model_id}_{new_version}.gz`.
- Returns `AggregationResult`.
