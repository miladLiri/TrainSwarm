"""Re-export handler and command for task compatibility."""

from .update_model_command import UpdateModelCommand
from .update_model_handler import UpdateModelCommandHandler

__all__ = ["UpdateModelCommand", "UpdateModelCommandHandler"]
