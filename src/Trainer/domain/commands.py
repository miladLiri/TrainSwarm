"""Command models and enum definitions for the Trainer node."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class CommandType(str, Enum):
    StartTraining = "StartTraining"


@dataclass(frozen=True)
class CommandEnvelope:
    id: str
    type: str
    data: str  # Raw UTF-8 JSON payload string


@dataclass(frozen=True)
class StartTrainingCommand:
    training_client_node_id: str
    session_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartTrainingCommand":
        training_client_node_id = data.get("trainingClientNodeId") or data.get("training_client_node_id")
        session_id = data.get("sessionId") or data.get("session_id")
        
        if not training_client_node_id or not session_id:
            raise ValueError(f"Missing required fields for StartTrainingCommand. Received: {data}")
            
        return cls(
            training_client_node_id=str(training_client_node_id),
            session_id=str(session_id),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trainingClientNodeId": self.training_client_node_id,
            "sessionId": self.session_id,
        }
