import logging
import sys
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class ConsoleUI:
    """Headless console interface for Trainer with real-time state and progress telemetry."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def run(self, args: Optional[List[str]] = None) -> int:
        """Run headless execution loop, listening for incoming Coordinator commands and reporting telemetry."""
        state = getattr(self.container, "state", None)
        node_id = getattr(state, "client_node_id", "unknown-node")

        print("========================================")
        print("       TrainSwarm Trainer Console       ")
        print("========================================")
        print(f"[Trainer] Running in headless CLI mode. Node ID: {node_id}")
        print("[Trainer] Listening for Coordinator commands. Press Ctrl+C to exit.")
        print("========================================")
        sys.stdout.flush()

        last_state = None
        last_heartbeat = 0.0

        try:
            while True:
                now = time.time()
                is_training = getattr(state, "is_training", False) if state else False
                status = getattr(state, "current_status", "UNKNOWN") if state else "UNKNOWN"
                step = getattr(state, "current_step", "") if state else ""
                metrics = getattr(state, "metrics", {}) if state else {}
                tasks = getattr(state, "assigned_tasks", []) if state else []

                current_state_snapshot = (is_training, status, step, tuple(metrics.items()), tuple(tasks))

                # Transition or heartbeat
                if current_state_snapshot != last_state:
                    last_state = current_state_snapshot
                    last_heartbeat = now
                    if not is_training:
                        print(f"[Trainer] [IDLE] Node: {node_id} | Status: {status} | Waiting for task assignment...")
                    else:
                        metrics_str = f" | Metrics: {dict(metrics)}" if metrics else ""
                        task_str = f" [Task: {tasks[0]}]" if tasks else ""
                        print(f"[Trainer] [TRAINING]{task_str} Status: {status} | {step}{metrics_str}")
                    sys.stdout.flush()
                elif not is_training and (now - last_heartbeat) >= 15.0:
                    last_heartbeat = now
                    print(f"[Trainer] [HEARTBEAT] Node: {node_id} | Status: {status} | Waiting for tasks...")
                    sys.stdout.flush()

                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            print("\n[Trainer] Shutting down...")
            return 0
