"""
Data and Model Artifact Generator for Full Distributed Training Test.

Generates:
1. Canonical PyTorch 2 model checkpoint (.pt2) exported via torch.export.export()
2. 50-sample canonical dataset (.pt) with features 'x' and targets 'y'
3. Training configuration JSON file (training_config.json)
"""

from __future__ import annotations
import json
from pathlib import Path
import sys
import torch
import torch.nn as nn
from torch.export import Dim, export, save

CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = CURRENT_DIR / "artifacts"


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


def generate(output_dir: Path | str = DEFAULT_OUTPUT_DIR) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print(f"=== [Data Generator] Generating Distributed Training Test Artifacts in: {out} ===")

    # 1. Base Model Export (.pt2)
    torch.manual_seed(42)
    model = Simple1DCNN()
    model.eval()

    sample_x = torch.randn(2, 1, 8, dtype=torch.float32)
    batch_dim = Dim("batch", min=1)
    exported = export(model, (sample_x,), dynamic_shapes=({0: batch_dim},))

    model_path = out / "test_model.pt2"
    save(exported, str(model_path))
    print(f"[OK] Exported base model: {model_path.name} ({model_path.stat().st_size} bytes)")

    # 2. 50-Sample Dataset (.pt)
    num_samples = 50
    x_data = torch.randn(num_samples, 1, 8, dtype=torch.float32)
    weights = torch.tensor([1.5, -2.0, 0.5, -1.0, 2.0, -0.5, 1.0, -1.5], dtype=torch.float32)
    y_data = torch.matmul(x_data.squeeze(1), weights).unsqueeze(1) + torch.randn(num_samples, 1, dtype=torch.float32) * 0.05

    dataset_path = out / "test_dataset.pt"
    torch.save({"x": x_data, "y": y_data}, str(dataset_path))
    print(f"[OK] Canonical dataset: {dataset_path.name} ({num_samples} samples, {dataset_path.stat().st_size} bytes)")

    # 3. Training Hyperparameters Configuration (.json)
    config = {
        "batch_size": 2,
        "shuffle": True,
        "epochs": 1,
        "gradient_accumulation_steps": 1,
        "optimizer": "AdamW",
        "learning_rate": 0.001,
        "loss": "MSELoss",
        "weight_decay": 0.01,
        "scheduler": "CosineAnnealingLR",
        "shard_sample_size": 25,
    }
    config_path = out / "training_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"[OK] Training configuration: {config_path.name}")

    print("=== [Data Generator] Completed successfully ===")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT_DIR
    generate(target)
