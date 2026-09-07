"""In-memory state management for the Trainer application."""

from typing import List, Optional


class TrainerState:
    """Manages the authoritative in-memory state of the running trainer node."""

    DEFAULT_CLIENT_NODE_ID: str = "trainer-node-01"

    def __init__(self) -> None:
        # Strictly hardcoded string constant per specification clarification
        self._client_node_id: str = self.DEFAULT_CLIENT_NODE_ID
        self._is_connected: bool = False
        self._trainer_id: Optional[str] = None
        self._current_status: str = "INITIALIZED"
        self._assigned_tasks: List[str] = []

    @property
    def client_node_id(self) -> str:
        """Returns the node identifier string constant sent to Coordinator."""
        return self._client_node_id

    @property
    def is_connected(self) -> bool:
        """Returns whether the trainer has successfully connected to Coordinator."""
        return self._is_connected

    @property
    def trainer_id(self) -> Optional[str]:
        """Returns the registration session GUID assigned by Coordinator."""
        return self._trainer_id

    @property
    def current_status(self) -> str:
        """Returns the current operational status of the trainer."""
        return self._current_status

    @property
    def assigned_tasks(self) -> List[str]:
        """Returns a copy of the assigned task identifiers."""
        return list(self._assigned_tasks)

    def mark_connected(self, trainer_id: str) -> None:
        """Marks the trainer as connected with the assigned registration GUID."""
        self._is_connected = True
        self._trainer_id = str(trainer_id)
        self._current_status = "IDLE"

    def mark_disconnected(self) -> None:
        """Marks the trainer as disconnected."""
        self._is_connected = False
        self._current_status = "DISCONNECTED"

    def set_status(self, status: str) -> None:
        """Updates the current operational status."""
        self._current_status = status

    def add_assigned_task(self, task_id: str) -> None:
        """Records an assigned training task."""
        if task_id not in self._assigned_tasks:
            self._assigned_tasks.append(task_id)

    def remove_assigned_task(self, task_id: str) -> None:
        """Removes a completed or cancelled task."""
        if task_id in self._assigned_tasks:
            self._assigned_tasks.remove(task_id)
