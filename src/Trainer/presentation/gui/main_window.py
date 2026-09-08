"""Minimalist PyQt6 desktop window shell for TrainSwarm Trainer."""

from __future__ import annotations
import re
import sys
from typing import Any, Optional

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor, QFont, QPalette
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QProgressBar,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


class MainWindow(QMainWindow):
    """Main application window for the Trainer desktop interface with real-time state telemetry."""

    def __init__(self, container: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.container = container

        node_id = getattr(getattr(container, "state", None), "client_node_id", "trainer-node")
        self.setWindowTitle(f"TrainSwarm Trainer - {node_id}")
        self.setMinimumSize(750, 500)
        self.resize(850, 550)

        self._setup_ui(node_id)

        # Setup polling timer for real-time state updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_state)
        self.timer.start(250)

    def _setup_ui(self, node_id: str) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(32, 28, 32, 28)
        root_layout.setSpacing(18)

        # Top Header: Title & Subtitle
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_label = QLabel("TrainSwarm Trainer Node", self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        self.subtitle_label = QLabel(f"Node Identity: {node_id}", self)
        subtitle_font = QFont()
        subtitle_font.setPointSize(11)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setStyleSheet("color: #a0aec0;")
        header_layout.addWidget(self.subtitle_label)

        root_layout.addLayout(header_layout)

        # Main Dynamic Content: Stacked Widget (Page 0: Idle, Page 1: Training)
        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack)

        # --- Page 0: Idle / Wait Screen ---
        self.idle_widget = QWidget()
        idle_layout = QVBoxLayout(self.idle_widget)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(16)

        idle_card = QFrame()
        idle_card.setStyleSheet(
            "QFrame { background-color: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; }"
        )
        idle_card_layout = QVBoxLayout(idle_card)
        idle_card_layout.setSpacing(14)

        self.idle_status_header = QLabel("STATUS: IDLE - AWAITING TASKS", idle_card)
        self.idle_status_header.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 15px; letter-spacing: 0.5px;")
        idle_card_layout.addWidget(self.idle_status_header)

        self.idle_desc_label = QLabel(
            "Trainer node is connected to Coordinator and listening for incoming training jobs...",
            idle_card,
        )
        self.idle_desc_label.setWordWrap(True)
        self.idle_desc_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        idle_card_layout.addWidget(self.idle_desc_label)

        self.idle_session_label = QLabel("Registration Session ID: N/A", idle_card)
        self.idle_session_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-family: monospace;")
        idle_card_layout.addWidget(self.idle_session_label)

        self.idle_p2p_label = QLabel("P2P Node ID: N/A", idle_card)
        self.idle_p2p_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-family: monospace;")
        idle_card_layout.addWidget(self.idle_p2p_label)

        idle_layout.addWidget(idle_card)
        idle_layout.addStretch()
        self.stack.addWidget(self.idle_widget)

        # --- Page 1: Active Training Screen ---
        self.training_widget = QWidget()
        training_layout = QVBoxLayout(self.training_widget)
        training_layout.setContentsMargins(0, 0, 0, 0)
        training_layout.setSpacing(16)

        training_card = QFrame()
        training_card.setStyleSheet(
            "QFrame { background-color: #1e293b; border: 1px solid #3b82f6; border-radius: 10px; padding: 24px; }"
        )
        training_card_layout = QVBoxLayout(training_card)
        training_card_layout.setSpacing(14)

        self.train_status_header = QLabel("STATUS: ACTIVE TRAINING IN PROGRESS", training_card)
        self.train_status_header.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 15px; letter-spacing: 0.5px;")
        training_card_layout.addWidget(self.train_status_header)

        self.task_info_label = QLabel("Task Assignment: Active", training_card)
        self.task_info_label.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        training_card_layout.addWidget(self.task_info_label)

        # Step description
        self.step_label = QLabel("Step: Initializing...", training_card)
        self.step_label.setStyleSheet("color: #38bdf8; font-size: 14px;")
        training_card_layout.addWidget(self.step_label)

        # Step Progress Bar (1 to 6)
        self.step_progress_bar = QProgressBar(training_card)
        self.step_progress_bar.setRange(0, 6)
        self.step_progress_bar.setValue(0)
        self.step_progress_bar.setTextVisible(True)
        self.step_progress_bar.setFormat("Step %v / 6")
        self.step_progress_bar.setStyleSheet(
            "QProgressBar { background-color: #0f172a; border: 1px solid #475569; border-radius: 5px; text-align: center; color: white; height: 22px; }"
            "QProgressBar::chunk { background-color: #3b82f6; border-radius: 4px; }"
        )
        training_card_layout.addWidget(self.step_progress_bar)

        # Indeterminate Activity / Loading Animation Bar
        self.activity_bar = QProgressBar(training_card)
        self.activity_bar.setRange(0, 0)  # Continuous pulse / marquee animation
        self.activity_bar.setStyleSheet(
            "QProgressBar { background-color: #0f172a; border: 1px solid #475569; border-radius: 5px; height: 10px; }"
            "QProgressBar::chunk { background-color: #06b6d4; border-radius: 4px; }"
        )
        training_card_layout.addWidget(self.activity_bar)

        # Metrics display box
        self.metrics_label = QLabel("Metrics: Pending completion of local training...", training_card)
        self.metrics_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-family: monospace; background: #0f172a; border-radius: 4px; padding: 8px;")
        self.metrics_label.setWordWrap(True)
        training_card_layout.addWidget(self.metrics_label)

        training_layout.addWidget(training_card)
        training_layout.addStretch()
        self.stack.addWidget(self.training_widget)

        # Initial view
        self._update_state()

    def _update_state(self) -> None:
        state = getattr(self.container, "state", None)
        if not state:
            return

        node_id = getattr(state, "client_node_id", "trainer-node")
        self.subtitle_label.setText(f"Node Identity: {node_id}")

        is_training = bool(getattr(state, "is_training", False))
        is_connected = bool(getattr(state, "is_connected", False))
        reg_id = getattr(state, "trainer_id", None) or "N/A"
        p2p_id = getattr(state, "p2p_node_id", None) or "N/A"
        current_step = getattr(state, "current_step", "") or ""
        metrics = getattr(state, "metrics", {}) or {}
        tasks = getattr(state, "assigned_tasks", []) or []

        if is_training:
            self.stack.setCurrentIndex(1)
            task_str = f"Task: {tasks[0]}" if tasks else "Training Task Active"
            self.task_info_label.setText(f"Assignment: {task_str}")
            self.step_label.setText(current_step if current_step else "Executing training lifecycle...")

            # Extract step number from current_step like "Step 3/6"
            step_match = re.search(r"Step\s+(\d+)/6", current_step)
            if step_match:
                self.step_progress_bar.setValue(int(step_match.group(1)))
            else:
                self.step_progress_bar.setValue(1)

            if metrics:
                formatted_metrics = " | ".join(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}" for k, v in metrics.items())
                self.metrics_label.setText(f"Metrics: {formatted_metrics}")
            else:
                self.metrics_label.setText("Metrics: Training in progress...")
        else:
            self.stack.setCurrentIndex(0)
            conn_status = "Connected & Idle" if is_connected else "Initialized (Connecting...)"
            self.idle_status_header.setText(f"STATUS: {conn_status.upper()}")
            self.idle_session_label.setText(f"Registration Session ID: {reg_id}")
            self.idle_p2p_label.setText(f"P2P Node ID: {p2p_id}")


def run_gui(container: Any) -> int:
    """Entry point for launching the Trainer PyQt6 desktop interface."""
    if not HAS_PYQT6:
        print(
            "[Trainer] [ERROR] PyQt6 is required to run the desktop GUI.\n"
            "          Please install GUI dependencies or run in headless mode: python main.py",
            file=sys.stderr,
        )
        return 1

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow(container)
    window.show()
    return app.exec()
