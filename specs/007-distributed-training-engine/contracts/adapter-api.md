# Training Adapter Contract & API Specification

**Feature**: [Distributed Training Engine](../spec.md)
**Status**: Complete
**Date**: 2026-08-30

## 1. Abstract Base Class: `TrainingAdapter`

Location: `src/distributed_training_engine/training/training_adapter.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from .training_task_model import TrainingTask
from .training_result import TrainingResult

class TrainingAdapter(ABC):
    """Abstract base class representing the execution lifecycle for a training type."""

    def __init__(self, task: TrainingTask, working_directory: Path) -> None:
        self.task = task
        self.working_directory = working_directory

    @abstractmethod
    def validate(self) -> None:
        """
        Validate task configuration, deserialization of parameters,
        and existence of input files in the working directory before training.
        Must raise explicit domain exceptions on invalid state.
        """
        pass

    @abstractmethod
    def prepare(self) -> None:
        """
        Load models, checkpoints, dataset shards, and prepare DataLoader and execution state.
        Must not perform optimization steps.
        """
        pass

    @abstractmethod
    def train(self) -> None:
        """
        Execute the core training/optimization loop according to task configuration.
        """
        pass

    @abstractmethod
    def save_result(self) -> TrainingResult:
        """
        Save the locally trained output artifact (e.g. trained_<task_id>.pt2)
        and return a populated TrainingResult DTO.
        """
        pass
```

---

## 2. Orchestrator API: `TrainingOrchestrator`

Location: `src/distributed_training_engine/training/training_orchestrator.py`

```python
from pathlib import Path
from typing import Union
from .training_task_model import TrainingTask
from .training_result import TrainingResult
from .training_adapter_registry import TrainingAdapterRegistry

class TrainingOrchestrator:
    """Type-agnostic orchestrator managing the training lifecycle."""

    def __init__(self, adapter_registry: TrainingAdapterRegistry | None = None) -> None:
        self._registry = adapter_registry or TrainingAdapterRegistry()

    def run(self, task: TrainingTask, working_directory: Union[str, Path]) -> TrainingResult:
        """
        Execute the local training task workflow:
        1. Resolve adapter from registry using task.type
        2. Construct adapter with (task, working_directory)
        3. Execute: validate() -> prepare() -> train() -> save_result()
        4. Return TrainingResult
        """
        work_dir = Path(working_directory).resolve()
        adapter_cls = self._registry.get(task.type)
        adapter = adapter_cls(task=task, working_directory=work_dir)

        adapter.validate()
        adapter.prepare()
        adapter.train()
        return adapter.save_result()
```

---

## 3. Registry Interfaces

### 3.1 `TrainingAdapterRegistry`
Location: `src/distributed_training_engine/training/training_adapter_registry.py`

```python
class TrainingAdapterRegistry:
    def register(self, model_type: ModelType, adapter_class: type[TrainingAdapter]) -> None: ...
    def get(self, model_type: Union[ModelType, str]) -> type[TrainingAdapter]: ...
```

### 3.2 `OptimizerRegistry`
Location: `src/distributed_training_engine/training/training_adapters/canonical_torch/optimizer_registry.py`

```python
class OptimizerRegistry:
    @classmethod
    def create(cls, optimizer_config: OptimizerConfig, model_parameters: Any) -> torch.optim.Optimizer: ...
```

### 3.3 `SchedulerRegistry`
Location: `src/distributed_training_engine/training/training_adapters/canonical_torch/scheduler_registry.py`

```python
class SchedulerRegistry:
    @classmethod
    def create(cls, scheduler_config: SchedulerConfig | None, optimizer: torch.optim.Optimizer) -> Any: ...
```

### 3.4 `CriterionRegistry`
Location: `src/distributed_training_engine/training/training_adapters/canonical_torch/criterion_registry.py`

```python
class CriterionRegistry:
    @classmethod
    def create(cls, loss_config: LossConfig) -> torch.nn.Module: ...
```
