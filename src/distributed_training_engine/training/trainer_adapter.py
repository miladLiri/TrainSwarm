"""
Abstract base class for all trainer adapters in the distributed training engine.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from .training_task_model import TrainingTask
from .training_result import TrainingResult


class TrainerAdapter(ABC):
    """
    Abstract contract representing the execution lifecycle for a specific training type.
    """

    def __init__(self, task: TrainingTask, working_directory: Path) -> None:
        self.task = task
        self.working_directory = Path(working_directory).resolve()

    @abstractmethod
    def validate(self) -> None:
        """
        Validate task configuration, hyperparameters, and existence of input artifacts.
        Must raise explicit domain exceptions if any aspect is invalid.
        """
        pass

    @abstractmethod
    def prepare(self) -> None:
        """
        Load model program and dataset shards, prepare DataLoader, device placement,
        and internal training state. Must not execute optimization steps.
        """
        pass

    @abstractmethod
    def train(self) -> None:
        """
        Execute the autograd training loop according to the validated configuration.
        """
        pass

    @abstractmethod
    def save_result(self) -> TrainingResult:
        """
        Save the locally trained output artifact and return a populated TrainingResult DTO.
        """
        pass


# Backward compatibility alias
TrainingAdapter = TrainerAdapter
