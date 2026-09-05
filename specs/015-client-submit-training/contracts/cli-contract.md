# Presentation Contract: Client Console CLI Interface

**Feature Branch**: `015-client-submit-training`  
**Date**: 2026-09-05  
**Spec Reference**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/015-client-submit-training/spec.md)

---

## 1. CLI Invocation Syntax

The Client application entry point [`main.py`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/main.py) exposes the `submit-training` subcommand:

```bash
python main.py submit-training \
  --model-path <path_to_model.pt2> \
  --dataset-path <path_to_dataset.pt> \
  --model-version <version_string> \
  --model-type <model_type> \
  --training-config <path_to_config.json>
```

### Argument Specifications

| Argument | Flag | Type | Required | Default | Description |
| :--- | :--- | :--- | :---: | :---: | :--- |
| Model Path | `--model-path` | `Path` | Yes | - | Path to the PyTorch 2 exported base model checkpoint (`.pt2`). |
| Dataset Path | `--dataset-path` | `Path` | Yes | - | Path to the raw canonical PyTorch dataset file (`.pt`). |
| Model Version | `--model-version` | `str` | Yes | - | Version tag string of the model (e.g. `v1.0`, `2.1.0`). |
| Model Type | `--model-type` | `str` | No | `canonical_torch` | Engine adapter model type (from `ModelType`). |
| Training Config | `--training-config`| `Path` | Yes | - | Path to a valid JSON file containing training hyperparameters. |

---

## 2. Standard Streams & Exit Codes

### Exit Codes

- `0`: Submission succeeded. Shards persisted in SQLite as `READY` and acknowledged by Coordinator.
- `1`: Submission failed (input validation error, smoke test failure, partitioning error, database error, or Coordinator communication failure).
- `2`: CLI argument parsing error (missing required flags or malformed argument syntax).

### Output Formatting

#### Success Output (stdout)
```text
[Client] [SubmitTraining] Staging base model to /artifacts/1a2b3c4d-5e6f/1a2b3c4d-5e6f_v1.0.pt2...
[Client] [SubmitTraining] Extracting representative dataset sample...
[Client] [SubmitTraining] Running smoke test benchmark...
[Client] [SubmitTraining] Smoke test succeeded: 24.50 samples/s, recommended shard size: 7350 samples
[Client] [SubmitTraining] Partitioning dataset into shards...
[Client] [SubmitTraining] Created 4 shards in /artifacts/shards/8f7e6d5c-4b3a/
[Client] [SubmitTraining] Persisting 4 shards to local SQLite database with status CREATED...
[Client] [SubmitTraining] Registering training tasks with Coordinator at http://coordinator:8080...
[Client] [SubmitTraining] Coordinator acknowledged task creation (4 tasks assigned)
[Client] [SubmitTraining] Updating local shard records in SQLite to status READY...
[Client] [SubmitTraining] SUCCESS: Training submission completed successfully!
  Model ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
  Dataset ID: 8f7e6d5c-4b3a-2f1e-0d9c-8b7a6f5e4d3c
  Shard Count: 4
  Task IDs:
    - 00000000-0000-0000-0000-000000000001
    - 00000000-0000-0000-0000-000000000002
    - 00000000-0000-0000-0000-000000000003
    - 00000000-0000-0000-0000-000000000004
```

#### Failure Output (stderr)
```text
[Client] [SubmitTraining] [ERROR] Smoke test benchmark failed: Checkpoint tensor dimensions mismatch.
[Client] [SubmitTraining] [ABORT] Cleaned up temporary sample artifact. No shards were partitioned.
```
