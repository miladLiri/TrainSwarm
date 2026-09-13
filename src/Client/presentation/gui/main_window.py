"""PyQt6 MainWindow presentation layer for TrainSwarm Client.

Provides a modern, responsive desktop interface with two functional tabs:
- Tab 1: Submit Training (composed of Section 1: Artifacts and Section 2: Training Parameters).
- Tab 2: Logs (Live event diagnostic streaming and clear utility).
- Persistent Footer: Global submit workflow action, styled progress bar, and status banner.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Minimal fallback stubs for syntax compilation in headless environments
    class QMainWindow:  # type: ignore
        def __init__(self, parent: Any = None) -> None:
            pass

    class QWidget:  # type: ignore
        def __init__(self, parent: Any = None) -> None:
            pass

from application.submit_training import (
    SubmitTrainingCommand,
    SubmitTrainingResult,
    SubmitTrainingValidationError,
)
from dependency_injection import DIContainer
from presentation.gui.worker import SubmitTrainingWorker

logger = logging.getLogger("trainswarm.client.gui")

DARK_STYLE = """
QMainWindow {
    background-color: #0a0d14;
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}

QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0f172a;
    border-radius: 12px;
    margin-top: -1px;
}

QTabBar::tab {
    background-color: #141d2e;
    color: #94a3b8;
    padding: 10px 24px;
    margin-right: 6px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #1e293b;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #0f172a;
    color: #38bdf8;
    border-top: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #1e293b;
    color: #f1f5f9;
}

QGroupBox {
    background-color: #131c2e;
    border: 1px solid #233149;
    border-radius: 10px;
    margin-top: 18px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
    font-size: 13px;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 2px 10px;
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 5px;
    color: #38bdf8;
}

QGroupBox QGroupBox {
    background-color: #0c1424;
    border: 1px solid #1b283d;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    font-size: 12px;
    color: #7dd3fc;
}

QGroupBox QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 8px;
    background-color: #172439;
    border: 1px solid #263c5d;
    border-radius: 4px;
    color: #7dd3fc;
    font-size: 11px;
}

QLabel {
    color: #cbd5e1;
    font-size: 12px;
}

QLabel.field-hint {
    color: #64748b;
    font-size: 11px;
    font-style: italic;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0a0f1d;
    border: 1px solid #2b3950;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
    font-size: 12px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
    background-color: #0e1626;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QCheckBox {
    color: #cbd5e1;
    font-size: 12px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #334155;
    background-color: #0a0f1d;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

QPushButton#submit_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:0.5 #6366f1, stop:1 #06b6d4);
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
    border-radius: 8px;
    border: none;
    padding: 12px 24px;
}

QPushButton#submit_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:0.5 #4f46e5, stop:1 #0891b2);
}

QPushButton#submit_btn:disabled {
    background: #1e293b;
    color: #475569;
}

QPushButton.secondary-btn {
    background-color: #1e293b;
    color: #cbd5e1;
    border-radius: 6px;
    border: 1px solid #334155;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton.secondary-btn:hover {
    background-color: #334155;
    color: #f8fafc;
    border-color: #475569;
}

QProgressBar {
    background-color: #0a0f1d;
    border: 1px solid #233149;
    border-radius: 8px;
    text-align: center;
    color: #f8fafc;
    font-weight: bold;
    height: 22px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #06b6d4);
    border-radius: 7px;
}

QPlainTextEdit {
    background-color: #050811;
    color: #38bdf8;
    border: 1px solid #1e293b;
    border-radius: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 10px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QTableWidget {
    background-color: #0c1424;
    color: #e2e8f0;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 8px;
    font-size: 12px;
    selection-background-color: #1e3a8a;
    selection-color: #f8fafc;
}

QHeaderView::section {
    background-color: #141d2e;
    color: #94a3b8;
    padding: 6px;
    font-weight: 600;
    border: 1px solid #1e293b;
}
"""


class MainWindow(QMainWindow):
    """Main application window for the TrainSwarm Client graphical interface."""

    def __init__(self, container: DIContainer, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is required to instantiate MainWindow.")

        self._container = container
        self._worker: Optional[SubmitTrainingWorker] = None

        self.setWindowTitle("TrainSwarm Training Client")
        self.setMinimumSize(880, 750)
        self.setStyleSheet(DARK_STYLE)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct the tabbed GUI layout with Submit Training and Logs tabs."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # Tab Widget (2 Tabs: Submit Training and Logs)
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)

        # Tab 1: Submit Training (contains Section 1: Artifacts and Section 2: Training Parameters)
        self.submit_tab = QWidget()
        self.artifacts_tab = self.submit_tab  # Backwards-compatible alias
        self.params_tab = self.submit_tab     # Backwards-compatible alias
        self._setup_submit_tab()
        self.tabs.addTab(self.submit_tab, "Submit Training")

        # Tab 2: Logs
        self.logs_tab = QWidget()
        self._setup_logs_tab()
        self.tabs.addTab(self.logs_tab, "Logs")

        # Tab 3: Training Shards
        self.shards_tab = QWidget()
        self._setup_shards_tab()
        self.tabs.addTab(self.shards_tab, "Training Shards")

        # Tab 4: Trained Versions
        self.trained_versions_tab = QWidget()
        self._setup_trained_versions_tab()
        self.tabs.addTab(self.trained_versions_tab, "Trained Versions")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Persistent Global Footer (Submit Action, Progress Bar & Status Banner)
        self._setup_persistent_footer(main_layout)

    def _setup_submit_tab(self) -> None:
        """Construct the Submit Training tab with two main sections:
        - Section 1: Artifacts (Model architecture, checkpoints, and datasets)
        - Section 2: Training Parameters (Merged lifecycle, dynamic optimizer, loss, and scheduler)
        """
        outer_layout = QVBoxLayout(self.submit_tab)
        outer_layout.setContentsMargins(2, 2, 2, 2)

        scroll_area = QScrollArea(self.submit_tab)
        scroll_area.setWidgetResizable(True)
        outer_layout.addWidget(scroll_area)

        content_container = QWidget()
        scroll_area.setWidget(content_container)
        layout = QVBoxLayout(content_container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # ======================================================================
        # SECTION 1: ARTIFACTS
        # ======================================================================
        self.artifacts_group = QGroupBox("1. Artifacts")
        artifacts_layout = QFormLayout(self.artifacts_group)
        artifacts_layout.setSpacing(12)

        # 1. Model Engine Type (FIRST INPUT)
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["canonical_torch", "canonical_causal_decoder"])
        self.model_type_combo.currentTextChanged.connect(self._on_model_type_changed)
        artifacts_layout.addRow("Model Engine Type:", self.model_type_combo)

        # 2. Model Checkpoint Picker (.pt2 for canonical_torch)
        model_box = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText("Path to exported PyTorch 2 model (.pt2)")
        self.model_browse_btn = QPushButton("Browse...")
        self.model_browse_btn.setProperty("class", "secondary-btn")
        self.model_browse_btn.clicked.connect(self._browse_model_file)
        model_box.addWidget(self.model_path_edit)
        model_box.addWidget(self.model_browse_btn)
        self.model_label = QLabel("Model Checkpoint (.pt2):")
        artifacts_layout.addRow(self.model_label, model_box)

        # 3. Dataset File Picker (.pt for canonical_torch)
        dataset_box = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("Path to canonical PyTorch dataset (.pt)")
        self.dataset_browse_btn = QPushButton("Browse...")
        self.dataset_browse_btn.setProperty("class", "secondary-btn")
        self.dataset_browse_btn.clicked.connect(self._browse_dataset_file)
        dataset_box.addWidget(self.dataset_path_edit)
        dataset_box.addWidget(self.dataset_browse_btn)
        self.dataset_label = QLabel("Dataset File (.pt):")
        artifacts_layout.addRow(self.dataset_label, dataset_box)

        # 4. Model Version
        self.model_version_edit = QLineEdit("v1.0")
        artifacts_layout.addRow("Model Version:", self.model_version_edit)

        # Quick Guidance Sub-box inside Section 1
        info_box = QFrame()
        info_box.setStyleSheet(
            "background-color: #0b121e; border: 1px solid #1a273b; border-radius: 6px; padding: 10px;"
        )
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_title = QLabel("ℹ Artifact Staging & Sizing Workflow")
        info_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 11px;")
        info_layout.addWidget(info_title)
        info_desc = QLabel(
            "The model checkpoint and dataset will be validated, sized via an autograd smoke test, "
            "partitioned into local shards, and registered with the TrainSwarm Coordinator."
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_layout.addWidget(info_desc)
        artifacts_layout.addRow(info_box)

        layout.addWidget(self.artifacts_group)

        # ======================================================================
        # SECTION 2: TRAINING PARAMETERS
        # ======================================================================
        self.params_group = QGroupBox("2. Training Parameters")
        params_layout = QVBoxLayout(self.params_group)
        params_layout.setSpacing(14)
        params_layout.setContentsMargins(14, 18, 14, 14)

        # 2.A Canonical PyTorch Parameters Container
        self.torch_params_widget = QWidget()
        torch_params_layout = QVBoxLayout(self.torch_params_widget)
        torch_params_layout.setContentsMargins(0, 0, 0, 0)
        torch_params_layout.setSpacing(14)

        # 2.1 Lifecycle & Batching Sub-group
        lifecycle_subgroup = QGroupBox("Lifecycle & Batching")
        lifecycle_layout = QGridLayout(lifecycle_subgroup)
        lifecycle_layout.setHorizontalSpacing(14)
        lifecycle_layout.setVerticalSpacing(10)

        lifecycle_layout.addWidget(QLabel("Batch Size:"), 0, 0)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 1048576)
        self.batch_size_spin.setValue(2)
        lifecycle_layout.addWidget(self.batch_size_spin, 0, 1)

        lifecycle_layout.addWidget(QLabel("Epochs:"), 0, 2)
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 10000)
        self.epochs_spin.setValue(1)
        lifecycle_layout.addWidget(self.epochs_spin, 0, 3)

        lifecycle_layout.addWidget(QLabel("Grad Accum Steps:"), 0, 4)
        self.grad_accum_spin = QSpinBox()
        self.grad_accum_spin.setRange(1, 1000)
        self.grad_accum_spin.setValue(1)
        lifecycle_layout.addWidget(self.grad_accum_spin, 0, 5)

        self.shuffle_check = QCheckBox("Shuffle Shard Data")
        self.shuffle_check.setChecked(True)
        lifecycle_layout.addWidget(self.shuffle_check, 1, 0, 1, 2)

        lifecycle_layout.addWidget(QLabel("Max Steps:"), 1, 2)
        self.max_steps_edit = QLineEdit()
        self.max_steps_edit.setPlaceholderText("Optional (e.g. 500)")
        lifecycle_layout.addWidget(self.max_steps_edit, 1, 3)

        lifecycle_layout.addWidget(QLabel("Max Grad Norm:"), 1, 4)
        self.max_grad_norm_edit = QLineEdit()
        self.max_grad_norm_edit.setPlaceholderText("Optional (e.g. 1.0)")
        lifecycle_layout.addWidget(self.max_grad_norm_edit, 1, 5)

        torch_params_layout.addWidget(lifecycle_subgroup)

        # 2.2 Dynamic Optimizer Configuration
        optim_subgroup = QGroupBox("Optimizer Configuration")
        optim_main_layout = QVBoxLayout(optim_subgroup)

        top_optim_box = QHBoxLayout()
        top_optim_box.addWidget(QLabel("Optimizer Type:"))
        self.optimizer_combo = QComboBox()
        self.optimizer_combo.addItems(["AdamW", "SGD"])
        self.optimizer_combo.currentTextChanged.connect(self._on_optimizer_changed)
        top_optim_box.addWidget(self.optimizer_combo)
        top_optim_box.addStretch()
        optim_main_layout.addLayout(top_optim_box)

        self.optim_stack = QStackedWidget()

        # AdamW Panel
        self.adamw_widget = QWidget()
        adamw_layout = QGridLayout(self.adamw_widget)
        adamw_layout.addWidget(QLabel("Learning Rate:"), 0, 0)
        self.adamw_lr_spin = QDoubleSpinBox()
        self.adamw_lr_spin.setRange(0.0000001, 10.0)
        self.adamw_lr_spin.setDecimals(6)
        self.adamw_lr_spin.setValue(0.001)
        adamw_layout.addWidget(self.adamw_lr_spin, 0, 1)

        adamw_layout.addWidget(QLabel("Weight Decay:"), 0, 2)
        self.adamw_wd_spin = QDoubleSpinBox()
        self.adamw_wd_spin.setRange(0.0, 1.0)
        self.adamw_wd_spin.setDecimals(6)
        self.adamw_wd_spin.setValue(0.01)
        adamw_layout.addWidget(self.adamw_wd_spin, 0, 3)

        adamw_layout.addWidget(QLabel("Betas (b1, b2):"), 1, 0)
        betas_box = QHBoxLayout()
        self.adamw_b1_spin = QDoubleSpinBox()
        self.adamw_b1_spin.setRange(0.0, 0.999)
        self.adamw_b1_spin.setValue(0.9)
        self.adamw_b1_spin.setDecimals(3)
        self.adamw_b2_spin = QDoubleSpinBox()
        self.adamw_b2_spin.setRange(0.0, 0.9999)
        self.adamw_b2_spin.setValue(0.999)
        self.adamw_b2_spin.setDecimals(4)
        betas_box.addWidget(self.adamw_b1_spin)
        betas_box.addWidget(self.adamw_b2_spin)
        adamw_layout.addLayout(betas_box, 1, 1)

        adamw_layout.addWidget(QLabel("Eps (epsilon):"), 1, 2)
        self.adamw_eps_edit = QLineEdit("1e-8")
        adamw_layout.addWidget(self.adamw_eps_edit, 1, 3)

        self.adamw_amsgrad_check = QCheckBox("AMSGrad Variant")
        self.adamw_amsgrad_check.setChecked(False)
        adamw_layout.addWidget(self.adamw_amsgrad_check, 2, 0, 1, 2)

        self.optim_stack.addWidget(self.adamw_widget)

        # SGD Panel
        self.sgd_widget = QWidget()
        sgd_layout = QGridLayout(self.sgd_widget)
        sgd_layout.addWidget(QLabel("Learning Rate:"), 0, 0)
        self.sgd_lr_spin = QDoubleSpinBox()
        self.sgd_lr_spin.setRange(0.0000001, 10.0)
        self.sgd_lr_spin.setDecimals(6)
        self.sgd_lr_spin.setValue(0.01)
        sgd_layout.addWidget(self.sgd_lr_spin, 0, 1)

        sgd_layout.addWidget(QLabel("Momentum:"), 0, 2)
        self.sgd_momentum_spin = QDoubleSpinBox()
        self.sgd_momentum_spin.setRange(0.0, 1.0)
        self.sgd_momentum_spin.setDecimals(4)
        self.sgd_momentum_spin.setValue(0.0)
        sgd_layout.addWidget(self.sgd_momentum_spin, 0, 3)

        sgd_layout.addWidget(QLabel("Dampening:"), 1, 0)
        self.sgd_dampening_spin = QDoubleSpinBox()
        self.sgd_dampening_spin.setRange(0.0, 1.0)
        self.sgd_dampening_spin.setDecimals(4)
        self.sgd_dampening_spin.setValue(0.0)
        sgd_layout.addWidget(self.sgd_dampening_spin, 1, 1)

        sgd_layout.addWidget(QLabel("Weight Decay:"), 1, 2)
        self.sgd_wd_spin = QDoubleSpinBox()
        self.sgd_wd_spin.setRange(0.0, 1.0)
        self.sgd_wd_spin.setDecimals(6)
        self.sgd_wd_spin.setValue(0.0)
        sgd_layout.addWidget(self.sgd_wd_spin, 1, 3)

        self.sgd_nesterov_check = QCheckBox("Nesterov Momentum")
        self.sgd_nesterov_check.setChecked(False)
        sgd_layout.addWidget(self.sgd_nesterov_check, 2, 0, 1, 2)

        self.optim_stack.addWidget(self.sgd_widget)
        optim_main_layout.addWidget(self.optim_stack)
        torch_params_layout.addWidget(optim_subgroup)

        # 2.3 Dynamic Loss Criterion Configuration
        loss_subgroup = QGroupBox("Loss Criterion Configuration")
        loss_layout = QGridLayout(loss_subgroup)

        loss_layout.addWidget(QLabel("Criterion Type:"), 0, 0)
        self.loss_combo = QComboBox()
        self.loss_combo.addItems([
            "MSELoss",
            "CrossEntropyLoss",
            "L1Loss",
            "SmoothL1Loss",
            "BCEWithLogitsLoss",
        ])
        self.loss_combo.currentTextChanged.connect(self._on_loss_changed)
        loss_layout.addWidget(self.loss_combo, 0, 1)

        loss_layout.addWidget(QLabel("Reduction:"), 0, 2)
        self.loss_reduction_combo = QComboBox()
        self.loss_reduction_combo.addItems(["mean", "sum", "none"])
        loss_layout.addWidget(self.loss_reduction_combo, 0, 3)

        # Criterion specific parameter containers
        self.smooth_l1_label = QLabel("SmoothL1 Beta:")
        self.smooth_l1_beta_spin = QDoubleSpinBox()
        self.smooth_l1_beta_spin.setRange(0.0, 100.0)
        self.smooth_l1_beta_spin.setValue(1.0)
        loss_layout.addWidget(self.smooth_l1_label, 1, 0)
        loss_layout.addWidget(self.smooth_l1_beta_spin, 1, 1)
        self.smooth_l1_label.hide()
        self.smooth_l1_beta_spin.hide()

        self.ce_label = QLabel("Label Smoothing:")
        self.ce_smoothing_spin = QDoubleSpinBox()
        self.ce_smoothing_spin.setRange(0.0, 1.0)
        self.ce_smoothing_spin.setValue(0.0)
        loss_layout.addWidget(self.ce_label, 1, 0)
        loss_layout.addWidget(self.ce_smoothing_spin, 1, 1)
        self.ce_label.hide()
        self.ce_smoothing_spin.hide()

        torch_params_layout.addWidget(loss_subgroup)

        # 2.4 Dynamic Learning Rate Scheduler Configuration
        sched_subgroup = QGroupBox("Learning Rate Scheduler")
        sched_main_layout = QVBoxLayout(sched_subgroup)

        top_sched_box = QHBoxLayout()
        top_sched_box.addWidget(QLabel("Scheduler Type:"))
        self.scheduler_combo = QComboBox()
        self.scheduler_combo.addItems([
            "CosineAnnealingLR",
            "None",
            "StepLR",
            "LinearLR",
            "ConstantLR",
            "ExponentialLR",
        ])
        self.scheduler_combo.currentTextChanged.connect(self._on_scheduler_changed)
        top_sched_box.addWidget(self.scheduler_combo)
        top_sched_box.addStretch()
        sched_main_layout.addLayout(top_sched_box)

        self.sched_stack = QStackedWidget()

        # 0: CosineAnnealingLR Panel
        self.cosine_widget = QWidget()
        cosine_layout = QGridLayout(self.cosine_widget)
        cosine_layout.addWidget(QLabel("T_max (Epochs):"), 0, 0)
        self.cosine_tmax_spin = QSpinBox()
        self.cosine_tmax_spin.setRange(1, 10000)
        self.cosine_tmax_spin.setValue(10)
        cosine_layout.addWidget(self.cosine_tmax_spin, 0, 1)

        cosine_layout.addWidget(QLabel("eta_min (Min LR):"), 0, 2)
        self.cosine_etamin_spin = QDoubleSpinBox()
        self.cosine_etamin_spin.setRange(0.0, 1.0)
        self.cosine_etamin_spin.setDecimals(6)
        self.cosine_etamin_spin.setValue(0.0)
        cosine_layout.addWidget(self.cosine_etamin_spin, 0, 3)
        self.sched_stack.addWidget(self.cosine_widget)

        # 1: None Panel
        self.none_widget = QWidget()
        none_layout = QHBoxLayout(self.none_widget)
        none_lbl = QLabel("No learning rate decay or scheduler configured.")
        none_lbl.setProperty("class", "field-hint")
        none_layout.addWidget(none_lbl)
        self.sched_stack.addWidget(self.none_widget)

        # 2: StepLR Panel
        self.step_widget = QWidget()
        step_layout = QGridLayout(self.step_widget)
        step_layout.addWidget(QLabel("Step Size:"), 0, 0)
        self.step_size_spin = QSpinBox()
        self.step_size_spin.setRange(1, 1000)
        self.step_size_spin.setValue(30)
        step_layout.addWidget(self.step_size_spin, 0, 1)

        step_layout.addWidget(QLabel("Gamma Multiplier:"), 0, 2)
        self.step_gamma_spin = QDoubleSpinBox()
        self.step_gamma_spin.setRange(0.0001, 1.0)
        self.step_gamma_spin.setDecimals(4)
        self.step_gamma_spin.setValue(0.1)
        step_layout.addWidget(self.step_gamma_spin, 0, 3)
        self.sched_stack.addWidget(self.step_widget)

        # 3: LinearLR Panel
        self.linear_widget = QWidget()
        linear_layout = QGridLayout(self.linear_widget)
        linear_layout.addWidget(QLabel("Start Factor:"), 0, 0)
        self.linear_start_spin = QDoubleSpinBox()
        self.linear_start_spin.setRange(0.0001, 10.0)
        self.linear_start_spin.setDecimals(6)
        self.linear_start_spin.setValue(0.333333)
        linear_layout.addWidget(self.linear_start_spin, 0, 1)

        linear_layout.addWidget(QLabel("End Factor:"), 0, 2)
        self.linear_end_spin = QDoubleSpinBox()
        self.linear_end_spin.setRange(0.0001, 10.0)
        self.linear_end_spin.setValue(1.0)
        linear_layout.addWidget(self.linear_end_spin, 0, 3)

        linear_layout.addWidget(QLabel("Total Iterations:"), 1, 0)
        self.linear_iters_spin = QSpinBox()
        self.linear_iters_spin.setRange(1, 1000)
        self.linear_iters_spin.setValue(5)
        linear_layout.addWidget(self.linear_iters_spin, 1, 1)
        self.sched_stack.addWidget(self.linear_widget)

        # 4: ConstantLR Panel
        self.constant_widget = QWidget()
        constant_layout = QGridLayout(self.constant_widget)
        constant_layout.addWidget(QLabel("Factor:"), 0, 0)
        self.constant_factor_spin = QDoubleSpinBox()
        self.constant_factor_spin.setRange(0.0001, 10.0)
        self.constant_factor_spin.setDecimals(6)
        self.constant_factor_spin.setValue(0.333333)
        constant_layout.addWidget(self.constant_factor_spin, 0, 1)

        constant_layout.addWidget(QLabel("Total Iterations:"), 0, 2)
        self.constant_iters_spin = QSpinBox()
        self.constant_iters_spin.setRange(1, 1000)
        self.constant_iters_spin.setValue(5)
        constant_layout.addWidget(self.constant_iters_spin, 0, 3)
        self.sched_stack.addWidget(self.constant_widget)

        # 5: ExponentialLR Panel
        self.exp_widget = QWidget()
        exp_layout = QGridLayout(self.exp_widget)
        exp_layout.addWidget(QLabel("Gamma Multiplier:"), 0, 0)
        self.exp_gamma_spin = QDoubleSpinBox()
        self.exp_gamma_spin.setRange(0.0001, 1.0)
        self.exp_gamma_spin.setDecimals(4)
        self.exp_gamma_spin.setValue(0.9)
        exp_layout.addWidget(self.exp_gamma_spin, 0, 1)
        self.sched_stack.addWidget(self.exp_widget)

        sched_main_layout.addWidget(self.sched_stack)
        torch_params_layout.addWidget(sched_subgroup)
        params_layout.addWidget(self.torch_params_widget)

        # ======================================================================
        # 2.B CANONICAL CAUSAL DECODER PARAMETERS CONTAINER
        # ======================================================================
        self.ccdm_params_widget = QWidget()
        ccdm_outer_layout = QVBoxLayout(self.ccdm_params_widget)
        ccdm_outer_layout.setContentsMargins(0, 0, 0, 0)
        ccdm_outer_layout.setSpacing(14)

        self.ccdm_params_group = QGroupBox("Hugging Face Causal Decoder Training Configuration")
        ccdm_grid = QGridLayout(self.ccdm_params_group)
        ccdm_grid.setHorizontalSpacing(14)
        ccdm_grid.setVerticalSpacing(10)

        # Row 0: Batch Size, Epochs, Grad Accum Steps
        ccdm_grid.addWidget(QLabel("Batch Size:"), 0, 0)
        self.ccdm_batch_size_spin = QSpinBox()
        self.ccdm_batch_size_spin.setRange(1, 1048576)
        self.ccdm_batch_size_spin.setValue(2)
        ccdm_grid.addWidget(self.ccdm_batch_size_spin, 0, 1)

        ccdm_grid.addWidget(QLabel("Epochs:"), 0, 2)
        self.ccdm_epochs_spin = QSpinBox()
        self.ccdm_epochs_spin.setRange(1, 10000)
        self.ccdm_epochs_spin.setValue(1)
        ccdm_grid.addWidget(self.ccdm_epochs_spin, 0, 3)

        ccdm_grid.addWidget(QLabel("Grad Accum Steps:"), 0, 4)
        self.ccdm_grad_accum_spin = QSpinBox()
        self.ccdm_grad_accum_spin.setRange(1, 1000)
        self.ccdm_grad_accum_spin.setValue(1)
        ccdm_grid.addWidget(self.ccdm_grad_accum_spin, 0, 5)

        # Row 1: Learning Rate, Weight Decay, Seed
        ccdm_grid.addWidget(QLabel("Learning Rate:"), 1, 0)
        self.ccdm_lr_spin = QDoubleSpinBox()
        self.ccdm_lr_spin.setRange(0.00000001, 1.0)
        self.ccdm_lr_spin.setDecimals(8)
        self.ccdm_lr_spin.setValue(0.00005)
        ccdm_grid.addWidget(self.ccdm_lr_spin, 1, 1)

        ccdm_grid.addWidget(QLabel("Weight Decay:"), 1, 2)
        self.ccdm_wd_spin = QDoubleSpinBox()
        self.ccdm_wd_spin.setRange(0.0, 1.0)
        self.ccdm_wd_spin.setDecimals(6)
        self.ccdm_wd_spin.setValue(0.01)
        ccdm_grid.addWidget(self.ccdm_wd_spin, 1, 3)

        ccdm_grid.addWidget(QLabel("Seed:"), 1, 4)
        self.ccdm_seed_spin = QSpinBox()
        self.ccdm_seed_spin.setRange(0, 2147483647)
        self.ccdm_seed_spin.setValue(42)
        ccdm_grid.addWidget(self.ccdm_seed_spin, 1, 5)

        # Row 2: Scheduler Type, Warmup Steps, Warmup Ratio
        ccdm_grid.addWidget(QLabel("Scheduler Type:"), 2, 0)
        self.ccdm_scheduler_combo = QComboBox()
        self.ccdm_scheduler_combo.addItems([
            "linear",
            "cosine",
            "cosine_with_restarts",
            "polynomial",
            "constant",
            "constant_with_warmup",
        ])
        ccdm_grid.addWidget(self.ccdm_scheduler_combo, 2, 1)

        ccdm_grid.addWidget(QLabel("Warmup Steps:"), 2, 2)
        self.ccdm_warmup_steps_spin = QSpinBox()
        self.ccdm_warmup_steps_spin.setRange(0, 1000000)
        self.ccdm_warmup_steps_spin.setValue(0)
        ccdm_grid.addWidget(self.ccdm_warmup_steps_spin, 2, 3)

        ccdm_grid.addWidget(QLabel("Warmup Ratio:"), 2, 4)
        self.ccdm_warmup_ratio_spin = QDoubleSpinBox()
        self.ccdm_warmup_ratio_spin.setRange(0.0, 1.0)
        self.ccdm_warmup_ratio_spin.setDecimals(4)
        self.ccdm_warmup_ratio_spin.setValue(0.0)
        ccdm_grid.addWidget(self.ccdm_warmup_ratio_spin, 2, 5)

        # Row 3: Max Steps, Max Grad Norm
        ccdm_grid.addWidget(QLabel("Max Steps:"), 3, 0)
        self.ccdm_max_steps_edit = QLineEdit()
        self.ccdm_max_steps_edit.setPlaceholderText("Optional (e.g. 500)")
        ccdm_grid.addWidget(self.ccdm_max_steps_edit, 3, 1)

        ccdm_grid.addWidget(QLabel("Max Grad Norm:"), 3, 2)
        self.ccdm_max_grad_norm_edit = QLineEdit("1.0")
        self.ccdm_max_grad_norm_edit.setPlaceholderText("Optional (e.g. 1.0)")
        ccdm_grid.addWidget(self.ccdm_max_grad_norm_edit, 3, 3)

        # Row 4: Checkboxes (Shuffle, FP16, BF16)
        check_box_layout = QHBoxLayout()
        self.ccdm_shuffle_check = QCheckBox("Shuffle Shard Data")
        self.ccdm_shuffle_check.setChecked(True)
        check_box_layout.addWidget(self.ccdm_shuffle_check)

        self.ccdm_fp16_check = QCheckBox("FP16 Precision")
        self.ccdm_fp16_check.setChecked(False)
        check_box_layout.addWidget(self.ccdm_fp16_check)

        self.ccdm_bf16_check = QCheckBox("BF16 Precision")
        self.ccdm_bf16_check.setChecked(False)
        check_box_layout.addWidget(self.ccdm_bf16_check)
        check_box_layout.addStretch()

        ccdm_grid.addLayout(check_box_layout, 4, 0, 1, 6)

        ccdm_outer_layout.addWidget(self.ccdm_params_group)
        params_layout.addWidget(self.ccdm_params_widget)
        self.ccdm_params_widget.hide()

        layout.addWidget(self.params_group)
        layout.addStretch()

    def _setup_artifacts_tab(self) -> None:
        """Backwards-compatible stub."""
        pass

    def _setup_params_tab(self) -> None:
        """Backwards-compatible stub."""
        pass

    def _setup_logs_tab(self) -> None:
        """Construct Tab 3: Live diagnostic logging view."""
        layout = QVBoxLayout(self.logs_tab)
        layout.setContentsMargins(14, 14, 14, 14)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        clear_btn = QPushButton("Clear Logs")
        clear_btn.setProperty("class", "secondary-btn")
        clear_btn.clicked.connect(self.log_text.clear)
        btn_box.addWidget(clear_btn)
        layout.addLayout(btn_box)

    def _setup_shards_tab(self) -> None:
        """Construct Tab 3: Active and completed training shards view."""
        layout = QVBoxLayout(self.shards_tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Shards Table
        self.shards_table = QTableWidget()
        self.shards_table.setColumnCount(6)
        self.shards_table.setHorizontalHeaderLabels([
            "Model ID", "Version", "Shard ID", "Status", "Trainer Node ID", "Samples"
        ])
        self.shards_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.shards_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.shards_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.shards_table.setSortingEnabled(True)
        self.shards_table.horizontalHeader().setStretchLastSection(True)
        self.shards_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.shards_table)

        # Controls bar
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.refresh_shards_btn = QPushButton("Refresh Shards")
        self.refresh_shards_btn.setProperty("class", "secondary-btn")
        self.refresh_shards_btn.clicked.connect(self.refresh_shards)
        btn_box.addWidget(self.refresh_shards_btn)
        layout.addLayout(btn_box)

        # Populate initially
        self.refresh_shards()

    def refresh_shards(self) -> None:
        """Fetch latest training shards and refresh the table."""
        if not hasattr(self._container, "get_training_shards_handler") or not self._container.get_training_shards_handler:
            return

        try:
            shards = self._container.get_training_shards_handler.handle()
        except Exception as exc:
            logger.warning("Failed to query training shards: %s", exc)
            return

        self.shards_table.setSortingEnabled(False)
        self.shards_table.setRowCount(len(shards))

        status_colors = {
            "completed": "#22c55e",
            "training": "#38bdf8",
            "ready": "#f59e0b",
            "created": "#f59e0b",
            "failed": "#ef4444",
        }

        for row_idx, shard in enumerate(shards):
            item_model = QTableWidgetItem(shard.model_id)
            item_ver = QTableWidgetItem(str(shard.model_version))
            item_shard = QTableWidgetItem(str(shard.shard_id))

            status_str = str(shard.status)
            item_status = QTableWidgetItem(status_str.upper())
            color_hex = status_colors.get(status_str.lower(), "#cbd5e1")
            item_status.setForeground(QColor(color_hex))

            item_trainer = QTableWidgetItem(shard.trainer_node_id or "-")
            item_samples = QTableWidgetItem(str(shard.sample_count))

            self.shards_table.setItem(row_idx, 0, item_model)
            self.shards_table.setItem(row_idx, 1, item_ver)
            self.shards_table.setItem(row_idx, 2, item_shard)
            self.shards_table.setItem(row_idx, 3, item_status)
            self.shards_table.setItem(row_idx, 4, item_trainer)
            self.shards_table.setItem(row_idx, 5, item_samples)

        self.shards_table.setSortingEnabled(True)

    def _setup_trained_versions_tab(self) -> None:
        """Construct Tab 4: Persisted trained model versions and checkpoint export view."""
        layout = QVBoxLayout(self.trained_versions_tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Trained Models Table
        self.trained_models_table = QTableWidget()
        self.trained_models_table.setColumnCount(5)
        self.trained_models_table.setHorizontalHeaderLabels([
            "Model ID", "Version", "Model Type", "Dataset ID", "Artifact Path"
        ])
        self.trained_models_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trained_models_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.trained_models_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.trained_models_table.setSortingEnabled(True)
        self.trained_models_table.horizontalHeader().setStretchLastSection(True)
        self.trained_models_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.trained_models_table)

        # Controls bar
        btn_box = QHBoxLayout()
        self.export_artifact_btn = QPushButton("Export / Save Artifact...")
        self.export_artifact_btn.setProperty("class", "secondary-btn")
        self.export_artifact_btn.clicked.connect(self._export_selected_model_artifact)
        btn_box.addWidget(self.export_artifact_btn)

        btn_box.addStretch()

        self.refresh_models_btn = QPushButton("Refresh Models")
        self.refresh_models_btn.setProperty("class", "secondary-btn")
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        btn_box.addWidget(self.refresh_models_btn)

        layout.addLayout(btn_box)

        # Populate initially
        self.refresh_models()

    def refresh_models(self) -> None:
        """Fetch latest trained models and refresh the table."""
        if not hasattr(self._container, "get_trained_models_handler") or not self._container.get_trained_models_handler:
            return

        try:
            models = self._container.get_trained_models_handler.handle()
        except Exception as exc:
            logger.warning("Failed to query trained models: %s", exc)
            return

        self.trained_models_table.setSortingEnabled(False)
        self.trained_models_table.setRowCount(len(models))

        for row_idx, model in enumerate(models):
            self.trained_models_table.setItem(row_idx, 0, QTableWidgetItem(model.model_id))
            self.trained_models_table.setItem(row_idx, 1, QTableWidgetItem(str(model.model_version)))
            self.trained_models_table.setItem(row_idx, 2, QTableWidgetItem(model.model_type))
            self.trained_models_table.setItem(row_idx, 3, QTableWidgetItem(model.dataset_id))
            self.trained_models_table.setItem(row_idx, 4, QTableWidgetItem(model.model_artifact_path))

        self.trained_models_table.setSortingEnabled(True)

    def _export_selected_model_artifact(self) -> None:
        """Export the selected model checkpoint artifact to a user-chosen destination."""
        selected_rows = self.trained_models_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Export Artifact", "Please select a model version from the table to export.")
            return

        row = selected_rows[0].row()
        model_id_item = self.trained_models_table.item(row, 0)
        ver_item = self.trained_models_table.item(row, 1)
        path_item = self.trained_models_table.item(row, 4)

        if not model_id_item or not ver_item or not path_item:
            QMessageBox.warning(self, "Export Artifact", "Incomplete row selected.")
            return

        model_id = model_id_item.text()
        model_version = ver_item.text()
        artifact_path_str = path_item.text()

        src_path = Path(artifact_path_str).resolve()
        if not src_path.is_file():
            QMessageBox.critical(
                self,
                "Export Artifact Error",
                f"Source model artifact file does not exist on disk:\n{src_path}",
            )
            return

        ext = "".join(src_path.suffixes) if src_path.suffixes else ".pt2"
        default_filename = f"{model_id}_v{model_version}{ext}"
        if "gz" in ext:
            filter_spec = "Compressed Model Archive (*.gz *.tar.gz);;All Files (*)"
        else:
            filter_spec = "PyTorch Checkpoints (*.pt2);;All Files (*)"
        dest_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Model Artifact",
            default_filename,
            filter_spec,
        )

        if not dest_path_str:
            return

        try:
            shutil.copy2(src_path, dest_path_str)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Model artifact successfully exported to:\n{dest_path_str}",
            )
        except Exception as exc:
            logger.error("Failed to export model artifact: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to copy model artifact:\n{exc}",
            )

    def _on_tab_changed(self, index: int) -> None:
        """Refresh tab contents when switched."""
        if index == 2:
            self.refresh_shards()
        elif index == 3:
            self.refresh_models()

    def _setup_persistent_footer(self, parent_layout: QVBoxLayout) -> None:
        """Construct the persistent footer with Submit button, Progress bar, and Status banner."""
        footer_frame = QFrame()
        footer_frame.setStyleSheet(
            "background-color: #0d121c; border-top: 1px solid #1e293b; padding-top: 8px;"
        )
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(8)

        # Submit Action Button
        self.submit_btn = QPushButton("🚀 Submit Training Workflow")
        self.submit_btn.setObjectName("submit_btn")
        self.submit_btn.setFixedHeight(44)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self._on_submit_clicked)
        footer_layout.addWidget(self.submit_btn)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        footer_layout.addWidget(self.progress_bar)

        # Status Banner
        self.status_banner = QLabel("Ready to submit distributed training task.")
        self.status_banner.setStyleSheet(
            "background-color: #141d2e; color: #38bdf8; border: 1px solid #233149; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600;"
        )
        footer_layout.addWidget(self.status_banner)

        parent_layout.addWidget(footer_frame)

    def _on_model_type_changed(self, model_type: str) -> None:
        """Dynamically update field descriptions, file extensions, and parameter controls based on model type."""
        if model_type == "canonical_torch":
            self.model_label.setText("Model Checkpoint (.pt2):")
            self.model_path_edit.setPlaceholderText("Path to exported PyTorch 2 model (.pt2)")
            self.dataset_label.setText("Dataset File (.pt):")
            self.dataset_path_edit.setPlaceholderText("Path to canonical PyTorch dataset (.pt)")
            self.torch_params_widget.show()
            self.ccdm_params_widget.hide()
        elif model_type == "canonical_causal_decoder":
            self.model_label.setText("Model Archive (.gz, .tar.gz):")
            self.model_path_edit.setPlaceholderText("Path to compressed Hugging Face model archive (.gz, .tar.gz)")
            self.dataset_label.setText("Dataset File (.pt):")
            self.dataset_path_edit.setPlaceholderText("Path to tokenized causal language model dataset (.pt)")
            self.torch_params_widget.hide()
            self.ccdm_params_widget.show()
        else:
            self.model_label.setText("Model Checkpoint:")
            self.model_path_edit.setPlaceholderText("Path to model checkpoint")
            self.dataset_label.setText("Dataset File:")
            self.dataset_path_edit.setPlaceholderText("Path to training dataset")

    def _on_optimizer_changed(self, optim_type: str) -> None:
        """Switch the dynamic optimizer configuration panel."""
        if optim_type == "AdamW":
            self.optim_stack.setCurrentWidget(self.adamw_widget)
        elif optim_type == "SGD":
            self.optim_stack.setCurrentWidget(self.sgd_widget)

    def _on_loss_changed(self, loss_type: str) -> None:
        """Show/hide criterion-specific parameter inputs."""
        self.smooth_l1_label.hide()
        self.smooth_l1_beta_spin.hide()
        self.ce_label.hide()
        self.ce_smoothing_spin.hide()

        if loss_type == "SmoothL1Loss":
            self.smooth_l1_label.show()
            self.smooth_l1_beta_spin.show()
        elif loss_type == "CrossEntropyLoss":
            self.ce_label.show()
            self.ce_smoothing_spin.show()

    def _on_scheduler_changed(self, sched_type: str) -> None:
        """Switch the dynamic scheduler configuration panel."""
        mapping = {
            "CosineAnnealingLR": self.cosine_widget,
            "None": self.none_widget,
            "StepLR": self.step_widget,
            "LinearLR": self.linear_widget,
            "ConstantLR": self.constant_widget,
            "ExponentialLR": self.exp_widget,
        }
        widget = mapping.get(sched_type, self.none_widget)
        self.sched_stack.setCurrentWidget(widget)

    def _browse_model_file(self) -> None:
        """Open file picker dialog tailored to current model type."""
        model_type = self.model_type_combo.currentText()
        if model_type == "canonical_torch":
            filter_str = "PyTorch 2 Checkpoint (*.pt2);;All Files (*)"
        elif model_type == "canonical_causal_decoder":
            filter_str = "Compressed Model Archive (*.gz *.tar.gz);;All Files (*)"
        else:
            filter_str = "All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Model Checkpoint / Archive",
            "",
            filter_str,
        )
        if file_path:
            self.model_path_edit.setText(file_path)

    def _browse_dataset_file(self) -> None:
        """Open file picker dialog tailored to current model type."""
        model_type = self.model_type_combo.currentText()
        if model_type == "canonical_torch":
            filter_str = "PyTorch Dataset (*.pt);;All Files (*)"
        else:
            filter_str = "All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Dataset File",
            "",
            filter_str,
        )
        if file_path:
            self.dataset_path_edit.setText(file_path)

    def _on_submit_clicked(self) -> None:
        """Validate input fields, construct SubmitTrainingCommand with dynamic parameters, and trigger worker."""
        if not self._container.submit_training_handler:
            QMessageBox.critical(self, "Error", "SubmitTrainingCommandHandler is not configured.")
            return

        model_path = self.model_path_edit.text().strip()
        dataset_path = self.dataset_path_edit.text().strip()
        model_version = self.model_version_edit.text().strip()
        model_type = self.model_type_combo.currentText()

        # Fast validations
        if not model_path:
            QMessageBox.warning(self, "Validation Error", "Please select a model checkpoint.")
            return
        if not Path(model_path).is_file():
            QMessageBox.warning(self, "Validation Error", f"Model file does not exist:\n{model_path}")
            return

        if not dataset_path:
            QMessageBox.warning(self, "Validation Error", "Please select a dataset file.")
            return
        if not Path(dataset_path).is_file():
            QMessageBox.warning(self, "Validation Error", f"Dataset file does not exist:\n{dataset_path}")
            return

        if not model_version:
            QMessageBox.warning(self, "Validation Error", "Please provide a model version (e.g. v1.0).")
            return

        if model_type == "canonical_causal_decoder":
            max_steps_val: Optional[int] = None
            max_steps_text = self.ccdm_max_steps_edit.text().strip()
            if max_steps_text:
                try:
                    max_steps_val = int(max_steps_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation Error", "Max Steps must be a valid integer or empty.")
                    return

            max_grad_norm_val: Optional[float] = None
            max_grad_text = self.ccdm_max_grad_norm_edit.text().strip()
            if max_grad_text:
                try:
                    max_grad_norm_val = float(max_grad_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation Error", "Max Grad Norm must be a valid number or empty.")
                    return

            training_config = {
                "seed": self.ccdm_seed_spin.value(),
                "batch_size": self.ccdm_batch_size_spin.value(),
                "epochs": self.ccdm_epochs_spin.value(),
                "max_steps": max_steps_val,
                "learning_rate": self.ccdm_lr_spin.value(),
                "weight_decay": self.ccdm_wd_spin.value(),
                "gradient_accumulation_steps": self.ccdm_grad_accum_spin.value(),
                "max_grad_norm": max_grad_norm_val,
                "scheduler_type": self.ccdm_scheduler_combo.currentText(),
                "warmup_steps": self.ccdm_warmup_steps_spin.value(),
                "warmup_ratio": self.ccdm_warmup_ratio_spin.value(),
                "fp16": self.ccdm_fp16_check.isChecked(),
                "bf16": self.ccdm_bf16_check.isChecked(),
                "shuffle": self.ccdm_shuffle_check.isChecked(),
            }
        else:
            # 1. Build Optimizer Payload
            optim_type = self.optimizer_combo.currentText()
            if optim_type == "AdamW":
                try:
                    eps_val = float(self.adamw_eps_edit.text().strip())
                except ValueError:
                    eps_val = 1e-8
                optim_dict = {
                    "type": "AdamW",
                    "parameters": {
                        "learning_rate": self.adamw_lr_spin.value(),
                        "betas": [self.adamw_b1_spin.value(), self.adamw_b2_spin.value()],
                        "eps": eps_val,
                        "weight_decay": self.adamw_wd_spin.value(),
                        "amsgrad": self.adamw_amsgrad_check.isChecked(),
                    },
                }
            else:  # SGD
                optim_dict = {
                    "type": "SGD",
                    "parameters": {
                        "learning_rate": self.sgd_lr_spin.value(),
                        "momentum": self.sgd_momentum_spin.value(),
                        "dampening": self.sgd_dampening_spin.value(),
                        "weight_decay": self.sgd_wd_spin.value(),
                        "nesterov": self.sgd_nesterov_check.isChecked(),
                    },
                }

            # 2. Build Loss Criterion Payload
            loss_type = self.loss_combo.currentText()
            loss_params: Dict[str, Any] = {
                "reduction": self.loss_reduction_combo.currentText(),
            }
            if loss_type == "SmoothL1Loss":
                loss_params["beta"] = self.smooth_l1_beta_spin.value()
            elif loss_type == "CrossEntropyLoss":
                loss_params["label_smoothing"] = self.ce_smoothing_spin.value()

            loss_dict = {
                "type": loss_type,
                "parameters": loss_params,
            }

            # 3. Build Scheduler Payload
            sched_type = self.scheduler_combo.currentText()
            sched_dict: Optional[Dict[str, Any]] = None
            if sched_type == "CosineAnnealingLR":
                sched_dict = {
                    "type": "CosineAnnealingLR",
                    "parameters": {
                        "T_max": self.cosine_tmax_spin.value(),
                        "eta_min": self.cosine_etamin_spin.value(),
                    },
                }
            elif sched_type == "StepLR":
                sched_dict = {
                    "type": "StepLR",
                    "parameters": {
                        "step_size": self.step_size_spin.value(),
                        "gamma": self.step_gamma_spin.value(),
                    },
                }
            elif sched_type == "LinearLR":
                sched_dict = {
                    "type": "LinearLR",
                    "parameters": {
                        "start_factor": self.linear_start_spin.value(),
                        "end_factor": self.linear_end_spin.value(),
                        "total_iters": self.linear_iters_spin.value(),
                    },
                }
            elif sched_type == "ConstantLR":
                sched_dict = {
                    "type": "ConstantLR",
                    "parameters": {
                        "factor": self.constant_factor_spin.value(),
                        "total_iters": self.constant_iters_spin.value(),
                    },
                }
            elif sched_type == "ExponentialLR":
                sched_dict = {
                    "type": "ExponentialLR",
                    "parameters": {
                        "gamma": self.exp_gamma_spin.value(),
                    },
                }

            # 4. Assemble Top-Level Training Config
            training_config = {
                "batch_size": self.batch_size_spin.value(),
                "shuffle": self.shuffle_check.isChecked(),
                "epochs": self.epochs_spin.value(),
                "gradient_accumulation_steps": self.grad_accum_spin.value(),
                "optimizer": optim_dict,
                "loss": loss_dict,
                "scheduler": sched_dict,
            }

            # Optional constraints
            max_steps_text = self.max_steps_edit.text().strip()
            if max_steps_text:
                try:
                    training_config["max_steps"] = int(max_steps_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation Error", "Max Steps must be a valid integer or empty.")
                    return

            max_grad_text = self.max_grad_norm_edit.text().strip()
            if max_grad_text:
                try:
                    training_config["max_grad_norm"] = float(max_grad_text)
                except ValueError:
                    QMessageBox.warning(self, "Validation Error", "Max Grad Norm must be a valid number or empty.")
                    return

        # Construct command
        try:
            command = SubmitTrainingCommand(
                model_path=model_path,
                dataset_path=dataset_path,
                model_version=model_version,
                model_type=model_type,
                training_config=training_config,
            )
        except SubmitTrainingValidationError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return

        # Lock UI during execution
        self.submit_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_banner.setText("⚡ Initiating distributed training submission...")
        self.status_banner.setStyleSheet(
            "background-color: #1e1b4b; color: #818cf8; border: 1px solid #4338ca; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600;"
        )

        # Launch QThread background worker
        self._worker = SubmitTrainingWorker(
            handler=self._container.submit_training_handler,
            command=command,
            parent=self,
        )
        self._worker.phase_changed.connect(self._on_worker_phase_changed)
        self._worker.progress_updated.connect(self._on_worker_progress_updated)
        self._worker.log_emitted.connect(self._on_worker_log_emitted)
        self._worker.submission_succeeded.connect(self._on_worker_succeeded)
        self._worker.submission_failed.connect(self._on_worker_failed)
        self._worker.start()

    def _on_worker_phase_changed(self, message: str) -> None:
        """Update inline status banner with current phase."""
        self.status_banner.setText(f"⏳ {message}")

    def _on_worker_progress_updated(self, percentage: int) -> None:
        """Update inline progress bar."""
        self.progress_bar.setValue(percentage)

    def _on_worker_log_emitted(self, log_line: str) -> None:
        """Append log line to the Logs tab."""
        self.log_text.appendPlainText(log_line)

    def _on_worker_succeeded(self, result: SubmitTrainingResult) -> None:
        """Handle successful submission completion."""
        self.submit_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        task_count = len(result.training_task_ids) if result.training_task_ids else 0
        success_msg = f"✓ SUCCESS: Registered {task_count} tasks across {result.shard_count} shards."
        self.status_banner.setText(success_msg)
        self.status_banner.setStyleSheet(
            "background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600;"
        )

        self.log_text.appendPlainText(f"[SUCCESS] Model ID: {result.model_id}")
        self.log_text.appendPlainText(f"[SUCCESS] Dataset ID: {result.dataset_id}")
        self.log_text.appendPlainText(f"[SUCCESS] Task IDs: {result.training_task_ids}")

        self.refresh_shards()
        self.refresh_models()

        QMessageBox.information(
            self,
            "Submission Successful",
            f"Training task submitted successfully!\n\n"
            f"Model ID: {result.model_id}\n"
            f"Dataset ID: {result.dataset_id}\n"
            f"Shard Count: {result.shard_count}\n"
            f"Coordinator Tasks: {task_count}",
        )

    def _on_worker_failed(self, error_message: str) -> None:
        """Handle submission failure."""
        self.submit_btn.setEnabled(True)
        self.status_banner.setText(f"✗ FAILED: {error_message}")
        self.status_banner.setStyleSheet(
            "background-color: #450a0a; color: #f87171; border: 1px solid #b91c1c; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600;"
        )
        self.log_text.appendPlainText(f"[ERROR] {error_message}")

        QMessageBox.critical(
            self,
            "Submission Failed",
            f"Failed to submit training task:\n\n{error_message}",
        )


def run_gui(container: DIContainer) -> int:
    """Entry point function to launch the desktop PyQt6 GUI."""
    if not PYQT_AVAILABLE:
        print("[Client] [ERROR] PyQt6 is required to launch the GUI.", file=sys.stderr)
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(container)
    window.show()
    return app.exec()
