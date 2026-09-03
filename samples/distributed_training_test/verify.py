"""
Sample verification and convergence validation tooling.
Loads both the base model (cnn_model_0.pt2) and the newly aggregated model (cnn_model_1.pt2),
evaluates their MSE loss on data/dataset.pt, and verifies measurable loss reduction.
"""

import sys
from pathlib import Path
import torch
import torch.nn as nn
from torch.export import load

SAMPLE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SAMPLE_DIR / "models"
DATA_DIR = SAMPLE_DIR / "data"


def verify_aggregation() -> None:
    print("=== [Verify] Starting Standalone Model Aggregation Verification ===")

    base_model_path = MODELS_DIR / "cnn_model_0.pt2"
    new_model_path = MODELS_DIR / "cnn_model_1.pt2"
    dataset_path = DATA_DIR / "dataset.pt"

    # 1. Verify existence of required artifacts
    for p, desc in [
        (base_model_path, "Baseline model"),
        (new_model_path, "Aggregated new model"),
        (dataset_path, "Full dataset"),
    ]:
        if not p.is_file():
            print(f"[ERROR] {desc} not found: '{p}'. Follow setup, partition, train, aggregate steps first!", file=sys.stderr)
            sys.exit(1)

    print(f"Loaded baseline model: {base_model_path.name}")
    print(f"Loaded aggregated model: {new_model_path.name}")
    print(f"Loaded evaluation dataset: {dataset_path.name}")

    # 2. Load models
    try:
        ep_base = load(str(base_model_path))
        base_module = ep_base.module()
        try:
            base_module.eval()
        except (NotImplementedError, AttributeError):
            pass
    except Exception as exc:
        print(f"[ERROR] Failed to load baseline PyTorch exported program: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        ep_new = load(str(new_model_path))
        new_module = ep_new.module()
        try:
            new_module.eval()
        except (NotImplementedError, AttributeError):
            pass
    except Exception as exc:
        print(f"[ERROR] Failed to load aggregated PyTorch exported program: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Load dataset
    try:
        dataset_dict = torch.load(str(dataset_path), weights_only=True)
        x_data = dataset_dict["x"]
        y_data = dataset_dict["y"]
    except Exception as exc:
        print(f"[ERROR] Failed to load dataset: {exc}", file=sys.stderr)
        sys.exit(1)

    criterion = nn.MSELoss(reduction="mean")

    # 4. Evaluate baseline model loss
    with torch.no_grad():
        base_output = base_module(x_data)
        baseline_loss = float(criterion(base_output, y_data).item())

    # 5. Evaluate aggregated model loss
    with torch.no_grad():
        new_output = new_module(x_data)
        aggregated_loss = float(criterion(new_output, y_data).item())

    loss_reduction = baseline_loss - aggregated_loss
    rel_improvement = (loss_reduction / baseline_loss) * 100.0 if baseline_loss > 0 else 0.0

    print("\n--- Evaluation Results ---")
    print(f"Baseline Model Loss (v0):   {baseline_loss:.6f}")
    print(f"Aggregated Model Loss (v1): {aggregated_loss:.6f}")
    print(f"Absolute Loss Reduction:   {loss_reduction:.6f}")
    print(f"Relative Improvement:      {rel_improvement:.2f}%")

    # 6. Verify mathematical improvement
    if aggregated_loss >= baseline_loss:
        print(
            f"\n[FAIL] Aggregated loss ({aggregated_loss:.6f}) is not lower than baseline loss ({baseline_loss:.6f})!",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n[SUCCESS] Verification passed: Aggregated loss ({aggregated_loss:.6f}) < Baseline loss ({baseline_loss:.6f}).")
    print("[SUCCESS] End-to-end distributed training and aggregation scenario verified with exit code 0.")
    sys.exit(0)


if __name__ == "__main__":
    verify_aggregation()
