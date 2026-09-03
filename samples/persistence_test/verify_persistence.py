"""Zero-mock standalone active verification runner for Training Client Persistence Infrastructure.

Validates all 9 scenarios in accordance with TrainSwarm Constitution
Principle V (Zero Mocks) and Principle VII (Mandatory Quality Gate).
"""

import os
import shutil
import sys
from pathlib import Path
import uuid

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.Client.domain.training_shard import TrainingShard, TrainingShardStatus
from src.Client.infrastructure.persistence.database import DatabaseManager
from src.Client.infrastructure.persistence.training_shard_repository import TrainingShardRepository
from src.Client.infrastructure.persistence.exceptions import (
    DuplicateShardError,
    PersistenceError,
)

TEMP_TEST_DIR = REPO_ROOT / ".tmp" / "persistence_verification"


def clean_temp_dir() -> None:
    """Remove temporary test files."""
    if TEMP_TEST_DIR.exists():
        shutil.rmtree(TEMP_TEST_DIR, ignore_errors=True)


def run_scenario(name: str, fn):
    """Run a single scenario and log outcome."""
    print(f"[{name}] ... ", end="", flush=True)
    try:
        fn()
        print("PASS")
    except Exception as e:
        print("FAIL")
        print(f"Error in {name}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        clean_temp_dir()
        sys.exit(1)


def scenario_1_config_and_directories():
    """SCENARIO 1: Environment configuration & directory provisioning."""
    clean_temp_dir()
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    os.environ["TRAINING_CLIENT_DB_PATH"] = str(custom_db_path)

    dm = DatabaseManager()
    assert dm.db_path == custom_db_path.resolve(), f"Expected {custom_db_path.resolve()}, got {dm.db_path}"

    dm.initialize()
    assert custom_db_path.parent.exists(), "Parent directory was not created"
    assert custom_db_path.exists(), "SQLite database file was not created"


def scenario_2_idempotent_initialization():
    """SCENARIO 2: Idempotent schema initialization (tables & indexes)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    # Call initialize a second time
    dm.initialize()

    with dm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_shards';")
        assert cursor.fetchone() is not None, "training_shards table does not exist"

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='uq_training_shards_logical_shard';")
        assert cursor.fetchone() is not None, "Composite unique index does not exist"


def scenario_3_single_shard_persistence():
    """SCENARIO 3: Single shard save & primary key lookup (get_by_id)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    shard_id_val = str(uuid.uuid4())
    shard = TrainingShard(
        id=shard_id_val,
        model_id="gpt2-small",
        model_type="canonical_torch",
        model_version="1",
        dataset_id="openwebtext",
        shard_id="shard-001",
        artifact_path="/tmp/artifacts/shard-001.pt",
        sample_count=1000,
        status=TrainingShardStatus.READY,
    )

    repo.save(shard)

    loaded = repo.get_by_id(shard_id_val)
    assert loaded is not None, "Failed to retrieve saved shard by ID"
    assert loaded.id == shard_id_val
    assert loaded.model_id == "gpt2-small"
    assert loaded.model_type == "canonical_torch"
    assert loaded.model_version == "1"
    assert loaded.dataset_id == "openwebtext"
    assert loaded.shard_id == "shard-001"
    assert loaded.artifact_path == "/tmp/artifacts/shard-001.pt"
    assert loaded.sample_count == 1000
    assert loaded.status == TrainingShardStatus.READY
    assert loaded.metrics is None
    assert loaded.training_metadata is None
    assert loaded.update_artifact_path is None
    assert loaded.training_task_id is None


def scenario_4_composite_key_lookup():
    """SCENARIO 4: Composite key lookup (get_by_shard_key)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    loaded = repo.get_by_shard_key(
        model_id="gpt2-small",
        model_version="1",
        dataset_id="openwebtext",
        shard_id="shard-001",
    )
    assert loaded is not None, "Failed to retrieve shard by composite key"
    assert loaded.model_id == "gpt2-small"
    assert loaded.shard_id == "shard-001"

    non_existent = repo.get_by_shard_key("gpt2-small", "999", "openwebtext", "shard-001")
    assert non_existent is None, "Expected None for non-existent composite key"


def scenario_5_json_serialization_roundtrip():
    """SCENARIO 5: Metrics & metadata JSON round-trip serialization."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    metrics_payload = {
        "loss": 0.245,
        "accuracy": 0.942,
        "epochs": 3,
        "eval_scores": [0.88, 0.91, 0.942],
    }
    metadata_payload = {
        "duration_ms": 34500,
        "device": "cuda:0",
        "batch_size": 64,
    }

    shard_id_val = str(uuid.uuid4())
    shard = TrainingShard(
        id=shard_id_val,
        model_id="gpt2-small",
        model_type="canonical_torch",
        model_version="2",
        dataset_id="openwebtext",
        shard_id="shard-002",
        artifact_path="/tmp/artifacts/shard-002.pt",
        sample_count=2500,
        status=TrainingShardStatus.COMPLETED,
        metrics=metrics_payload,
        training_metadata=metadata_payload,
        update_artifact_path="/tmp/updates/delta_shard_002.safetensors",
        training_task_id="task-xyz-789",
    )

    repo.save(shard)

    loaded = repo.get_by_id(shard_id_val)
    assert loaded is not None, "Failed to retrieve saved shard"
    assert loaded.status == TrainingShardStatus.COMPLETED
    assert loaded.metrics == metrics_payload, f"Metrics mismatch: {loaded.metrics}"
    assert loaded.training_metadata == metadata_payload, f"Metadata mismatch: {loaded.training_metadata}"
    assert loaded.update_artifact_path == "/tmp/updates/delta_shard_002.safetensors"
    assert loaded.training_task_id == "task-xyz-789"


def scenario_6_bulk_save_atomic_batch():
    """SCENARIO 6: Bulk shard atomic batch persistence (bulk_save)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    shards = []
    ids = []
    for i in range(5):
        sid = str(uuid.uuid4())
        ids.append(sid)
        shards.append(
            TrainingShard(
                id=sid,
                model_id="bert-base",
                model_type="canonical_torch",
                model_version="1",
                dataset_id="bookcorpus",
                shard_id=f"shard-{i:03d}",
                artifact_path=f"/data/shards/shard-{i:03d}.pt",
                sample_count=500 * (i + 1),
                status=TrainingShardStatus.READY,
            )
        )

    repo.bulk_save(shards)

    for sid in ids:
        loaded = repo.get_by_id(sid)
        assert loaded is not None, f"Shard {sid} not found after bulk_save"


def scenario_7_duplicate_key_rejection():
    """SCENARIO 7: Duplicate composite key rejection (DuplicateShardError)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    # Attempt to save a duplicate of shard-001 (from scenario 3) with different UUID
    duplicate = TrainingShard(
        id=str(uuid.uuid4()),  # different UUID
        model_id="gpt2-small",
        model_type="canonical_torch",
        model_version="1",
        dataset_id="openwebtext",
        shard_id="shard-001",  # Same composite key!
        artifact_path="/tmp/artifacts/shard-001-alt.pt",
        sample_count=1000,
        status=TrainingShardStatus.READY,
    )

    duplicate_caught = False
    try:
        repo.save(duplicate)
    except DuplicateShardError as e:
        duplicate_caught = True
        assert e.model_id == "gpt2-small"
        assert e.shard_id == "shard-001"

    assert duplicate_caught, "Failed to catch DuplicateShardError on duplicate composite key"

    # Also verify duplicate rejection inside bulk_save
    batch_with_dups = [
        TrainingShard(
            id=str(uuid.uuid4()),
            model_id="t5-small",
            model_type="canonical_torch",
            model_version="1",
            dataset_id="c4",
            shard_id="shard-01",
            artifact_path="/data/c4-01.pt",
            sample_count=100,
        ),
        TrainingShard(
            id=str(uuid.uuid4()),
            model_id="t5-small",
            model_type="canonical_torch",
            model_version="1",
            dataset_id="c4",
            shard_id="shard-01",  # Duplicate within batch!
            artifact_path="/data/c4-01-dup.pt",
            sample_count=100,
        ),
    ]

    bulk_dup_caught = False
    try:
        repo.bulk_save(batch_with_dups)
    except DuplicateShardError:
        bulk_dup_caught = True

    assert bulk_dup_caught, "Failed to catch DuplicateShardError on in-batch duplicate composite keys"


def scenario_8_invalid_sample_count_rejection():
    """SCENARIO 8: Invalid sample count rejection (sample_count <= 0)."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"
    dm = DatabaseManager(db_path=custom_db_path)
    repo = TrainingShardRepository(dm)

    for invalid_count in [0, -5, -100]:
        invalid_shard = TrainingShard(
            id=str(uuid.uuid4()),
            model_id="gpt2-small",
            model_type="canonical_torch",
            model_version="1",
            dataset_id="openwebtext",
            shard_id=f"shard-invalid-{invalid_count}",
            artifact_path="/tmp/invalid.pt",
            sample_count=invalid_count,
        )

        validation_caught = False
        try:
            repo.save(invalid_shard)
        except ValueError:
            validation_caught = True

        assert validation_caught, f"Expected ValueError for sample_count={invalid_count}"


def scenario_9_process_restart_recovery():
    """SCENARIO 9: Process restart recovery & state preservation."""
    custom_db_path = TEMP_TEST_DIR / "nested" / "subfolder" / "custom_training.db"

    # Simulate fresh process startup with new DatabaseManager and Repository
    new_dm = DatabaseManager(db_path=custom_db_path)
    new_dm.initialize()
    new_repo = TrainingShardRepository(new_dm)

    # Shard from scenario 3 must still exist
    shard_1 = new_repo.get_by_shard_key("gpt2-small", "1", "openwebtext", "shard-001")
    assert shard_1 is not None, "Historical shard lost after simulated restart!"
    assert shard_1.sample_count == 1000

    # Shard from scenario 5 must still exist with intact metrics
    shard_2 = new_repo.get_by_shard_key("gpt2-small", "2", "openwebtext", "shard-002")
    assert shard_2 is not None, "Historical shard with metrics lost after restart!"
    assert shard_2.metrics["accuracy"] == 0.942
    assert shard_2.status == TrainingShardStatus.COMPLETED

    # Also test default fallback when TRAINING_CLIENT_DB_PATH is unset
    os.environ.pop("TRAINING_CLIENT_DB_PATH", None)
    fallback_dm = DatabaseManager()
    assert fallback_dm.db_path.name == "training.db", f"Expected training.db, got {fallback_dm.db_path.name}"


def main():
    print("=" * 70)
    print("TrainSwarm Client Persistence Infrastructure Verification")
    print("=" * 70)

    try:
        run_scenario("SCENARIO 1: Config & Directory Provisioning", scenario_1_config_and_directories)
        run_scenario("SCENARIO 2: Idempotent Schema Initialization", scenario_2_idempotent_initialization)
        run_scenario("SCENARIO 3: Single Shard Save & Point Lookup", scenario_3_single_shard_persistence)
        run_scenario("SCENARIO 4: Composite Key Lookup", scenario_4_composite_key_lookup)
        run_scenario("SCENARIO 5: JSON Serialization Round-Trip", scenario_5_json_serialization_roundtrip)
        run_scenario("SCENARIO 6: Bulk Save Batch Persistence", scenario_6_bulk_save_atomic_batch)
        run_scenario("SCENARIO 7: Duplicate Key Rejection", scenario_7_duplicate_key_rejection)
        run_scenario("SCENARIO 8: Invalid Sample Count Rejection", scenario_8_invalid_sample_count_rejection)
        run_scenario("SCENARIO 9: Process Restart Recovery", scenario_9_process_restart_recovery)

        print("=" * 70)
        print("ALL PERSISTENCE SCENARIOS PASSED (Exit Code 0)")
        print("=" * 70)
    finally:
        clean_temp_dir()


if __name__ == "__main__":
    main()
