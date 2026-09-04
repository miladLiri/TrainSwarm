# Phase 0 Research: Training Client Configuration, Dependency Injection, and Smoke Test

**Feature Branch**: `014-client-config-smoke-test`  
**Date**: 2026-09-04  
**Author**: Antigravity  
**Status**: Completed  

---

## 1. Centralized Configuration Management Strategy

### Decision
Create a dedicated `src/Client/config/` module centered on `ConfigManager` and an immutable `ClientConfig` dataclass. The `ConfigManager` is the sole module in `src/Client` permitted to import `os` or invoke `os.getenv` / `os.environ`. It loads `.env` if present, validates all required configuration (such as `COORDINATOR_ADDRESS`), parses numeric types (e.g., `float(REQUEST_TIMEOUT_SECONDS)`, `float(SHARD_TRAINING_TIME_LIMIT)`, `float(SHARD_SAFETY_FACTOR)`), and applies documented defaults for optional settings.

### Rationale
- **Fail-Fast Reliability**: Malformed or missing environment configuration is caught immediately during application initialization rather than at the moment a network request or training job runs.
- **Single Source of Truth**: Eliminates conflicting fallback values, duplicated `.env` parsing, and hidden dependencies across disparate infrastructure adapters.
- **Strict Compliance**: Satisfies Constitutional Principle IV (configuration-driven behavior) and the specification's non-negotiable Rule 1 (Configuration is centralized).

### Alternatives Considered
- *Pydantic `BaseSettings`*: Rejected because it introduces a heavyweight third-party dependency, violating Constitutional Principle V (NO LARGE FRAMEWORKS / MVP simplicity).
- *Distributed config dictionary*: Rejected because string-keyed untyped dictionaries lack IDE auto-completion, static type checking, and explicit attribute contracts.
- *Preserving existing `config.py` as a single file*: Migrated into `src/Client/config/` package (`config_manager.py` + `__init__.py`) to support clear modular organization, with backward-compatibility aliasing if needed.

---

## 2. Dependency Injection / Composition Root Pattern

### Decision
Implement a pure-Python `DIContainer` in `src/Client/dependency_injection/container.py` acting strictly as a **Composition Root**. The container receives a `ClientConfig` (or instantiates `ConfigManager`) and explicitly constructs all infrastructure persistence instances (`DatabaseManager`, `TrainingShardRepository`), adapters (`CoordinatorAdapter`), external engine orchestrators (`TrainingOrchestrator`), and application command handlers (`SmokeTestCommandHandler`).

### Rationale
- **Constructor Injection Only**: Dependencies are explicitly declared in class `__init__` signatures and passed at construction time.
- **No Third-Party Overhead**: Requires zero third-party packages (e.g. `injector`, `dependency-injector`, `pinject`), adhering strictly to MVP principles.
- **Prohibition of Service Locator Pattern**: Application code (`SmokeTestCommandHandler`, domain services) never receives or queries `container.get()` or `container.resolve()`. Application objects only interact with explicit collaborator contracts.

### Alternatives Considered
- *Third-party DI container library*: Rejected due to Constitutional Principle V (NO LARGE FRAMEWORKS) and specification section 19.
- *Global Service Locator (`ServiceLocator.get(...)`)*: Rejected because service locators hide dependencies, create hidden global state, and complicate isolated testing.
- *Factory methods scattered across modules*: Rejected because scattered factory functions decentralize dependency wiring and recreate coupling.

---

## 3. Existing Client Constructors & Environment Audit

### Decision
Audit and refactor all existing classes in `src/Client` that currently access environment variables:
1. `src/Client/infrastructure/adapters/coordinator_adapter.py`: Remove `os.getenv(ENV_COORDINATOR_ADDRESS)` and `os.getenv(FALLBACK_ENV_COORDINATOR_URL)`. `CoordinatorAdapter.__init__` now requires `coordinator_address: str` as an explicit parameter.
2. `src/Client/infrastructure/persistence/database.py`: Remove `os.getenv(ENV_DB_PATH)`. `DatabaseManager.__init__` now accepts `db_path: Union[str, Path]` directly.
3. `src/Client/main.py`: Updated to initialize `ConfigManager`, assemble `DIContainer`, and launch the application.
4. Verify via automated scan that 0 occurrences of `os.getenv`, `os.environ`, or `environ.get` remain outside `src/Client/config/`.

### Rationale
- Removes duplicate environment resolution logic (e.g. `COORDINATOR_ADDRESS` was previously checked in both `config.py` and `coordinator_adapter.py`).
- Guarantees that adapters and persistence implementations can be tested or wired with arbitrary configurations without mutating global environment variables.

### Alternatives Considered
- *Leaving optional fallback to `os.getenv` in constructors*: Rejected because it violates specification Section 16 & 17, and creates ambient configuration drift.

---

## 4. Smoke Test Execution & Timing Precision

### Decision
Implement `SmokeTestCommand`, `SmokeTestCommandHandler`, and `SmokeTestResult` under `src/Client/application/smoke_test/`. The handler receives `training_orchestrator: TrainingOrchestrator`, `shard_training_time_limit: float`, `working_directory: Union[str, Path]`, and `safety_factor: float` via constructor.
When `handle(command)` is invoked:
1. Validates `command.sample_count > 0`.
2. Records monotonic start time using `time.perf_counter()`.
3. Calls `self.training_orchestrator.run(task=command.training_task_model, working_directory=self.working_directory)`.
4. Records elapsed monotonic time `duration_seconds = time.perf_counter() - start_time`.
5. Checks `duration_seconds > 0.0`. If non-positive or sub-millisecond, treats calculation as invalid to prevent division by zero.
6. Calculates throughput and shard sample estimates.
7. Deletes the generated model delta artifact (`.safetensors`) from the working directory per clarification session decisions.
8. Returns `SmokeTestResult(success=True, ...)`.
9. In case of training error: catches `Exception`, logs failure diagnostics with full exception details, ensures shard sizing is `None`, and returns `SmokeTestResult(success=False, error=str(e))`.

### Rationale
- **Zero Mocks (Constitutional Principle VI)**: Executes the actual `TrainingOrchestrator` lifecycle (`validate`, `prepare`, `train`, `save_result`) against the real PyTorch engine.
- **High-Precision Monotonic Time**: `time.perf_counter()` is unaffected by system clock adjustments or daylight savings, ensuring strictly monotonic elapsed time calculation.
- **Non-Fatal Graceful Degradation**: Protects the client application from crashing while clearly signaling failure to downstream workflows.

### Alternatives Considered
- *Using `time.time()`*: Rejected because wall-clock time can skew or jump backwards during NTP synchronization.
- *Synthetic / Dry-Run Training Path*: Strictly prohibited by specification Section 4.1 & 28 and Constitutional Principle VI.

---

## 5. Shard Sizing Arithmetic & Safety Factor Formulation

### Decision
Calculate shard capacity as follows:
$$ \text{samples\_per\_second} = \frac{\text{sample\_count}}{\text{training\_time\_seconds}} $$
$$ \text{estimated\_samples\_per\_shard} = \max\left(1, \text{int}\left(\text{samples\_per\_second} \times \text{shard\_training\_time\_limit\_seconds}\right)\right) $$
$$ \text{recommended\_samples\_per\_shard} = \max\left(1, \text{int}\left(\text{estimated\_samples\_per\_shard} \times \text{shard\_safety\_factor}\right)\right) $$

If `duration_seconds <= 0.0` or training fails:
`training_time_seconds = None`, `samples_per_second = None`, `estimated_samples_per_shard = None`, `recommended_samples_per_shard = None`.

### Rationale
- Truncation via `int()` ensures integer sample counts.
- `max(1, ...)` guarantees that a successful run never produces zero or negative shard sizes.
- Separating estimated from recommended sizes allows dynamic tuning of safety margins without modifying core throughput metrics.

### Alternatives Considered
- *Floating-point shard sizes*: Rejected because dataset samples are discrete units.
- *Rounding up via `math.ceil()`*: Rejected because optimistic rounding could cause shards to exceed the time budget on slower workers.

---

## 6. Output Artifact Cleanup & Disk Management

### Decision
Per the clarification session decision, upon completion of a successful smoke test training run, `SmokeTestCommandHandler` identifies the generated `.safetensors` delta file in `working_directory` (from `result.delta.path` or task metadata) and deletes it via `path.unlink(missing_ok=True)`. If a filesystem permission error or file lock occurs, it logs a warning but does not fail the smoke test result.

### Rationale
- Smoke tests are diagnostic benchmarks, not production training runs. Leaving multi-megabyte delta files after every startup benchmark would quickly exhaust disk space.
- Defensive cleanup logging prevents OS-level locking hiccups from corrupting a legitimate training benchmark.

---

## 7. Quality Gate & Verification Harness

### Decision
Implement active verification under `samples/client_smoke_test/verify_client_config_smoke_test.py`:
1. Verify `ConfigManager` fast-fail with missing required variables, and valid default resolution.
2. Verify `DIContainer` construction and component wiring.
3. Verify constructor refactoring of `CoordinatorAdapter` and `DatabaseManager`.
4. Verify 0 occurrences of `os.getenv` outside `src/Client/config/`.
5. Execute end-to-end `SmokeTestCommandHandler` on a valid task, validating monotonic timing, throughput calculation, recommended shard sizing, and delta cleanup.
6. Execute `SmokeTestCommandHandler` on an invalid/failing task, validating `success=False` and non-null error propagation.

### Rationale
Conforms strictly to Constitutional Principle VII (Mandatory Post-Change Quality Gate: compilability, runnability, and correctness via active zero-mock execution).
