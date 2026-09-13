# Phase 0 Research: Canonical Causal Decoder Model Adapter Suite

**Feature Branch**: `021-canonical-causal-decoder`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Hugging Face Causal Language Model Fine-Tuning Lifecycle

### Research Context
The distributed training engine requires a concrete trainer adapter (`CanonicalCausalDecoderTrainer`) implementing the 4-phase lifecycle (`validate`, `prepare`, `train`, `save_result`) using Hugging Face's `transformers` library (`AutoModelForCausalLM`, `AutoTokenizer`, `Trainer`, and `TrainingArguments`).

### Decision
1. **Model Loading & Device Placement**:
   - Resolve target compute device dynamically: `cuda` if `torch.cuda.is_available()`, otherwise `cpu`.
   - In `prepare()`, unpack the `.gz` or `.tar.gz` model archive into a dedicated task-isolated directory (`model_unpacked/`) inside `self.working_directory`.
   - Load the model using `AutoModelForCausalLM.from_pretrained(str(model_path))` and tokenizer using `AutoTokenizer.from_pretrained(str(tokenizer_path))`.
   - If `tokenizer.pad_token` is not set, default it to `tokenizer.eos_token` to guarantee consistent causal attention masking.

2. **Immutable Baseline Snapshot**:
   - Before `train()` begins, capture an immutable CPU clone of all trainable model parameters:
     ```python
     self.baseline_parameters = {
         name: param.detach().clone().cpu()
         for name, param in self.model.named_parameters()
         if param.requires_grad
     }
     ```
   - Retaining baseline parameters in CPU memory prevents unnecessary GPU memory consumption while ensuring original weights remain unmutated for delta extraction.

3. **Hugging Face Trainer & Dataset Wrapping**:
   - Wrap the canonical dictionary dataset (`input_ids`, `attention_mask`, `labels`) in a lightweight PyTorch `Dataset` subclass yielding dictionary batches.
   - Construct `TrainingArguments` from `CanonicalCausalDecoderTrainingConfig`:
     - Output directory: `self.working_directory / "hf_trainer_output"`
     - Batch size: `per_device_train_batch_size=config.batch_size`
     - Epochs / Steps: `num_train_epochs=config.epochs`, `max_steps=config.max_steps or -1`
     - Optimizer & LR: `learning_rate=config.learning_rate`, `weight_decay=config.weight_decay`
     - Accumulation & Norm: `gradient_accumulation_steps=config.gradient_accumulation_steps`, `max_grad_norm=config.max_grad_norm`
     - Precision: `fp16=config.fp16 and torch.cuda.is_available()`, `bf16=config.bf16 and torch.cuda.is_available()`
     - Scheduler: `lr_scheduler_type=config.scheduler_type`, `warmup_steps=config.warmup_steps`, `warmup_ratio=config.warmup_ratio`
     - Logging/Checkpointing: Disable intermediate checkpointing (`save_strategy="no"`) to optimize I/O and conserve disk space.
   - Initialize `transformers.Trainer(model=self.model, args=training_args, train_dataset=dataset, tokenizer=self.tokenizer)`.

4. **Rationale**:
   - Encapsulating Hugging Face `Trainer` directly satisfies the engine's 4-phase contract while offloading complex gradient accumulation, learning rate scheduling, mixed-precision handling, and loss computation to standard, heavily tested transformers components.

5. **Alternatives Considered**:
   - *Custom PyTorch Training Loop*: Writing a raw manual PyTorch loop with AdamW. Rejected because the feature explicitly specifies using Hugging Face `Trainer` and `TrainingArguments`, and manual loops introduce maintenance overhead for scheduler types, mixed precision, and gradient accumulation.

---

## 2. Parameter Delta Extraction & Safetensors Serialization

### Research Context
After local fine-tuning completes, Trainer nodes must not transmit full model checkpoints. Instead, they must compute parameter deltas ($\Delta W = W_{\text{trained}} - W_{\text{base}}$) for all trainable parameters and serialize them into a `.safetensors` file.

### Decision
1. **Delta Calculation**:
   - Compute deltas on CPU in contiguous memory:
     ```python
     deltas: Dict[str, torch.Tensor] = {}
     for name, param in self.model.named_parameters():
         if param.requires_grad and name in self.baseline_parameters:
             trained_tensor = param.detach().cpu()
             base_tensor = self.baseline_parameters[name]
             deltas[name] = (trained_tensor - base_tensor).contiguous()
     ```
   - Validate that every delta matches the shape and dtype of its baseline parameter.

2. **Serialization & Naming**:
   - Serialize deltas via `safetensors.torch.save_file(deltas, str(artifact_path))`.
   - File naming follows the engine standard: `{base_model_id}_{version}_{dataset_id}_{shard_id}.safetensors`.
   - Return a populated `TrainingResult` containing total samples trained, loss, training duration, and the absolute path to the delta artifact.

3. **Rationale**:
   - Safetensors provides zero-copy deserialization, built-in safety against arbitrary code execution (unlike `torch.save` pickle), and consistent cross-platform binary storage.

4. **Alternatives Considered**:
   - *PyTorch `.pt` state dict*: Rejected because `safetensors` is explicitly required by the specification and avoids pickle security risks.

---

## 3. Causal Language Model Dataset Partitioning & Sampling

### Research Context
Client nodes prepare datasets before initiating distributed training. The partitioner must inspect a tokenized dataset `.pt` file, extract a representative single-batch sample for smoke testing, and divide the full dataset into balanced shards of at most `shardSampleSize`.

### Decision
1. **Dataset Contract Validation**:
   - Canonical dataset structure is a PyTorch tensor dictionary:
     ```python
     {
         "input_ids": torch.LongTensor,       # Shape: [N, seq_len]
         "attention_mask": torch.LongTensor,  # Shape: [N, seq_len]
         "labels": torch.LongTensor           # Shape: [N, seq_len]
     }
     ```
   - Ensure all three keys exist, have matching sample dimensions ($N$), matching sequence lengths, and compatible dtypes (`torch.long`).

2. **Sampling (`CreateSample`)**:
   - Slice the first $K$ samples (default $K=min(2, N)$) across all 3 tensors.
   - Save to `sampleOutputDirecotry / f"{dataset_id}_sample.pt"` using `torch.save()`.
   - Return `SamplingResult` with sample path, sample count, and metadata.

3. **Sharding (`CreateShards`)**:
   - Calculate total shards: $M = \lceil N / \text{shardSampleSize} \rceil$.
   - Slice each tensor along dimension 0:
     `shard_dict = {k: v[start_idx:end_idx].clone() for k, v in data.items()}`.
   - Save each shard to `shardsOutputDirectory / f"{dataset_id}_{shard_id}.pt"`.
   - Return `PartitioningResult` containing list of `ShardInfo` records with sample counts and filenames.

4. **Rationale**:
   - Slicing contiguous PyTorch tensors preserves exact token sequences and attention masks without mutating dataset semantics.

---

## 4. Architecture-Agnostic Sample-Weighted Federated Averaging

### Research Context
The aggregator combines `.safetensors` parameter updates from multiple trainers into a unified model version using sample-weighted Federated Averaging:
$$\Delta W_{\text{avg}} = \sum_{i=1}^{M} \frac{n_i}{N} \Delta W_i \quad \text{where} \quad N = \sum_{i=1}^{M} n_i$$

### Decision
1. **Delta Loading & Validation**:
   - In `LoadDelta()`, deserialize each `.safetensors` file via `safetensors.torch.load_file(str(path), device="cpu")`.
   - In `ValidateDelta()`, unpack the base model from the base archive, inspect its named parameters, and verify:
     - Every key in the delta exists in the base model state dict.
     - Shapes and dtypes match exactly.
     - `samplesTrained` $> 0$.
     - All deltas share the identical base model ID and base version.

2. **Aggregation Calculation**:
   - Compute total samples $N = \sum n_i$.
   - For each parameter name, calculate:
     $$\Delta W_{\text{avg}}[k] = \sum_{i=1}^{M} \left(\frac{n_i}{N} \times \Delta W_i[k]\right)$$
   - Execute accumulation in `float32` (or original float dtype) on CPU to prevent numerical underflow, converting back to original dtype if necessary.

3. **New Version Publishing (`CreateNewVersion`)**:
   - Add aggregated deltas to base parameters: $W_{\text{new}}[k] = W_{\text{base}}[k] + \Delta W_{\text{avg}}[k]$.
   - Load base model state dict into `AutoModelForCausalLM`, call `save_pretrained(temp_model_dir)`.
   - Copy tokenizer directory files from base archive into `temp_tokenizer_dir`.
   - Create a temporary `.tar.gz` archive containing `model/` and `tokenizer/`, then atomically rename to `{model_id}_{new_version}.gz`.
   - Return `AggregationResult` describing the published version.

4. **Rationale**:
   - Operating directly on parameter names and tensors without hardcoded layer names ensures complete Transformer architecture agnosticism (GPT-2, Llama, Qwen, Mistral, TinyStories, etc.).

---

## 5. Client GUI and CLI Dynamic Presentation

### Research Context
The Client presentation layer must enable users to select between `canonical_torch` and `canonical_causal_decoder` as the primary configuration choice, dynamically tailoring file selectors and hyperparameter inputs.

### Decision
1. **GUI Dynamic View Switching**:
   - Populate `model_type_combo` from `[ModelType.CANONICAL_TORCH.value, ModelType.CANONICAL_CAUSAL_DECODER.value]`.
   - When `canonical_causal_decoder` is active:
     - Model Checkpoint label: `Model Archive (.gz / .tar.gz):` with file filter `"Compressed Model Archive (*.gz *.tar.gz)"`.
     - Dataset File label: `Tokenized Dataset (.pt):` with file filter `"PyTorch Dataset (*.pt)"`.
     - Training Parameters: Display HF Trainer parameters grouped cleanly (Learning Rate, Batch Size, Epochs, Max Steps, Weight Decay, Gradient Accumulation, Max Grad Norm, Scheduler Type, Warmup Steps, Warmup Ratio, FP16, BF16, Shuffle, Seed).
   - When `canonical_torch` is active:
     - Retain `.pt2` model picker and optimizer/criterion/scheduler dropdowns.

2. **CLI Parsing**:
   - Update `ConsoleUI.build_parser()` in `console_ui.py`:
     - `--model-type`: Choices `["canonical_torch", "canonical_causal_decoder"]`, default `"canonical_torch"`.
     - `--model-path`, `--dataset-path`, `--training-config`: Common required paths.
     - Validate config JSON against the corresponding config parser based on `--model-type`.

3. **Rationale**:
   - Providing model type selection as the first field establishes the schema context for all subsequent input validation while leaving downstream submission commands model-agnostic.

---

## 6. End-to-End Native Verification Test Harness

### Research Context
A non-containerized multi-service test harness in `samples/canonical_causal_decoder_training_test/` must verify real end-to-end execution per Constitution Principles VI & VII using TinyStories-1M.

### Decision
1. **Direct HF Hub Asset Acquisition**:
   - `setup.py` directly fetches `roneneldan/TinyStories-1M` model and `roneneldan/TinyStories` dataset from Hugging Face Hub using `transformers` and `datasets`.
   - Saves model weights (`AutoModelForCausalLM`) and tokenizer (`AutoTokenizer`) into `model/` and `tokenizer/`, archiving them into `tinystories_base.gz`.
   - Tokenizes a small subset of stories, creating a 2-shard training dataset and a small validation dataset, saved as `.pt`.

2. **Process Management**:
   - `setup.py` launches Coordinator (`dotnet run`), Relay (`go run`), Client (`python main.py`), 2 Trainers (`python main.py`), and 3 p2p sidecars as detached background processes, writing process IDs to `.test_pids.json`.
   - `clean.py` terminates processes via PID lookup and cleans temporary directories.

3. **Perplexity Verification**:
   - `verify.py` evaluates version 0 (`tinystories_base.gz`) and version 1 (`tinystories_v1.gz`) on the validation dataset:
     $$\text{Loss} = -\frac{1}{T} \sum \log P(w_t \mid w_{<t}), \quad \text{Perplexity} = e^{\text{Loss}}$$
   - Asserts valid numeric perplexity and outputs comparison table.
