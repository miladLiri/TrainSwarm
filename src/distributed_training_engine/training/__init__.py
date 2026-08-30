"""
Training package for the distributed training engine.
"""

from .model_type import ModelType
from .training_task_model import TrainingTask
from .training_result import TrainingResult
from .training_adapter import TrainingAdapter
from .training_adapter_registry import TrainingAdapterRegistry
from .training_orchestrator import TrainingOrchestrator
from .exceptions import (
    TrainingEngineError,
    UnsupportedTrainingTypeError,
    InvalidTaskConfigurationError,
    InvalidCanonicalTrainingConfigError,
    MissingArtifactError,
    InvalidArtifactError,
    ModelContractViolationError,
    DatasetContractViolationError,
    UnsupportedOptimizerError,
    InvalidOptimizerParametersError,
    UnsupportedSchedulerError,
    InvalidSchedulerParametersError,
    UnsupportedCriterionError,
    InvalidCriterionParametersError,
    TrainingExecutionError,
    ResultSaveError,
)

__all__ = [
    "ModelType",
    "TrainingTask",
    "TrainingResult",
    "TrainingAdapter",
    "TrainingAdapterRegistry",
    "TrainingOrchestrator",
    "TrainingEngineError",
    "UnsupportedTrainingTypeError",
    "InvalidTaskConfigurationError",
    "InvalidCanonicalTrainingConfigError",
    "MissingArtifactError",
    "InvalidArtifactError",
    "ModelContractViolationError",
    "DatasetContractViolationError",
    "UnsupportedOptimizerError",
    "InvalidOptimizerParametersError",
    "UnsupportedSchedulerError",
    "InvalidSchedulerParametersError",
    "UnsupportedCriterionError",
    "InvalidCriterionParametersError",
    "TrainingExecutionError",
    "ResultSaveError",
]
