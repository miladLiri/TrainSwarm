# Quickstart: TinyStories Multi-Round Distributed Training Test & Visual Reporting

**Feature**: `023-tiny-stories-training-test`
**Date**: 2026-10-31

This guide provides end-to-end instructions for setting up, running, evaluating, and viewing the multi-round distributed training test harness under `samples/tiny_stories_training_test/`.

---

## 1. Prerequisites

Ensure the following tools and binaries are installed and available in `PATH`:
- **Python**: 3.10+ with `torch`, `transformers`, `datasets`, `huggingface_hub`, `safetensors`, `rich`, and `matplotlib`.
- **.NET SDK**: 10.0+ (required for native Coordinator compilation via `dotnet run`).
- **Go**: 1.24+ (required for native Bootstrap Relay and `p2p-node` execution).
- **Docker** (optional, for `setup_docker.py`): Docker daemon running if testing containerized control plane services.
- **Hardware**: GPU with at least 2GB free VRAM (e.g. NVIDIA GTX 1650 Ti) or CPU fallback.

---

## 2. Step-by-Step Validation Workflow

All commands must be executed from `samples/tiny_stories_training_test/`:

```bash
cd samples/tiny_stories_training_test
```

### Step 2.1: Download & Prepare Test Assets

Download the TinyStories base model and raw data:
```bash
python download_artifacts.py
```
*Expected Outcome*: Pretrained model and tokenizer saved to `./artifacts/model/` and raw dataset files to `./artifacts/dataset/`.

Tokenize training shard and package model archive:
```bash
python prepare_data.py
```
*Expected Outcome*:
- Packaged base model archive: `artifacts/tinystories_base.tar.gz`
- Tokenized training dataset: `artifacts/tinystories_train.pt` (5,000 samples, sequence length 288)
- Configuration: `artifacts/causal_decoder_config.json`

---

### Step 2.2: Launch the Cluster

#### Option A: Native Execution
Start all 8 services natively (Relay, Coordinator, 3 P2P sidecars, 2 Trainers, Client):
```bash
python setup.py
```
*Expected Outcome*: All 8 processes boot in sequence, health checks pass (`http://127.0.0.1:8090/health` and `http://127.0.0.1:8080/health`), and `.test_pids.json` is created.

#### Option B: Docker-Native Hybrid Execution
Start Coordinator and Bootstrap Relay in Docker containers, and the rest natively:
```bash
python setup_docker.py
```
*Expected Outcome*: `trainswarm-relay` and `trainswarm-coordinator` containers run, health endpoints report OK, and native sidecars/trainers connect.

---

### Step 2.3: Execute Distributed Training

#### Fast Smoke Verification Run (2 Rounds)
To quickly verify distributed training and version aggregation:
```bash
python train.py --rounds 2
```
*Expected Outcome*:
- Round 1 partitions dataset into 2 shards, dispatches to `trainer-node-01` and `trainer-node-02`, aggregates deltas, and creates Model Version 1.
- Round 2 takes Model Version 1 as base, trains both nodes, and creates Model Version 2.
- Telemetry files are written to `reports/round_timings.json`, `reports/coordinator_summary.json`, and `reports/trainers/`.

#### Full Benchmark Run (5 Rounds)
To run the full 5-round learning progression:
```bash
python train.py
```
*Expected Outcome*: Executes 5 sequential federated training rounds producing Model Version 1 through Version 5.

---

### Step 2.4: Offline Model Quality Evaluation

Evaluate loss, top-1 accuracy, and perplexity on the training dataset across all versions:
```bash
python verify.py
```
*Expected Outcome*: Evaluates Version 0 (baseline) and each generated version (`v1`, `v2`, ...), computing cross-entropy loss, top-1 token accuracy, and perplexity. Generates `reports/version_evaluations.json`.

---

### Step 2.5: View Comprehensive Visual Report

Render the styled terminal dashboard and generate the progression chart:
```bash
python show_reports.py
```
*Expected Outcome*:
- Displays formatted Rich tables showing model progression (loss delta, perplexity delta, accuracy delta) and process duration per round.
- Renders an inline terminal ASCII/Unicode progression graph.
- Generates `reports/training_progression_plot.png`.

---

### Step 2.6: Teardown & Reset

Terminate all running processes, containers, release network ports, and remove created files/artifacts:
```bash
python clean.py
```
*Expected Outcome*:
- Terminates all background processes and port listeners (4001, 8090, 8080, 8081, 50051..50053, 9001..9003).
- Stops and removes Docker containers (`trainswarm-relay`, `trainswarm-coordinator`).
- Purges working directory (`work/`), reports (`reports/`), model/dataset artifacts (`artifacts/`), and dataset staging (`fine-tuning-dataset/`).
- Optional flags:
  - `--keep-artifacts`: Preserves `artifacts/` and `fine-tuning-dataset/`.
  - `--keep-reports`: Preserves `reports/` telemetry and progression plots.
  - `--keep-work`: Preserves `work/` runtime data.
  - `--artifacts-only`: Only purges created files without terminating processes.
