"""
Verification and quality evaluation script for Canonical Causal Decoder Training Test.
Evaluates validation loss and perplexity on:
- Version 0: Base TinyStories-1M Model (artifacts/tinystories_base.gz)
- Version 1: Aggregated Model Archive produced by distributed training
on the held-out validation dataset (artifacts/tinystories_val.pt).
"""

from __future__ import annotations
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import torch

SAMPLE_DIR = Path(__file__).resolve().parent
WORK_DIR = SAMPLE_DIR / "work"
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
DB_PATH = WORK_DIR / "db" / "training.db"


def evaluate_model_archive(archive_path: Path, val_dataset_path: Path) -> tuple[float, float]:
    """Unpack model archive and compute validation loss and perplexity."""
    from transformers import AutoModelForCausalLM

    if not archive_path.is_file():
        raise FileNotFoundError(f"Model archive not found: {archive_path}")
    if not val_dataset_path.is_file():
        raise FileNotFoundError(f"Validation dataset not found: {val_dataset_path}")

    # Unpack archive to temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="eval_unpack_"))
    try:
        with tarfile.open(str(archive_path), "r:*") as tar:
            tar.extractall(path=str(temp_dir))

        model_dir = temp_dir / "model"
        if not model_dir.is_dir():
            nested = list(temp_dir.glob("**/model"))
            if nested:
                model_dir = nested[0]
            else:
                raise ValueError(f"No 'model' directory found in archive {archive_path}")

        # Load model in eval mode
        model = AutoModelForCausalLM.from_pretrained(str(model_dir))
        model.eval()

        # Load validation tensors
        val_data = torch.load(str(val_dataset_path), map_location="cpu", weights_only=False)
        input_ids = val_data["input_ids"]
        attention_mask = val_data["attention_mask"]
        labels = val_data["labels"]

        total_loss = 0.0
        num_batches = 0
        batch_size = 4

        with torch.no_grad():
            for i in range(0, len(input_ids), batch_size):
                b_ids = input_ids[i:i + batch_size]
                b_mask = attention_mask[i:i + batch_size]
                b_labels = labels[i:i + batch_size]

                outputs = model(
                    input_ids=b_ids,
                    attention_mask=b_mask,
                    labels=b_labels,
                )
                total_loss += outputs.loss.item()
                num_batches += 1

        avg_loss = total_loss / max(num_batches, 1)
        try:
            perplexity = math.exp(avg_loss)
        except OverflowError:
            perplexity = float("inf")

        return avg_loss, perplexity
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def get_aggregated_model_path() -> Path:
    """Find aggregated model path from Client database or client artifacts directory."""
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT model_artifact_path FROM models WHERE model_version != '0' ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row and row["model_artifact_path"]:
                candidate = Path(row["model_artifact_path"]).resolve()
                if candidate.is_file():
                    return candidate
        except Exception:
            pass

    # Fallback: search work/client_artifacts for .gz archives
    client_work = WORK_DIR / "client_artifacts"
    if client_work.exists():
        gz_files = list(client_work.glob("**/*.gz"))
        # Exclude temporary archives
        gz_files = [f for f in gz_files if ".tmp" not in f.name and "tinystories_base" not in f.name]
        if gz_files:
            # Sort by modification time, newest first
            gz_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return gz_files[0]

    raise FileNotFoundError("Could not locate aggregated model archive in database or working directory.")


def main() -> int:
    print("================================================================================")
    print("    Canonical Causal Decoder: Model Quality & Perplexity Verification          ")
    print("================================================================================")

    base_model_path = ARTIFACTS_DIR / "tinystories_base.gz"
    val_dataset_path = ARTIFACTS_DIR / "tinystories_val.pt"

    if not base_model_path.is_file():
        print(f"[Verify] [ERROR] Base model missing: {base_model_path}", file=sys.stderr)
        return 1
    if not val_dataset_path.is_file():
        print(f"[Verify] [ERROR] Validation dataset missing: {val_dataset_path}", file=sys.stderr)
        return 1

    try:
        agg_model_path = get_aggregated_model_path()
        print(f"[Verify] Located aggregated model: {agg_model_path}")
    except Exception as exc:
        print(f"[Verify] [ERROR] {exc}", file=sys.stderr)
        return 1

    print("[Verify] Evaluating Version 0 (Base TinyStories-1M Model)...")
    base_loss, base_ppl = evaluate_model_archive(base_model_path, val_dataset_path)
    print(f"  Base Loss:       {base_loss:.4f}")
    print(f"  Base Perplexity: {base_ppl:.2f}")

    print("[Verify] Evaluating Version 1 (Aggregated Distributed Model)...")
    agg_loss, agg_ppl = evaluate_model_archive(agg_model_path, val_dataset_path)
    print(f"  Aggregated Loss:       {agg_loss:.4f}")
    print(f"  Aggregated Perplexity: {agg_ppl:.2f}")

    print("\n============================================================")
    print("CANONICAL CAUSAL DECODER VERIFICATION RESULTS")
    print("============================================================")
    print("Version 0 (Base Model):")
    print(f"  - Validation Loss:        {base_loss:.4f}")
    print(f"  - Perplexity:             {base_ppl:.2f}")
    print("Version 1 (Aggregated Model):")
    print(f"  - Validation Loss:        {agg_loss:.4f}")
    print(f"  - Perplexity:             {agg_ppl:.2f}")
    print("------------------------------------------------------------")

    # Assert validity of perplexity
    if math.isnan(agg_ppl) or math.isinf(agg_ppl) or agg_ppl <= 0:
        print("Status: FAILED (Invalid perplexity value)", file=sys.stderr)
        print("============================================================")
        return 1

    print("Status: VERIFICATION SUCCESSFUL (Valid perplexity computed)")
    print("============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
