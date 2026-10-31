"""
Configuration constants for TinyStories Multi-Round Distributed Training Test.
Calibrated for local training on consumer GPUs (e.g. NVIDIA GTX 1650 Ti ~200MB VRAM) or CPU fallback.
"""

from __future__ import annotations
from typing import Optional

BATCH_SIZE: int = 16                   # Batch size per step (utilizes GTX 1650 Ti VRAM safely, ~200MB)
GRAD_ACCUM_STEPS: int = 2             # Effective batch size = 32 (reduces gradient variance)
LEARNING_RATE: float = 1e-4           # Calibrated fine-tuning learning rate (prevents weight thrashing)
WEIGHT_DECAY: float = 0.01            # Weight decay for regularization
MAX_SEQ_LENGTH: int = 288             # Max sequence length (captures >95% of full stories)

# Steps & Epochs
MAX_STEPS: Optional[int] = None       # Set to None for full epoch training (or integer to limit steps)
WARMUP_STEPS: int = 20                # Gentle linear warmup steps

# Logging intervals
LOG_EVERY_STEPS: int = 5              # Log metrics and check best checkpoint every N steps

# Dataset limits
MAX_TRAIN_SAMPLES: int = 5000         # Training subset size
SEED: int = 42

# Sequential training rounds
ROUNDS: int = 5                       # Default sequential training rounds (overridable via CLI --rounds)
