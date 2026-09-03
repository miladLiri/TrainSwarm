# Quickstart & Verification Guide: Local Training Shard Persistence

**Feature Branch**: `011-training-shard-persistence`  
**Date**: 2026-09-03  
**Status**: Ready  

## 1. Overview

This guide describes how to verify and exercise the local training shard persistence infrastructure implemented for the TrainSwarm Client application.

The persistence infrastructure provides:
1. Pure Python domain models: `TrainingShard` and `TrainingShardStatus`.
2. Dedicated persistence infrastructure: `DatabaseManager` and `TrainingShardRepository`.
3. SQLite local store with composite uniqueness protection, JSON serialization, and atomic transaction guarantees.

---

## 2. Prerequisites

- Python 3.10+ installed and available on `PATH`.
- Python standard library with `sqlite3` support.
- Working directory: Repository root (`TrainSwarm/`).

---

## 3. Configuration Scenarios

### Scenario 3.1: Default Configuration (Fallback)

When `TRAINING_CLIENT_DB_PATH` is unset or empty, the database infrastructure automatically defaults to creating and using `./training.db` relative to the current working directory.

```powershell
# Windows PowerShell
Remove-Item env:TRAINING_CLIENT_DB_PATH -ErrorAction SilentlyContinue
python -c "from src.Client.infrastructure.persistence.database import DatabaseManager; dm = DatabaseManager(); print('DB Path:', dm.db_path)"
# Expected Output: DB Path: .../training.db
```

### Scenario 3.2: Custom Environment Path

When `TRAINING_CLIENT_DB_PATH` is specified, the infrastructure resolves the path and automatically creates any non-existent parent directories.

```powershell
# Windows PowerShell
$env:TRAINING_CLIENT_DB_PATH = "$PWD/.tmp/data/training.db"
python -c "from src.Client.infrastructure.persistence.database import DatabaseManager; dm = DatabaseManager(); dm.initialize(); print('Initialized at:', dm.db_path)"
# Expected Output: Initialized at: .../.tmp/data/training.db
```

---

## 4. End-to-End Persistence Scenarios

A dedicated runnable validation script is provided at `samples/persistence_test/verify_persistence.py` to execute all validation scenarios in accordance with TrainSwarm Constitution Principle VII (Mandatory Post-Change Quality Gate):

```powershell
python samples/persistence_test/verify_persistence.py
```

### Expected Output Summary:

```text
======================================================================
TrainSwarm Client Persistence Infrastructure Verification
======================================================================
[SCENARIO 1] Environment configuration & directory provisioning ... PASS
[SCENARIO 2] Idempotent schema initialization (tables & indexes) ... PASS
[SCENARIO 3] Single shard save & primary key lookup (get_by_id) ... PASS
[SCENARIO 4] Composite key lookup (get_by_shard_key) ............. PASS
[SCENARIO 5] Metrics & metadata JSON round-trip serialization ... PASS
[SCENARIO 6] Bulk shard atomic batch persistence (bulk_save) ..... PASS
[SCENARIO 7] Duplicate composite key rejection (DuplicateShardError) PASS
[SCENARIO 8] Invalid sample count rejection (sample_count <= 0) . PASS
[SCENARIO 9] Process restart recovery & state preservation ...... PASS
======================================================================
ALL PERSISTENCE SCENARIOS PASSED (Exit Code 0)
======================================================================
```

---

## 5. Programmatic Usage Example

```python
import uuid
from src.Client.domain.training_shard import TrainingShard, TrainingShardStatus
from src.Client.infrastructure.persistence.database import DatabaseManager
from src.Client.infrastructure.persistence.training_shard_repository import TrainingShardRepository
from src.Client.infrastructure.persistence.exceptions import DuplicateShardError

# 1. Initialize Persistence Infrastructure
db_manager = DatabaseManager()  # reads TRAINING_CLIENT_DB_PATH or defaults to ./training.db
db_manager.initialize()

# 2. Instantiate Repository
repository = TrainingShardRepository(db_manager)

# 3. Create a new TrainingShard domain model
shard = TrainingShard(
    id=str(uuid.uuid4()),
    model_id="gpt2-medium",
    model_type="canonical_torch",
    model_version="1",
    dataset_id="openwebtext",
    shard_id="shard-00042",
    artifact_path="/var/data/shards/shard-00042.pt",
    sample_count=5000,
    status=TrainingShardStatus.READY,
    metrics={"initial_loss": 3.45},
    training_metadata={"split": "train", "checksum": "abc1234"},
)

# 4. Persist to SQLite
repository.save(shard)
print(f"Persisted shard {shard.id}")

# 5. Point lookups
loaded = repository.get_by_id(shard.id)
assert loaded is not None
assert loaded.metrics["initial_loss"] == 3.45

by_composite = repository.get_by_shard_key("gpt2-medium", "1", "openwebtext", "shard-00042")
assert by_composite is not None
assert by_composite.id == shard.id

# 6. Duplicate rejection
try:
    duplicate = TrainingShard(
        id=str(uuid.uuid4()),  # different UUID
        model_id="gpt2-medium",
        model_type="canonical_torch",
        model_version="1",
        dataset_id="openwebtext",
        shard_id="shard-00042",  # identical composite key!
        artifact_path="/var/data/shards/shard-00042.pt",
        sample_count=5000,
    )
    repository.save(duplicate)
except DuplicateShardError as e:
    print(f"Correctly caught duplicate rejection: {e}")
```

---

## 6. Verification Checklist

- [x] Compilation/syntax check passes (`python -m py_compile src/Client/domain/training_shard.py ...`)
- [x] Schema table `training_shards` created with check constraint and composite unique index.
- [x] No `sqlite3` or persistence dependencies imported into domain packages.
- [x] Database path cleanly externalized via `TRAINING_CLIENT_DB_PATH`.
- [x] End-to-end verification script runs cleanly with exit code 0.
