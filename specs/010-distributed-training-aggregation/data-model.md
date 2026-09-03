# Data Model: Distributed Training Engine — Aggregation Subsystem

**Feature**: `010-distributed-training-aggregation`  
**Date**: 2026-09-03  
**Status**: Complete

---

## 1. Core Entities & Value Objects

### 1.1 `ModelType` (Enum)
Defined in `src/distributed_training_engine/model_type.py`.

```python
class ModelType(str, Enum):
    CANONICAL_TORCH = "canonical_torch"
```

---

### 1.2 `ModelUpdate` (Value Object)
Defined in `src/distributed_training_engine/aggregation/aggregation_request.py`.  
Represents a single training update produced by a worker node.

| Field | Type | Required | Description | Validation Rules |
| :--- | :--- | :---: | :--- | :--- |
| `samplesTrained` | `int` | Yes | Count of training samples used for the update | Must be an integer `> 0` |
| `deltaPath` | `Union[str, Path]` | Yes | Filesystem path to the serialized delta artifact | Must be non-empty; normalized to `Path` |

**Validation Constraints**:
- `samplesTrained` must be strictly positive (`> 0`). A value of `0` or negative raises `InvalidUpdateError`.
- `deltaPath` must be a valid non-empty string or `Path`.

**Wire Representation (Dictionary / JSON)**:
```json
{
  "samplesTrained": 10,
  "deltaPath": "deltas/1/task-001.delta.safetensors"
}
```

---

### 1.3 `AggregationRequest` (DTO)
Defined in `src/distributed_training_engine/aggregation/aggregation_request.py`.  
Encapsulates all metadata and artifact references required to execute one federated learning aggregation round.

| Field | Type | Required | Description | Validation Rules |
| :--- | :--- | :---: | :--- | :--- |
| `modelId` | `str` | Yes | Unique identifier of the model | Non-empty string |
| `baseModelVersion` | `int` | Yes | Version number of the immutable base model | Integer `>= 0` |
| `baseModelPath` | `Union[str, Path]` | Yes | Filesystem path to base model artifact (`.pt2`) | Non-empty; normalized to `Path` |
| `newVersion` | `int` | Yes | Version number to assign to the new model artifact | Integer `> baseModelVersion` |
| `newVersionOutputDirectory` | `Union[str, Path]` | Yes | Directory where the new version will be published | Non-empty; normalized to `Path` |
| `updates` | `List[ModelUpdate]` | Yes | Collection of trainer updates to aggregate | Non-empty list (`len(updates) > 0`) |

**Validation Constraints**:
- `modelId` must be a non-empty string.
- `baseModelVersion >= 0` and `newVersion > baseModelVersion`.
- `updates` must contain at least 1 `ModelUpdate`. An empty list raises `InvalidAggregationRequestError`.
- Paths are validated and normalized to `pathlib.Path`.

**Wire Representation (Dictionary / JSON)**:
```json
{
  "modelId": "gpt2",
  "baseModelVersion": 0,
  "baseModelPath": "models/gpt2/gpt2_0.pt2",
  "newVersion": 1,
  "newVersionOutputDirectory": "models/gpt2",
  "updates": [
    {
      "samplesTrained": 10,
      "deltaPath": "models/gpt2/deltas/0/task-001.safetensors"
    },
    {
      "samplesTrained": 40,
      "deltaPath": "models/gpt2/deltas/0/task-002.safetensors"
    }
  ]
}
```

---

### 1.4 `AggregationResult` (DTO)
Defined in `src/distributed_training_engine/aggregation/aggregation_result.py`.  
Returned upon successful completion of an aggregation round.

| Field | Type | Required | Description | Validation Rules |
| :--- | :--- | :---: | :--- | :--- |
| `modelId` | `str` | Yes | Model identifier | Matches request `modelId` |
| `baseModelVersion` | `int` | Yes | Version of the base model aggregated from | Matches request `baseModelVersion` |
| `newModelVersion` | `int` | Yes | Published version of the new model artifact | Matches request `newVersion` |
| `updatesCount` | `int` | Yes | Total number of updates included in the aggregation | Matches `len(request.updates)` |
| `modelPath` | `str` | Yes | Canonical path to the published model file | Must end with `<modelId>_<newVersion>.pt2` |

**Wire Representation (Dictionary / JSON)**:
```json
{
  "modelId": "gpt2",
  "baseModelVersion": 0,
  "newModelVersion": 1,
  "updatesCount": 2,
  "modelPath": "models/gpt2/gpt2_1.pt2"
}
```

---

## 2. Aggregator Lifecycle & State Transitions

The `AggregatorAdapter` lifecycle is coordinated strictly by `AggregationOrchestrator`.

```text
[ INITIALIZED ]
       │
       │ LoadDelta()
       ▼
[ DELTAS_LOADED ]
       │
       │ ValidateDelta()
       ▼
[ DELTAS_VALIDATED ]
       │
       │ Aggregate()
       ▼
[ DELTAS_AGGREGATED ]
       │
       │ CreateNewVersion()
       ▼
[ VERSION_PUBLISHED ]
```

### State Definitions

| State | Allowed Transitions | Invariant / Pre-condition |
| :--- | :--- | :--- |
| `INITIALIZED` | `DELTAS_LOADED`, `FAILED` | Adapter constructed with immutable `AggregationRequest`. |
| `DELTAS_LOADED` | `DELTAS_VALIDATED`, `FAILED` | All delta files specified in `request.updates` loaded into memory. Missing/unreadable delta fails immediately. |
| `DELTAS_VALIDATED` | `DELTAS_AGGREGATED`, `FAILED` | All deltas checked against base model keys, shapes, and dtypes. Target version checked for collision. Target output directory exists. |
| `DELTAS_AGGREGATED` | `VERSION_PUBLISHED`, `FAILED` | Weighted FedAvg computed across all deltas into one combined parameter delta dictionary. Base model file remains untouched. |
| `VERSION_PUBLISHED` | *(Terminal)* | Combined delta applied to base model module; serialized to temporary file; atomically renamed to final target path; `AggregationResult` returned. |
| `FAILED` | *(Terminal)* | Validation, computation, or serialization failure. No model published. Temporary files cleaned up. |

---

## 3. Storage & Artifact Conventions

```text
<workingDirectory>/
└── models/
    └── <modelId>/
        ├── <modelId>_<baseVersion>.pt2          # Immutable base model (PyTorch ExportedProgram)
        ├── <modelId>_<newVersion>.pt2           # Newly published model (atomically created)
        │
        └── deltas/
            └── <baseVersion>/
                ├── <task_1>.safetensors         # Parameter delta artifact (trained - base)
                ├── <task_2>.safetensors
                └── ...
```

### File Formats
1. **Model Checkpoints (`.pt2`)**: Serialized PyTorch 2 `ExportedProgram` loaded via `torch.export.load` and saved via `torch.export.save`.
2. **Parameter Deltas (`.safetensors`)**: Parameter difference dictionary $\Delta = \theta_{\text{trained}} - \theta_{\text{base}}$ saved and loaded via `safetensors.torch`.
