"""Handler for UpdateModelCommand in Client."""

from __future__ import annotations
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union

try:
    from Client.domain.training_shard import TrainingShardStatus
    from Client.domain.model import Model
    from Client.infrastructure.persistence.training_shard_repository import ITrainingShardRepository
    from Client.infrastructure.persistence.model_repository import IModelRepository
    from Client.infrastructure.adapters.coordinator_adapter import CoordinatorAdapter
except ImportError:
    from domain.training_shard import TrainingShardStatus
    from domain.model import Model
    from infrastructure.persistence.training_shard_repository import ITrainingShardRepository
    from infrastructure.persistence.model_repository import IModelRepository
    from infrastructure.adapters.coordinator_adapter import CoordinatorAdapter

try:
    from distributed_training_engine.training import TrainingResult
    from distributed_training_engine.aggregation import (
        AggregationOrchestrator,
        AggregationRequest,
        ModelUpdate,
    )
except ImportError:
    try:
        from distributed_training_engine import (
            TrainingResult,
            AggregationOrchestrator,
            AggregationRequest,
            ModelUpdate,
        )
    except ImportError:
        pass

from .update_model_command import UpdateModelCommand

logger = logging.getLogger("trainswarm.client.update_model")


class UpdateModelCommandHandler:
    """Handles UpdateModelCommand by recording the update artifact path, metrics, transitioning shard to COMPLETED,
    detaching trainer, checking for round completion under lock, and running aggregation."""

    def __init__(
        self,
        shard_repository: ITrainingShardRepository,
        coordinator_adapter: Optional[CoordinatorAdapter] = None,
        model_repository: Optional[IModelRepository] = None,
        client_state: Optional[Any] = None,
        working_directory: Optional[Union[str, Path]] = None,
        aggregation_orchestrator: Optional[Any] = None,
    ) -> None:
        self.shard_repository = shard_repository
        self.coordinator_adapter = coordinator_adapter
        self.model_repository = model_repository
        self.client_state = client_state
        self.working_directory = Path(working_directory).resolve() if working_directory else None
        self.aggregation_orchestrator = aggregation_orchestrator
        self._lock = threading.Lock()

    def handle(
        self,
        command: Optional[UpdateModelCommand] = None,
        *,
        trainer_node_id: Optional[str] = None,
        training_result: Optional[TrainingResult] = None,
        saved_update_artifact_path: Optional[str] = None,
    ) -> None:
        """Process completed training update, detach trainer, and trigger aggregation if all shards complete."""
        if command is not None:
            t_node_id = command.trainer_node_id
            result = command.training_result
            update_path = command.saved_update_artifact_path
        else:
            t_node_id = trainer_node_id or ""
            result = training_result
            update_path = saved_update_artifact_path or ""

        if result is None:
            raise ValueError("training_result is required for UpdateModelCommand")

        m_id = result.base_model_id
        m_ver = str(result.base_model_version)
        d_id = result.dataset_id
        s_id = str(result.dataset_shard_id)

        logger.info(
            "[UpdateModelCommandHandler] Received update for shard (%s, %s, %s, %s) from trainer=%s, saved at %s",
            m_id, m_ver, d_id, s_id, t_node_id, update_path
        )

        shard = self.shard_repository.get_by_shard_key(m_id, m_ver, d_id, s_id)
        if not shard:
            raise ValueError(
                f"Training shard ({m_id}, {m_ver}, {d_id}, {s_id}) not found in repository"
            )

        # 1. Update shard status to COMPLETED and set update artifact path and metrics
        self.shard_repository.update_shard_completed(
            model_id=m_id,
            model_version=m_ver,
            dataset_id=d_id,
            shard_id=s_id,
            update_artifact_path=update_path,
            metrics=result.metrics if hasattr(result, "metrics") else None,
            status=TrainingShardStatus.COMPLETED,
        )

        logger.info(
            "[UpdateModelCommandHandler] Successfully transitioned shard (%s, %s, %s, %s) to COMPLETED",
            m_id, m_ver, d_id, s_id
        )

        # 2. Detach trainer via Coordinator adapter
        if self.coordinator_adapter and t_node_id:
            try:
                self.coordinator_adapter.detach_trainer(t_node_id, is_training_complete=True)
                logger.info(
                    "[UpdateModelCommandHandler] Detached trainer %s via Coordinator API (isTrainingComplete=True)",
                    t_node_id
                )
            except Exception as exc:
                logger.warning(
                    "[UpdateModelCommandHandler] Could not detach trainer %s via Coordinator: %s",
                    t_node_id, exc
                )

        # 3. Check under concurrency lock whether all shards for (m_id, m_ver, d_id) are complete
        with self._lock:
            shards = self.shard_repository.get_by_model_version_and_dataset(m_id, m_ver, d_id)
            if not shards:
                logger.warning(
                    "[UpdateModelCommandHandler] No shards found for model_id=%s, version=%s, dataset_id=%s",
                    m_id, m_ver, d_id
                )
                return

            all_complete = all(
                s.status == TrainingShardStatus.COMPLETED and s.update_artifact_path
                for s in shards
            )

            completed_count = sum(1 for s in shards if s.status == TrainingShardStatus.COMPLETED)
            total_count = len(shards)
            logger.info(
                "[UpdateModelCommandHandler] Shard progress: %d/%d shards completed for model %s version %s",
                completed_count, total_count, m_id, m_ver
            )

            if not all_complete:
                logger.info("[UpdateModelCommandHandler] Waiting for remaining shards to complete before aggregation.")
                return

            # 4. Trigger aggregation
            logger.info(
                "[UpdateModelCommandHandler] All %d shards complete! Starting model aggregation for model=%s...",
                total_count, m_id
            )
            self._run_aggregation(m_id, m_ver, d_id, shards)

    def _run_aggregation(self, model_id: str, model_version: str, dataset_id: str, shards: List[Any]) -> None:
        """Executes aggregation, creates new version checkpoint, saves to models repository, and resets submitted flag."""
        try:
            # Resolve base model record
            base_model = None
            if self.model_repository:
                if hasattr(self.model_repository, "get_by_model_id_and_version"):
                    try:
                        base_model = self.model_repository.get_by_model_id_and_version(model_id, model_version)
                    except Exception:
                        pass
                if not base_model and hasattr(self.model_repository, "get_by_model_id"):
                    try:
                        base_model = self.model_repository.get_by_model_id(model_id)
                    except Exception:
                        pass

            if not base_model:
                raise ValueError(
                    f"Base model record not found in repository for model_id='{model_id}' version='{model_version}'"
                )

            base_model_path = Path(base_model.model_artifact_path).resolve()
            if not base_model_path.exists():
                raise FileNotFoundError(f"Base model checkpoint not found at: {base_model_path}")

            # Parse integer version and increment
            try:
                base_v_int = int(model_version)
            except ValueError:
                import re
                match = re.search(r'\d+', str(model_version))
                base_v_int = int(match.group(0)) if match else 1
            new_v_int = base_v_int + 1

            # Determine output directory for new version
            if self.working_directory:
                out_dir = self.working_directory / "models" / model_id / f"v{new_v_int}"
            else:
                out_dir = base_model_path.parent.parent / f"v{new_v_int}"
            out_dir.mkdir(parents=True, exist_ok=True)

            # Build ModelUpdate records
            updates = [
                ModelUpdate(
                    samplesTrained=int(s.sample_count),
                    deltaPath=Path(s.update_artifact_path).resolve()
                )
                for s in shards
            ]

            agg_request = AggregationRequest(
                modelId=model_id,
                baseModelVersion=base_v_int,
                baseModelPath=base_model_path,
                newVersion=new_v_int,
                newVersionOutputDirectory=out_dir,
                updates=updates,
            )

            orchestrator = self.aggregation_orchestrator
            if orchestrator is None:
                orchestrator = AggregationOrchestrator(model_type=base_model.model_type)

            logger.info(
                "[UpdateModelCommandHandler] Invoking AggregationOrchestrator for model=%s, base_v=%d -> new_v=%d (%d updates)",
                model_id, base_v_int, new_v_int, len(updates)
            )

            result = orchestrator.Aggregate(agg_request)

            raw_path = getattr(result, "model_path", None) or getattr(result, "modelPath", None) or getattr(result, "new_model_artifact_path", None)
            new_artifact_path = str(Path(raw_path).resolve())
            logger.info("[UpdateModelCommandHandler] Aggregated new model checkpoint saved: %s", new_artifact_path)

            # Save new version Model entity into database
            new_model = Model(
                model_id=model_id,
                model_type=base_model.model_type,
                model_version=str(new_v_int),
                dataset_id=dataset_id,
                model_artifact_path=new_artifact_path,
                training_config_path=base_model.training_config_path,
            )
            if self.model_repository:
                self.model_repository.save(new_model)
                logger.info(
                    "[UpdateModelCommandHandler] Persisted new Model entity (model_id=%s, version=%s) into models table",
                    model_id, new_v_int
                )

            # Reset submitted flag
            if self.client_state:
                if hasattr(self.client_state, "set_submitted"):
                    self.client_state.set_submitted(False)
                elif hasattr(self.client_state, "submitted"):
                    self.client_state.submitted = False
                logger.info("[UpdateModelCommandHandler] Reset ClientState.submitted = False")

        except Exception as exc:
            logger.error("[UpdateModelCommandHandler] Aggregation failed: %s", exc, exc_info=True)
            raise
