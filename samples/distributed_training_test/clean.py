"""
Cleanup utility for the distributed training and aggregation test suite.
Removes all generated models, datasets, shards, deltas, and temporary artifacts.
"""

import os
import shutil
import sys
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent

# Target artifact directories to remove
TARGET_DIRECTORIES = [
    SAMPLE_DIR / "models",
    SAMPLE_DIR / "data",
    SAMPLE_DIR / "deltas",
]

# File patterns to remove if present in SAMPLE_DIR root
TARGET_PATTERNS = [
    "*.pt",
    "*.pt2",
    "*.safetensors",
    "*.tmp",
    "*.tmp.*",
]


def clean() -> None:
    print(f"=== [Clean] Cleaning Test Artifacts in {SAMPLE_DIR} ===")
    removed_count = 0

    # 1. Remove target directories
    for dir_path in TARGET_DIRECTORIES:
        if dir_path.exists():
            try:
                if dir_path.is_dir():
                    shutil.rmtree(dir_path)
                    print(f"[REMOVED] Directory: {dir_path.relative_to(SAMPLE_DIR)}")
                    removed_count += 1
                elif dir_path.is_file():
                    dir_path.unlink()
                    print(f"[REMOVED] File: {dir_path.relative_to(SAMPLE_DIR)}")
                    removed_count += 1
            except Exception as exc:
                print(f"[WARN] Failed to delete '{dir_path}': {exc}", file=sys.stderr)

    # 2. Remove lingering artifact files in the root sample directory if any
    for pattern in TARGET_PATTERNS:
        for file_path in SAMPLE_DIR.glob(pattern):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    print(f"[REMOVED] Lingering artifact: {file_path.name}")
                    removed_count += 1
                except Exception as exc:
                    print(f"[WARN] Failed to delete '{file_path}': {exc}", file=sys.stderr)

    if removed_count == 0:
        print("[INFO] No generated artifacts found. Working directory is already clean.")
    else:
        print(f"[SUCCESS] Cleanup completed successfully. Removed {removed_count} artifact resource(s).")

    print("=== [Clean] Finished ===")


if __name__ == "__main__":
    clean()
