# Feature Specification: TinyStories Multi-Round Distributed Training Test & Visual Reporting

**Feature Branch**: `023-tiny-stories-training-test`

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "in this specification we're gonna have a test under samples/tiny_stories_training_test in this test were gonna train model with train swarm from samples/training_report_test take downlaod_artifacts.py and prepare_data.py an copy them to tiny_strories_test/ have a config.py file containing this settigns ... then in a setup.py first launch coordinator and bootstrap relay then launch 2 trainer with one p2p-node with each one and config each env so each trainer connect to it's not p2p-node and coordinator and bootstrap-relay then run a client with it's own p2p-node and config it's env for also create setup_docker that just runs coordinator and bootstrap-relay on docker and does every thing else same as normal setup.py in train.py give prepared data structure created by prepare_data with training_task model detail with settings from config.py to the client to train it after the training is completed and a new version was created then you give newversion with same data again to the client to train for another round and do this for 10 times so 5 time training and get a version 10 of model for reaporting gather report files from trainers for each training task and for each round and put them in a directory structure under reports/ and also save the time span from submitting task to get the new version each time so it would be 5 time lapses and save in a json file also for each submit gather log of coordinator and also add it's usefull info to another json file in veryfy.py using training data compute loss/ accuricy and preplexity of each created version and save them in another json file in show_reports.py in a pretty and tabular and butiful way like (traingin _report test) gather all the json files and create a comperhensive report in terminial especially i want a plot that shows change in accuricy and ppl from version 0 to version 5 and also a reports that shows time span each proccess in training make sure proccess of distributed training across all the sistems execute correctly and without any problem when you done emplementing run test for 2 round to check every thing is ok"

## Clarifications

### Session 2026-10-31

- Q: How many sequential training rounds should train.py execute by default when no --rounds argument is provided? → A: 5 rounds by default (generates v1 through v5 matching the v0–v5 progression plots; accepts `--rounds` for 2 or 10 rounds).
- Q: How should setup_docker.py launch and manage the Docker containerized Coordinator and Bootstrap Relay services? → A: Direct `docker run` and `docker rm -f` CLI commands executed directly by setup_docker.py without extra compose files.
- Q: What specific Coordinator execution details should be extracted and recorded in reports/coordinator_summary.json? → A: Structured task lifecycle metrics (task registration timestamp, trainer assignment timestamp per shard, scheduling latency, and completion confirmation per round).
- Q: How should show_reports.py present the accuracy and perplexity progression plots? → A: Dual presentation: Save high-resolution PNG image (`reports/training_progression_plot.png`) AND display an inline ASCII/Unicode progression graph in a terminal Rich panel.
- Q: Which dataset split should verify.py evaluate against when computing loss, accuracy, and perplexity across model versions? → A: Training data subset (evaluates against the prepared training dataset as requested, measuring training fit and convergence across versions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cluster Lifecycle & Environment Orchestration (Priority: P1)

As an ML infrastructure operator,
I want to bootstrap a complete TrainSwarm distributed cluster containing a Coordinator, a Bootstrap Relay, two independent Trainers (each coupled with a dedicated P2P node sidecar), and a Client node (with its dedicated P2P node sidecar) either natively or using Docker for control plane services,
So that all distributed communication pathways (REST, gRPC, and DCUtR P2P) are verified healthy and ready for parallel task execution before training begins.

**Why this priority**: Without a functional cluster runtime and verified peer-to-peer connectivity between the client, trainers, and coordinator, distributed training and iterative model aggregation cannot execute.

**Independent Test**: Can be validated by executing `setup.py` (or `setup_docker.py`), confirming all 8 processes/services report healthy status endpoints without process crashes or connection timeouts.

**Acceptance Scenarios**:
1. **Given** clean working directories and compiled service binaries, **When** the operator runs `python setup.py`, **Then** the Bootstrap Relay, Coordinator, three P2P nodes, two Trainer daemons, and the Client daemon start in their configured order and respond to health probes.
2. **Given** Docker is available, **When** the operator runs `python setup_docker.py`, **Then** Coordinator and Bootstrap Relay start as containerized services while P2P nodes, Trainers, and Client start natively and connect to the containerized endpoints.
3. **Given** a running cluster, **When** the cluster shutdown routine is triggered, **Then** all spawned child processes, sidecars, and containers terminate cleanly with zero dangling network port locks.

---

### User Story 2 - Iterative Multi-Round Distributed Training Loop (Priority: P1)

As a distributed ML researcher,
I want to execute consecutive training rounds where the Client splits prepared training data, submits training tasks to the Coordinator, distributes work to both Trainers across P2P links, aggregates resulting weight deltas into a newly versioned model, and feeds that new version back into the next round,
So that the model undergoes iterative federated learning over multiple sequential rounds (e.g., producing Version 1 through Version 5 or Version 10).

**Why this priority**: Core value of the TrainSwarm system is demonstrating multi-round iterative fine-tuning and weight aggregation across distributed peers.

**Independent Test**: Can be validated by running `train.py` with the `--rounds 2` smoke test flag, ensuring round 1 produces Version 1, round 2 takes Version 1 as baseline and produces Version 2, and all intermediate weight updates pass validation.

**Acceptance Scenarios**:
1. **Given** base model Version 0 and prepared dataset shards, **When** `train.py` begins round 1, **Then** both trainers receive tasks, compute updates on their assigned data shards, upload deltas back to the client, and the client aggregates them into Model Version 1.
2. **Given** Model Version 1 is successfully aggregated in round 1, **When** round 2 initiates, **Then** the system automatically uses Model Version 1 as the new baseline input model, partitions/assigns training shards, and produces Model Version 2.
3. **Given** a requested round count of N (defaulting to 5, with configuration support up to 10), **When** `train.py` runs to completion, **Then** all N successive versions (v1..vN) are saved in the client models directory with valid metadata records.

---

### User Story 3 - Structured Metric Harvesting & Coordinator Audit Extraction (Priority: P2)

As a DevOps and ML engineer,
I want each completed training round to automatically collect Trainer step report files into a structured `reports/` directory hierarchy, measure the end-to-end elapsed time span from task submission to version aggregation, and parse Coordinator execution logs for scheduling events,
So that comprehensive operational telemetry and timing data are persisted in machine-readable JSON files for auditability and visualization.

**Why this priority**: Distributed systems require persistent telemetry per node and per round to identify stragglers, assess throughput bottlenecks, and verify fair task scheduling.

**Independent Test**: Can be validated after a 2-round training run by verifying `reports/trainer_metrics/` contains metrics files for both trainers across all rounds, `reports/round_timings.json` records valid time spans, and `reports/coordinator_summary.json` contains scheduling timestamps.

**Acceptance Scenarios**:
1. **Given** trainer nodes finishing their assigned training steps, **When** aggregation completes for round R, **Then** trainer metric reports are copied into `reports/round_R/trainer1/` and `reports/round_R/trainer2/` without data corruption.
2. **Given** task submission at timestamp T1 and model aggregation completion at timestamp T2, **When** round R ends, **Then** the elapsed time span (T2 - T1) along with phase breakdown is recorded in `reports/round_timings.json`.
3. **Given** Coordinator service logs, **When** audit extraction runs, **Then** useful scheduling events, task assignments, and node registrations are parsed and saved to `reports/coordinator_summary.json`.

---

### User Story 4 - Cross-Version Validation & Model Quality Evaluation (Priority: P2)

As an ML quality evaluator,
I want to run `verify.py` to evaluate the baseline model (Version 0) and every generated model version (Version 1 through Version N) against the prepared training dataset, computing cross-entropy loss, token prediction accuracy, and perplexity,
So that quantitative model improvements and learning trends across successive training rounds are calculated and stored in a consolidated JSON report.

**Why this priority**: Distributed training must demonstrably improve or maintain model performance; quantitative metrics confirm weights aggregated correctly without degradation.

**Independent Test**: Can be validated by executing `verify.py` against existing model versions v0 through v2, verifying that each version's loss, perplexity, and token accuracy are computed and written to `reports/version_evaluations.json`.

**Acceptance Scenarios**:
1. **Given** model checkpoints v0, v1, and v2, **When** `verify.py` executes, **Then** it evaluates each model archive against the prepared training dataset without out-of-memory errors.
2. **Given** computed evaluation batches, **When** calculations finish, **Then** average loss, perplexity (`exp(loss)`), and top-1 token prediction accuracy percentage are exported to `reports/version_evaluations.json`.

---

### User Story 5 - Rich Visual Reporting & Learning Progression Visualization (Priority: P3)

As a project stakeholder or lead researcher,
I want to run `show_reports.py` to view an elegant, styled terminal summary using Rich tables and ASCII/Matplotlib progression plots,
So that I can immediately inspect the change in accuracy and perplexity from Version 0 to the final version, as well as the time taken by each training phase and round.

**Why this priority**: Clear visualization allows researchers and stakeholders to evaluate convergence speed and cluster efficiency at a glance.

**Independent Test**: Can be validated by invoking `python show_reports.py` when reports exist, verifying terminal tables render with clear column headers, summary metrics, and a generated graphical/ASCII plot showing perplexity and accuracy progressions.

**Acceptance Scenarios**:
1. **Given** populated evaluation and timing JSON files, **When** `show_reports.py` runs, **Then** a tabular overview displaying each version's metrics, loss delta, and perplexity reduction prints to the terminal.
2. **Given** multi-round execution data, **When** plotting logic executes, **Then** a plot file `reports/training_progression_plot.png` is generated and an ASCII trend chart displays in the terminal showing accuracy and perplexity across versions.
3. **Given** recorded round time spans, **When** displaying timing telemetry, **Then** a dedicated process duration table breaks down submission time, training execution time, and aggregation time per round.

---

### Edge Cases

- **Trainer Disconnection or Delayed Heartbeat**: What happens if one trainer node responds significantly slower or experiences network delay during P2P delta transfer? The Client submission handler enforces polling timeouts and logs per-shard status transitions (`SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`).
- **GPU VRAM Limitations**: What happens if the training batch size exceeds VRAM on lower-tier cards (such as the GTX 1650 Ti with 4GB VRAM)? The configuration parameters (`BATCH_SIZE = 16`, `GRAD_ACCUM_STEPS = 2`, `MAX_SEQ_LENGTH = 288`) are calibrated to consume ~200MB-800MB VRAM safely.
- **Port Conflicts on Startup**: What happens if previous test runs left orphaned relay (4001, 8090), coordinator (8080, 8081), or P2P sidecar (50051..50053, 9001..9003) ports bound? `setup.py` and `clean.py` kill lingering processes before starting.
- **Single or Uneven Shard Counts**: What happens if the dataset shard count does not match the trainer node count? The Client partitioner splits data into equal shards matching available trainers, ensuring each trainer receives work.
- **Early Termination / Interrupted Rounds**: What happens if training is interrupted after round 2 of a 5-round schedule? Existing generated versions and telemetry remain persisted and valid for partial verification and reporting.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a self-contained test environment located at `samples/tiny_stories_training_test/`.
- **FR-002**: System MUST incorporate `download_artifacts.py` and `prepare_data.py` (migrated from `samples/training_report_test/`) to download TinyStories assets and tokenize instruction datasets into training shards.
- **FR-003**: System MUST define a central configuration file `config.py` specifying:
  - `BATCH_SIZE = 16`
  - `GRAD_ACCUM_STEPS = 2`
  - `LEARNING_RATE = 1e-4`
  - `WEIGHT_DECAY = 0.01`
  - `MAX_SEQ_LENGTH = 288`
  - `MAX_STEPS = None` (allowing full epoch or override)
  - `WARMUP_STEPS = 20`
  - `LOG_EVERY_STEPS = 5`
  - `MAX_TRAIN_SAMPLES = 5000`
  - `SEED = 42`
  - Configurable `ROUNDS` (defaulting to 5, supporting 2-round test run and up to 10 rounds).
- **FR-004**: System MUST implement `setup.py` to start the complete native cluster:
  1. Bootstrap Relay (HTTP 8090, P2P 4001)
  2. Coordinator API (HTTP 8080, gRPC 8081)
  3. Client P2P node sidecar (gRPC 50051, P2P 9001)
  4. Trainer 1 P2P node sidecar (gRPC 50052, P2P 9002)
  5. Trainer 2 P2P node sidecar (gRPC 50053, P2P 9003)
  6. Client daemon
  7. Trainer 1 daemon (`trainer-node-01`)
  8. Trainer 2 daemon (`trainer-node-02`)
  with all background process IDs tracked in `.test_pids.json` for reliable teardown.
- **FR-005**: System MUST implement `setup_docker.py` to launch Coordinator and Bootstrap Relay directly using `docker run` commands (mapping container ports to host ports) and manage container teardown via `docker rm -f`, while launching P2P sidecars, Trainers, and Client natively with identical environment bindings.
- **FR-006**: System MUST implement `clean.py` to terminate all background processes and Docker containers spawned by the test harness, release port bindings, and provide an option to clean or preserve generated model artifacts.
- **FR-007**: System MUST implement `train.py` to orchestrate multi-round training:
  - Submit the initial training task using base model Version 0 and prepared dataset shards with hyperparameters from `config.py`.
  - Poll for shard execution across Trainer 1 and Trainer 2 and wait for the Client to aggregate weight deltas into a newly versioned model.
  - Automatically feed the newly generated model version as the baseline model into the subsequent training round.
  - Repeat the process for the configured number of rounds (e.g., 2 rounds for verification, 5 rounds for benchmark, up to 10 rounds).
- **FR-008**: System MUST gather individual trainer metric report files for each training task and round, archiving them under a structured `reports/trainers/round_R/trainer_node_id/` directory tree.
- **FR-009**: System MUST record the submission-to-aggregation elapsed duration for each round and persist round timing metrics in `reports/round_timings.json`.
- **FR-010**: System MUST extract structured task lifecycle telemetry from Coordinator logs (including task registration timestamps, trainer assignment timestamps per shard, scheduling latency, and completion confirmation per round) and persist the structured audit data in `reports/coordinator_summary.json`.
- **FR-011**: System MUST implement `verify.py` to evaluate the base model (Version 0) and each newly created model version (v1..vN) against the prepared training dataset, computing cross-entropy loss, token prediction accuracy, and perplexity.
- **FR-012**: System MUST persist the evaluation metrics across all evaluated versions in `reports/version_evaluations.json`.
- **FR-013**: System MUST implement `show_reports.py` to ingest all JSON reports in `reports/` and display a comprehensive, formatted terminal dashboard using Rich tables.
- **FR-014**: `show_reports.py` MUST render a progression plot via dual presentation: saving a high-resolution image to `reports/training_progression_plot.png` AND rendering an inline ASCII/Unicode progression graph directly inside a terminal Rich panel illustrating the change in token accuracy and perplexity from Version 0 through the final model version.
- **FR-015**: `show_reports.py` MUST render a process duration report showing the time span of each round and sub-phase of training.
- **FR-016**: System MUST support running a 2-round end-to-end verification run via command-line arguments (e.g., `python train.py --rounds 2`) to validate cluster execution correctness.

---

### Key Entities

- **Training Configuration (`config.py`)**: Defines hyperparameters including batch size, gradient accumulation, learning rate, weight decay, sequence length, steps, warmup, sample limits, seed, and round counts.
- **Cluster Harness (`setup.py` / `setup_docker.py` / `clean.py`)**: Represents the process orchestration and lifecycle management of the multi-process TrainSwarm test environment.
- **Training Round**: An iteration of the training loop encompassing task submission, parallel shard execution across trainer nodes, delta upload, federated aggregation, and creation of an incremented model version (v`R`).
- **Trainer Task Report**: Execution telemetry collected from individual trainer nodes for a given task and shard, containing step loss, throughput, and hardware utilization.
- **Coordinator Execution Audit (`coordinator_summary.json`)**: Structured log extraction capturing task scheduling times, trainer assignments, and state transitions.
- **Round Timing Metric (`round_timings.json`)**: Records start timestamp, end timestamp, and total elapsed duration for each round.
- **Model Version Evaluation (`version_evaluations.json`)**: Stores validation loss, top-1 accuracy percentage, and perplexity for each model version from v0 to vN.
- **Visual Report Dashboard (`show_reports.py`)**: Formatted terminal output and exported plot summarizing learning convergence and cluster time spans.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Complete 8-component cluster (Relay, Coordinator, 3 P2P sidecars, 2 Trainers, Client) starts and achieves healthy status within 45 seconds of running `setup.py` (or `setup_docker.py`).
- **SC-002**: Multi-round training in `train.py` runs unattended for at least 2 consecutive rounds during verification (and up to 5 or 10 rounds in full run), producing valid, incremented model version archives (e.g. `v1`, `v2`, etc.) with zero shard dropouts or deadlocks.
- **SC-003**: 100% of Trainer task metric reports are collected and organized under `reports/trainers/` for every completed round and participating trainer node.
- **SC-004**: End-to-end time spans from task submission to version creation are recorded for every round in `reports/round_timings.json` with second-level precision.
- **SC-005**: `verify.py` evaluates every generated version (v0 through vN) without memory exhaustion, generating complete loss, perplexity, and token accuracy entries in `reports/version_evaluations.json`.
- **SC-006**: `show_reports.py` renders formatted summary tables in under 5 seconds and generates `reports/training_progression_plot.png` reflecting accuracy and perplexity trajectories.
- **SC-007**: Clean teardown via `clean.py` terminates all spawned processes and releases all network ports within 10 seconds.

---

## Assumptions

- **Hardware & VRAM**: Training is executed locally on developer hardware (such as an NVIDIA GTX 1650 Ti GPU or equivalent CPU fallback). Configured batch size (16), gradient accumulation steps (2), and sequence length (288) have been calibrated to fit comfortably within 4GB VRAM.
- **Dataset Reuse**: The tokenized training shard (5,000 samples) and validation slice generated by `prepare_data.py` are reused across rounds to benchmark incremental learning progression.
- **Default Round Schedule**: The default target for evaluation plotting is 5 rounds (producing Version 0 through Version 5), while `train.py` accepts a `--rounds` argument to support 2-round fast verification runs or extended 10-round training runs.
- **Coordinator Logs Access**: The Coordinator log file written to `work/logs/coordinator.log` contains structured ASP.NET Core log entries that can be parsed for task creation and scheduling events.
- **Zero Mocks**: All services (Coordinator, Relay, P2P nodes, Trainers, Client) execute their real production binaries and code paths without mock objects or simulated networking, adhering strictly to the TrainSwarm Constitution.
