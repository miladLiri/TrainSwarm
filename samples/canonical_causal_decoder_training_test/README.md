# Canonical Causal Decoder Model Distributed Training Test Harness

This sample provides a fully native (non-containerized) multi-node verification harness for the **Canonical Causal Decoder Model** adapter suite.

## Architecture Tested
- **Model**: `roneneldan/TinyStories-1M` (Hugging Face Causal LM) packaged as `.gz`
- **Dataset**: `roneneldan/TinyStories` tokenized `.pt` dictionary (`input_ids`, `attention_mask`, `labels`)
- **Nodes**:
  - **Relay**: Bootstrap P2P Relay (port 4001, HTTP 8090)
  - **Coordinator**: ASP.NET Core Web API & gRPC (HTTP 8080, gRPC 8081)
  - **Client**: TrainSwarm Client daemon & P2P node (gRPC 50051, P2P 9001)
  - **Trainer 1**: `trainer-node-01` & P2P node (gRPC 50052, P2P 9002)
  - **Trainer 2**: `trainer-node-02` & P2P node (gRPC 50053, P2P 9003)

## Workflow

### 1. Setup Environment
```bash
python setup.py
```
Downloads `TinyStories-1M` model and dataset from Hugging Face Hub, packages `artifacts/tinystories_base.gz` and `artifacts/tinystories_train.pt`, and spawns all background processes.

### 2. Submit Task & Run Cluster
```bash
python submit.py
```
Submits training task using Client CLI with `--model-type canonical_causal_decoder`. Partitions into 2 shards, executes distributed fine-tuning across Trainer 1 and Trainer 2, transfers `.safetensors` weight deltas, and aggregates into Version 1 (`.gz`).

### 3. Verify Model & Perplexity
```bash
python verify.py
```
Evaluates cross-entropy validation loss and perplexity on the holdout validation set (`artifacts/tinystories_val.pt`) for both Version 0 (Base Model) and Version 1 (Aggregated Model).

### 4. Cleanup
```bash
python clean.py
```
Terminates all tracked background processes and cleans temporary work files.
