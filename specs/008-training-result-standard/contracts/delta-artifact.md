# Contract: Delta Artifact Specification

**Format**: SafeTensors (`.safetensors`)  
**Feature**: `008-training-result-standard`  
**Date**: 2026-09-02  

---

## 1. Filename Convention

Delta artifact files MUST adhere strictly to the format:
```text
<baseline_model_id>_<baseline_model_version>_<data_set_id>_<data_set_shard_id>.safetensors
```

### Example
- Baseline Model ID: `base_model`
- Baseline Model Version: `v1`
- Dataset ID: `dataset1`
- Dataset Shard ID: `shard1`
- **Output Filename**: `base_model_v1_dataset1_shard1.safetensors`

---

## 2. Binary Layout & Header Structure

Safetensors is a zero-copy tensor storage format containing:
1. **8-byte header length**: Unsigned 64-bit little-endian integer ($N$).
2. **UTF-8 JSON header ($N$ bytes)**: Metadata dictionary mapping tensor names to shapes, dtypes, and byte offsets.
3. **Contiguous tensor buffers**: Raw tensor byte arrays (in `torch.float32`).

---

## 3. Tensor Schema & Subtraction Semantics

For every parameter key $k$ in the base model `state_dict`:
- **Tensor Key**: String matching the PyTorch parameter name exactly (e.g. `"fc1.weight"`, `"fc1.bias"`, `"fc2.weight"`, `"fc2.bias"`).
- **Data Type**: `F32` (`torch.float32`).
- **Shape**: Identical dimensions to the baseline parameter tensor (e.g. `[8, 4]`, `[8]`, `[1, 8]`, `[1]`).
- **Difference Value**:
  $$\text{delta\_tensor}[k] = \text{trained\_tensor}[k] - \text{base\_tensor}[k]$$

---

## 4. Reconstructibility Contract

A consumer or aggregator node given baseline model $B$ and delta file $\Delta$ can reconstruct the trained model $T$ via:
```python
from safetensors.torch import load_file
import torch

delta = load_file(delta_path)
state_dict = model.state_dict()
for name, delta_tensor in delta.items():
    state_dict[name] = state_dict[name] + delta_tensor
model.load_state_dict(state_dict)
```
