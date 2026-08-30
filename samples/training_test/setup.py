"""
Sample setup script for the Distributed Training Engine test scenario.
Generates:
1. checkpoint-001.pt2 (Exported PyTorch 2 MLP model with dynamic batch dimension)
2. shard-001.pt (10-sample canonical dataset shard with float32 x and y tensors)
"""

import sys
from pathlib import Path
import torch
import torch.nn as nn
from torch.export import Dim

SAMPLE_DIR = Path(__file__).resolve().parent


class SimpleMLP(nn.Module):
    """Simple 2-layer Multi-Layer Perceptron satisfying canonical torch single-input/single-output contract."""

    def __init__(self, in_features: int = 4, hidden_features: int = 8, out_features: int = 1) -> None:
        super().__init__()
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_features, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.relu(self.fc1(x))
        return self.fc2(h)


def generate_sample_artifacts() -> None:
    print(f"=== Generating Canonical Training Test Artifacts in {SAMPLE_DIR} ===")

    # 1. Create and export canonical PyTorch 2 model
    torch.manual_seed(42)
    model = SimpleMLP(in_features=4, hidden_features=8, out_features=1)
    model.eval()

    sample_x = torch.randn(2, 4, dtype=torch.float32)
    batch_dim = Dim("batch", min=1)
    print("Exporting PyTorch 2 program using torch.export.export()...")
    exported_program = torch.export.export(
        model,
        (sample_x,),
        dynamic_shapes=({0: batch_dim},)
    )

    checkpoint_path = SAMPLE_DIR / "checkpoint-001.pt2"
    torch.export.save(exported_program, str(checkpoint_path))
    print(f"[OK] Exported checkpoint saved: {checkpoint_path.name} ({checkpoint_path.stat().st_size} bytes)")

    # 2. Create 10-sample canonical dataset shard
    num_samples = 10
    x_data = torch.randn(num_samples, 4, dtype=torch.float32)
    weights = torch.tensor([[2.0], [-3.0], [1.0], [-0.5]], dtype=torch.float32)
    y_data = torch.matmul(x_data, weights) + torch.randn(num_samples, 1, dtype=torch.float32) * 0.05

    shard_path = SAMPLE_DIR / "shard-001.pt"
    torch.save({"x": x_data, "y": y_data}, str(shard_path))
    print(f"[OK] Dataset shard saved: {shard_path.name} ({num_samples} samples, {shard_path.stat().st_size} bytes)")

    print("=== Artifact generation completed successfully! ===")


if __name__ == "__main__":
    generate_sample_artifacts()
