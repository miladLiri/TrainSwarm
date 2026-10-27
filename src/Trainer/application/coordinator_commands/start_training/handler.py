"""Handler for StartTrainingCommand received from Coordinator."""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Union

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


class TaskLifecycleRecorder:
    """Records timing and status for each step of the start-training lifecycle."""

    def __init__(self, command: StartTrainingCommand, working_directory: Path) -> None:
        self.command = command
        self.working_directory = working_directory
        self.metrics_file = working_directory / "training_lifecycle_metrics.json"
        self.start_time = time.time()
        self.steps: List[Dict[str, Any]] = []
        self._current_step_start: Optional[float] = None
        self._current_step_info: Optional[Dict[str, Any]] = None

    def start_step(self, step_number: int, name: str) -> None:
        self._current_step_start = time.time()
        self._current_step_info = {
            "step_number": step_number,
            "name": name,
            "status": "RUNNING",
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._current_step_start)),
            "end_time": "",
            "duration_sec": 0.0,
            "details": {},
            "error": None,
        }

    def complete_step(self, details: Optional[Dict[str, Any]] = None) -> None:
        if self._current_step_info and self._current_step_start is not None:
            now = time.time()
            self._current_step_info["status"] = "COMPLETED"
            self._current_step_info["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            self._current_step_info["duration_sec"] = round(now - self._current_step_start, 4)
            if details:
                self._current_step_info["details"].update(details)
            self.steps.append(self._current_step_info)
            self._current_step_info = None
            self._current_step_start = None

    def fail_step(self, error: Any) -> None:
        if self._current_step_info and self._current_step_start is not None:
            now = time.time()
            self._current_step_info["status"] = "FAILED"
            self._current_step_info["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            self._current_step_info["duration_sec"] = round(now - self._current_step_start, 4)
            self._current_step_info["error"] = str(error)
            self.steps.append(self._current_step_info)
            self._current_step_info = None
            self._current_step_start = None

    def save(self, status: str = "COMPLETED", error: Optional[str] = None) -> None:
        total_elapsed = round(time.time() - self.start_time, 4)
        report = {
            "task_metadata": {
                "client_node_id": str(self.command.client_node_id),
                "model_id": str(self.command.model_id),
                "model_version": str(self.command.model_version),
                "data_set_id": str(self.command.data_set_id),
                "shard_id": str(self.command.shard_id),
                "status": status,
                "total_elapsed_sec": total_elapsed,
                "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.start_time)),
                "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error": error,
            },
            "steps": self.steps,
        }
        temp_path = self.metrics_file.with_name(f"{self.metrics_file.name}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            os.replace(temp_path, self.metrics_file)
        except Exception as e:
            logger.warning("Failed to write training lifecycle metrics: %s", e)


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
        recorder = TaskLifecycleRecorder(command=command, working_directory=self.working_directory)

        try:
            # Step 1: Query TrainingTask specification from Client over P2P
            recorder.start_step(1, "Request training task specification over P2P")
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
            recorder.complete_step({"training_task_id": getattr(task, "training_task_id", "")})

            # Step 2: Check local cache for base model; stream from Client if missing
            recorder.start_step(2, "Check local cache / stream base model over P2P")
            self.trainer_state.current_step = "Step 2/6: Checking local cache / streaming base model"
            model_ext = ".gz" if getattr(task, "type", "") == "canonical_causal_decoder" else ".pt2"
            expected_model_name = f"{task.baseline_model_id}_{task.baseline_model_version}{model_ext}"
            expected_model_path = self.working_directory / expected_model_name

            is_cached = expected_model_path.is_file()
            if is_cached:
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
            recorder.complete_step({
                "model_name": expected_model_name,
                "cached": is_cached,
                "size_bytes": expected_model_path.stat().st_size if expected_model_path.is_file() else 0,
            })

            # Step 3: Stream assigned dataset shard from Client over P2P
            recorder.start_step(3, "Stream dataset shard over P2P")
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
            recorder.complete_step({
                "shard_name": shard_path.name,
                "size_bytes": shard_path.stat().st_size if shard_path.is_file() else 0,
            })

            # Step 4: Execute local training via TrainingOrchestrator
            recorder.start_step(4, "Execute local training via PyTorch engine")
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
            recorder.complete_step({
                "samples_trained": getattr(result, "samples_trained", 0),
                "final_loss": result.metrics.get("final_loss") if hasattr(result, "metrics") else None,
            })

            # Step 5: Send update delta and metadata to Client over P2P
            recorder.start_step(5, "Transmit weight delta to Client over P2P")
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
            recorder.complete_step({
                "delta_artifact": delta_path.name,
                "size_bytes": delta_path.stat().st_size if delta_path.is_file() else 0,
            })

            # Step 6: Cleanup ephemeral shard and update files, retaining base model
            recorder.start_step(6, "Clean up ephemeral artifacts")
            self.trainer_state.current_step = "Step 6/6: Cleaning up ephemeral artifacts"
            print("[Trainer] [6/6] Cleaning up ephemeral shard and update files...")
            if shard_path and shard_path.is_file():
                shard_path.unlink(missing_ok=True)
                logger.debug("Deleted ephemeral shard file: %s", shard_path)
            if delta_path and delta_path.is_file():
                delta_path.unlink(missing_ok=True)
                logger.debug("Deleted ephemeral update delta file: %s", delta_path)

            print(f"[Trainer] [6/6] Base model retained in cache: {expected_model_name}")
            recorder.complete_step()

            recorder.save(status="COMPLETED")

            self.trainer_state.remove_assigned_task(command.shard_id)
            self.trainer_state.set_status("IDLE")
            print(f"[Trainer] [COMPLETED] Successfully trained and delivered update for shard {command.shard_id}\n")

        except Exception as e:
            recorder.fail_step(e)
            recorder.save(status="FAILED", error=str(e))
            print(f"[Trainer] [ERROR] Training run failed: {e}. Retaining artifacts for diagnosis.", file=sys.stderr)
            logger.error("Training lifecycle failed for shard %s: %s", command.shard_id, e, exc_info=True)
            self.trainer_state.set_status("FAILED")
            raise
        finally:
            self.trainer_state.is_training = False
            self.trainer_state.current_step = ""
