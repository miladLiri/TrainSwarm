"""Command dispatcher for Coordinator streaming commands."""

from __future__ import annotations
from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Callable, Dict, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .start_training.command import CommandEnvelope

logger = logging.getLogger(__name__)


class ICommandHandler(ABC):
    """Abstract base class for typed command handlers."""

    @abstractmethod
    def handle(self, command: Any) -> None:
        """Handle the strongly typed command."""
        pass


class CommandDispatcher:
    """Dispatches incoming CommandEnvelope instances to registered strongly-typed handlers."""

    def __init__(self) -> None:
        self._handlers: Dict[str, ICommandHandler] = {}
        self._model_classes: Dict[str, Type[Any]] = {}

    def register_handler(
        self,
        command_type: str,
        model_class: Type[Any],
        handler: ICommandHandler,
    ) -> None:
        """Register a handler and model class for a specific CommandType."""
        type_str = str(command_type.value if hasattr(command_type, "value") else command_type)
        self._handlers[type_str] = handler
        self._model_classes[type_str] = model_class
        logger.info("[CommandDispatcher] Registered handler for command type: '%s'", type_str)

    def dispatch(self, envelope: CommandEnvelope) -> None:
        """Parse raw envelope payload into strongly-typed command and invoke registered handler."""
        type_str = str(envelope.type)
        handler = self._handlers.get(type_str)
        model_class = self._model_classes.get(type_str)

        if not handler or not model_class:
            logger.warning("[CommandDispatcher] No handler registered for command type '%s'. Discarding envelope.", type_str)
            return

        try:
            # Parse raw UTF-8 JSON payload
            raw_data = envelope.data
            if isinstance(raw_data, (bytes, bytearray)):
                raw_data = raw_data.decode("utf-8")

            payload_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

            # Deserialize strongly-typed command instance
            if hasattr(model_class, "from_dict") and callable(getattr(model_class, "from_dict")):
                typed_command = model_class.from_dict(payload_dict)
            else:
                typed_command = model_class(**payload_dict)

            # Invoke handler
            logger.info("[CommandDispatcher] Dispatching '%s' (Envelope ID: %s)", type_str, envelope.id)
            handler.handle(typed_command)

        except Exception as e:
            logger.error(
                "[CommandDispatcher] Error dispatching command '%s' (Envelope ID: %s): %s",
                type_str,
                envelope.id,
                e,
                exc_info=True,
            )
