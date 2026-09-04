"""Coordinator API adapter for TrainSwarm Client infrastructure."""

import logging
import os
from typing import Any, Dict, List, Optional
import requests

from .create_training_task import CreateTrainingTaskDto

logger = logging.getLogger(__name__)

ENV_COORDINATOR_ADDRESS = "COORDINATOR_ADDRESS"
FALLBACK_ENV_COORDINATOR_URL = "COORDINATOR_URL"
DEFAULT_TIMEOUT_SECONDS = 10.0


class CoordinatorAdapterError(Exception):
    """Base exception for all Coordinator adapter failures."""
    pass


class CoordinatorConfigurationError(CoordinatorAdapterError):
    """Raised when Coordinator address configuration is missing or invalid."""
    pass


class CoordinatorApiError(CoordinatorAdapterError):
    """Raised when the Coordinator API returns a non-success HTTP status code."""

    def __init__(self, status_code: int, response_text: str):
        super().__init__(f"Coordinator API error ({status_code}): {response_text}")
        self.status_code = status_code
        self.response_text = response_text


class CoordinatorNetworkError(CoordinatorAdapterError):
    """Raised when low-level network communication fails (timeout, connection refused, DNS)."""
    pass


class CoordinatorAdapter:
    """Adapter for HTTP communication with the Coordinator REST API."""

    def __init__(
        self,
        coordinator_address: Optional[str] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize CoordinatorAdapter.

        Args:
            coordinator_address: Optional explicit Coordinator base URL. If None, reads from
                                 COORDINATOR_ADDRESS environment variable.
            timeout_seconds: Request timeout in seconds.
            session: Optional reusable requests.Session for connection pooling and testing.

        Raises:
            CoordinatorConfigurationError: If COORDINATOR_ADDRESS is missing, empty, or whitespace.
        """
        self.timeout = float(timeout_seconds)
        self.base_url = self._resolve_address(coordinator_address)
        self._session = session or requests.Session()
        self._owns_session = session is None

    @staticmethod
    def _resolve_address(coordinator_address: Optional[str]) -> str:
        """Resolve and normalize Coordinator base address from argument or environment."""
        if coordinator_address is not None:
            raw = str(coordinator_address).strip()
            if not raw:
                raise CoordinatorConfigurationError(
                    f"Coordinator address cannot be empty. Missing environment variable '{ENV_COORDINATOR_ADDRESS}'."
                )
            return raw.rstrip("/")

        env_val = os.getenv(ENV_COORDINATOR_ADDRESS, "").strip()
        if not env_val:
            # Check secondary legacy variable without silent fallback to localhost
            env_val = os.getenv(FALLBACK_ENV_COORDINATOR_URL, "").strip()

        if not env_val:
            raise CoordinatorConfigurationError(
                f"Missing required environment variable '{ENV_COORDINATOR_ADDRESS}'."
            )

        return env_val.rstrip("/")

    def create_training_task(self, request: CreateTrainingTaskDto) -> List[str]:
        """Request creation of training tasks from the Coordinator API.

        Args:
            request: Validated CreateTrainingTaskDto instance.

        Returns:
            List of created Training Task IDs (GUID strings).

        Raises:
            CoordinatorApiError: If Coordinator returns non-success HTTP status.
            CoordinatorNetworkError: If transport fails or times out.
            CoordinatorAdapterError: If response body is malformed or missing trainingTaskIds.
        """
        if not isinstance(request, CreateTrainingTaskDto):
            raise TypeError("request must be an instance of CreateTrainingTaskDto")

        url = f"{self.base_url}/api/training-tasks"
        payload = request.to_dict()
        headers = {"Content-Type": "application/json"}

        diag_context: Dict[str, Any] = {
            "coordinator_address": self.base_url,
            "method": "POST",
            "endpoint": "/api/training-tasks",
            "model_id": request.model_id,
            "model_version": request.model_version,
            "data_set_id": request.data_set_id,
            "shard_count": len(request.shard_id_list),
        }

        try:
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            logger.error(
                "Request to Coordinator timed out after %.1fs | Context: %s",
                self.timeout,
                diag_context,
            )
            raise CoordinatorNetworkError(
                f"Request to Coordinator at {self.base_url} timed out after {self.timeout}s"
            ) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "Connection failed communicating with Coordinator at %s | Context: %s",
                self.base_url,
                diag_context,
            )
            raise CoordinatorNetworkError(
                f"Cannot connect to Coordinator at {self.base_url} (Connection refused or host unreachable)"
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(
                "Network request exception communicating with Coordinator: %s | Context: %s",
                e,
                diag_context,
            )
            raise CoordinatorNetworkError(
                f"Network communication failed with {self.base_url}: {e}"
            ) from e

        # Validate HTTP Status Code
        if not response.ok:
            error_body = response.text
            logger.error(
                "Coordinator returned HTTP error status %d: %s | Context: %s",
                response.status_code,
                error_body,
                diag_context,
            )
            raise CoordinatorApiError(response.status_code, error_body)

        # Validate HTTP Response Body
        try:
            data = response.json()
        except Exception as e:
            logger.error(
                "Coordinator returned status %d with invalid JSON body: %s | Context: %s",
                response.status_code,
                response.text,
                diag_context,
            )
            raise CoordinatorAdapterError(
                f"Coordinator returned status {response.status_code} with invalid JSON body"
            ) from e

        if not isinstance(data, dict):
            logger.error(
                "Coordinator returned non-object JSON body (%s) | Context: %s",
                type(data).__name__,
                diag_context,
            )
            raise CoordinatorAdapterError(
                "Coordinator response body must be a JSON object"
            )

        task_ids = data.get("trainingTaskIds")
        if task_ids is None or not isinstance(task_ids, list):
            logger.error(
                "Coordinator response missing expected 'trainingTaskIds' collection: %s | Context: %s",
                data,
                diag_context,
            )
            raise CoordinatorAdapterError(
                "Coordinator response body is missing valid 'trainingTaskIds' collection"
            )

        return [str(tid) for tid in task_ids]

    def close(self) -> None:
        """Close underlying HTTP session if owned by adapter."""
        if self._owns_session and self._session:
            self._session.close()

    def __enter__(self) -> "CoordinatorAdapter":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
