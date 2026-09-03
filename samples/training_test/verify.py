"""
Standalone delta verification and mathematical reconstruction tooling.
Reconstructs trained model from base model + delta artifact and evaluates loss on dataset shard.
"""

import sys
from pathlib import Path
import torch
import torch.nn as nn
from safetensors.torch import load_file

SAMPLE_DIR = Path(__file__).resolve().parent

# Hardcoded standard sample artifact filenames
BASE_MODEL_NAME = "base_model_v1.pt2"
DATASET_SHARD_NAME = "dataset1_shard1.pt"
DELTA_ARTIFACT_NAME = "base_model_v1_dataset1_shard1.safetensors"


def verify_delta() -> None:
    print("=== Starting Standalone Delta Verification Tooling ===")

    base_model_path = SAMPLE_DIR / BASE_MODEL_NAME
    shard_path = SAMPLE_DIR / DATASET_SHARD_NAME
    delta_path = SAMPLE_DIR / DELTA_ARTIFACT_NAME

    # 1. Verify existence of all required artifacts
    for p, desc in [
        (base_model_path, "Baseline model"),
        (shard_path, "Dataset shard"),
        (delta_path, "Delta artifact"),
    ]:
        if not p.is_file():
            print(f"[ERROR] {desc} file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Loaded baseline model: {base_model_path.name}")
    print(f"Loaded delta artifact: {delta_path.name}")
    print(f"Loaded dataset shard: {shard_path.name}")

    # 2. Load baseline model module
    try:
        exported_program = torch.export.load(str(base_model_path))
        model = exported_program.module()
        try:
            model.eval()
        except (NotImplementedError, AttributeError):
            pass
    except Exception as exc:
        print(f"[ERROR] Failed to load baseline PyTorch exported program: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Load dataset shard
    try:
        shard_data = torch.load(str(shard_path), weights_only=True)
        x_data = shard_data["x"]
        y_data = shard_data["y"]
    except Exception as exc:
        print(f"[ERROR] Failed to load dataset shard: {exc}", file=sys.stderr)
        sys.exit(1)

    criterion = nn.MSELoss(reduction="mean")

    # 4. Compute baseline evaluation loss
    with torch.no_grad():
        base_outputs = model(x_data)
        baseline_loss = float(criterion(base_outputs, y_data).item())

    print(f"Baseline model evaluation loss: {baseline_loss:.6f}")

    # 5. Load delta artifact via safetensors
    try:
        delta_dict = load_file(str(delta_path))
    except Exception as exc:
        print(f"[ERROR] Failed to load safetensors delta: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded delta artifact: {delta_path.name} ({len(delta_dict)} tensors)")

    # 6. Validate tensor shapes and reconstruct state_dict (reconstructed = base + delta)
    base_state_dict = model.state_dict()
    reconstructed_state_dict = {}

    print("Applying delta tensors to base model parameters...")
    for name, base_tensor in base_state_dict.items():
        if name not in delta_dict:
            print(f"[ERROR] Parameter '{name}' missing from delta artifact!", file=sys.stderr)
            sys.exit(1)

        delta_tensor = delta_dict[name]
        if delta_tensor.shape != base_tensor.shape:
            print(
                f"[ERROR] Shape mismatch for '{name}': base {base_tensor.shape} vs delta {delta_tensor.shape}",
                file=sys.stderr
            )
            sys.exit(1)

        reconstructed_state_dict[name] = base_tensor + delta_tensor
        print(f"[OK] Parameter '{name}' delta applied (shape: {delta_tensor.shape})")

    # 7. Apply reconstructed state to model
    try:
        model.load_state_dict(reconstructed_state_dict)
    except Exception as exc:
        print(f"[ERROR] Failed to load reconstructed state dict: {exc}", file=sys.stderr)
        sys.exit(1)

    # 8. Compute reconstructed evaluation loss
    with torch.no_grad():
        reconstructed_outputs = model(x_data)
        reconstructed_loss = float(criterion(reconstructed_outputs, y_data).item())

    print(f"Reconstructed model evaluation loss: {reconstructed_loss:.6f}")

    # 9. Verify loss improvement
    if reconstructed_loss >= baseline_loss:
        print(
            f"[FAIL] Reconstructed loss ({reconstructed_loss:.6f}) is not lower than baseline loss ({baseline_loss:.6f})!",
            file=sys.stderr
        )
        sys.exit(1)

    print(f"[SUCCESS] Verification passed: Reconstructed loss ({reconstructed_loss:.6f}) < Baseline loss ({baseline_loss:.6f}).")
    print(f"[SUCCESS] Total loss reduction: {baseline_loss - reconstructed_loss:.6f}")
    print("[SUCCESS] Standalone delta verification completed with exit code 0.")
    sys.exit(0)


if __name__ == "__main__":
    verify_delta()
