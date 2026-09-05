"""Presentation layer for the Client console and CLI interface."""

from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import sys
from typing import List, Optional

from application.submit_training import (
    SubmitTrainingCommand,
    SubmitTrainingCommandHandler,
    SubmitTrainingResult,
    SubmitTrainingValidationError,
)

logger = logging.getLogger("trainswarm.client.cli")


class ConsoleUI:
    """Provides console and command-line execution for the Training Client."""

    def __init__(self, submit_training_handler: Optional[SubmitTrainingCommandHandler] = None) -> None:
        self.submit_training_handler = submit_training_handler

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Construct the CLI argument parser for TrainSwarm Client."""
        parser = argparse.ArgumentParser(
            prog="python main.py",
            description="TrainSwarm Training Client CLI",
        )
        subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

        # submit-training subcommand
        sub_parser = subparsers.add_parser(
            "submit-training",
            help="Submit a model and dataset for distributed training",
        )
        sub_parser.add_argument(
            "--model-path",
            required=True,
            type=str,
            help="Path to the PyTorch base model checkpoint (.pt2)",
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
            "--model-type",
            default="canonical_torch",
            type=str,
            help="Engine model type (default: canonical_torch)",
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

    def run(self, raw_args: Optional[List[str]] = None) -> int:
        """Parse CLI arguments or run standard console banner."""
        parser = self.build_parser()
        args = parser.parse_args(raw_args)

        if args.subcommand == "submit-training":
            return self.handle_submit_training(args)
        elif args.subcommand == "gui":
            # Handled in main.py via GUI runner
            return 0
        else:
            print("========================================")
            print("       TrainSwarm Client Console        ")
            print("========================================")
            print("[Client] Persistence and Coordinator Adapter ready.")
            print("[Client] Use 'python main.py submit-training --help' to submit tasks.")
            print("[Client] Use 'python main.py gui' to launch graphical interface.")
            print("========================================")
            return 0
