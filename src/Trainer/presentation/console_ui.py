"""Presentation layer for Trainer console and headless execution."""

from __future__ import annotations
import logging
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class ConsoleUI:
    """Minimal headless console interface for Trainer."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def run(self, args: Optional[List[str]] = None) -> int:
        """Run headless execution loop, listening for incoming Coordinator commands."""
        print("[Trainer] Running in headless CLI mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1.0)
        except (KeyboardInterrupt, SystemExit):
            print("\n[Trainer] Shutting down...")
            return 0
