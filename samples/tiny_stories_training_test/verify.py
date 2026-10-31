"""
verify.py

Cross-Version Model Quality & Performance Evaluator for TinyStories:
1. Evaluates baseline model (v0) and all aggregated model versions (v1..vN) against the training dataset shard.
2. Computes cross-entropy loss, perplexity, and masked top-1 token prediction accuracy.
3. Calculates quality improvement deltas relative to baseline.
4. Exports evaluations to reports/version_evaluations.json.
Runs without command-line arguments.
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import torch

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SAMPLE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = SAMPLE_DIR / "artifacts"
WORK_DIR = SAMPLE_DIR / "work"
REPORTS_DIR = SAMPLE_DIR / "reports"
DB_PATH = WORK_DIR / "db" / "training.db"
TRAIN_DATASET_PATH = ARTIFACTS_DIR / "tinystories_train.pt"
OUTPUT_EVAL_PATH = REPORTS_DIR / "version_evaluations.json"


def discover_model_versions() -> list[tuple[int, Path]]:
    """Discovers all available model version archives (v0 baseline + v1..vN)."""
    versions: list[tuple[int, Path]] = []

    # 1. Base Version 0
    base_candidates = [
        ARTIFACTS_DIR / "tinystories_base.tar.gz",
        ARTIFACTS_DIR / "tinystories_base.gz",
    ]
    base_path = next((p for p in base_candidates if p.is_file()), None)
    if base_path:
        versions.append((0, base_path.resolve()))
    else:
        print("[!] Warning: Base model archive not found in artifacts/.")

    # 2. Aggregated Versions from Database
    if DB_PATH.is_file():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT model_version, model_artifact_path FROM models "
                "WHERE model_version != '0' ORDER BY CAST(model_version AS INTEGER)"
            )
            for row in cursor.fetchall():
                v_num = int(row["model_version"])
                p = Path(row["model_artifact_path"]).resolve()
                if p.is_file() and not any(v[0] == v_num for v in versions):
                    versions.append((v_num, p))
            conn.close()
        except Exception as e:
            print(f"[!] Warning querying database: {e}")

    # 3. Fallback scan of work directory
    models_dir = WORK_DIR / "client_artifacts" / "models" / "tinystories"
    if models_dir.is_dir():
        for v_dir in models_dir.glob("v*"):
            v_name = v_dir.name.lstrip("v")
            if v_name.isdigit():
                v_num = int(v_name)
                if not any(v[0] == v_num for v in versions):
                    archive = next((f for f in v_dir.glob("*.gz")), None) or next((f for f in v_dir.glob("*.tar.gz")), None)
                    if archive and archive.is_file():
                        versions.append((v_num, archive.resolve()))

    versions.sort(key=lambda x: x[0])
    return versions


def evaluate_model_archive(archive_path: Path, dataset_path: Path, max_eval_samples: int | None = None) -> tuple[float, float, float]:
    """Unpacks model archive and computes average loss, perplexity, and top-1 token prediction accuracy."""
    from transformers import AutoModelForCausalLM

    temp_dir = Path(tempfile.mkdtemp(prefix="eval_unpack_"))
    try:
        with tarfile.open(str(archive_path), "r:*") as tar:
            tar.extractall(path=str(temp_dir))

        model_dir = temp_dir / "model"
        if not model_dir.is_dir():
            nested = list(temp_dir.glob("**/model"))
            if nested:
                model_dir = nested[0]
            elif (temp_dir / "config.json").is_file():
                model_dir = temp_dir
            else:
                raise ValueError(f"Could not locate 'model' directory inside archive {archive_path.name}")

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = AutoModelForCausalLM.from_pretrained(str(model_dir)).to(device)
        model.eval()

        shard_data = torch.load(str(dataset_path), map_location="cpu", weights_only=False)
        input_ids = shard_data["input_ids"]
        attention_mask = shard_data["attention_mask"]
        labels = shard_data["labels"]

        if max_eval_samples is not None and max_eval_samples > 0:
            input_ids = input_ids[:max_eval_samples]
            attention_mask = attention_mask[:max_eval_samples]
            labels = labels[:max_eval_samples]

        total_loss = 0.0
        total_correct = 0
        total_masked_tokens = 0
        num_batches = 0
        batch_size = 16

        with torch.no_grad():
            for i in range(0, len(input_ids), batch_size):
                b_ids = input_ids[i : i + batch_size].to(device)
                b_mask = attention_mask[i : i + batch_size].to(device)
                b_labels = labels[i : i + batch_size].to(device)

                outputs = model(input_ids=b_ids, attention_mask=b_mask, labels=b_labels)
                total_loss += outputs.loss.item()
                num_batches += 1

                # Calculate top-1 accuracy on instruction-generated tokens
                shift_logits = outputs.logits[..., :-1, :].contiguous()
                shift_labels = b_labels[..., 1:].contiguous()
                mask = shift_labels != -100

                preds = shift_logits.argmax(dim=-1)
                correct = (preds == shift_labels) & mask
                total_correct += correct.sum().item()
                total_masked_tokens += mask.sum().item()

        avg_loss = total_loss / max(num_batches, 1)
        try:
            perplexity = math.exp(avg_loss)
        except OverflowError:
            perplexity = float("inf")

        accuracy = total_correct / max(total_masked_tokens, 1)
        return avg_loss, perplexity, accuracy

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="TinyStories Model Quality Evaluator")
    parser.add_argument("--max-samples", type=int, default=None, help="Limit number of eval samples (default: all)")
    args = parser.parse_args()

    print("=" * 65)
    print(" TinyStories Model Quality & Cross-Version Evaluator ")
    print("=" * 65)

    if not TRAIN_DATASET_PATH.is_file():
        print(f"[!] Evaluation dataset missing: {TRAIN_DATASET_PATH}", file=sys.stderr)
        print("[!] Please run `python prepare_data.py` first.", file=sys.stderr)
        return 1

    versions = discover_model_versions()
    if not versions:
        print("[!] No model versions found to evaluate.", file=sys.stderr)
        return 1

    print(f"[*] Discovered {len(versions)} model version(s) to evaluate: {[f'v{v[0]}' for v in versions]}\n")

    eval_records: list[dict] = []
    base_metrics: dict | None = None

    for v_num, archive_path in versions:
        print(f"[*] Evaluating Version {v_num} from '{archive_path.name}'...")
        loss, ppl, acc = evaluate_model_archive(archive_path, TRAIN_DATASET_PATH, max_eval_samples=args.max_samples)
        print(f"    - Loss:       {loss:.4f}")
        print(f"    - Perplexity: {ppl:.2f}")
        print(f"    - Accuracy:   {acc * 100:.2f}%\n")

        rec = {
            "version": v_num,
            "is_baseline": (v_num == 0),
            "loss": round(loss, 4),
            "perplexity": round(ppl, 2),
            "top1_accuracy": round(acc, 4),
            "archive_path": str(archive_path),
        }

        if v_num == 0:
            base_metrics = rec
        elif base_metrics:
            loss_delta = ((loss - base_metrics["loss"]) / base_metrics["loss"]) * 100
            ppl_delta = ((ppl - base_metrics["perplexity"]) / base_metrics["perplexity"]) * 100
            acc_delta = ((acc - base_metrics["top1_accuracy"]) / max(base_metrics["top1_accuracy"], 1e-6)) * 100

            rec["loss_delta_percent"] = round(loss_delta, 2)
            rec["perplexity_delta_percent"] = round(ppl_delta, 2)
            rec["accuracy_delta_percent"] = round(acc_delta, 2)

        eval_records.append(rec)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "model_id": "tinystories",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "eval_dataset_samples": 5000,
        "versions": eval_records,
    }

    with open(OUTPUT_EVAL_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 65)
    print(f"[+] Cross-version evaluation complete! Saved to '{OUTPUT_EVAL_PATH.name}'.")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
