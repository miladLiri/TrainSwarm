"""Long-lived gRPC command stream listener with automatic 5s reconnection."""

import logging
import threading
import time
from typing import Optional

import grpc

try:
    from infrastructure import coordinator_commands_pb2, coordinator_commands_pb2_grpc
except ImportError:
    import coordinator_commands_pb2, coordinator_commands_pb2_grpc

from application.command_dispatcher import CommandDispatcher
from domain.commands import CommandEnvelope

logger = logging.getLogger(__name__)


class TrainerCommandListener:
    """Manages the long-lived server-streaming gRPC connection from Coordinator to Trainer."""

    def __init__(
        self,
        trainer_node_id: str,
        coordinator_grpc_url: str,
        command_dispatcher: CommandDispatcher,
        reconnect_interval_seconds: float = 5.0,
    ) -> None:
        self.trainer_node_id = trainer_node_id
        self.coordinator_grpc_url = coordinator_grpc_url
        self.command_dispatcher = command_dispatcher
        self.reconnect_interval_seconds = reconnect_interval_seconds

        self._is_running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._active_channel: Optional[grpc.Channel] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        """Starts the background listening thread."""
        if self._is_running:
            return

        self._is_running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="TrainerCommandListenerThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("[TrainerCommandListener] Background command listener started.")

    def stop(self) -> None:
        """Stops the listener and closes the active channel."""
        self._is_running = False
        self._connected = False
        if self._active_channel:
            try:
                self._active_channel.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("[TrainerCommandListener] Background command listener stopped.")

    def _listen_loop(self) -> None:
        while self._is_running:
            channel: Optional[grpc.Channel] = None
            try:
                logger.info(
                    "[TrainerCommandListener] Connecting to Coordinator gRPC at %s...",
                    self.coordinator_grpc_url,
                )
                channel = grpc.insecure_channel(self.coordinator_grpc_url)
                self._active_channel = channel
                stub = coordinator_commands_pb2_grpc.CoordinatorCommandServiceStub(channel)

                request = coordinator_commands_pb2.TrainerRegistrationRequest(
                    trainer_id=self.trainer_node_id
                )
                logger.info(
                    "[TrainerCommandListener] Subscribing to commands for trainer '%s'...",
                    self.trainer_node_id,
                )

                stream = stub.SubscribeCommands(request)
                self._connected = True
                logger.info("[TrainerCommandListener] Connected to Coordinator command stream.")
                print(f"[Trainer] Connected to Coordinator command stream at {self.coordinator_grpc_url}.")

                for proto_envelope in stream:
                    if not self._is_running:
                        break
                    domain_envelope = CommandEnvelope(
                        id=proto_envelope.id,
                        type=proto_envelope.type,
                        data=proto_envelope.data,
                    )
                    self.command_dispatcher.dispatch(domain_envelope)

            except grpc.RpcError as rpc_err:
                if not self._is_running:
                    break
                self._connected = False
                details = rpc_err.details() if hasattr(rpc_err, "details") and rpc_err.details() else str(rpc_err)
                logger.warning(
                    "[TrainerCommandListener] Stream disconnected: %s. Reconnecting in %.0f seconds...",
                    details,
                    self.reconnect_interval_seconds,
                )
                print(
                    f"[Trainer] [WARN] Coordinator command stream disconnected. Reconnecting in {int(self.reconnect_interval_seconds)}s..."
                )
            except Exception as ex:
                if not self._is_running:
                    break
                self._connected = False
                logger.error(
                    "[TrainerCommandListener] Unexpected stream error: %s. Reconnecting in %.0f seconds...",
                    ex,
                    self.reconnect_interval_seconds,
                )
                print(
                    f"[Trainer] [ERROR] Command stream error: {ex}. Reconnecting in {int(self.reconnect_interval_seconds)}s..."
                )
            finally:
                if channel:
                    try:
                        channel.close()
                    except Exception:
                        pass
                self._active_channel = None

            if self._is_running:
                time.sleep(self.reconnect_interval_seconds)
