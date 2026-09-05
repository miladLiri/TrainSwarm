"""Command handler for the Submit Training application use case."""

from __future__ import annotations
import json
import logging
from pathlib import Path
import shutil
from typing import Callable, List, Optional, Union
import uuid

try:
    from Client.domain.training_shard import TrainingShard, TrainingShardStatus
    from Client.infrastructure.adapters import CoordinatorAdapter, CreateTrainingTaskDto
    from Client.infrastructure.persistence import ITrainingShardRepository
    from Client.application.smoke_test import (
        SmokeTestCommand,
        SmokeTestCommandHandler,
        SmokeTestResult,
    )
except ImportError:
    from domain.training_shard import TrainingShard, TrainingShardStatus
    from infrastructure.adapters import CoordinatorAdapter, CreateTrainingTaskDto
    from infrastructure.persistence import ITrainingShardRepository
    from application.smoke_test import (
        SmokeTestCommand,
        SmokeTestCommandHandler,
        SmokeTestResult,
    )
from distributed_training_engine.partitioning import (
    PartitioningOrchestrator,
    PartitioningRequest,
)
from distributed_training_engine.training import TrainingTask
from .exceptions import SubmitTrainingError, SubmitTrainingExecutionError
from .submit_training_command import SubmitTrainingCommand
from .submit_training_result import SubmitTrainingResult

logger = logging.getLogger("trainswarm.client.submit_training")


class SubmitTrainingCommandHandler:
    """Orchestrates end-to-end training submission workflow."""

    def __init__(
        self,
        working_directory: Union[str, Path],
        smoke_test_handler: SmokeTestCommandHandler,
        shard_repository: ITrainingShardRepository,
        coordinator_adapter: Optional[CoordinatorAdapter] = None,
        client_node_id: str = "client-node-dev",
    ) -> None:
        self.working_directory = Path(working_directory).resolve()
        self.smoke_test_handler = smoke_test_handler
        self.shard_repository = shard_repository
        self.coordinator_adapter = coordinator_adapter
        self.client_node_id = client_node_id

    @staticmethod
    def normalize_training_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize flat configuration parameters into canonical nested dictionary structures."""
        norm = dict(cfg)
        # Normalize optimizer if given as flat string
        if isinstance(norm.get("optimizer"), str):
            optim_name = norm["optimizer"]
            lr = float(norm.get("learning_rate", 0.001))
            wd = float(norm.get("weight_decay", 0.01))
            norm["optimizer"] = {
                "type": optim_name,
                "parameters": {
                    "learning_rate": lr,
                    "weight_decay": wd,
                },
            }
        # Normalize loss if given as flat string
        if isinstance(norm.get("loss"), str):
            loss_name = norm["loss"]
            norm["loss"] = {
                "type": loss_name,
                "parameters": {
                    "reduction": "mean",
                },
            }
        # Normalize scheduler if given as flat string
        if isinstance(norm.get("scheduler"), str):
            sched_name = norm["scheduler"]
            if sched_name.lower() in ("none", ""):
                norm["scheduler"] = None
            else:
                norm["scheduler"] = {
                    "type": sched_name,
                    "parameters": {
                        "T_max": 10,
                    },
                }
        return norm

    def handle(
        self,
        command: SubmitTrainingCommand,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> SubmitTrainingResult:
        """Execute the submit training workflow.

        Args:
            command: Validated SubmitTrainingCommand DTO.
            progress_callback: Optional callback receiving (status_message, progress_percent).

        Returns:
            SubmitTrainingResult detailing success status, IDs, and any errors.
        """
        def report_progress(msg: str, pct: int) -> None:
            logger.info("[SubmitTraining] %s (%d%%)", msg, pct)
            if progress_callback:
                try:
                    progress_callback(msg, pct)
                except Exception as e:
                    logger.debug("Progress callback error: %s", e)

        command.validate()
        normalized_training_config = self.normalize_training_config(command.training_config)

        # 1. Generate unique UUIDs for model and dataset
        model_id = str(uuid.uuid4())
        dataset_id = str(uuid.uuid4())
        model_type_str = command.model_type.value if hasattr(command.model_type, "value") else str(command.model_type)

        report_progress(f"Initializing submission [model_id={model_id}, dataset_id={dataset_id}]", 5)

        # 2. Stage model checkpoint and config in {working_directory}/{model_id}/
        model_staging_dir = self.working_directory / model_id
        try:
            model_staging_dir.mkdir(parents=True, exist_ok=True)
            model_dest = model_staging_dir / f"{model_id}_{command.model_version}.pt2"
            report_progress(f"Staging model checkpoint to {model_dest.name}", 15)
            shutil.copy2(command.model_path, model_dest)

            config_dest = model_staging_dir / f"{model_id}_{command.model_version}_config.json"
            with open(config_dest, "w", encoding="utf-8") as f:
                json.dump(normalized_training_config, f, indent=2)
        except Exception as exc:
            err = f"Failed to stage model checkpoint or configuration: {exc}"
            logger.error(err, exc_info=True)
            return SubmitTrainingResult(success=False, model_id=model_id, dataset_id=dataset_id, error=err)

        # 3. Extract representative sample for smoke testing
        report_progress("Extracting representative sample for smoke testing", 25)
        shards_output_dir = self.working_directory / "shards" / dataset_id
        sample_request = PartitioningRequest(
            model_type=command.model_type,
            datasetPath=Path(command.dataset_path).resolve(),
            shardsOutputDirectory=shards_output_dir,
            sampleOutputDirecotry=model_staging_dir,
            datasetId=dataset_id,
        )

        try:
            partition_orchestrator = PartitioningOrchestrator(sample_request)
            sampling_result = partition_orchestrator.get_sample()
        except Exception as exc:
            err = f"Failed to extract dataset sample for smoke test: {exc}"
            logger.error(err, exc_info=True)
            return SubmitTrainingResult(success=False, model_id=model_id, dataset_id=dataset_id, error=err)

        # 4. Execute Smoke Test benchmark
        report_progress("Running smoke test benchmark on sample", 35)
        sample_task_id = f"smoke-{uuid.uuid4()}"
        smoke_task = TrainingTask.from_dict({
            "training_task_id": sample_task_id,
            "baseline_model_id": model_id,
            "baseline_model_version": command.model_version,
            "data_set_id": dataset_id,
            "data_set_shard_id": "sample",
            "type": model_type_str,
            "training": normalized_training_config,
        })
        smoke_cmd = SmokeTestCommand(
            training_task_model=smoke_task,
            sample_count=sampling_result.sample_count,
        )

        orig_work_dir = self.smoke_test_handler.working_directory
        try:
            self.smoke_test_handler.working_directory = model_staging_dir
            smoke_result: SmokeTestResult = self.smoke_test_handler.handle(smoke_cmd)
        finally:
            self.smoke_test_handler.working_directory = orig_work_dir
            # Clean up temporary sample file
            sample_file = Path(sampling_result.sample_path)
            if sample_file.is_file():
                try:
                    sample_file.unlink(missing_ok=True)
                    logger.debug("Cleaned up temporary sample file: %s", sample_file)
                except Exception as e:
                    logger.warning("Failed to delete sample file %s: %s", sample_file, e)

        if not smoke_result.success:
            err = f"Smoke test failed: {smoke_result.error}"
            logger.error("[SubmitTraining] %s", err)
            return SubmitTrainingResult(
                success=False,
                model_id=model_id,
                dataset_id=dataset_id,
                error=err,
            )

        rec_shard_size = smoke_result.recommended_samples_per_shard or smoke_result.estimated_samples_per_shard or 1
        report_progress(f"Smoke test succeeded. Recommended shard size: {rec_shard_size} samples", 50)

        # 5. Partition dataset into shards
        report_progress(f"Partitioning dataset into shards (size={rec_shard_size})", 65)
        try:
            partition_result = partition_orchestrator.create_shards(shardSampleSize=rec_shard_size)
        except Exception as exc:
            err = f"Dataset partitioning failed: {exc}"
            logger.error(err, exc_info=True)
            return SubmitTrainingResult(
                success=False,
                model_id=model_id,
                dataset_id=dataset_id,
                recommended_samples_per_shard=rec_shard_size,
                error=err,
            )

        shard_count = partition_result.shard_count
        report_progress(f"Partitioned dataset into {shard_count} shards", 75)

        # 6. Persist shards locally in SQLite with initial status CREATED
        report_progress("Persisting shard metadata in local database with status CREATED", 80)
        training_shards: List[TrainingShard] = []
        for s in partition_result.shards:
            training_shards.append(
                TrainingShard(
                    id=str(uuid.uuid4()),
                    model_id=model_id,
                    model_type=model_type_str,
                    model_version=command.model_version,
                    dataset_id=dataset_id,
                    shard_id=s.shard_id,
                    artifact_path=s.artifact_path,
                    sample_count=s.sample_count,
                    status=TrainingShardStatus.CREATED,
                )
            )

        try:
            self.shard_repository.bulk_save(training_shards)
        except Exception as exc:
            err = f"Failed to persist shards in local database: {exc}"
            logger.error(err, exc_info=True)
            return SubmitTrainingResult(
                success=False,
                model_id=model_id,
                dataset_id=dataset_id,
                shard_count=shard_count,
                recommended_samples_per_shard=rec_shard_size,
                error=err,
            )

        # 7. Register tasks with Coordinator API
        if not self.coordinator_adapter:
            err = "Coordinator adapter is not configured; shards saved locally with status CREATED."
            logger.warning("[SubmitTraining] %s", err)
            return SubmitTrainingResult(
                success=False,
                model_id=model_id,
                dataset_id=dataset_id,
                shard_count=shard_count,
                recommended_samples_per_shard=rec_shard_size,
                error=err,
            )

        report_progress("Registering training tasks with Coordinator", 90)
        dto = CreateTrainingTaskDto(
            client_node_id=self.client_node_id,
            model_id=model_id,
            model_version=command.model_version,
            data_set_id=dataset_id,
            shard_id_list=[s.shard_id for s in partition_result.shards],
        )

        try:
            task_ids = self.coordinator_adapter.create_training_task(dto)
        except Exception as exc:
            err = f"Coordinator task registration failed: {exc}"
            logger.error("[SubmitTraining] %s", err, exc_info=True)
            return SubmitTrainingResult(
                success=False,
                model_id=model_id,
                dataset_id=dataset_id,
                shard_count=shard_count,
                recommended_samples_per_shard=rec_shard_size,
                error=err,
            )

        # 8. Update local shard status in SQLite to READY
        report_progress("Updating local shard statuses to READY", 95)
        shard_pks = [s.id for s in training_shards]
        try:
            self.shard_repository.update_status(shard_pks, TrainingShardStatus.READY)
        except Exception as exc:
            logger.warning("Failed to update shard status to READY in SQLite: %s", exc)

        report_progress("Training submission completed successfully!", 100)
        return SubmitTrainingResult(
            success=True,
            model_id=model_id,
            dataset_id=dataset_id,
            shard_count=shard_count,
            training_task_ids=task_ids,
            recommended_samples_per_shard=rec_shard_size,
            error=None,
        )
