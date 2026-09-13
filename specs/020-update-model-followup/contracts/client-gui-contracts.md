# Presentation UI Contracts: Client GUI & CLI

**Feature**: `020-update-model-followup`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. GUI Tab: "Training Shards"

### Structure & Layout
- **Container**: `QTabWidget` page labeled `"Training Shards"`.
- **Controls**:
  - `QTableWidget` (`shards_table`):
    - Columns: `Model ID`, `Version`, `Shard ID`, `Status`, `Trainer Node ID`, `Samples`
    - Read-only cells, full row selection, sortable columns.
  - `QPushButton` (`refresh_button`):
    - Label: `"Refresh Shards"`
    - Action: Invokes `GetTrainingShardsQueryHandler.handle()` and repopulates `shards_table`.
- **Status Styles**:
  - `completed`: Green text badge / `#22c55e`
  - `training`: Cyan text badge / `#38bdf8`
  - `ready` / `created`: Amber text badge / `#f59e0b`
  - `failed`: Red text badge / `#ef4444`

---

## 2. GUI Tab: "Trained Versions"

### Structure & Layout
- **Container**: `QTabWidget` page labeled `"Trained Versions"`.
- **Controls**:
  - `QTableWidget` (`trained_models_table`):
    - Columns: `Model ID`, `Version`, `Model Type`, `Dataset ID`, `Artifact Path`
    - Selection behavior: Single row selection.
  - `QPushButton` (`save_artifact_button`):
    - Label: `"Export / Save Artifact..."`
    - Action:
      1. Determines selected model record from table.
      2. Opens `QFileDialog.getSaveFileName(self, "Save Model Artifact", default_filename, "PyTorch Checkpoints (*.pt2)")`.
      3. Copies `model_artifact_path` to user-chosen destination using `shutil.copy2`.
      4. Displays confirmation via `QMessageBox.information`.
  - `QPushButton` (`refresh_models_button`):
    - Label: `"Refresh Models"`
    - Action: Re-executes `GetTrainedModelsQueryHandler.handle()` and updates table.

---

## 3. Console CLI Subcommand: `watch-shards`

### CLI Syntax
```bash
python main.py watch-shards [--model-id <UUID>]
```

### Terminal Output Contract
```text
========================================================================================
                       TrainSwarm Client: Active Training Shards                        
========================================================================================
Model ID                             Ver   Shard ID   Status      Trainer Node       
----------------------------------------------------------------------------------------
a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d 1     shard_0    COMPLETED   trainer-node-1     
a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d 1     shard_1    COMPLETED   trainer-node-2     
========================================================================================
Press [Enter] to refresh, or type 'q' and press [Enter] to exit:
```
- **Loop**: Continuously waits for user input. If `Enter` (empty string), re-queries and reprints table. If `'q'` or `'quit'`, exits with code 0.
