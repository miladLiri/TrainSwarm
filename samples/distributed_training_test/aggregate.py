"""
Sample aggregation runner for distributed training test scenario.
Collects the 5 delta files produced by parallel training, performs sample-weighted
Federated Averaging using AggregationOrchestrator, and atomically creates models/cnn_model_1.pt2.
"""

import json
import sys
from pathlib import Path

# Add src to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from distributed_training_engine.model_type import ModelType
from distributed_training_engine.aggregation import (
    AggregationOrchestrator,
    AggregationRequest,
    ModelUpdate,
)

SAMPLE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SAMPLE_DIR / "models"
DELTAS_DIR = SAMPLE_DIR / "deltas" / "0"


def run_aggregation() -> None:
    print(f"=== [Aggregate] Starting Model Aggregation in {SAMPLE_DIR} ===")

    base_model_path = MODELS_DIR / "cnn_model_0.pt2"
    if not base_model_path.is_file():
        print(f"[ERROR] Baseline model not found: '{base_model_path}'. Run setup.py first!", file=sys.stderr)
        sys.exit(1)

    delta_files = sorted(list(DELTAS_DIR.glob("*.safetensors")))
    if len(delta_files) == 0:
        print(f"[ERROR] No delta files found in '{DELTAS_DIR}'. Run train.py first!", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(delta_files)} delta artifacts to aggregate:")
    updates = []
    for d in delta_files:
        print(f"     Delta: {d.name} ({d.stat().st_size} bytes)")
        # Each shard has 10 samples
        updates.append(ModelUpdate(samplesTrained=10, deltaPath=d))

    # Clean existing target model version if rerun
    target_model_file = MODELS_DIR / "cnn_model_1.pt2"
    if target_model_file.exists():
        target_model_file.unlink()

    # Build AggregationRequest
    request = AggregationRequest(
        modelId="cnn_model",
        baseModelVersion=0,
        baseModelPath=base_model_path,
        newVersion=1,
        newVersionOutputDirectory=MODELS_DIR,
        updates=updates,
    )

    # Instantiate orchestrator and execute aggregation
    orchestrator = AggregationOrchestrator(model_type=ModelType.CANONICAL_TORCH)
    result = orchestrator.aggregate(request)

    print("\n[OK] Aggregation completed successfully!")
    print(f"     Published Model Version: {result.new_model_version}")
    print(f"     Aggregated Updates: {result.updates_count}")
    print(f"     Published Model Path: {result.model_path}")

    if not Path(result.model_path).is_file():
        print(f"[FAIL] Published model file does not exist at '{result.model_path}'", file=sys.stderr)
        sys.exit(1)

    print("=== [Aggregate] Next model version artifact created successfully! ===")


if __name__ == "__main__":
    run_aggregation()
