"""Background worker thread for TrainSwarm Client GUI execution."""

from __future__ import annotations
import logging
from typing import Any, Optional

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    # Graceful fallback for type inspection / environments without PyQt6
    class QThread:  # type: ignore
        def __init__(self, parent: Any = None) -> None:
            pass

        def start(self) -> None:
            pass

    def pyqtSignal(*args: Any, **kwargs: Any) -> Any:  # type: ignore
        return None

from application.submit_training import (
    SubmitTrainingCommand,
    SubmitTrainingCommandHandler,
    SubmitTrainingResult,
)

logger = logging.getLogger("trainswarm.client.gui.worker")


class SubmitTrainingWorker(QThread):
    """QThread background worker that executes SubmitTrainingCommandHandler without blocking the UI."""

    # Signals for UI communication
    phase_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    log_emitted = pyqtSignal(str)
    submission_succeeded = pyqtSignal(object)  # SubmitTrainingResult
    submission_failed = pyqtSignal(str)

    def __init__(
        self,
        handler: SubmitTrainingCommandHandler,
        command: SubmitTrainingCommand,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._handler = handler
        self._command = command

    def run(self) -> None:
        """Execute the command handler and emit progress and completion signals."""
        def on_progress(msg: str, pct: int) -> None:
            if hasattr(self, "log_emitted") and self.log_emitted is not None:
                self.log_emitted.emit(f"[{pct:3d}%] {msg}")
            if hasattr(self, "progress_updated") and self.progress_updated is not None:
                self.progress_updated.emit(pct)
            if hasattr(self, "phase_changed") and self.phase_changed is not None:
                self.phase_changed.emit(msg)

        try:
            if hasattr(self, "phase_changed") and self.phase_changed is not None:
                self.phase_changed.emit("Initiating training submission...")
            if hasattr(self, "log_emitted") and self.log_emitted is not None:
                self.log_emitted.emit(f"Starting submission for model {self._command.model_path}")

            result: SubmitTrainingResult = self._handler.handle(
                self._command,
                progress_callback=on_progress,
            )

            if result.success:
                if hasattr(self, "submission_succeeded") and self.submission_succeeded is not None:
                    self.submission_succeeded.emit(result)
            else:
                error_msg = result.error or "Submission failed due to an unknown error."
                if hasattr(self, "submission_failed") and self.submission_failed is not None:
                    self.submission_failed.emit(error_msg)
        except Exception as exc:
            logger.exception("Unhandled error during training submission worker execution")
            if hasattr(self, "submission_failed") and self.submission_failed is not None:
                self.submission_failed.emit(f"Internal execution error: {exc}")
