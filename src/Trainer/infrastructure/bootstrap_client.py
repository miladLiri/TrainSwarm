"""HTTP client infrastructure for communicating with the Bootstrap Relay service."""

import json
from typing import Optional, Dict, Any, List
from domain.models import PeerSession

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


class BootstrapError(Exception):
    """Base exception for Bootstrap client errors."""
    pass


class BootstrapConnectionError(BootstrapError):
    """Raised when the Bootstrap relay cannot be reached."""
    pass


class BootstrapApiError(BootstrapError):
    """Raised when the Bootstrap relay returns an HTTP error status."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Bootstrap Relay API error ({status_code}): {message}")
        self.status_code = status_code
        self.message = message


class BootstrapClient:
    """Handles HTTP communication with the Bootstrap Relay API."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def register_peer(
        self,
        node_id: str,
        role: str = "trainer",
        endpoint: Optional[str] = None,
    ) -> PeerSession:
        """Registers the node with the Bootstrap relay and returns an assigned PeerSession."""
        url = f"{self.base_url}/api/peers/register"
        payload = {
            "nodeId": node_id,
            "role": role,
            "endpoint": endpoint,
        }

        data = self._post_json(url, payload)
        return PeerSession(
            peer_id=str(data.get("peerId", "")),
            node_id=str(data.get("nodeId", node_id)),
            role=str(data.get("role", role)),
            relay_address=str(data.get("relayAddress", self.base_url)),
            registered_at=str(data.get("registeredAt", "")),
        )

    def list_peers(self) -> List[Dict[str, Any]]:
        """Queries the Bootstrap relay for all active registered peers."""
        url = f"{self.base_url}/api/peers"
        data = self._get_json(url)
        if isinstance(data, list):
            return data
        return []

    def send_relay_message(
        self,
        source_peer_id: str,
        target_peer_id: str,
        payload: Any,
    ) -> Dict[str, Any]:
        """Enqueues a message for a target peer via the relay."""
        url = f"{self.base_url}/api/relay/send"
        req_body = {
            "sourcePeerId": source_peer_id,
            "targetPeerId": target_peer_id,
            "payload": payload,
        }
        return self._post_json(url, req_body)

    def get_inbox(self, peer_id: str) -> List[Dict[str, Any]]:
        """Retrieves and clears queued messages for this peer."""
        url = f"{self.base_url}/api/relay/inbox/{peer_id}"
        data = self._get_json(url)
        if isinstance(data, dict):
            return data.get("messages", [])
        return []

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if HAS_REQUESTS:
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
            except requests.exceptions.ConnectionError as e:
                raise BootstrapConnectionError(
                    f"Cannot connect to Bootstrap Relay at {self.base_url} (Connection refused or unreachable)"
                ) from e
            except requests.exceptions.Timeout as e:
                raise BootstrapConnectionError(
                    f"Request to Bootstrap Relay at {self.base_url} timed out after {self.timeout}s"
                ) from e
            except requests.exceptions.RequestException as e:
                raise BootstrapConnectionError(
                    f"Network error with Bootstrap Relay at {self.base_url}: {str(e)}"
                ) from e

            if not resp.ok:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    if isinstance(err_json, dict) and "detail" in err_json:
                        err_detail = err_json["detail"]
                except Exception:
                    pass
                raise BootstrapApiError(resp.status_code, err_detail)

            return resp.json()
        else:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                try:
                    err_json = json.loads(err_body)
                    if isinstance(err_json, dict) and "detail" in err_json:
                        err_body = err_json["detail"]
                except Exception:
                    pass
                raise BootstrapApiError(e.code, err_body)
            except urllib.error.URLError as e:
                raise BootstrapConnectionError(
                    f"Cannot connect to Bootstrap Relay at {self.base_url} ({e.reason})"
                ) from e
            except Exception as e:
                raise BootstrapConnectionError(
                    f"Network error with Bootstrap Relay at {self.base_url}: {str(e)}"
                ) from e

    def _get_json(self, url: str) -> Any:
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, timeout=self.timeout)
            except requests.exceptions.ConnectionError as e:
                raise BootstrapConnectionError(
                    f"Cannot connect to Bootstrap Relay at {self.base_url} (Connection refused or unreachable)"
                ) from e
            except requests.exceptions.Timeout as e:
                raise BootstrapConnectionError(
                    f"Request to Bootstrap Relay at {self.base_url} timed out after {self.timeout}s"
                ) from e
            except requests.exceptions.RequestException as e:
                raise BootstrapConnectionError(
                    f"Network error with Bootstrap Relay at {self.base_url}: {str(e)}"
                ) from e

            if not resp.ok:
                raise BootstrapApiError(resp.status_code, resp.text)
            return resp.json()
        else:
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raise BootstrapApiError(e.code, e.read().decode("utf-8", errors="ignore"))
            except urllib.error.URLError as e:
                raise BootstrapConnectionError(
                    f"Cannot connect to Bootstrap Relay at {self.base_url} ({e.reason})"
                ) from e
            except Exception as e:
                raise BootstrapConnectionError(
                    f"Network error with Bootstrap Relay at {self.base_url}: {str(e)}"
                ) from e

