"""
prepare_data.py

Prepares test artifacts for canonical causal decoder training:
1. Packages artifacts/tinystories_base.tar.gz (containing model/ and tokenizer/ dirs).
2. Tokenizes instruction story samples from fine-tuning-dataset/train.json into
   a PyTorch tensor dictionary shard artifacts/tinystories_train.pt (input_ids, attention_mask, labels with prompt masking = -100).
3. Generates artifacts/causal_decoder_config.json with training hyperparameters.
Runs without command-line arguments.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import torch
from transformers import AutoTokenizer

# UTF-8 console output guard for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "model"
FINETUNING_DIR = SCRIPT_DIR / "fine-tuning-dataset"
TRAIN_DATA_PATH = FINETUNING_DIR / "train.json"

TARGET_MODEL_ARCHIVE = ARTIFACTS_DIR / "tinystories_base.tar.gz"
TARGET_MODEL_ARCHIVE_GZ = ARTIFACTS_DIR / "tinystories_base.gz"
TARGET_SHARD_PATH = ARTIFACTS_DIR / "tinystories_train.pt"
TARGET_CONFIG_PATH = ARTIFACTS_DIR / "causal_decoder_config.json"

MAX_SAMPLES = int(os.environ.get("MAX_SAMPLES", 5000))
MAX_SEQ_LENGTH = int(os.environ.get("MAX_SEQ_LENGTH", 128))


def package_model_archive() -> None:
    """Packages model and tokenizer files into tinystories_base.tar.gz."""
    if TARGET_MODEL_ARCHIVE.is_file() and TARGET_MODEL_ARCHIVE_GZ.is_file():
        print(f"[*] Base model archive already exists: '{TARGET_MODEL_ARCHIVE.name}'")
        return

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    if not MODEL_DIR.is_dir():
        print(f"[*] Sourcing model & tokenizer weights for 'roneneldan/TinyStories-1M'...")
        from transformers import AutoModelForCausalLM
        tok = AutoTokenizer.from_pretrained("roneneldan/TinyStories-1M")
        mod = AutoModelForCausalLM.from_pretrained("roneneldan/TinyStories-1M")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tok.save_pretrained(str(MODEL_DIR))
        mod.save_pretrained(str(MODEL_DIR))
        print(f"[+] Saved model & tokenizer files under '{MODEL_DIR}'.")

    print(f"[*] Packaging base model archive to '{TARGET_MODEL_ARCHIVE}'...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # The canonical causal decoder expects "model/" and "tokenizer/" entries inside archive
    with tarfile.open(str(TARGET_MODEL_ARCHIVE), "w:gz") as tar:
        tar.add(str(MODEL_DIR), arcname="model")
        tar.add(str(MODEL_DIR), arcname="tokenizer")

    if not TARGET_MODEL_ARCHIVE_GZ.is_file():
        shutil.copyfile(TARGET_MODEL_ARCHIVE, TARGET_MODEL_ARCHIVE_GZ)

    size_mb = TARGET_MODEL_ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"[+] Packaged '{TARGET_MODEL_ARCHIVE.name}' ({size_mb:.2f} MB).")


def prepare_dataset_shard(max_samples: int = MAX_SAMPLES, max_seq_length: int = MAX_SEQ_LENGTH) -> None:
    """Tokenizes instruction dataset and saves PyTorch shard .pt."""
    if TARGET_SHARD_PATH.is_file():
        try:
            existing = torch.load(str(TARGET_SHARD_PATH), map_location="cpu", weights_only=False)
            if isinstance(existing, dict) and "input_ids" in existing:
                if existing["input_ids"].shape[0] >= max_samples:
                    print(f"[*] Dataset shard already exists: '{TARGET_SHARD_PATH.name}' ({existing['input_ids'].shape[0]} samples)")
                    return
        except Exception:
            pass

    if not MODEL_DIR.is_dir():
        print(f"[!] Model directory '{MODEL_DIR}' not found. Please run 'python download_artifacts.py' first.")
        sys.exit(1)

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id

    raw_items = []
    if TRAIN_DATA_PATH.is_file():
        print(f"[*] Loading stories from '{TRAIN_DATA_PATH}'...")
        with open(TRAIN_DATA_PATH, "r", encoding="utf-8") as f:
            raw_items = json.load(f)
    else:
        # Check raw data00.json
        raw_json = ARTIFACTS_DIR / "dataset" / "data00.json"
        if raw_json.is_file():
            print(f"[*] Loading stories from '{raw_json}'...")
            with open(raw_json, "r", encoding="utf-8") as f:
                items = json.load(f)
            for it in items:
                story = it.get("story", "").strip()
                if story:
                    raw_items.append({
                        "prompt": "Instruction: Write a short story.\nStory:\n",
                        "story": story,
                    })

    if not raw_items:
        print("[!] No training samples found. Sourcing fallback TinyStories samples...")
        raw_items = [
            {
                "prompt": "Instruction: Write a short story.\nStory:\n",
                "story": f"Once upon a time, there was a little friendly robot numbered {i}. It loved to learn new words and explore the sunny garden every single day.",
            }
            for i in range(max_samples)
        ]

    subset = raw_items[:max_samples]
    print(f"[*] Tokenizing {len(subset)} samples with prompt label masking (seq_len={max_seq_length})...")

    all_input_ids = []
    all_attention_mask = []
    all_labels = []

    for item in subset:
        prompt = item.get("prompt", "")
        story = item.get("story", "").strip()
        if not story:
            continue

        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        story_ids = tokenizer.encode(story + tokenizer.eos_token, add_special_tokens=False)

        input_ids = prompt_ids + story_ids
        if len(input_ids) > max_seq_length:
            input_ids = input_ids[:max_seq_length]

        # Prompt tokens masked with -100
        labels = list(input_ids)
        prompt_len = min(len(prompt_ids), len(input_ids))
        for i in range(prompt_len):
            labels[i] = -100

        attention_mask = [1] * len(input_ids)

        # Pad to max_seq_length
        pad_len = max_seq_length - len(input_ids)
        if pad_len > 0:
            input_ids += [pad_id] * pad_len
            labels += [-100] * pad_len
            attention_mask += [0] * pad_len

        all_input_ids.append(input_ids)
        all_attention_mask.append(attention_mask)
        all_labels.append(labels)

    shard_data = {
        "input_ids": torch.tensor(all_input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(all_attention_mask, dtype=torch.long),
        "labels": torch.tensor(all_labels, dtype=torch.long),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(shard_data, str(TARGET_SHARD_PATH))
    print(f"[+] Saved dataset shard '{TARGET_SHARD_PATH.name}' ({len(all_input_ids)} samples, shape={shard_data['input_ids'].shape}).")


def write_training_config() -> None:
    """Writes causal_decoder_config.json for local training."""
    if TARGET_CONFIG_PATH.is_file():
        print(f"[*] Config already exists: '{TARGET_CONFIG_PATH.name}'")
        return

    config_data = {
        "seed": 42,
        "batch_size": 64,
        "epochs": 5,
        "max_steps": None,
        "learning_rate": 1e-4,
        "weight_decay": 0.01,
        "gradient_accumulation_steps": 2,
        "max_grad_norm": 1.0,
        "scheduler_type": "cosine",
        "warmup_steps": 50,
        "warmup_ratio": 0.0,
        "fp16": False,
        "bf16": False,
        "shuffle": True,
    }
    with open(TARGET_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"[+] Saved training config: '{TARGET_CONFIG_PATH.name}'.")


def main() -> None:
    print("=" * 65)
    print(" Prepare Artifacts for Canonical Causal Decoder Training ")
    print("=" * 65)
    package_model_archive()
    prepare_dataset_shard()
    write_training_config()
    print("=" * 65)
    print("[+] All causal decoder artifacts successfully prepared in './artifacts/'.\n")


if __name__ == "__main__":
    main()
