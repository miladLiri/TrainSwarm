"""In-memory state management for the Trainer application."""

from typing import List, Optional


class TrainerState:
    """Manages the authoritative in-memory state of the running trainer node."""

    DEFAULT_CLIENT_NODE_ID: str = "trainer-node-01"

    def __init__(self) -> None:
        # Initial client node ID, updated when P2P node ID is resolved
        self._client_node_id: str = self.DEFAULT_CLIENT_NODE_ID
        self._p2p_node_id: Optional[str] = None
        self._is_training: bool = False
        self._current_step: str = ""
        self._metrics: dict = {}
        self._is_connected: bool = False
        self._trainer_id: Optional[str] = None
        self._current_status: str = "INITIALIZED"
        self._assigned_tasks: List[str] = []

    @property
    def p2p_node_id(self) -> Optional[str]:
        """Returns the libp2p peer ID retrieved from the local p2p-node."""
        return self._p2p_node_id

    @property
    def is_training(self) -> bool:
        """Returns True if the trainer is actively performing a training run."""
        return self._is_training

    @is_training.setter
    def is_training(self, value: bool) -> None:
        self._is_training = bool(value)

    @property
    def current_step(self) -> str:
        """Returns the human-readable description of the current training step."""
        return self._current_step

    @current_step.setter
    def current_step(self, value: str) -> None:
        self._current_step = str(value)

    @property
    def metrics(self) -> dict:
        """Returns the latest training metrics dictionary."""
        return dict(self._metrics)

    @metrics.setter
    def metrics(self, value: dict) -> None:
        self._metrics = dict(value) if value else {}

    def set_node_id(self, node_id: str) -> None:
        """Sets the authoritative P2P node ID and updates client_node_id."""
        self._p2p_node_id = str(node_id)
        self._client_node_id = str(node_id)

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
