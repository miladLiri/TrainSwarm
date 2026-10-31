# Phase 0 Research: TinyStories Multi-Round Distributed Training Test & Visual Reporting

**Feature**: `023-tiny-stories-training-test`
**Date**: 2026-10-31

---

## 1. Test Environment Layout & Artifact Migration

### Context
The test requires a dedicated sample directory at `samples/tiny_stories_training_test/` incorporating `download_artifacts.py` and `prepare_data.py` from `samples/training_report_test/`, driven by a centralized configuration file `config.py`.

### Decision
Migrate and parameterize `download_artifacts.py` and `prepare_data.py` inside `samples/tiny_stories_training_test/`:
- `download_artifacts.py`: Downloads `roneneldan/TinyStories-1M` model/tokenizer and `TinyStories_all_data.tar.gz` (extracting `data00.json`) under `./artifacts/`.
- `config.py`: Exposes configuration constants:
  ```python
  BATCH_SIZE = 16
  GRAD_ACCUM_STEPS = 2
  LEARNING_RATE = 1e-4
  WEIGHT_DECAY = 0.01
  MAX_SEQ_LENGTH = 288
  MAX_STEPS = None
  WARMUP_STEPS = 20
  LOG_EVERY_STEPS = 5
  MAX_TRAIN_SAMPLES = 5000
  SEED = 42
  ROUNDS = 5  # Configurable default; overrides supported via CLI (--rounds)
  ```
- `prepare_data.py`: Directly imports constants from `config.py`. It packages `artifacts/tinystories_base.tar.gz` (containing `model/` and `tokenizer/`), tokenizes up to `MAX_TRAIN_SAMPLES` (5,000) stories with sequence length `MAX_SEQ_LENGTH` (288) into `artifacts/tinystories_train.pt`, and exports `artifacts/causal_decoder_config.json` with the exact hyperparameters from `config.py`.

### Rationale
- Parameterizing `prepare_data.py` through `config.py` ensures that changes to batch sizes, sequence lengths, and step limits propagate consistently across data preparation and training task execution without hardcoded discrepancies.
- Packaging standard `tinystories_base.tar.gz` and PyTorch tensor dictionaries preserves full compatibility with `CanonicalCausalDecoderTrainer` and `CanonicalCausalDecoderPartitioner`.

### Alternatives Considered
- *Hardcoding values inside `prepare_data.py`*: Rejected because changes to `config.py` would not reflect in tokenized tensor sequence lengths and config JSON files.
- *Downloading assets at runtime during `setup.py`*: Rejected because downloading multi-megabyte models during cluster startup slows down rapid iteration; separating download/preparation into explicit steps aligns with `samples/training_report_test/`.

---

## 2. Cluster Orchestration & Process Lifecycle (`setup.py` & `clean.py`)

### Context
TrainSwarm distributed execution requires 8 processes:
1. Bootstrap Relay (Go libp2p relay on TCP/UDP 4001, HTTP 8090)
2. Coordinator (ASP.NET Core API on HTTP 8080, gRPC 8081)
3. Client P2P Sidecar (Go p2pd on gRPC 50051, P2P 9001)
4. Trainer 1 P2P Sidecar (Go p2pd on gRPC 50052, P2P 9002)
5. Trainer 2 P2P Sidecar (Go p2pd on gRPC 50053, P2P 9003)
6. Client Daemon (`Client/main.py`)
7. Trainer 1 Daemon (`Trainer/main.py`, node `trainer-node-01`)
8. Trainer 2 Daemon (`Trainer/main.py`, node `trainer-node-02`)

### Decision
- `setup.py`: Executes background processes in sequential startup order with health checks:
  1. Kills any lingering processes on ports `[4001, 8090, 8080, 8081, 50051, 50052, 50053, 9001, 9002, 9003]` via clean routine.
  2. Creates working subdirectories under `work/`: `db/`, `logs/`, `client_artifacts/`, `trainer1_artifacts/`, `trainer2_artifacts/`.
  3. Launches Relay; waits for `http://127.0.0.1:8090/health` (HTTP 200).
  4. Launches Coordinator; waits for `http://127.0.0.1:8080/health` (HTTP 200).
  5. Launches 3 P2P sidecars with dedicated keys and working directories; sleeps 3–4 seconds for gRPC sockets to bind.
  6. Launches Client daemon; verifies connection to Client P2P sidecar.
  7. Launches Trainer 1 and Trainer 2 daemons; verifies connection to respective P2P sidecars and Coordinator.
  8. Tracks all spawned PIDs in `samples/tiny_stories_training_test/.test_pids.json`.
- `clean.py`: Reads `.test_pids.json`, issues forceful process termination (`taskkill /F /T /PID` on Windows or `kill -9` on POSIX), checks all test ports and kills any remaining port listeners, stops orphan relay/p2pd binaries, stops Docker containers if running, and provides options to purge temporary `work/` runtime data while preserving `reports/`.

### Rationale
- Strict PID tracking and port clearing prevent socket collision (`WSAEADDRINUSE`) bugs between test runs.
- Health-probe polling ensures dependent services do not crash from race conditions during startup.

---

## 3. Docker-Native Hybrid Cluster Orchestration (`setup_docker.py`)

### Context
The user requested `setup_docker.py` to run Coordinator and Bootstrap Relay inside Docker containers while running everything else natively (matching `setup.py`).

### Decision
`setup_docker.py` manages containerized control-plane services using direct `docker run` CLI commands:
- Pre-execution: Stops and removes existing containers `trainswarm-relay` and `trainswarm-coordinator` (`docker rm -f`).
- Bootstrap Relay Container:
  - Docker context: `src/bootstrap-relay`
  - Port bindings: `-p 4001:4001 -p 8090:8090`
  - Container name: `trainswarm-relay`
  - Environment: `P2P_RELAY_LISTEN_TCP=/ip4/0.0.0.0/tcp/4001`, `P2P_RELAY_LISTEN_HTTP=8090`
- Coordinator Container:
  - Docker context: `src/Coordinator` (using `TrainSwarm.Coordinator.Api/Dockerfile`)
  - Port bindings: `-p 8080:8080 -p 8081:8081`
  - Container name: `trainswarm-coordinator`
  - Environment: `COORDINATOR_HTTP_PORT=8080`, `COORDINATOR_GRPC_PORT=8081`, `ASPNETCORE_URLS=http://+:8080`
- Post-boot: Awaits HTTP health endpoints on `http://127.0.0.1:8090/health` and `http://127.0.0.1:8080/health`, then spawns native P2P sidecars, Client daemon, and Trainer daemons identically to `setup.py`.

### Rationale
Direct `docker run` avoids requiring extra Compose files while ensuring identical port exposure and seamless native client/trainer connectivity.

---

## 4. Iterative Multi-Round Distributed Training Loop (`train.py`)

### Context
Each round of training submits a task to the Coordinator, partitions the dataset across trainers, collects updates, and aggregates weights into a new model version. The newly created version must then become the baseline input model for the next round.

### Decision
`train.py` orchestrates the training sequence:
1. Parse CLI arguments: `--rounds` (default: `config.ROUNDS` = 5, supports 2 for smoke test, up to 10 for extended runs).
2. For round `R` from `1` to `rounds`:
   - Identify base model path:
     - If `R == 1`: Base model is `artifacts/tinystories_base.tar.gz` with `--model-version 0`.
     - If `R > 1`: Base model is the aggregated archive from round `R-1` (`work/client_artifacts/models/tinystories/v{R-1}/tinystories_v{R-1}.gz` or `.tar.gz`) with `--model-version {R-1}`.
   - Record `start_time = time.time()`.
   - Submit training via Client CLI:
     ```bash
     python src/Client/main.py submit-training \
       --model-type canonical_causal_decoder \
       --model-path <base_model_path> \
       --dataset-path artifacts/tinystories_train.pt \
       --model-version <version_str> \
       --training-config artifacts/causal_decoder_config.json
     ```
   - Poll `work/db/training.db` until all shards reach `COMPLETED` and the aggregated model record for version `R` exists on disk.
   - Record `elapsed = time.time() - start_time`.
   - Collect metrics and logs:
     - Copy `work/trainer1_artifacts/training_metrics.json` and `training_lifecycle_metrics.json` to `reports/trainers/round_{R}/trainer1/`.
     - Copy `work/trainer2_artifacts/training_metrics.json` and `training_lifecycle_metrics.json` to `reports/trainers/round_{R}/trainer2/`.
     - Parse `work/logs/coordinator.log` for task registration, scheduler assignments, and latencies; update `reports/coordinator_summary.json`.
     - Record round elapsed duration and timestamps in `reports/round_timings.json`.

### Rationale
- Leverages existing production Client commands and database tracking without introducing artificial delays.
- Ensures the aggregation handler's version increment (`new_v = base_v + 1`) chains smoothly from v0 -> v1 -> v2 ... -> vN.

---

## 5. Offline Model Evaluation & Top-1 Token Accuracy (`verify.py`)

### Context
The user specified: "in verify.py using training data compute loss/ accuracy and perplexity of each created version and save them in another json file".

### Decision
`verify.py` evaluates all available versions (`v0` through `vN`) on the prepared training dataset:
- For version 0: Unpacks `artifacts/tinystories_base.tar.gz`.
- For version `R` (1..N): Unpacks `work/client_artifacts/models/tinystories/v{R}/tinystories_v{R}.gz` (or `.tar.gz`).
- Loads model into memory via `AutoModelForCausalLM.from_pretrained(model_dir)` in eval mode on GPU (if CUDA available) or CPU.
- Loads PyTorch tensor dictionary from `artifacts/tinystories_train.pt` (`input_ids`, `attention_mask`, `labels`).
- In batches of 8:
  - Computes cross-entropy loss `outputs.loss.item()`.
  - Computes top-1 token prediction accuracy:
    ```python
    shift_logits = outputs.logits[..., :-1, :].contiguous()
    shift_labels = labels[..., 1:].contiguous()
    mask = shift_labels != -100
    preds = shift_logits.argmax(dim=-1)
    correct = (preds == shift_labels) & mask
    batch_acc = correct.sum().item() / max(mask.sum().item(), 1)
    ```
  - Computes perplexity: `math.exp(avg_loss)`.
- Exports consolidated results to `reports/version_evaluations.json`.

### Rationale
- Top-1 token prediction accuracy against masked instruction tokens (-100 ignored) directly reflects fine-tuning convergence.
- Pre-extracting to a temporary directory avoids file lock issues on Windows.

---

## 6. Visual Reporting Dashboard & Progression Plotting (`show_reports.py`)

### Context
Display comprehensive, tabular, styled reports in the terminal (matching `training_report_test` / `show_single_node_train_result.py`), generate a progression plot showing accuracy and perplexity from v0 to v5/vN, and display a process duration report.

### Decision
Implement `show_reports.py` using `rich` and `matplotlib`:
1. Ingests all generated report JSON files (`reports/round_timings.json`, `reports/coordinator_summary.json`, `reports/version_evaluations.json`, and trainer metrics).
2. Terminal Panels & Tables (via `rich`):
   - **Header Panel**: Test overview, configuration hyperparameters, and cluster nodes.
   - **Model Quality Progression Table**: Version, Loss, Loss Delta (%), Perplexity, Perplexity Delta (%), Token Accuracy (%), Accuracy Delta (%).
   - **Terminal ASCII / Unicode Charts**: Inline sparklines/character plots for Accuracy and Perplexity trends across versions.
   - **Process Duration & Cluster Timing Table**: Round, Submission timestamp, Completion timestamp, Elapsed time (seconds), Shard throughput, and Aggregation duration.
   - **Coordinator Audit Summary Table**: Task registration, scheduling latency, trainer node assignments.
3. Dual Presentation Plot:
   - Saves high-resolution chart `reports/training_progression_plot.png` featuring:
     - Top-left subplot: Perplexity trajectory across versions (`v0`..`vN`).
     - Top-right subplot: Token Accuracy trajectory across versions (`v0`..`vN`).
     - Bottom subplot: Stage/round elapsed durations bar chart.

### Rationale
Meets all visual and quantitative reporting requirements with both instant terminal feedback and persistent publication-quality figures.
