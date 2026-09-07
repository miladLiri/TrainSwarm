"""Minimalist PyQt6 desktop window shell for TrainSwarm Trainer."""

from __future__ import annotations
import sys
from typing import Any, Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QFont, QPalette
    from PyQt6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QVBoxLayout,
        QWidget,
    )
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


class MainWindow(QMainWindow):
    """Main application window for the Trainer desktop interface."""

    def __init__(self, container: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.container = container

        node_id = getattr(getattr(container, "state", None), "client_node_id", "trainer-node")
        self.setWindowTitle(f"TrainSwarm Trainer - {node_id}")
        self.setMinimumSize(700, 450)
        self.resize(800, 500)

        self._setup_ui(node_id)

    def _setup_ui(self, node_id: str) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("TrainSwarm Trainer Node", self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Subtitle
        subtitle = QLabel(f"Node Identity: {node_id}", self)
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Status Card
        state = getattr(self.container, "state", None)
        status_text = "Connected & Idle" if (state and state.is_connected) else "Initialized"
        reg_id = state.trainer_id if (state and state.trainer_id) else "N/A"

        status_card = QWidget(self)
        status_card.setStyleSheet(
            "background-color: #2b2b2b; border-radius: 8px; padding: 16px;"
        )
        card_layout = QVBoxLayout(status_card)

        status_header = QLabel(f"Status: {status_text}", status_card)
        status_header.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;")
        card_layout.addWidget(status_header)

        reg_label = QLabel(f"Registration Session ID: {reg_id}", status_card)
        reg_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        card_layout.addWidget(reg_label)

        layout.addWidget(status_card)
        layout.addStretch()


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
