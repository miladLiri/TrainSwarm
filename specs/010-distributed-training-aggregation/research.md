# Research & Architecture Decisions: Distributed Training Engine — Aggregation Module

**Feature**: `010-distributed-training-aggregation`
**Status**: Completed

---

## 1. PyTorch 2 Exported Program (`.pt2`) Loading and Parameter Mutation

### Decision
Load the base model artifact using `torch.export.load(str(base_model_path))`, access the underlying `torch.nn.Module` via `exported_program.module()`, reconstruct the updated state dictionary $\theta_{\text{new}} = \theta_{\text{base}} + \Delta_{\text{aggregated}}$, update the module state using `module.load_state_dict(new_state_dict, strict=True)`, and serialize the updated program via `torch.export.save(exported_program, str(target_path))`.

### Rationale
- PyTorch 2 `ExportedProgram` captures an immutable graph representation along with parameter/buffer tensors.
- Mutating the module weights via `load_state_dict` directly updates the underlying tensor buffers inside `exported_program.state_dict`.
- Re-exporting (`torch.export.export`) is not suitable during aggregation because aggregation does not and should not possess sample inputs or original model definition source code.
- Serializing the existing `ExportedProgram` after updating weights preserves the exact computation graph, node metadata, input/output schemas, and dynamic shape contracts.

### Alternatives Considered
- **Re-export from Python model definition**: Rejected. The aggregator operates on compiled model artifacts (`.pt2`), not on arbitrary user Python model classes.
- **Saving raw state_dict via `torch.save`**: Rejected. TrainSwarm's training subsystem specifically requires `.pt2` exported program artifacts.

---

## 2. SafeTensors Delta Loading and Schema Compatibility Validation

### Decision
Load delta artifacts exclusively using `safetensors.torch.load_file(str(delta_path), device="cpu")`. Validate that:
1. Every file exists, is readable, and can be deserialized into a dictionary of PyTorch tensors.
2. The delta dictionary keys match `base_model.state_dict().keys()` exactly (no missing keys, no unexpected extra keys).
3. The shape of every tensor in the delta matches the shape of the corresponding base model tensor.
4. The dtype of every tensor in the delta matches the base model tensor dtype.
5. In accordance with user clarification, model compatibility is enforced strictly through parameter key/shape/dtype verification against the base model state dict, without parsing delta filenames or header metadata.

### Rationale
- SafeTensors is memory-efficient, fast, and eliminates arbitrary code execution risks (CVE-safe, no Python pickle deserialization).
- Strict key and shape matching ensures that deltas generated from incompatible model architectures or different baseline snapshots fail fast during the validation phase before any mathematical operations occur.

### Alternatives Considered
- **Standard `torch.load`**: Rejected. `CanonicalTorchTrainer` saves updates in `.safetensors` format, not `.pt`.
- **Sparse / Partial parameter deltas**: Rejected. Federated Averaging requires consistent parameter coverage across all participating workers in a synchronous round.

---

## 3. Weighted Federated Averaging Numerical Stability & Dtype Handling

### Decision
For a set of $N$ updates where update $i$ has parameter delta $\Delta_i$ and sample count $w_i = \text{samplesTrained}_i > 0$:
1. Compute the total weight:
   $$W = \sum_{i=1}^N w_i$$
2. For each parameter/buffer key $k$:
   - For floating-point tensors (`float32`, `float64`, `float16`, `bfloat16`): accumulate in `float64` precision:
     $$\Delta_{\text{agg}}[k] = \frac{\sum_{i=1}^N w_i \times \Delta_i[k]}{W}$$
     Cast the resulting tensor back to the parameter's native floating-point dtype.
   - For non-floating point buffers (e.g., integer tracking counters like `torch.int64` batch counters): compute the weighted float sum divided by $W$, round to the nearest integer using `torch.round()`, and cast back to the native integer dtype.

### Rationale
- Accumulating weighted deltas in `float64` avoids numerical cancellation and precision drift when aggregating over many updates or large sample counts.
- Handling integer buffers with rounding and dtype recasting satisfies the user clarification and prevents PyTorch `load_state_dict` type mismatch exceptions.

### Alternatives Considered
- **Unweighted (simple) averaging**: Rejected by specification; updates must be weighted proportionally to sample volume.
- **Sequential application of deltas**: Rejected by specification; all deltas originate from the same base model and must be aggregated concurrently before adding to base weights.

---

## 4. Atomic Version Creation and Immutability Protection

### Decision
1. **Pre-flight conflict check**: During the validation phase, verify that `<modelId>_<newVersion>.pt2` does NOT already exist in `newVersionOutputDirectory`. If it exists, immediately abort with `ExistingModelVersionConflictError`.
2. **Directory preparation**: Ensure `newVersionOutputDirectory` exists, creating parent directories if necessary.
3. **Atomic serialization**: Write the updated `ExportedProgram` to a uniquely named temporary file located in the same output directory:
   $$\text{temp\_path} = \text{newVersionOutputDirectory} / f"{modelId}\_{newVersion}.pt2.tmp.{uuid4().hex}"$$
4. **Verification & atomic rename**: Verify that `temp_path` exists and has non-zero size, then call `os.replace(str(temp_path), str(final_path))`.
5. **Rollback & cleanup**: In case of serialization errors, unlink `temp_path` if it exists, ensuring no incomplete or corrupted artifact remains.
6. **Base model protection**: Never write to or mutate `baseModelPath`.

### Rationale
- `os.replace` provides atomic replacement semantics on both Windows and POSIX when the source and destination are on the same filesystem volume. Placing the temporary file in `newVersionOutputDirectory` guarantees that both files share the same filesystem mount point.
- Pre-flight validation protects against accidental overwrites and preserves model checkpoint immutability.

### Alternatives Considered
- **System `/tmp` directory**: Rejected. Cross-device filesystem moves cannot be performed atomically.
- **Direct overwrite**: Rejected. Process interruption would leave a half-written, unreadable model artifact.

---

## 5. End-to-End Sample Suite Architecture (`samples/distributed_training_test/`)

### Decision
Implement a complete, standalone, zero-mock sample pipeline:
- `setup.py`: Generates a lightweight 1D CNN model (`Conv1d` -> `ReLU` -> `AdaptiveAvgPool1d` -> `Linear`) exported to `.pt2`, and a 50-sample synthetic dataset `{"x": ..., "y": ...}` with float32 tensors saved as `dataset.pt`.
- `partition.py`: Instantiates `PartitioningRequest` and `PartitioningOrchestrator` to partition the 50-sample dataset into 5 shards of 10 samples each in deterministic order.
- `train.py`: Spawns 5 parallel training jobs using `concurrent.futures.ProcessPoolExecutor`, running `TrainingOrchestrator` to produce 5 `.safetensors` delta files.
- `aggregate.py`: Builds an `AggregationRequest` referencing the 5 delta files and invokes `AggregationOrchestrator`, publishing `model_1.pt2`.
- `verify.py`: Evaluates baseline model (`model_0.pt2`) and aggregated model (`model_1.pt2`) on the full dataset, verifying measurable loss reduction and mathematical improvement.
- `README.md`: Explains scenario, dependencies, and execution commands.

### Rationale
- Uses `ProcessPoolExecutor` to ensure complete process and memory isolation across PyTorch training tasks on both Windows and POSIX.
- Validates the entire TrainSwarm data plane workflow (partitioning -> parallel training -> federated aggregation -> verification) with real functional code and zero mocks.

### Alternatives Considered
- **ThreadPoolExecutor**: Rejected. Python GIL and shared PyTorch autograd engine can cause contention during concurrent backward passes.
- **Mock trainer deltas**: Strictly prohibited by Constitution Principle V and VI.
