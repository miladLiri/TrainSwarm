# Research & Architecture Decisions: Distributed Training Engine — Partitioning Module

**Feature**: `009-dataset-partitioning`  
**Date**: 2026-09-03  
**Status**: Completed

---

## 1. Partitioner Adapter Abstraction & Orchestration

### Decision
Implement `PartitionerAdapter` as an abstract base class (`ABC`) in `partitioning/partitioner_adapter.py` whose constructor receives a validated `PartitioningRequest` instance and exposes exactly two abstract methods:
- `CreateSample() -> SamplingResult`
- `CreateShards(shardSampleSize: int) -> PartitioningResult`

`PartitioningOrchestrator` in `partitioning/partitioning_orchecstrator.py` receives `PartitioningRequest` in its constructor, resolves the model-specific adapter class via `PartitionerAdapterRegistry.Get(request.model_type)`, instantiates the adapter with the request, and delegates `GetSample()` and `CreateShards(shardSampleSize)` directly to the adapter.

### Rationale
- Decouples workflow orchestration and pre-flight validation from model- and framework-specific serialization details.
- Matches the pattern established by `TrainingOrchestrator` and `TrainerAdapter`.
- Enforces constructor injection of dataset paths, target output directories, and dataset identifiers as explicitly required by Section 4 & 9 of the specification.

### Alternatives Considered
- **Method-level Parameter Injection**: Passing dataset path, output directory, and dataset ID as arguments to `CreateShards()` and `CreateSample()`. Rejected because the specification mandates receiving `PartitioningRequest` in the adapter constructor.
- **Monolithic Partitioning Engine**: Implementing PyTorch dataset slicing directly in `PartitioningOrchestrator` with `if model_type == CANONICAL_TORCH:`. Rejected because it violates the Open/Closed Principle and breaches FR-007 and FR-019.

---

## 2. PyTorch Dataset Slicing & Serialization Algorithm

### Decision
`CanonicalTorchPartitioner` in `adapters/canonical_torch/partitioning/canonical_torch_partitioner.py` handles PyTorch `.pt` datasets containing tensor dictionaries (e.g., `{"x": torch.Tensor, "y": torch.Tensor}`).
The slicing algorithm:
1. Validates that `datasetPath` exists and is a readable `.pt` file.
2. Loads the dataset via `torch.load(str(dataset_path), weights_only=True)`.
3. Validates that the loaded object is a dictionary containing `x` and `y` tensors with `dtype == torch.float32` and equal sample counts along dimension 0 (`num_samples = x.shape[0] == y.shape[0]`).
4. Verifies `shardSampleSize > 0`.
5. Iterates through sample indices in deterministic order: `[start : end]` where `end = min(start + shardSampleSize, num_samples)`.
6. Creates a shard dictionary containing sliced tensor views: `{"x": x[start:end], "y": y[start:end]}`.
7. Generates a unique UUID `shardId` via `str(uuid.uuid4())`.
8. Serializes the shard to `<datasetId>_<shardId>.pt` in `shardsOutputDirectory` using `torch.save()`.
9. Retains the final partial shard if `num_samples % shardSampleSize != 0`.
10. Returns a `PartitioningResult` containing `PartitionedShard` descriptors for each persisted shard.

### Rationale
- PyTorch tensor slicing (`tensor[start:end]`) produces efficient views without duplicating underlying data buffers in memory prior to serialization.
- Preserves the canonical tensor contract expected by `CanonicalTorchTrainer`.
- Deterministic iteration ensures reproducible shard sample assignments.

### Alternatives Considered
- **PyTorch DataLoader / Chunking**: Using `torch.utils.data.random_split` or `DataLoader`. Rejected because `random_split` introduces non-deterministic sampling unless seeded, and `DataLoader` batches tensors into mini-batches rather than saving complete shard blocks suitable for local trainer iteration.
- **Dropping Trailing Remainder**: Truncating the dataset if `num_samples % shardSampleSize != 0`. Rejected because Section 15 and FR-025 strictly require that final partial shards must be preserved.

---

## 3. Shard Identifier Format & Shard Filenames

### Decision
Generate `shardId` as a random full UUID v4 string (`str(uuid.uuid4())`).
Each shard file is named strictly according to:
```text
<datasetId>_<shardId>.pt
```
Example:
```text
dataset-001_3b9b46e2-5701-499b-bf20-c751a7d65b11.pt
```

### Rationale
- Confirmed during Clarification Session 2026-09-03 (Question 1).
- Guarantees global uniqueness across independent worker nodes, partitioner runs, and decentralized storage namespaces without requiring coordinated sequential counters.

### Alternatives Considered
- **Sequential Integers (`0, 1, 2`)**: Rejected during clarification in favor of UUID strings to prevent namespace collisions across cluster nodes.
- **Short 8-character Hex Tokens**: Rejected during clarification in favor of standard full UUID strings.

---

## 4. Output Directory Precondition & Collision Prevention

### Decision
`CanonicalTorchPartitioner.CreateShards()` enforces a strict empty-directory precondition on `shardsOutputDirectory`:
1. If `shardsOutputDirectory` does not exist, create it (including parent directories).
2. If `shardsOutputDirectory` exists, inspect its contents. If it contains any files or subdirectories (`any(shardsOutputDirectory.iterdir())`), immediately raise `ExistingShardConflictError`.

### Rationale
- Confirmed during Clarification Session 2026-09-03 (Question 3).
- Prevents accidental mingling of shards from previous or parallel runs, eliminating stale shard confusion during trainer dispatch.

### Alternatives Considered
- **Dataset-Specific Collision Check (`<datasetId>_*.pt`)**: Rejected during clarification in favor of the strict empty-directory rule.
- **Silent Overwrite**: Strictly prohibited by Section 17 and FR-026.

---

## 5. Sample Extraction & Idempotent Overwrite

### Decision
`CanonicalTorchPartitioner.CreateSample()` extracts sample index 0 (`x[0:1]`, `y[0:1]`), retaining batch dimension 1 (`shape = [1, ...]`):
1. Verifies `num_samples >= 1`.
2. Creates `sampleOutputDirectory` if it does not exist.
3. Target path: `sampleOutputDirectory / f"{dataset_id}_sample.pt"`.
4. Atomically overwrites the target path if it already exists (writing to a temporary file in the same directory and renaming, or direct overwrite).
5. Returns `SamplingResult(dataset_id, str(sample_path), sample_count=1)`.

### Rationale
- Confirmed during Clarification Session 2026-09-03 (Question 2).
- Representative sample extraction is intended for pre-flight validation and dry-runs; making sample generation idempotent allows coordinators to re-validate datasets without failing due to previous inspection runs.
- Keeping batch dimension 1 (`[1, ...]`) ensures the sample matches the tensor rank expected by `SimpleMLP` and exported PyTorch 2 programs.

### Alternatives Considered
- **Strict Collision Failure for Samples**: Rejected during clarification because dry-run validation should not require manual filesystem cleanup between coordinator checks.
- **Dropping Batch Dimension (`x[0]`)**: Resulting in shape `[4]` instead of `[1, 4]`. Rejected because canonical PyTorch models expect input shape `[batch, in_features]`.

---

## 6. Package Reorganization & Backward Compatibility Strategy

### Decision
Reorganize `src/distributed_training_engine/` strictly according to the required folder structure:
1. **Package Root**:
   - `model_type.py`: Move from `training/model_type.py` to package root `src/distributed_training_engine/model_type.py`.
2. **`training/`**:
   - Rename `training_adapter.py` -> `trainer_adapter.py`.
   - Rename `training_adapter_registry.py` -> `trainer_adapter_registery.py`.
   - Rename `training_orchestrator.py` -> `training_orchecstrator.py`.
   - Maintain `training_task_model.py`, `training_result.py`, `exceptions.py`.
3. **`aggregation/`**:
   - Create placeholder files: `exceptions.py`, `aggregator_adapter_registery.py`, `aggregator_adapter.py`, `aggregation_request.py`, `aggregation_result.py`, `aggregation_orchecstrator.py`.
4. **`partitioning/`**:
   - Create: `exceptions.py`, `partitioner_adapter_registery.py`, `partitioner_adapter.py`, `partitioning_request.py`, `sampling_result.py`, `partitioning_result.py`, `partitioning_orchecstrator.py`.
5. **`adapters/canonical_torch/`**:
   - Move `training_adapters/canonical_torch/` files into `adapters/canonical_torch/training/`.
   - Rename `canonical_torch_adapter.py` -> `canonical_torch_trainer.py`.
   - Create `adapters/canonical_torch/aggragation/canonical_torch_aggregator.py` (placeholder).
   - Create `adapters/canonical_torch/partitioning/canonical_torch_partitioner.py`.
6. **Backward Compatibility**:
   - In `distributed_training_engine/__init__.py` and `training/__init__.py`, re-export both old and new symbol names (`TrainingOrchestrator` / `TrainingOrchecstrator`, `TrainingAdapter` / `TrainerAdapter`, `TrainingAdapterRegistry` / `TrainerAdapterRegistery`).
   - Keep import statements in `samples/training_test/train.py` functioning seamlessly.

### Rationale
- Complies 100% with the folder layout specified in Section 2 while guaranteeing that existing training tests and verification tooling (`samples/training_test/train.py`, `verify.py`) continue to pass with 0 regressions.

### Alternatives Considered
- **Breaking Existing Imports**: Updating only the new names without aliases. Rejected because it risks breaking external sample scripts and violating FR-002 ("preserve existing training functionality").
