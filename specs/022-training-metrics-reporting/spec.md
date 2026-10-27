# Feature Specification: Unified Training Metrics & Task Lifecycle Reporting

**Feature Branch**: `022-training-metrics-reporting`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "in this specification we have to work in 2 directories samples/comparision_test distributed_training_engine/adapters/canonical_causal_decoder in canonical causal decoder adapter for training there is process of training a training task using trainer api what i like it to be done is compare it with samples/comparision_test/train_single_node.py the traifing flow in adapter must be like the one in the train_single_node in case of proccess and logging and recording the trainging data in a json file i don't want you to change how arguments are read from config and map to TraningArguments Class i want to training steps and logging stemps be the same in train swarm adapter and the test file (the reference is samples/comparision_test/train_single_node.py) at the end after training using canonical causal decoder adapter i want to have the same json report for training and i should be able to read it by show_single_node_train_result.py ---- also i want to have a similar report for start training command handler in Trainer at src/Trainer/application/coordinator_commands/start_training this json report must shows every step of the work -> asking for training data / getting the model / gettign the dataset / training / sending the updates how much these steps took time to fully execute --------- at the end in comaparision_test/ create a file show_training_task_result.py and inside it use the json files created by trainer (for training and the whole proccess) and create a pretty report like what show_single_node_train_result.py does (but still this shlould get the result when any json report does not exists) --- for test under the /samples create training_report_test/ and copy the download_artifacts.py file from comparision_test there and get the dataset and with another file prepare_data.py make result of train_dataset sutable for canonical causal decoder model input model structure and dataset strcutre and config then in train.py (dont run the app) just use distributed_training_engine to run a training session (a real quick one with a littel samples and small batch number) then use in show_report.py use the show_single_node_train_result.py in comaparision_test/ directory to get a report also create a clean.py for remove results of training.py and show_report.py and a clean_artifacts.py to remove every file created by download_artifacts and prepare_data.py files in training_report_test/ must not have any argument to run --- make sure all the files compile and training works correctly. make"

## Clarifications

### Session 2026-10-27
- Q: How should `show_single_node_train_result.py` locate the `training_metrics.json` file when invoked across different directories (such as from `samples/training_report_test/show_report.py`)? → A: Accept optional CLI path argument (`sys.argv[1]`) with automatic fallbacks checking `./training_metrics.json` and `./single_node_finetuning/training_metrics.json`.
- Q: Should `CanonicalCausalDecoderTrainer` save full model checkpoint weights to a `best_checkpoint/` directory on disk whenever a new best loss is achieved, or only record the best step/loss in `training_metrics.json`? → A: Record best step/loss metrics in `training_metrics.json` only (skip saving full model weights to disk).
- Q: What default file search order should `show_training_task_result.py` use to discover `training_metrics.json` and `training_lifecycle_metrics.json` when invoked without arguments? → A: Accept optional CLI path arguments with automatic search in `./`, `./work/`, and `./single_node_finetuning/`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Training Progress & Metric Parity in Canonical Causal Decoder Adapter (Priority: P1)

As an ML engineer, when training a model using the causal decoder adapter, I want the training loop, step-level metrics collection (loss, perplexity, token accuracy, token throughput, and elapsed time), and progress output to match the reference single-node baseline benchmark, and to save this data into a standardized metrics report that can be parsed and displayed by existing single-node inspection tools.

**Why this priority**: Essential foundation. Without parity in metric collection, loss tracking, and reporting between single-node baseline runs and distributed adapter runs, distributed model convergence cannot be validated against the reference baseline.

**Independent Test**: Can be tested independently by running the adapter on sample weights and a prepared dataset shard; verify stdout displays step updates matching the reference format and produces a valid metrics report readable by the single-node results viewer.

**Acceptance Scenarios**:

1. **Given** a valid training task and dataset shard, **When** adapter training executes, **Then** training step logs are output matching the single-node baseline format (`Step X/Y (Ep E/N) | Loss: L | PPL: P | Acc: A% | Speed: S tok/s | Time: Ts`).
2. **Given** an in-progress or completed training session, **When** step checkpoints or training completion occur, **Then** a metrics report file is continuously updated on disk containing metadata, per-step entries, and summary metrics.
3. **Given** the generated metrics report from the adapter, **When** opened with the single-node results viewer, **Then** the viewer displays summary panels, convergence tables, ASCII charts, and progression snapshots without modification or errors.
4. **Given** the task configuration dictionary, **When** mapped to training arguments, **Then** the existing configuration mapping structure and parameter deserialization remain intact and functional.

---

### User Story 2 - Coordinator Start-Training Task Lifecycle Duration Reporting (Priority: P2)

As a distributed cluster operator, when a training node receives an instruction to start training, I want each step of the task lifecycle (requesting task spec, retrieving base model, streaming dataset shard, local training execution, transmitting updates, cleanup) to be timed and recorded into a structured lifecycle execution report showing timestamps, elapsed durations in seconds, and execution status.

**Why this priority**: High operational priority. Diagnosing performance bottlenecks, transfer delays, and execution latencies across distributed training nodes requires granular timing visibility into every stage of the task lifecycle.

**Independent Test**: Can be tested independently by running the training command handler through its lifecycle stages and verifying that a lifecycle metrics report is written to disk recording stage-by-stage timings and completion status.

**Acceptance Scenarios**:

1. **Given** an assigned training task command, **When** the handler processes the lifecycle, **Then** a structured report file is created recording timings and status for all six stages:
   - Requesting training task specification over the network
   - Checking local cache and retrieving base model
   - Streaming assigned dataset shard
   - Executing local model training
   - Transmitting weight updates
   - Cleaning up ephemeral task artifacts
2. **Given** the completion of all lifecycle stages, **When** inspecting the lifecycle report, **Then** it records each step's duration in seconds, overall elapsed time, timestamps, and terminal status ("COMPLETED" or "FAILED").
3. **Given** a failure occurring during any lifecycle stage, **When** an error occurs, **Then** the report records the failed step, duration elapsed before failure, error message, and terminal status "FAILED" while ensuring the report file is preserved on disk.

---

### User Story 3 - Unified Training Task Inspection Tool in Comparison Suite (Priority: P3)

As a developer evaluating training results, I want an inspection tool in the comparison test suite that reads both the adapter training metrics report and the coordinator task lifecycle report, displaying an integrated terminal report with tables and diagrams, while gracefully handling situations where one or both reports do not exist.

**Why this priority**: Crucial usability feature. Provides a single unified dashboard command for developers to inspect both training convergence and cluster orchestration timings without crashing when only partial data is available.

**Independent Test**: Can be tested independently by executing the tool under four conditions: (1) both reports exist, (2) only training metrics exist, (3) only lifecycle metrics exist, (4) neither report exists. Verify formatted terminal output and zero uncaught exceptions in all four conditions.

**Acceptance Scenarios**:

1. **Given** both training metrics and task lifecycle reports are present, **When** running the inspection tool, **Then** the tool displays formatted tables of task lifecycle stages with durations alongside model training progression, loss/perplexity summary, and convergence curves.
2. **Given** only the training metrics report exists, **When** running the inspection tool, **Then** the tool renders the model training report and cleanly displays an informative notice that lifecycle metrics were not found.
3. **Given** only the task lifecycle report exists, **When** running the inspection tool, **Then** the tool renders the lifecycle stage duration breakdown and cleanly displays an informative notice that training metrics were not found.
4. **Given** neither report exists, **When** running the inspection tool, **Then** the tool exits gracefully with a friendly message guiding the user on how to generate the reports first.

---

### User Story 4 - Standalone Training Report Test Harness (Priority: P4)

As an automated tester and contributor, I want a self-contained sample directory that contains all required scripts to download artifacts, prepare dataset shards formatted for the causal decoder, run a fast local training session, view reports, and cleanly reset state, with every script executable without command-line arguments.

**Why this priority**: Validates end-to-end functionality, automated reproducibility, and non-regression of reporting artifacts in a lightweight local test harness without requiring multi-daemon cluster boot.

**Independent Test**: Can be tested independently by running each script sequentially in the test directory with zero command-line arguments: download artifacts, prepare data, train, view report, clean outputs, and clean artifacts.

**Acceptance Scenarios**:

1. **Given** the artifact download script is run without arguments, **When** execution finishes, **Then** base model weights and raw dataset files are downloaded.
2. **Given** the data preparation script is run without arguments, **When** processing completes, **Then** it produces a tokenized dataset shard containing required input, mask, and label tensors, a packaged base model archive, and task configuration.
3. **Given** the training script is run without arguments, **When** execution finishes, **Then** it runs a fast training session, generating standard training metrics and weight delta outputs.
4. **Given** the report viewing script is run without arguments, **When** execution finishes, **Then** it invokes the reporting tool to display the training result.
5. **Given** the cleanup script is run, **When** executed, **Then** it removes all outputs produced by training and report viewing.
6. **Given** the artifact cleanup script is run, **When** executed, **Then** it removes all files downloaded or created by artifact download and data preparation.

---

### Edge Cases

- **Missing Report Files**: If training metrics or lifecycle metrics files do not exist at runtime, report viewing tools must not crash or emit uncaught exceptions; they must print informative status notifications and exit cleanly.
- **Short Training Runs**: When total training steps are fewer than the periodic logging interval, the logging mechanism must still capture the final step, calculate summary deltas, and flush the completed metrics report to disk.
- **Zero Elapsed Time**: In ultra-fast steps or zero elapsed seconds, token throughput calculation must safeguard against division by zero (defaulting throughput to 0.0 tokens/sec).
- **CPU vs GPU Environment**: If GPU acceleration is unavailable, memory usage metrics must record 0.0 MB without error, and device type must accurately reflect CPU execution.
- **Handler Failure Mid-Run**: If an error occurs during any stage of task lifecycle execution, the lifecycle report must be saved up to the failing step with the error message and elapsed duration recorded.
- **Existing Config Contract Compatibility**: In the causal decoder adapter, enhancing the training callback and progress logging must not alter how task envelope configuration values are parsed or mapped into training arguments.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The causal decoder trainer adapter MUST compute running token-level accuracy, average loss, perplexity, and token throughput during training forward passes.
- **FR-002**: The causal decoder trainer adapter MUST print step-level progress to standard output at configurable intervals matching the formatting of the reference single-node training benchmark.
- **FR-003**: The causal decoder trainer adapter MUST continuously save and update an on-the-go JSON report named `training_metrics.json` in its working directory containing `metadata`, `steps`, and `summary` sections.
- **FR-004**: The existing task configuration mapping logic from `CanonicalCausalDecoderTrainingConfig` to `TrainingArguments` in `CanonicalCausalDecoderTrainer` MUST remain unchanged in logic and supported fields.
- **FR-005**: The `StartTrainingHandler` at `src/Trainer/application/coordinator_commands/start_training/handler.py` MUST record a task lifecycle report in JSON format (`training_lifecycle_metrics.json`) measuring individual durations, timestamps, and status for each of the 6 execution steps.
- **FR-006**: The lifecycle report MUST record execution time in seconds for: (1) querying training task specification, (2) checking cache and retrieving base model, (3) streaming dataset shard, (4) executing local training, (5) transmitting update deltas, and (6) cleaning up ephemeral artifacts.
- **FR-007**: A viewer script named `show_training_task_result.py` MUST be created in `samples/comaparision_test` that reads both `training_metrics.json` and `training_lifecycle_metrics.json`, accepting optional CLI path arguments while automatically searching candidate paths (`./`, `./work/`, and `./single_node_finetuning/`).
- **FR-008**: `show_training_task_result.py` MUST render a formatted terminal display using tables and ASCII charts, and MUST gracefully handle missing report files with clear diagnostic notices.
- **FR-009**: A self-contained test sample directory `samples/training_report_test` MUST be created containing: `download_artifacts.py`, `prepare_data.py`, `train.py`, `show_report.py`, `clean.py`, and `clean_artifacts.py`.
- **FR-010**: All scripts in `samples/training_report_test` MUST be executable with zero required command-line arguments.
- **FR-011**: `prepare_data.py` MUST transform dataset inputs into the tensor dictionary contract (`input_ids`, `attention_mask`, `labels`) and package the base model archive required by `CanonicalCausalDecoderTrainer`.
- **FR-012**: `train.py` in `samples/training_report_test` MUST execute a fast training run via `distributed_training_engine` without running external service daemons or background network processes.
- **FR-013**: `clean.py` in `samples/training_report_test` MUST remove all outputs produced by `train.py` and `show_report.py`, and `clean_artifacts.py` MUST remove all files downloaded or prepared by `download_artifacts.py` and `prepare_data.py`.
- **FR-014**: The result viewer `show_single_node_train_result.py` MUST accept an optional CLI path argument (`sys.argv[1]`) to specify the metrics JSON file location, while automatically falling back to check `./training_metrics.json` and `./single_node_finetuning/training_metrics.json` when no path is provided.
- **FR-015**: The causal decoder trainer adapter MUST record best step, epoch, loss, and accuracy metrics in `training_metrics.json` and in terminal step flags (`[*BEST*]`) without persisting full intermediate model checkpoint directories to disk.

### Key Entities

- **TrainingMetricsReport**: Represents model training progression metrics containing:
  - `metadata`: Model identifier, compute device type, parameter count, batch size, learning rate, planned steps, epochs, and start time.
  - `steps`: Array of periodic step records (`step`, `epoch`, `loss`, `perplexity`, `accuracy`, `learning_rate`, `tokens_per_sec`, `total_tokens`, `elapsed_sec`, `vram_allocated_mb`).
  - `summary`: Overall status, total steps, total epochs, total elapsed time, token count, initial/final/best metrics for loss, perplexity, and token accuracy.
- **TaskLifecycleReport**: Represents the coordinator command handler execution timeline containing:
  - `task_metadata`: Client node identifier, model identifier, model version, dataset identifier, shard identifier, overall status, total elapsed duration.
  - `steps`: Ordered list of lifecycle stage entries, each with `step_number`, `name`, `status`, `start_time`, `end_time`, `duration_sec`, and optional `details` or `error`.
- **CausalDecoderDatasetShard**: Structured tensor dictionary containing 2D tensors `input_ids`, `attention_mask`, and `labels` with prompt masking (-100 for non-target tokens).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% schema compatibility between the adapter's `training_metrics.json` and the existing `show_single_node_train_result.py` viewer, allowing the viewer to render the report without script modifications.
- **SC-002**: Step-level stdout logs during adapter training match the format, metric columns, and interval frequency of the reference single-node baseline benchmark.
- **SC-003**: The task lifecycle report records execution durations for all 6 stages of `StartTrainingHandler` with millisecond precision and accurate step attribution.
- **SC-004**: `show_training_task_result.py` completes execution in under 3 seconds in all 4 availability permutations (both files, single file, no files) with zero uncaught exceptions.
- **SC-005**: Automated test workflow in `samples/training_report_test` executes with 100% success rate without requiring interactive parameters or command-line arguments.
- **SC-006**: 100% of modified and newly created Python files pass compilation checks (`python -m py_compile`) with zero syntax errors.

## Assumptions

- The base model architecture used for testing and comparison is `roneneldan/TinyStories-1M`.
- The reference single-node script is `samples/comaparision_test/train_single_node.py` and the existing comparison viewer is `samples/comaparision_test/show_single_node_train_result.py`.
- The adapter output directory for metrics during local task execution defaults to the task's working directory (`working_directory / "training_metrics.json"`).
- In `StartTrainingHandler`, the task lifecycle report is written to `working_directory / "training_lifecycle_metrics.json"`.
- If `show_training_task_result.py` is executed without arguments, it defaults to checking standard report paths in the current directory or designated output directories, while supporting optional custom path parameters.
- For `samples/training_report_test/train.py`, execution directly invokes `distributed_training_engine.training.TrainingOrchestrator` on prepared local artifacts to run a minimal training task (e.g., 20 samples, batch size 2, 1-2 steps) without requiring Docker or network daemons.
