# CLI & GUI Presentation Contract: Canonical Causal Decoder Model

**Feature Branch**: `021-canonical-causal-decoder`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. CLI Command Contract

### Command: `python main.py submit-training`

The Client CLI exposes `submit-training` with `--model-type` as the primary configuration selector:

```bash
python main.py submit-training \
    --model-type canonical_causal_decoder \
    --model-path /path/to/tinystories_base.gz \
    --dataset-path /path/to/tinystories_train.pt \
    --model-version v1.0 \
    --training-config /path/to/causal_decoder_config.json
```

### Options Specification

| Argument | Type | Required | Default | Allowed Values / Description |
| :--- | :--- | :---: | :--- | :--- |
| `--model-type` | `str` | No | `"canonical_torch"` | `["canonical_torch", "canonical_causal_decoder"]`. Selects the engine adapter suite. |
| `--model-path` | `str` | Yes | - | Path to base model artifact. For `canonical_torch`: `.pt2`. For `canonical_causal_decoder`: `.gz` or `.tar.gz`. |
| `--dataset-path` | `str` | Yes | - | Path to tokenized PyTorch dataset (`.pt`). |
| `--model-version` | `str` | Yes | - | Initial model version string (e.g. `v1.0`). |
| `--training-config` | `str` | Yes | - | Path to training hyperparameter JSON configuration file matching the schema for the selected `--model-type`. |

---

## 2. GUI Dynamic Presentation Contract

### Tab: `Submit Training`

The graphical user interface dynamically adapts form inputs based on the selected `model_type_combo`:

1. **Top Control**:
   - `model_type_combo`: First interactive widget in the form.
   - Items: `["canonical_torch", "canonical_causal_decoder"]`.
   - Event: `currentTextChanged` signals dynamic sub-panel visibility update.

2. **Artifact Pickers**:
   - When `canonical_causal_decoder`:
     - Model Checkpoint Label: `Model Archive (.gz / .tar.gz):`
     - Model File Browse Filter: `Compressed Model Archive (*.gz *.tar.gz)`
     - Dataset File Label: `Tokenized Dataset (.pt):`
     - Dataset File Browse Filter: `PyTorch Dataset (*.pt)`
   - When `canonical_torch`:
     - Model Checkpoint Label: `Model Checkpoint (.pt2):`
     - Model File Browse Filter: `PyTorch 2 Exported Program (*.pt2)`
     - Dataset File Label: `Dataset File (.pt):`
     - Dataset File Browse Filter: `PyTorch Dataset (*.pt)`

3. **Training Hyperparameter Panels**:
   - When `canonical_causal_decoder`:
     - Display Hugging Face Trainer Parameter inputs:
       - Learning Rate (double spin box / line edit)
       - Batch Size (spin box)
       - Epochs (spin box)
       - Max Steps (spin box, optional)
       - Weight Decay (double spin box)
       - Gradient Accumulation Steps (spin box)
       - Max Grad Norm (double spin box, optional)
       - Scheduler Type (combo box: `linear`, `cosine`, `constant`, etc.)
       - Warmup Steps (spin box)
       - Warmup Ratio (double spin box)
       - FP16 (checkbox)
       - BF16 (checkbox)
       - Shuffle (checkbox)
       - Seed (spin box)
   - When `canonical_torch`:
     - Display canonical torch parameter inputs:
       - Optimizer combo box & dynamic optimizer parameters (Adam, SGD, AdamW)
       - Criterion combo box & parameters (CrossEntropyLoss, MSELoss, etc.)
       - Scheduler combo box & parameters (StepLR, CosineAnnealingLR, etc.)
