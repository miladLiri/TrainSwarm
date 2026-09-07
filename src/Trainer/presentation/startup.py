"""Startup routine and connection guard for TrainSwarm Trainer presentation."""

from __future__ import annotations
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

_has_run = False


def run_startup(container: Any) -> bool:
    """Execute the startup connection routine.

    Guarantees single execution across presentation entry points.
    Invokes ConnectTrainerCommandHandler and aborts application execution with an
    error if the connection fails.
    """
    global _has_run
    if _has_run:
        return True

    print("========================================")
    print("        TrainSwarm Trainer Node         ")
    print("========================================")
    print("[Trainer] Running startup connection guard...")

    handler = getattr(container, "connect_trainer_handler", None)
    if not handler:
        print(
            "[Trainer] [FATAL ERROR] ConnectTrainerCommandHandler is not configured in DIContainer.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = handler.handle()
    if not result.success:
        print(
            f"[Trainer] [FATAL ERROR] Could not connect to Coordinator: {result.description}",
            file=sys.stderr,
        )
        logger.error("[TrainerStartup] Aborting startup due to connection failure: %s", result.description)
        sys.exit(1)

    print(f"[Trainer] Successfully connected to Coordinator! Registration ID: {result.trainer_id}")
    _has_run = True
    return True


def reset_startup_flag() -> None:
    """Reset the execution flag (primarily for testing)."""
    global _has_run
    _has_run = False
