# Research: Distributed Training Engine

**Feature**: [Distributed Training Engine](spec.md)
**Status**: Completed
**Date**: 2026-08-30

## 1. PyTorch 2 ExportedProgram Contract & Local Checkpoint Lifecycle

### Decision
Use PyTorch 2 `torch.export` standard for the `canonical_torch` model lifecycle:
- Loading: `loaded_program = torch.export.load(checkpoint_path)`
- Module extraction: `model = loaded_program.module()`
- Device assignment: `model.to(device)`
- Execution mode: `model.train()` with standard single-tensor forward `outputs = model(x)`
- Result export: Export the updated model module using `torch.export.export(model, args=(sample_x,))` or save the exported program using `torch.export.save(exported_program, output_path)` to save as `trained_<task_id>.pt2`.

### Rationale
- `torch.export.ExportedProgram` is PyTorch 2's official hermetic, graph-captured representation that guarantees model architecture integrity across distributed worker nodes without arbitrary pickled code execution (guards against RCE and ensures safe deserialization).
- Calling `.module()` extracts an `nn.Module` whose parameters and buffers are standard `torch.nn.Parameter` instances directly optimizable via PyTorch autograd and optimizers.
- The input checkpoint `<checkpoint_version>.pt2` remains strictly immutable and unmodified. The output artifact `trained_<task_id>.pt2` provides a new, non-colliding `.pt2` file for downstream consumption by the aggregator.

### Alternatives Considered
- `torch.save(model.state_dict(), ...)`: Standard state dict format is simple, but lacks graph-level metadata and contract guarantees enforced by PyTorch 2 export.
- `torch.jit.script` / `torch.jit.trace`: TorchScript is legacy in PyTorch 2.x and has known limitations with dynamic Python features compared to `torch.export`.

---

## 2. Polymorphic Configuration Deserialization & Validation

### Decision
Implement strongly typed dataclasses/pydantic models for `TrainingTask`, `CanonicalTorchTrainingConfig`, and individual parameter DTOs:
- `TrainingTask` deserializes the top-level envelope (`task_id`, `session_id`, `type`, `checkpoint_version`, `dataset_shard_id`, `training`).
- `CanonicalTorchAdapter.validate()` is responsible for deserializing `training` into `CanonicalTorchTrainingConfig`.
- Configuration validation verifies all numeric boundaries (`batch_size > 0`, `epochs > 0`, `gradient_accumulation_steps > 0`, `max_steps > 0` if present, `max_grad_norm > 0` if present).
- Parameter DTOs validate optimizer-specific, scheduler-specific, and criterion-specific fields before instantiating PyTorch objects.

### Rationale
- The `TrainingOrchestrator` remains completely type-agnostic and does not inspect the polymorphic `training` dictionary.
- Each adapter owns its type-specific validation rules and deserializes its own strongly typed config.
- Catching misconfigurations during `validate()` guarantees fail-fast behavior before GPU/CPU allocations or file I/O take place.

### Alternatives Considered
- Passing raw unvalidated `dict` to PyTorch constructors: Prone to silent parameter misinterpretation, default argument confusion, and security risks.
- Monolithic schema in `TrainingOrchestrator`: Violates the adapter abstraction principle and couples generic orchestration to specific model types.

---

## 3. Component Registries & Extensibility Architecture

### Decision
Implement dedicated registry classes for:
1. `TrainingAdapterRegistry`: Maps `ModelType` (e.g. `ModelType.CANONICAL_TORCH`) to adapter class (e.g. `CanonicalTorchAdapter`).
2. `OptimizerRegistry`: Maps string names (`AdamW`, `SGD`) to parameter DTOs and instantiates `torch.optim` classes.
3. `SchedulerRegistry`: Maps string names (`ConstantLR`, `LinearLR`, `StepLR`, `ExponentialLR`, `CosineAnnealingLR`) to parameter DTOs and instantiates `torch.optim.lr_scheduler` classes.
4. `CriterionRegistry`: Maps string names (`MSELoss`, `L1Loss`, `SmoothL1Loss`, `CrossEntropyLoss`, `BCEWithLogitsLoss`) to parameter DTOs and instantiates `torch.nn` loss classes.

### Rationale
- Decouples component creation from the training execution loop.
- Adding a new optimizer, scheduler, criterion, or adapter requires adding a registry entry and parameter DTO with zero modifications to existing training loops or orchestrator logic.
- Registries validate incoming parameters against strong schemas before passing keyword arguments to PyTorch constructors.

### Alternatives Considered
- Direct string eval or `getattr(torch.optim, name)`: Highly unsafe, permits arbitrary class instantiation, bypasses parameter validation.

---

## 4. Canonical Autograd Training Loop Semantics

### Decision
The training loop in `CanonicalTorchAdapter.train()` adheres to standard PyTorch autograd semantics:
1. Loss Scaling: `scaled_loss = loss / gradient_accumulation_steps` before `scaled_loss.backward()`.
2. Step Counter: `step_count` counts actual optimizer updates, not DataLoader batch iterations.
3. Gradient Clipping: If `max_grad_norm` is provided (> 0.0), invoke `torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)` immediately before `optimizer.step()`.
4. Scheduler Step Order: `optimizer.step()` &rarr; `scheduler.step()` (if scheduler configured) &rarr; `optimizer.zero_grad()`.
5. Incomplete Gradient Accumulation: At the end of the DataLoader epoch loop or when training halts, any accumulated gradients in an incomplete accumulation window are stepped and cleared.
6. Early Stopping on Steps: If `max_steps` is configured, training loop terminates immediately once `optimizer_steps == max_steps` even if epoch count has not elapsed.

### Rationale
- Correctly implements average gradient computation across multi-batch accumulation groups.
- Complies with PyTorch 2.x learning rate scheduler guidelines (scheduler stepped after optimizer).
- Prevents gradient leaks across epoch boundaries or dropped training data on remainder batches.

---

## 5. Dataset Shard Contract & Memory Pipeline

### Decision
Canonical dataset shards are `.pt` files loaded via `torch.load(path, weights_only=True)`.
- Format: Dictionary containing `{"x": x_tensor, "y": y_tensor}`.
- Contract Checks:
  - Both `x` and `y` are `torch.Tensor`.
  - Both have `dtype == torch.float32`.
  - First dimension `x.shape[0] == y.shape[0]`.
- Memory Pipeline: Wrapped in `torch.utils.data.TensorDataset(x, y)` and served via `torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)`.

### Rationale
- `weights_only=True` prevents unpickling arbitrary Python code, satisfying project security requirements.
- `TensorDataset` and `DataLoader` provide high-performance, batched, shuffled tensor iteration natively in PyTorch.

---

## 6. Device Agnosticism & Reproducibility

### Decision
- Device Selection: Automatic runtime detection:
  ```python
  device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
  ```
- Random Seeding: If `seed` is set in config:
  ```python
  random.seed(seed)
  torch.manual_seed(seed)
  if torch.cuda.is_available():
      torch.cuda.manual_seed_all(seed)
  try:
      import numpy as np
      np.random.seed(seed)
  except ImportError:
      pass
  ```

### Rationale
- Enables seamless operation on CPU-only local development/test environments as well as GPU-accelerated trainer worker nodes.
- Establishes reproducible initial weights and DataLoader shuffle ordering when seeds are specified.
