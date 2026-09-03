"""
Sample setup script for distributed training and aggregation test scenario.
Generates:
1. Canonical PyTorch CNN base model exported to .pt2 (models/cnn_model_0.pt2)
2. 50-sample canonical dataset (data/dataset.pt)
"""

import sys
from pathlib import Path
import torch
import torch.nn as nn
from torch.export import Dim, export, save

SAMPLE_DIR = Path(__file__).resolve().parent
MODELS_DIR = SAMPLE_DIR / "models"
DATA_DIR = SAMPLE_DIR / "data"


class Simple1DCNN(nn.Module):
    """Simple 1D CNN model satisfying canonical Torch export specifications."""

    def __init__(self, in_channels: int = 1, hidden_channels: int = 4, out_features: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, hidden_channels, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.pool = nn.AdaptiveAvgPool1d(4)
        self.fc = nn.Linear(hidden_channels * 4, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.relu(self.conv1(x))
        h = self.pool(h)
        h = torch.flatten(h, start_dim=1)
        return self.fc(h)


def generate_artifacts() -> None:
    print(f"=== [Setup] Generating Distributed Training Test Artifacts in {SAMPLE_DIR} ===")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Create and export canonical PyTorch 2 model
    torch.manual_seed(42)
    model = Simple1DCNN()
    model.eval()

    sample_x = torch.randn(2, 1, 8, dtype=torch.float32)
    batch_dim = Dim("batch", min=1)
    print("Exporting PyTorch 2 program using torch.export.export()...")
    exported_program = export(
        model,
        (sample_x,),
        dynamic_shapes=({0: batch_dim},)
    )

    base_model_path = MODELS_DIR / "cnn_model_0.pt2"
    save(exported_program, str(base_model_path))
    print(f"[OK] Exported base model saved: {base_model_path.name} ({base_model_path.stat().st_size} bytes)")

    # 2. Generate synthetic 50-sample dataset
    num_samples = 50
    x_data = torch.randn(num_samples, 1, 8, dtype=torch.float32)

    # Define a clean target signal based on input features + minor noise
    weights = torch.tensor([1.5, -2.0, 0.5, -1.0, 2.0, -0.5, 1.0, -1.5], dtype=torch.float32)
    y_data = torch.matmul(x_data.squeeze(1), weights).unsqueeze(1) + torch.randn(num_samples, 1, dtype=torch.float32) * 0.05

    dataset_path = DATA_DIR / "dataset.pt"
    torch.save({"x": x_data, "y": y_data}, str(dataset_path))
    print(f"[OK] Canonical dataset saved: {dataset_path.name} ({num_samples} samples, {dataset_path.stat().st_size} bytes)")

    print("=== [Setup] Artifact generation completed successfully! ===")


if __name__ == "__main__":
    generate_artifacts()
