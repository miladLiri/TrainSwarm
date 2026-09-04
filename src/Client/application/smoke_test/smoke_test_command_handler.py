"""Command handler for the Smoke Test application use case."""

from __future__ import annotations
import logging
from pathlib import Path
import time
from typing import Optional, Union

from distributed_training_engine.training import TrainingOrchestrator
from .exceptions import SmokeTestValidationError
from .smoke_test_command import SmokeTestCommand
from .smoke_test_result import SmokeTestResult

logger = logging.getLogger("trainswarm.client.smoke_test")


class SmokeTestCommandHandler:
    """Handles execution of smoke test training runs, timing measurement, and shard sizing."""

    def __init__(
        self,
        training_orchestrator: TrainingOrchestrator,
        shard_training_time_limit: float = 300.0,
        working_directory: Union[str, Path] = Path("."),
        safety_factor: float = 1.0,
    ) -> None:
        self.training_orchestrator = training_orchestrator
        self.shard_training_time_limit = float(shard_training_time_limit)
        self.working_directory = Path(working_directory).resolve()
        self.safety_factor = float(safety_factor)

    def _cleanup_delta_artifact(self, task_id: str, result_delta_path: Optional[str] = None) -> None:
        """Attempt to delete the generated output delta model artifact to prevent disk accumulation."""
        target_path: Optional[Path] = None
        if result_delta_path:
            p = Path(result_delta_path)
            if not p.is_absolute():
                p = self.working_directory / p
            target_path = p
        else:
            # Check default pattern in working directory
            candidates = list(self.working_directory.glob(f"*{task_id}*.safetensors")) + \
                         list(self.working_directory.glob("*.safetensors"))
            if candidates:
                target_path = candidates[0]

        if target_path and target_path.is_file():
            try:
                target_path.unlink(missing_ok=True)
                logger.info("Cleaned up smoke test output delta artifact: %s", target_path)
            except Exception as e:
                logger.warning(
                    "Failed to delete smoke test output delta artifact '%s': %s",
                    target_path,
                    e,
                )

    def handle(self, command: SmokeTestCommand) -> SmokeTestResult:
        """Execute smoke test training and calculate throughput and recommended shard sizing."""
        command.validate()
        task = command.training_task_model
        sample_count = command.sample_count

        logger.info(
            "Executing Smoke Test [task_id=%s, model=%s_%s, dataset=%s_%s, samples=%d, work_dir=%s]",
            task.training_task_id,
            task.baseline_model_id,
            task.baseline_model_version,
            task.data_set_id,
            task.data_set_shard_id,
            sample_count,
            self.working_directory,
        )

        start_time = time.perf_counter()
        try:
            orchestrator_result = self.training_orchestrator.run(
                task=task,
                working_directory=self.working_directory,
            )
            elapsed_seconds = time.perf_counter() - start_time

            # Attempt cleanup of the produced delta artifact
            delta_path_str = getattr(getattr(orchestrator_result, "delta", None), "path", None)
            self._cleanup_delta_artifact(task.training_task_id, delta_path_str)

        except Exception as exc:
            logger.error(
                "Smoke test training failed for task '%s': %s",
                task.training_task_id,
                exc,
                exc_info=True,
            )
            # Cleanup any partial artifact if generated
            self._cleanup_delta_artifact(task.training_task_id)
            return SmokeTestResult(
                success=False,
                sample_count=sample_count,
                training_time_seconds=None,
                samples_per_second=None,
                shard_training_time_limit_seconds=self.shard_training_time_limit,
                estimated_samples_per_shard=None,
                recommended_samples_per_shard=None,
                error=str(exc),
            )

        # Validate elapsed duration
        if elapsed_seconds <= 0.0:
            logger.warning("Measured elapsed duration is non-positive (%s); treating throughput as invalid.", elapsed_seconds)
            return SmokeTestResult(
                success=True,
                sample_count=sample_count,
                training_time_seconds=elapsed_seconds,
                samples_per_second=None,
                shard_training_time_limit_seconds=self.shard_training_time_limit,
                estimated_samples_per_shard=None,
                recommended_samples_per_shard=None,
                error="Monotonic duration was too small to calculate valid throughput.",
            )

        throughput = sample_count / elapsed_seconds
        estimated_shard_size = max(1, int(throughput * self.shard_training_time_limit))
        recommended_shard_size = max(1, int(estimated_shard_size * self.safety_factor))

        logger.info(
            "Smoke test succeeded [duration=%.3fs, throughput=%.2f samples/s, est_shard=%d, rec_shard=%d]",
            elapsed_seconds,
            throughput,
            estimated_shard_size,
            recommended_shard_size,
        )

        return SmokeTestResult(
            success=True,
            sample_count=sample_count,
            training_time_seconds=elapsed_seconds,
            samples_per_second=throughput,
            shard_training_time_limit_seconds=self.shard_training_time_limit,
            estimated_samples_per_shard=estimated_shard_size,
            recommended_samples_per_shard=recommended_shard_size,
            error=None,
        )
