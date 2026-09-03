"""
Domain exceptions and error definitions for the distributed training engine.
"""


class TrainingEngineError(Exception):
    """Base exception for all distributed training engine errors."""
    pass


class UnsupportedTrainingTypeError(TrainingEngineError):
    """Raised when an requested training type is not registered."""
    pass


class InvalidTaskConfigurationError(TrainingEngineError):
    """Raised when a TrainingTask payload fails schema or structural validation."""
    pass


class InvalidCanonicalTrainingConfigError(TrainingEngineError):
    """Raised when CanonicalTorchTrainingConfig parameters fail validation."""
    pass


class MissingArtifactError(TrainingEngineError):
    """Raised when an expected input artifact (checkpoint or shard) is not found."""
    pass


class InvalidArtifactError(TrainingEngineError):
    """Raised when an artifact file cannot be loaded or deserialized."""
    pass


class ModelContractViolationError(TrainingEngineError):
    """Raised when a model does not adhere to the single-input/single-output float32 contract."""
    pass


class DatasetContractViolationError(TrainingEngineError):
    """Raised when a dataset shard does not contain valid matching float32 x/y tensors."""
    pass


class UnsupportedOptimizerError(TrainingEngineError):
    """Raised when an unsupported optimizer type is requested."""
    pass


class InvalidOptimizerParametersError(TrainingEngineError):
    """Raised when optimizer parameters fail validation."""
    pass


class UnsupportedSchedulerError(TrainingEngineError):
    """Raised when an unsupported scheduler type is requested."""
    pass


class InvalidSchedulerParametersError(TrainingEngineError):
    """Raised when scheduler parameters fail validation."""
    pass


class UnsupportedCriterionError(TrainingEngineError):
    """Raised when an unsupported loss criterion type is requested."""
    pass


class InvalidCriterionParametersError(TrainingEngineError):
    """Raised when criterion parameters fail validation."""
    pass


class TrainingExecutionError(TrainingEngineError):
    """Raised when an unhandled error occurs during the autograd training loop."""
    pass


class ResultSaveError(TrainingEngineError):
    """Raised when saving the locally trained output artifact fails."""
    pass


class DeltaCalculationError(TrainingEngineError):
    """Raised when model delta calculation fails due to incompatible states."""
    pass


class TensorCompatibilityError(TrainingEngineError):
    """Raised when tensors have mismatched shapes, names, or data types during delta operations."""
    pass


class ReconstructionError(TrainingEngineError):
    """Raised when reconstructing a trained model from baseline weights and delta fails."""
    pass

