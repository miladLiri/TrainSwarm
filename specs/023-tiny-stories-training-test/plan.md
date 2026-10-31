# Implementation Plan: TinyStories Multi-Round Distributed Training Test & Visual Reporting

**Branch**: `023-tiny-stories-training-test` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/023-tiny-stories-training-test/spec.md`

---

## Summary

This feature establishes an end-to-end, multi-round distributed training verification test and visual reporting suite under `samples/tiny_stories_training_test/`:
1. **Asset Management & Configuration**: Migrates and parameterizes `download_artifacts.py` and `prepare_data.py` driven by a unified `config.py` (calibrated for GTX 1650 Ti ~200MB VRAM).
2. **Cluster Orchestration**: Provides `setup.py` (native execution of all 8 cluster components: Relay, Coordinator, 3 P2P sidecars, 2 Trainers, and Client) and `setup_docker.py` (containerized Coordinator and Bootstrap Relay via direct `docker run`), alongside `clean.py` for reliable PID and port teardown.
3. **Iterative Multi-Round Training Loop**: Implements `train.py` to execute sequential training rounds (default 5, accepting `--rounds` for 2-round smoke verification or up to 10 rounds), feeding the newly aggregated model from round $R$ as baseline input to round $R+1$.
4. **Structured Telemetry & Log Harvesting**: Gathers per-task trainer metric reports under `reports/trainers/`, tracks submit-to-aggregation elapsed times in `reports/round_timings.json`, and extracts Coordinator scheduling latencies into `reports/coordinator_summary.json`.
5. **Offline Quality Evaluation**: Implements `verify.py` to evaluate validation loss, top-1 token prediction accuracy, and perplexity on the training dataset across all generated model versions (`v0` through `vN`), persisting results to `reports/version_evaluations.json`.
6. **Rich Visual Reporting Dashboard**: Implements `show_reports.py` using `rich` tables and panels for terminal metrics and timing breakdowns, paired with dual visual progression outputs: an inline ASCII graph and an exported high-resolution plot (`reports/training_progression_plot.png`).

---

## Technical Context

**Language/Version**: Python 3.10+ (Trainer, Client, test orchestration, and verification tooling); Go 1.24+ (Bootstrap Relay and P2P node sidecar); .NET 10.0 (Coordinator Web API).

**Primary Dependencies**:
- Deep Learning: `torch>=2.2.0`, `transformers>=4.40.0`, `safetensors>=0.4.0`
- Data & Tokenization: `datasets`, `huggingface_hub`
- Visualization & CLI: `rich`, `matplotlib`
- Persistence & Database: SQLite 3 (`sqlite3`)

**Storage**:
- Base Artifacts: `artifacts/tinystories_base.tar.gz`, `artifacts/tinystories_train.pt`, `artifacts/causal_decoder_config.json`
- Local Databases: `work/db/training.db` (Client SQLite), `work/db/coordinator.db` (Coordinator SQLite)
- Model Versions: `work/client_artifacts/models/tinystories/v{R}/tinystories_v{R}.gz`
- Reports Directory:
  - `reports/round_timings.json`
  - `reports/coordinator_summary.json`
  - `reports/version_evaluations.json`
  - `reports/training_progression_plot.png`
  - `reports/trainers/round_{R}/trainer{1,2}/`

**Testing & Verification**:
- Automated 2-round smoke verification via `python train.py --rounds 2` validating P2P transfer, gradient delta aggregation, and version incrementing.
- Model quality evaluation via `python verify.py` checking top-1 accuracy and perplexity reduction.
- Python syntax and compilation check via `python -m py_compile` across all scripts per Constitution Principle VII.

**Target Platform**: Windows 11 / Linux (x86_64), native PowerShell / Bash, with optional Docker daemon for `setup_docker.py`.

**Project Type**: Standalone Integration Test Harness, Cluster Orchestration, and Visual Analytics Suite.

**Performance Goals**:
- Full 8-component cluster boot and health readiness within 45 seconds.
- Memory consumption calibrated under 1GB VRAM per trainer process on NVIDIA GTX 1650 Ti GPU (or CPU fallback).
- Multi-round training handoff latency (aggregation completion to next round submission) < 5 seconds.
- `show_reports.py` renders all terminal tables and generates Matplotlib figures within 5 seconds.

**Constraints**:
- Zero mocks: All cluster services (Coordinator, Relay, P2P nodes, Trainers, Client) execute real production binaries.
- Safe port allocation: Relay (4001, 8090), Coordinator (8080, 8081), Client P2P (50051, 9001), Trainer 1 P2P (50052, 9002), Trainer 2 P2P (50053, 9003).
- Clean process teardown: `.test_pids.json` tracking must ensure zero orphaned background daemons or socket locks.

**Scale/Scope**:
- Test harness directory: `samples/tiny_stories_training_test/` (8 primary scripts + config).
- Evaluates 5,000 instruction-following samples across 2 distributed workers over 2 to 10 sequential rounds.

---

## Constitution Check

*GATE: Passed before Phase 0 research. Re-checked and confirmed after Phase 1 design.*

| Principle | Check | Status | Notes |
|---|---|:---:|---|
| **I. Semi-Distributed Architecture** | Control/data plane boundaries | **PASS** | Control plane (Coordinator, Relay) separated from data plane (Trainers, Client, P2P sidecars). Coordinator owns zero checkpoints or weights. |
| **II. Language Strictness** | Language boundaries respected | **PASS** | Go used for Relay & P2P sidecars; .NET used for Coordinator; Python used for Trainers, Client, and test harness. |
| **III. Explicit Contracts** | Versioned contracts & schemas | **PASS** | JSON schemas defined in `contracts/` for config, round timings, coordinator summary, and version evaluations. |
| **IV. Engineering Standards (MVP)** | Simple, explicit, no bloat | **PASS** | Reuses existing client submission commands and database queries; configuration-driven via `config.py`. |
| **V. Prohibitions & AI Guidelines** | Zero mocks, zero stubs | **PASS** | Real network sockets, live DCUtR P2P transfers, and genuine PyTorch weight aggregations used exclusively. |
| **VI. Real Functional Implementations** | Operational integrity | **PASS** | Complete multi-round federated training pipeline with real gradient updates. |
| **VII. Verification & Compilability** | Build and runtime checks | **PASS** | Executable validation through `quickstart.md`, compilable verification, and active 2-round test run. |

---

## Project Structure

### Documentation (this feature)

```text
specs/023-tiny-stories-training-test/
├── spec.md                              # Feature specification with clarifications
├── plan.md                              # This implementation plan
├── research.md                          # Phase 0 architectural research and decisions
├── data-model.md                        # Phase 1 data models, schemas, and lifecycle
├── quickstart.md                        # Phase 1 runnable validation guide
├── contracts/                           # Phase 1 contract schemas
│   ├── config.schema.json
│   ├── round-timings.schema.json
│   ├── coordinator-summary.schema.json
│   └── version-evaluations.schema.json
└── checklists/
    └── requirements.md                  # Spec quality checklist
```

### Source Code Layout

```text
samples/tiny_stories_training_test/
├── config.py                            # Central hyperparameter configuration
├── download_artifacts.py                # Pretrained model and raw dataset downloader
├── prepare_data.py                      # Shard tokenizer and base model archiver
├── setup.py                             # Native 8-component cluster boot harness
├── setup_docker.py                      # Docker hybrid cluster boot harness
├── train.py                             # Iterative multi-round training loop orchestrator
├── verify.py                            # Offline cross-version loss, accuracy & perplexity evaluator
├── show_reports.py                      # Rich terminal dashboard and progression plotter
└── clean.py                             # Process, container, and port teardown utility
```

---

## Complexity Tracking

*No violations to justify. All designs adhere strictly to constitutional boundaries and MVP principles.*
