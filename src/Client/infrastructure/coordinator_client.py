"""HTTP client infrastructure for communicating with the Coordinator API."""

import json
from typing import Optional, Dict, Any
from domain.models import Session

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


class CoordinatorError(Exception):
    """Base exception for Coordinator client errors."""
    pass


class CoordinatorConnectionError(CoordinatorError):
    """Raised when the Coordinator cannot be reached."""
    pass


class CoordinatorApiError(CoordinatorError):
    """Raised when the Coordinator returns an HTTP error status."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Coordinator API error ({status_code}): {message}")
        self.status_code = status_code
        self.message = message


class HttpCoordinatorClient:
    """Handles HTTP communication with the Coordinator REST API."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_session(self, client_node_id: str, name: Optional[str] = None) -> Session:
        """Sends a request to Coordinator to create a new training session."""
        url = f"{self.base_url}/api/sessions"
        payload: Dict[str, Any] = {
            "clientNodeId": client_node_id,
        }
        if name and name.strip():
            payload["name"] = name.strip()

        if HAS_REQUESTS:
            return self._send_requests(url, payload, client_node_id)
        else:
            return self._send_urllib(url, payload, client_node_id)

    def _send_requests(self, url: str, payload: Dict[str, Any], client_node_id: str) -> Session:
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            raise CoordinatorConnectionError(
                f"Cannot connect to Coordinator at {self.base_url} (Connection refused or host unreachable)"
            ) from e
        except requests.exceptions.Timeout as e:
            raise CoordinatorConnectionError(
                f"Request to Coordinator at {self.base_url} timed out after {self.timeout}s"
            ) from e
        except requests.exceptions.RequestException as e:
            raise CoordinatorConnectionError(
                f"Network communication failed with {self.base_url}: {str(e)}"
            ) from e

        if not response.ok:
            error_detail = response.text
            try:
                err_json = response.json()
                if isinstance(err_json, dict) and "error" in err_json:
                    error_detail = err_json["error"]
            except Exception:
                pass
            raise CoordinatorApiError(response.status_code, error_detail)

        data = response.json()
        return self._parse_session_response(data, client_node_id)

    def _send_urllib(self, url: str, payload: Dict[str, Any], client_node_id: str) -> Session:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_bytes = resp.read()
                data = json.loads(resp_bytes.decode("utf-8"))
                return self._parse_session_response(data, client_node_id)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_body)
                if isinstance(err_json, dict) and "error" in err_json:
                    err_body = err_json["error"]
            except Exception:
                pass
            raise CoordinatorApiError(e.code, err_body)
        except urllib.error.URLError as e:
            raise CoordinatorConnectionError(
                f"Cannot connect to Coordinator at {self.base_url} ({e.reason})"
            ) from e
        except Exception as e:
            raise CoordinatorConnectionError(
                f"Network communication failed with {self.base_url}: {str(e)}"
            ) from e

    def _parse_session_response(self, data: Dict[str, Any], client_node_id: str) -> Session:
        session_id = str(data.get("id") or data.get("sessionId") or "")
        session_name = str(data.get("name") or "")
        returned_client_node_id = str(data.get("clientNodeId") or client_node_id)
        status = str(data.get("status") or "NONE")

        return Session(
            session_id=session_id,
            name=session_name,
            client_node_id=returned_client_node_id,
            status=status,
        )