"""Coordinator API adapter for TrainSwarm Trainer infrastructure."""

from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0


class CoordinatorAdapterError(Exception):
    """Base exception for Coordinator adapter initialization errors."""
    pass


class CoordinatorConfigurationError(CoordinatorAdapterError):
    """Raised when Coordinator address configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class CoordinatorAdapterResult:
    """Standardized result returned by CoordinatorAdapter operations."""

    success: bool
    description: str
    trainer_id: Optional[str] = None
    status_code: Optional[int] = None


class CoordinatorAdapter:
    """Adapter for HTTP communication with the Coordinator REST API."""

    def __init__(
        self,
        coordinator_address: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = float(timeout_seconds)
        self.base_url = self._resolve_address(coordinator_address)
        self._session = session or requests.Session()
        self._owns_session = session is None

    @staticmethod
    def _resolve_address(coordinator_address: str) -> str:
        """Resolve and normalize Coordinator base address."""
        if coordinator_address is None:
            raise CoordinatorConfigurationError(
                "Missing required coordinator_address parameter."
            )
        raw = str(coordinator_address).strip()
        if not raw:
            raise CoordinatorConfigurationError(
                "Coordinator address cannot be empty."
            )
        return raw.rstrip("/")

    def connect_trainer(self, trainer_node_id: str) -> CoordinatorAdapterResult:
        """Call Coordinator's POST /api/trainers/connect endpoint.

        Args:
            trainer_node_id: Logical string identifier of the trainer node.

        Returns:
            CoordinatorAdapterResult with outcome details. Never raises unhandled network exceptions.
        """
        node_id = str(trainer_node_id).strip()
        if not node_id:
            return CoordinatorAdapterResult(
                success=False,
                description="Trainer node ID cannot be empty or whitespace.",
            )

        url = f"{self.base_url}/api/trainers/connect"
        payload = {"trainerNodeId": node_id}
        headers = {"Content-Type": "application/json"}

        try:
            logger.info("Connecting to Coordinator at %s with TrainerNodeId='%s'...", url, node_id)
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            logger.error("Request to Coordinator timed out after %.1fs: %s", self.timeout, e)
            return CoordinatorAdapterResult(
                success=False,
                description=f"Request to Coordinator at {self.base_url} timed out after {self.timeout}s.",
            )
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection failed communicating with Coordinator at %s: %s", self.base_url, e)
            return CoordinatorAdapterResult(
                success=False,
                description=f"Cannot connect to Coordinator at {self.base_url} (Connection refused or unreachable).",
            )
        except requests.exceptions.RequestException as e:
            logger.error("Network error communicating with Coordinator: %s", e)
            return CoordinatorAdapterResult(
                success=False,
                description=f"Network communication failed with Coordinator at {self.base_url}: {e}",
            )

        # Validate HTTP status code
        if response.status_code in (200, 201):
            try:
                data: Dict[str, Any] = response.json()
                trainer_id = data.get("id")
                return CoordinatorAdapterResult(
                    success=True,
                    description="Trainer registered successfully with Coordinator.",
                    trainer_id=str(trainer_id) if trainer_id else None,
                    status_code=response.status_code,
                )
            except Exception as ex:
                logger.error("Coordinator returned status %d with invalid JSON: %s", response.status_code, ex)
                return CoordinatorAdapterResult(
                    success=False,
                    description=f"Coordinator returned status {response.status_code} with invalid JSON payload.",
                    status_code=response.status_code,
                )

        error_body = response.text
        logger.error(
            "Coordinator returned HTTP error status %d: %s",
            response.status_code,
            error_body,
        )
        return CoordinatorAdapterResult(
            success=False,
            description=f"Coordinator returned HTTP {response.status_code}: {error_body}",
            status_code=response.status_code,
        )

    def close(self) -> None:
        """Close underlying HTTP session if owned by adapter."""
        if self._owns_session and self._session:
            self._session.close()

    def __enter__(self) -> "CoordinatorAdapter":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
