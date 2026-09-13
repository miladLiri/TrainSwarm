# Quickstart & Verification Guide: Canonical Causal Decoder Model

**Feature Branch**: `021-canonical-causal-decoder`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## Overview

This guide provides step-by-step instructions to run the end-to-end verification harness for the **Canonical Causal Decoder Model** adapter suite in `samples/canonical_causal_decoder_training_test/`. The sample starts all cluster services natively (without Docker) and executes distributed training on Hugging Face's `TinyStories-1M` model and dataset across two trainer nodes.

---

## 1. Prerequisites

- **Python**: 3.10+ with active virtual environment containing `torch`, `transformers`, `datasets`, `safetensors`, `grpcio`, `protobuf`, `requests`.
- **.NET SDK**: 10.0+ for running the Coordinator service.
- **Go**: 1.22+ for running the Relay server and P2P sidecars.
- **Network Access**: Internet connectivity to download `roneneldan/TinyStories-1M` and `roneneldan/TinyStories` from Hugging Face Hub during initial test setup.

---

## 2. Test Harness Lifecycle Commands

All commands are executed from `samples/canonical_causal_decoder_training_test/` (or repository root):

```bash
cd samples/canonical_causal_decoder_training_test
```

### Step 2.1: Spin Up Environment & Prepare Assets
```bash
python setup.py
```
**What it does**:
1. Starts the Coordinator (`dotnet run`), Bootstrap Relay (`go run`), Client (`python main.py`), 2 Trainers (`python main.py`), and 3 P2P sidecars as background processes with isolated working directories.
2. Writes process IDs to `.test_pids.json` for tracked lifecycle control.
3. Downloads `roneneldan/TinyStories-1M` and tokenizer from Hugging Face Hub, packaging them into `artifacts/tinystories_base.gz`.
4. Downloads and tokenizes a slice of `roneneldan/TinyStories`, partitioning into a 2-shard training dataset (`artifacts/tinystories_train.pt`) and validation holdout (`artifacts/tinystories_val.pt`).
5. Generates `artifacts/causal_decoder_config.json`.

**Expected Output**:
```text
[INFO] Sourced Hugging Face TinyStories-1M model and tokenizer successfully.
[INFO] Packaged artifacts/tinystories_base.gz (size: XX MB).
[INFO] Generated artifacts/tinystories_train.pt (N samples) and artifacts/tinystories_val.pt.
[INFO] Spawned Coordinator, Relay, Client, and 2 Trainers. All health probes green.
[INFO] Environment setup complete.
```

---

### Step 2.2: Submit Training Task & Run Cluster
```bash
python submit.py
```
**What it does**:
1. Invokes the Client CLI `submit-training` with `--model-type canonical_causal_decoder`.
2. Client performs the smoke test using `CanonicalCausalDecoderPartitioner.CreateSample()`.
3. Partitions the dataset into 2 shards using `CanonicalCausalDecoderPartitioner.CreateShards()`.
4. Persists records to Client SQLite and submits tasks to Coordinator.
5. Coordinator assigns 1 shard to Trainer 1 and 1 shard to Trainer 2.
6. Trainers pull artifacts via P2P file transfer, fine-tune using `CanonicalCausalDecoderTrainer` (Hugging Face `Trainer`), and push `.safetensors` delta updates to Client.
7. Client executes `CanonicalCausalDecoderAggregator`, computes sample-weighted Federated Averaging, and atomically publishes version 1 model archive (`tinystories_v1.gz`).

**Expected Output**:
```text
[INFO] Training task submitted: model_id=... dataset_id=...
[INFO] Smoke test passed (Loss: X.XXXX).
[INFO] Partitioner generated 2 shards: shard_0, shard_1.
[INFO] Shards dispatched to Trainer 1 and Trainer 2.
[INFO] Trainer 1 completed 1 epoch; update delta serialized to safetensors.
[INFO] Trainer 2 completed 1 epoch; update delta serialized to safetensors.
[INFO] Aggregator received 2 updates. Computing sample-weighted FedAvg...
[INFO] Published new model version: tinystories_v1.gz.
```

---

### Step 2.3: Verify Improvement & Perplexity
```bash
python verify.py
```
**What it does**:
1. Loads base model version 0 (`tinystories_base.gz`) and runs causal language model inference on `tinystories_val.pt`.
2. Calculates cross-entropy loss and baseline perplexity:
   $$\text{Perplexity} = e^{\text{Loss}}$$
3. Loads aggregated model version 1 (`tinystories_v1.gz`) and evaluates on `tinystories_val.pt`.
4. Calculates updated loss and perplexity.
5. Asserts that perplexity is valid and reports the comparison table.

**Expected Output**:
```text
============================================================
CANONICAL CAUSAL DECODER VERIFICATION RESULTS
============================================================
Version 0 (Base Model):
  - Validation Loss:        X.XXXX
  - Perplexity:             XX.XX
Version 1 (Aggregated Model):
  - Validation Loss:        Y.YYYY
  - Perplexity:             YY.YY
------------------------------------------------------------
Status: VERIFICATION SUCCESSFUL (Perplexity improved)
============================================================
```

---

### Step 2.4: Teardown & Clean
```bash
python clean.py
```
**What it does**:
1. Reads `.test_pids.json` and terminates all background processes (Coordinator, Relay, Client, Trainers, sidecars).
2. Cleans temporary working directories, databases, and generated test files.

**Expected Output**:
```text
[INFO] Terminating 7 tracked background processes...
[INFO] All test processes terminated cleanly.
[INFO] Cleaned temporary test artifacts and directories.
```
