"""
show_report.py

Displays visual training report for training_report_test by calling
show_single_node_train_result.py from samples/comaparision_test.
Runs without command-line arguments.
"""

from __future__ import annotations
import os
from pathlib import Path
import sys

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
COMPARISON_DIR = REPO_ROOT / "samples" / "comaparision_test"

if str(COMPARISON_DIR) not in sys.path:
    sys.path.insert(0, str(COMPARISON_DIR))


def main() -> None:
    # Discover metrics file
    candidates = [
        SCRIPT_DIR / "training_metrics.json",
        SCRIPT_DIR / "work" / "training_metrics.json",
        SCRIPT_DIR / "single_node_finetuning" / "training_metrics.json",
    ]
    metrics_path = next((c for c in candidates if c.is_file()), None)

    if metrics_path is None:
        print("[!] No training metrics found in './' or './work/'.")
        print("[*] Please run 'python train.py' first to execute a training session.\n")
        return

    import show_single_node_train_result
    show_single_node_train_result.main(metrics_path_arg=str(metrics_path))


if __name__ == "__main__":
    main()
