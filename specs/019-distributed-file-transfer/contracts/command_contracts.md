# Application Command Contracts

**Feature**: `019-distributed-file-transfer` | **Phase**: 1 | **Date**: 2026-09-08

## 1. `SetNodeIdCommand` (Client & Trainer)

- **Client Location**: `src/Client/application/commands/set_node_id/`
- **Trainer Location**: `src/Trainer/application/trainer_commands/set_node_id/`

### Command Schema
```python
@dataclass
class SetNodeIdCommand:
    """Takes no arguments; instructs the application to query local p2p-node and record its peer ID."""
    pass
```

### Handler Contract
- Calls `p2p_node_adapter.get_p2p_node_id()`.
- Updates application state (`state.client_node_id = peer_id` / `state.p2p_node_id = peer_id`).
- Returns `str` peer ID on success.
- Raises `P2PNodeUnavailableError` if connection fails.

---

## 2. `GetTrainingTaskCommand` (Client)

- **Location**: `src/Client/application/commands/get_training_task/`

### Command Schema
```python
@dataclass
class GetTrainingTaskCommand:
    trainer_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str
```

### Handler Contract
- Queries `ModelRepository.get_by_model_id(command.model_id)`.
- Loads training config JSON from `model.training_config_path`.
- Queries `TrainingShardRepository.get_by_shard_key(model_id, model_version, data_set_id, shard_id)`.
- Updates `TrainingShard` in SQLite: sets `trainer_node_id = command.trainer_node_id` and `status = TrainingShardStatus.TRAINING` (unconditionally, per Clarification Q1).
- Constructs and returns `TrainingTask` instance with gathered configuration and shard coordinates.

---

## 3. `TransferModelCommand` (Client)

- **Location**: `src/Client/application/commands/transfer_model/`

### Command Schema
```python
@dataclass
class TransferModelCommand:
    trainer_node_id: str
    model_id: str
    model_version: str
```

### Handler Contract
- Queries `ModelRepository.get_by_model_id(command.model_id)`.
- Validates that `model.model_version == command.model_version`.
- Returns `model.model_artifact_path` (str) pointing to local base model file (`.pt2`).

---

## 4. `TransferShardCommand` (Client)

- **Location**: `src/Client/application/commands/transfer_shard/`

### Command Schema
```python
@dataclass
class TransferShardCommand:
    trainer_node_id: str
    model_id: str
    model_version: str
    data_set_id: str
    shard_id: str
```

### Handler Contract
- Queries `TrainingShardRepository.get_by_shard_key(model_id, model_version, data_set_id, shard_id)`.
- Returns `shard.artifact_path` (str) pointing to local dataset partition file (`.pt`).

---

## 5. `UpdateModelCommand` (Client)

- **Location**: `src/Client/application/commands/update_model/`

### Command Schema
```python
@dataclass
class UpdateModelCommand:
    trainer_node_id: str
    training_result: TrainingResult
    saved_update_artifact_path: str
```

### Handler Contract
- Extracts `(base_model_id, base_model_version, dataset_id, dataset_shard_id)` from `training_result`.
- Locates `TrainingShard` in `TrainingShardRepository.get_by_shard_key(...)`.
- Updates `shard.update_artifact_path = command.saved_update_artifact_path`.
- Updates `shard.metrics = command.training_result.metrics`.
- Updates `shard.status = TrainingShardStatus.COMPLETED`.
- Persists changes to SQLite via repository.
