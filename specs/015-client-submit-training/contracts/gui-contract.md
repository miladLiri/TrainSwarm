# Presentation Contract: PyQt6 Desktop Graphical User Interface

**Feature Branch**: `015-client-submit-training`  
**Date**: 2026-09-05  
**Spec Reference**: [spec.md](file:///C:/Users/azure-dev/dev/TrainSwarm/specs/015-client-submit-training/spec.md)

---

## 1. GUI Architecture & Separation of Concerns

The GUI resides under [`src/Client/presentation/gui/`](file:///C:/Users/azure-dev/dev/TrainSwarm/src/Client/presentation) and adheres to Model-View-Presenter (MVP).

- **View (`MainWindow`)**: Owns `QMainWindow`, `QTabWidget`, form layouts, file selection dialogs, buttons, progress bar, and log text edit. Does NOT execute application business logic or import SQLite/Coordinator adapters directly.
- **Presenter / Worker (`SubmitTrainingWorker`)**: A `QThread` subclass that receives the command payload from the UI thread, invokes `SubmitTrainingCommandHandler.handle()`, and emits PyQt signals back to the UI thread.
- **Signals**:
  - `phase_changed(str)`: Emits status messages (e.g. `"Staging model checkpoint..."`, `"Executing smoke test..."`, `"Partitioning dataset..."`).
  - `progress_updated(int)`: Updates the inline progress bar (0 to 100%).
  - `log_emitted(str)`: Streams diagnostic lines to the Logs tab.
  - `submission_succeeded(SubmitTrainingResult)`: Signals completion to display success banner with task IDs.
  - `submission_failed(str)`: Signals error message to display modal error dialog.

---

## 2. Window Layout & Component Specification

```text
+-------------------------------------------------------------------------+
| TrainSwarm Training Client                                              |
+-------------------------------------------------------------------------+
| [ Submit Training ]  [ Logs ]                                           |
+-------------------------------------------------------------------------+
| Model Checkpoint (.pt2): [ C:/models/cnn_model.pt2      ] [ Browse... ] |
| Dataset File (.pt):      [ C:/data/dataset.pt           ] [ Browse... ] |
| Model Version:           [ v1.0                         ]               |
| Model Type:              [ Canonical PyTorch (Torch2) v ]               |
|                                                                         |
| --- Training Hyperparameters ----------------------------------------- |
| Batch Size: [ 2   ]      Epochs: [ 1   ]      Grad Accum Steps: [ 1   ] |
| Optimizer:  [ AdamW              v ]  Learning Rate: [ 0.001          ] |
| Loss:       [ MSELoss            v ]  Weight Decay:  [ 0.01           ] |
| Scheduler:  [ CosineAnnealingLR  v ]  Max Steps:     [ None           ] |
|                                                                         |
| [ Submit Training ]                                                     |
|                                                                         |
| Progress: [===============================>                ] 65%        |
| Status: Partitioning dataset into shards...                             |
+-------------------------------------------------------------------------+
```

### Form Controls & Validations

1. **Model Checkpoint**: Text field with "Browse..." button restricted to `.pt2` file extension.
2. **Dataset File**: Text field with "Browse..." button restricted to `.pt` file extension.
3. **Model Version**: Mandatory text field, non-empty.
4. **Model Type Dropdown**: Pre-populated with supported enum values (`canonical_torch`).
5. **Optimizer Dropdown**: Pre-populated with registry keys (`AdamW`, `SGD`).
6. **Loss Criterion Dropdown**: Pre-populated with registry keys (`MSELoss`, `CrossEntropyLoss`, `L1Loss`, `SmoothL1Loss`, `BCEWithLogitsLoss`).
7. **Scheduler Dropdown**: Pre-populated with registry keys (`None`, `CosineAnnealingLR`, `StepLR`, `LinearLR`, `ConstantLR`, `ExponentialLR`).
8. **Hyperparameter Form**: Numeric spinboxes with min/max bounds (Batch size >= 1, Epochs >= 1, Learning rate > 0.0).

---

## 3. Launching the GUI

The desktop GUI can be launched directly via:

```bash
python main.py gui
```

If launched in a headless environment without an active display server (`DISPLAY` or `WAYLAND_DISPLAY` unset on Linux), the application outputs an error:
```text
[Client] [ERROR] No graphical display detected. Please run the client in CLI mode (e.g. python main.py submit-training --help).
```
