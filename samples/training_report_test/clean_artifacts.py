"""
clean_artifacts.py

Removes all downloaded and prepared artifacts created by download_artifacts.py
and prepare_data.py (artifacts/ and fine-tuning-dataset/ directories).
Runs without command-line arguments.
"""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import sys

SCRIPT_DIR = Path(__file__).resolve().parent

ARTIFACT_DIRS_TO_REMOVE = [
    SCRIPT_DIR / "artifacts",
    SCRIPT_DIR / "fine-tuning-dataset",
]


def main() -> None:
    print("=" * 65)
    print(" Cleaning Downloaded & Prepared Artifacts ")
    print("=" * 65)
    removed_count = 0

    for path in ARTIFACT_DIRS_TO_REMOVE:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            print(f"[-] Removed directory: '{path.name}/'")
            removed_count += 1
        elif path.is_file():
            try:
                path.unlink()
                print(f"[-] Removed file:      '{path.name}'")
                removed_count += 1
            except OSError as e:
                print(f"[!] Warning deleting '{path.name}': {e}")

    print("=" * 65)
    print(f"[+] Artifact cleanup completed. ({removed_count} item(s) cleaned)\n")


if __name__ == "__main__":
    main()
