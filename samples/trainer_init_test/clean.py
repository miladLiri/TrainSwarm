"""Teardown and cleanup utility for the Trainer Connection test environment.

Removes Docker containers, test networks, and volume directories.
"""

from __future__ import annotations
from pathlib import Path
import sys

SAMPLE_DIR = Path(__file__).resolve().parent
if str(SAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(SAMPLE_DIR))

from setup import clean_environment


def clean() -> None:
    clean_environment()


if __name__ == "__main__":
    clean()
