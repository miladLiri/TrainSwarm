"""Command dispatcher and handler registry for the Trainer."""

import json
import logging
from typing import Any, Dict, Tuple, Type
from domain.commands import CommandEnvelope, CommandType
from application.command_handlers import ICommandHandler

logger = logging.getLogger(__name__)


class CommandDispatcher:
    """Dispatches generic CommandEnvelope messages to registered typed command handlers."""

    def __init__(self) -> None:
        self._registry: Dict[str, Tuple[Type[Any], ICommandHandler]] = {}

    def register_handler(
        self,
        command_type: CommandType | str,
        model_class: Type[Any],
        handler: ICommandHandler,
    ) -> None:
        """Registers a typed handler and model class for a given command type."""
        type_key = command_type.value if isinstance(command_type, CommandType) else str(command_type)
        self._registry[type_key] = (model_class, handler)
        logger.debug(
            "[CommandDispatcher] Registered handler '%s' for command type '%s'.",
            handler.__class__.__name__,
            type_key,
        )

    def dispatch(self, envelope: CommandEnvelope) -> bool:
        """
        Dispatches a generic CommandEnvelope to the appropriate typed handler.
        Returns True if handled successfully, False if skipped or failed.
        """
        command_id = envelope.id
        command_type = envelope.type

        logger.info("[CommandDispatcher] Processing command '%s' (ID: '%s').", command_type, command_id)

        if command_type not in self._registry:
            logger.warning(
                "[CommandDispatcher] [WARN] Unknown command type '%s' (ID: '%s'). Safely ignoring.",
                command_type,
                command_id,
            )
            print(f"\n[Trainer] [WARN] Received unknown command type '{command_type}' (ID: {command_id}). Ignored.")
            return False

        model_class, handler = self._registry[command_type]

        # 1. Parse JSON string data payload
        try:
            raw_data = envelope.data
            if not raw_data:
                payload_dict = {}
            elif isinstance(raw_data, str):
                payload_dict = json.loads(raw_data)
            elif isinstance(raw_data, dict):
                payload_dict = raw_data
            else:
                logger.error(
                    "[CommandDispatcher] Unsupported payload format for command '%s' (ID: '%s'): %s",
                    command_type,
                    command_id,
                    type(raw_data),
                )
                return False
        except Exception as e:
            logger.error(
                "[CommandDispatcher] Malformed JSON payload in command '%s' (ID: '%s'): %s",
                command_type,
                command_id,
                e,
            )
            print(f"\n[Trainer] [ERROR] Failed to parse JSON payload for command '{command_type}' (ID: {command_id}): {e}")
            return False

        # 2. Convert to typed command model
        try:
            if hasattr(model_class, "from_dict") and callable(getattr(model_class, "from_dict")):
                typed_command = model_class.from_dict(payload_dict)
            else:
                typed_command = model_class(**payload_dict)
        except Exception as e:
            logger.error(
                "[CommandDispatcher] Failed to deserialize payload into model '%s' for command '%s' (ID: '%s'): %s",
                model_class.__name__,
                command_type,
                command_id,
                e,
            )
            print(f"\n[Trainer] [ERROR] Deserialization error for '{command_type}' (ID: {command_id}): {e}")
            return False

        # 3. Invoke handler
        try:
            handler.handle(typed_command)
            logger.info(
                "[CommandDispatcher] Successfully executed handler for command '%s' (ID: '%s').",
                command_type,
                command_id,
            )
            return True
        except Exception as e:
            logger.error(
                "[CommandDispatcher] Handler '%s' execution failed for command '%s' (ID: '%s'): %s",
                handler.__class__.__name__,
                command_type,
                command_id,
                e,
                exc_info=True,
            )
            print(f"\n[Trainer] [ERROR] Handler execution failure for '{command_type}' (ID: {command_id}): {e}")
            return False
