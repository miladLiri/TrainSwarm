"""HTTP client infrastructure for communicating with the Coordinator API from Trainer."""

import json
from typing import Optional, Dict, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


class CoordinatorClient:
    """Handles communication with the Coordinator API."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def check_health(self) -> Dict[str, Any]:
        """Checks if the Coordinator is reachable and returns health/status info."""
        url = f"{self.base_url}/api/sessions"
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, timeout=self.timeout)
                return {"reachable": True, "status_code": resp.status_code}
            except requests.exceptions.RequestException as e:
                return {"reachable": False, "error": str(e)}
        else:
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return {"reachable": True, "status_code": resp.status}
            except urllib.error.HTTPError as e:
                return {"reachable": True, "status_code": e.code}
            except Exception as e:
                return {"reachable": False, "error": str(e)}

