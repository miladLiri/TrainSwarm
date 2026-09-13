"""Presentation layer for the Client console and CLI interface."""

from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import List, Optional

from application.submit_training import (
    SubmitTrainingCommand,
    SubmitTrainingCommandHandler,
    SubmitTrainingResult,
    SubmitTrainingValidationError,
)
try:
    from Client.application.queries.get_training_shards import (
        GetTrainingShardsQuery,
        GetTrainingShardsQueryHandler,
    )
except ImportError:
    from application.queries.get_training_shards import (
        GetTrainingShardsQuery,
        GetTrainingShardsQueryHandler,
    )

logger = logging.getLogger("trainswarm.client.cli")


class ConsoleUI:
    """Provides console and command-line execution for the Training Client."""

    def __init__(
        self,
        submit_training_handler: Optional[SubmitTrainingCommandHandler] = None,
        get_training_shards_handler: Optional[GetTrainingShardsQueryHandler] = None,
    ) -> None:
        self.submit_training_handler = submit_training_handler
        self.get_training_shards_handler = get_training_shards_handler

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Construct the CLI argument parser for TrainSwarm Client."""
        parser = argparse.ArgumentParser(
            prog="python main.py",
            description="TrainSwarm Training Client CLI",
        )
        subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

        # watch-shards subcommand
        watch_parser = subparsers.add_parser(
            "watch-shards",
            help="Watch training shards in real time",
        )
        watch_parser.add_argument(
            "--model-id",
            type=str,
            default=None,
            help="Filter shards by model ID (UUID)",
        )

        # submit-training subcommand
        sub_parser = subparsers.add_parser(
            "submit-training",
            help="Submit a model and dataset for distributed training",
        )
        sub_parser.add_argument(
            "--model-type",
            default="canonical_torch",
            choices=["canonical_torch", "canonical_causal_decoder"],
            type=str,
            help="Engine model type (default: canonical_torch)",
        )
        sub_parser.add_argument(
            "--model-path",
            required=True,
            type=str,
            help="Path to base model file (.pt2 for canonical_torch, .gz/.tar.gz for canonical_causal_decoder)",
        )
        sub_parser.add_argument(
            "--dataset-path",
            required=True,
            type=str,
            help="Path to the canonical PyTorch dataset file (.pt)",
        )
        sub_parser.add_argument(
            "--model-version",
            required=True,
            type=str,
            help="Version identifier of the model (e.g. v1.0)",
        )
        sub_parser.add_argument(
            "--training-config",
            required=True,
            type=str,
            help="Path to training hyperparameters configuration JSON file",
        )

        # gui subcommand
        subparsers.add_parser("gui", help="Launch the PyQt6 desktop graphical user interface")

        return parser

    def handle_submit_training(self, args: argparse.Namespace) -> int:
        """Handle execution of the submit-training CLI subcommand."""
        if not self.submit_training_handler:
            print("[Client] [ERROR] SubmitTrainingCommandHandler is not configured.", file=sys.stderr)
            return 1

        # 1. Validate training config JSON file
        config_path = Path(args.training_config).resolve()
        if not config_path.is_file():
            print(f"[Client] [ERROR] Training configuration file not found: '{config_path}'", file=sys.stderr)
            return 1

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                training_config = json.load(f)
            if not isinstance(training_config, dict):
                print(f"[Client] [ERROR] Training config must be a JSON object, got {type(training_config).__name__}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"[Client] [ERROR] Failed to parse training configuration JSON: {e}", file=sys.stderr)
            return 1

        # 2. Construct SubmitTrainingCommand
        try:
            command = SubmitTrainingCommand(
                model_path=args.model_path,
                dataset_path=args.dataset_path,
                model_version=args.model_version,
                model_type=args.model_type,
                training_config=training_config,
            )
        except SubmitTrainingValidationError as e:
            print(f"[Client] [ERROR] Command validation failed: {e}", file=sys.stderr)
            return 1

        # 3. Progress reporter callback
        def on_progress(msg: str, pct: int) -> None:
            print(f"[Client] [SubmitTraining] [{pct:3d}%] {msg}")
            sys.stdout.flush()

        print("========================================")
        print("  TrainSwarm: Submitting Training Task  ")
        print("========================================")
        result: SubmitTrainingResult = self.submit_training_handler.handle(command, progress_callback=on_progress)

        if not result.success:
            print("========================================", file=sys.stderr)
            print(f"[Client] [SubmitTraining] [FAILURE] {result.error}", file=sys.stderr)
            print("========================================", file=sys.stderr)
            return 1

        print("========================================")
        print("[Client] [SubmitTraining] SUCCESS: Training task successfully submitted!")
        print(f"  Model ID:     {result.model_id}")
        print(f"  Dataset ID:   {result.dataset_id}")
        print(f"  Shard Count:  {result.shard_count}")
        print(f"  Samples/Shard: {result.recommended_samples_per_shard}")
        if result.training_task_ids:
            print(f"  Task IDs ({len(result.training_task_ids)} registered):")
            for tid in result.training_task_ids:
                print(f"    - {tid}")
        print("========================================")
        return 0

    def handle_watch_shards(self, args: argparse.Namespace) -> int:
        """Handle execution of the watch-shards CLI subcommand."""
        if not self.get_training_shards_handler:
            print("[Client] [ERROR] GetTrainingShardsQueryHandler is not configured.", file=sys.stderr)
            return 1

        model_id_filter = getattr(args, "model_id", None)
        query = GetTrainingShardsQuery(model_id=model_id_filter) if model_id_filter else None

        while True:
            shards = self.get_training_shards_handler.handle(query)
            print("========================================================================================")
            print("                       TrainSwarm Client: Active Training Shards                        ")
            print("========================================================================================")
            print(f"{'Model ID':<36} {'Ver':<5} {'Shard ID':<10} {'Status':<11} {'Trainer Node':<20}")
            print("----------------------------------------------------------------------------------------")
            if not shards:
                print("  (No training shards found)")
            else:
                for s in shards:
                    m_id = s.model_id
                    ver = s.model_version
                    shard_id = s.shard_id
                    status = s.status.upper()
                    node = s.trainer_node_id or "-"
                    print(f"{m_id:<36} {ver:<5} {shard_id:<10} {status:<11} {node:<20}")
            print("========================================================================================")
            try:
                choice = input("Press [Enter] to refresh, or type 'q' and press [Enter] to exit: ").strip().lower()
                if choice in ("q", "quit", "exit"):
                    return 0
            except (KeyboardInterrupt, EOFError):
                print("\n[Client] Exiting watch-shards...")
                return 0

    def run(self, raw_args: Optional[List[str]] = None) -> int:
        """Parse CLI arguments or run standard console banner."""
        parser = self.build_parser()
        args = parser.parse_args(raw_args)

        if args.subcommand == "submit-training":
            return self.handle_submit_training(args)
        elif args.subcommand == "watch-shards":
            return self.handle_watch_shards(args)
        elif args.subcommand == "gui":
            # Handled in main.py via GUI runner
            return 0
        else:
            print("========================================")
            print("       TrainSwarm Client Console        ")
            print("========================================")
            print("[Client] Persistence and Coordinator Adapter ready.")
            print("[Client] Inbound P2P request listener active.")
            print("[Client] Running in headless CLI mode. Press Ctrl+C to exit.")
            print("========================================")
            sys.stdout.flush()
            try:
                while True:
                    time.sleep(1.0)
            except (KeyboardInterrupt, SystemExit):
                print("\n[Client] Shutting down...")
                return 0
