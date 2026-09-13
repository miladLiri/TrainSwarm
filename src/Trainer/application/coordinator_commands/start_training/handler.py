"""Handler for StartTrainingCommand received from Coordinator."""

from __future__ import annotations
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Optional, Union

try:
    from Trainer.application.state import TrainerState
    from Trainer.application.coordinator_commands.dispatcher import ICommandHandler
    from Trainer.infrastructure.adapters.trainer_p2p_node_adapter import (
        ITrainerP2PNodeAdapter,
        TrainerP2PNodeAdapter,
    )
    from .command import StartTrainingCommand
except ImportError:
    from application.state import TrainerState
    from application.coordinator_commands.dispatcher import ICommandHandler
    from infrastructure.adapters.trainer_p2p_node_adapter import (
        ITrainerP2PNodeAdapter,
        TrainerP2PNodeAdapter,
    )
    from .command import StartTrainingCommand

try:
    from distributed_training_engine.training import TrainingOrchestrator
except ImportError:
    try:
        from distributed_training_engine import TrainingOrchestrator
    except ImportError:
        pass

logger = logging.getLogger("trainswarm.trainer.start_training")


class StartTrainingHandler(ICommandHandler):
    """Handler executing the complete 6-step P2P training execution lifecycle."""

    def __init__(
        self,
        trainer_state: TrainerState,
        p2p_node_adapter: Optional[ITrainerP2PNodeAdapter] = None,
        training_orchestrator: Optional[object] = None,
        working_directory: Optional[Union[str, Path]] = None,
    ) -> None:
        self.trainer_state = trainer_state
        self.p2p_node_adapter = p2p_node_adapter or TrainerP2PNodeAdapter()
        self.training_orchestrator = training_orchestrator or TrainingOrchestrator()
        work_dir = working_directory or os.getenv("WORKING_DIR", ".")
        self.working_directory = Path(work_dir).resolve()
        self.working_directory.mkdir(parents=True, exist_ok=True)

    def handle(self, command: StartTrainingCommand) -> None:
        logger.info(
            "[StartTrainingHandler] Received StartTrainingCommand - ClientNodeId: %s, ModelId: %s, ModelVersion: %s, DataSetId: %s, ShardId: %s",
            command.client_node_id,
            command.model_id,
            command.model_version,
            command.data_set_id,
            command.shard_id,
        )
        print(
            f"\n[Trainer] [START TRAINING] Model: {command.model_id} v{command.model_version}, "
            f"Dataset: {command.data_set_id} (Shard {command.shard_id}) from Client: {command.client_node_id}"
        )

        self.trainer_state.is_training = True
        self.trainer_state.set_status("TRAINING")
        self.trainer_state.add_assigned_task(command.shard_id)

        shard_path: Optional[Path] = None
        delta_path: Optional[Path] = None

        try:
            # Step 1: Query TrainingTask specification from Client over P2P
            self.trainer_state.current_step = "Step 1/6: Requesting training task specification over P2P"
            print("[Trainer] [1/6] Requesting training task specification over P2P...")
            task = self.p2p_node_adapter.get_training_task(
                client_node_id=command.client_node_id,
                model_id=command.model_id,
                model_version=str(command.model_version),
                data_set_id=command.data_set_id,
                shard_id=str(command.shard_id),
            )
            print(f"[Trainer] [1/6] Training task envelope received: {task.training_task_id}")

            # Step 2: Check local cache for base model; stream from Client if missing
            self.trainer_state.current_step = "Step 2/6: Checking local cache / streaming base model"
            model_ext = ".gz" if getattr(task, "type", "") == "canonical_causal_decoder" else ".pt2"
            expected_model_name = f"{task.baseline_model_id}_{task.baseline_model_version}{model_ext}"
            expected_model_path = self.working_directory / expected_model_name

            if expected_model_path.is_file():
                print(f"[Trainer] [2/6] Base model found in cache ({expected_model_name}), skipping P2P transfer.")
            else:
                print(f"[Trainer] [2/6] Base model not found in cache. Streaming {expected_model_name} over P2P...")
                downloaded_model_path = self.p2p_node_adapter.get_model(
                    client_node_id=command.client_node_id,
                    model_id=command.model_id,
                    model_version=str(command.model_version),
                )
                if Path(downloaded_model_path).resolve() != expected_model_path.resolve():
                    shutil.copyfile(downloaded_model_path, expected_model_path)
                print(f"[Trainer] [2/6] Base model successfully downloaded: {expected_model_path.name}")

            # Step 3: Stream assigned dataset shard from Client over P2P
            self.trainer_state.current_step = "Step 3/6: Streaming dataset shard over P2P"
            expected_shard_name = f"{task.data_set_id}_{task.data_set_shard_id}.pt"
            expected_shard_path = self.working_directory / expected_shard_name

            print(f"[Trainer] [3/6] Streaming dataset shard {expected_shard_name} over P2P...")
            downloaded_shard_path = self.p2p_node_adapter.get_shard(
                client_node_id=command.client_node_id,
                model_id=command.model_id,
                model_version=str(command.model_version),
                data_set_id=command.data_set_id,
                shard_id=str(command.shard_id),
            )
            if Path(downloaded_shard_path).resolve() != expected_shard_path.resolve():
                shutil.copyfile(downloaded_shard_path, expected_shard_path)
            shard_path = expected_shard_path
            print(f"[Trainer] [3/6] Dataset shard successfully downloaded: {shard_path.name}")

            # Step 4: Execute local training via TrainingOrchestrator
            self.trainer_state.current_step = "Step 4/6: Executing local PyTorch training"
            print(f"[Trainer] [4/6] Executing local training via PyTorch engine...")
            result = self.training_orchestrator.run(
                task=task,
                working_directory=self.working_directory,
            )
            self.trainer_state.metrics = getattr(result, "metrics", {}) or {}
            print(
                f"[Trainer] [4/6] Training completed: {result.samples_trained} samples trained, "
                f"final loss: {result.metrics.get('final_loss', 'N/A')}"
            )

            # Step 5: Send update delta and metadata to Client over P2P
            self.trainer_state.current_step = "Step 5/6: Transmitting weight delta to Client over P2P"
            raw_delta_path = Path(result.delta.path)
            if raw_delta_path.is_absolute():
                delta_path = raw_delta_path
            else:
                delta_path = self.working_directory / raw_delta_path

            print(f"[Trainer] [5/6] Transmitting update artifact {delta_path.name} to Client over P2P...")
            self.p2p_node_adapter.send_update(
                client_node_id=command.client_node_id,
                training_result=result,
                update_artifact_path=str(delta_path),
            )
            print("[Trainer] [5/6] Training update confirmed by Client.")

            # Step 6: Cleanup ephemeral shard and update files, retaining base model
            self.trainer_state.current_step = "Step 6/6: Cleaning up ephemeral artifacts"
            print("[Trainer] [6/6] Cleaning up ephemeral shard and update files...")
            if shard_path and shard_path.is_file():
                shard_path.unlink(missing_ok=True)
                logger.debug("Deleted ephemeral shard file: %s", shard_path)
            if delta_path and delta_path.is_file():
                delta_path.unlink(missing_ok=True)
                logger.debug("Deleted ephemeral update delta file: %s", delta_path)

            print(f"[Trainer] [6/6] Base model retained in cache: {expected_model_name}")

            self.trainer_state.remove_assigned_task(command.shard_id)
            self.trainer_state.set_status("IDLE")
            print(f"[Trainer] [COMPLETED] Successfully trained and delivered update for shard {command.shard_id}\n")

        except Exception as e:
            print(f"[Trainer] [ERROR] Training run failed: {e}. Retaining artifacts for diagnosis.", file=sys.stderr)
            logger.error("Training lifecycle failed for shard %s: %s", command.shard_id, e, exc_info=True)
            self.trainer_state.set_status("FAILED")
            raise
        finally:
            self.trainer_state.is_training = False
            self.trainer_state.current_step = ""
