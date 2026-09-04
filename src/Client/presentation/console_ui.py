"""Presentation layer for the Client console application."""


class ConsoleUI:
    """Provides a minimal console interface for the Training Client (cleared/dormant per spec)."""

    def __init__(self, session_service=None) -> None:
        self.session_service = session_service

    def run(self) -> None:
        """Display startup banner and exit cleanly."""
        print("========================================")
        print("       TrainSwarm Client Console        ")
        print("========================================")
        print("[Client] Console UI initialized (cleared for now).")
        print("[Client] Persistence and Coordinator Adapter ready.")
        print("========================================")
