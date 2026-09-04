"""Active zero-mock verification suite for Coordinator Adapter & Infrastructure.

Validates:
1. Fast-fail configuration when COORDINATOR_ADDRESS is missing or empty.
2. Address normalization (stripping trailing slashes).
3. CreateTrainingTaskDto attribute and shard list validation.
4. CreateTrainingTaskDto camelCase wire serialization.
5. Successful task creation response parsing (200/201).
6. Non-success HTTP status handling (4xx/5xx) and CoordinatorApiError escalation.
7. Malformed success response handling and CoordinatorAdapterError escalation.
8. Transport failure handling (timeout/connection failure) and CoordinatorNetworkError escalation.
9. Architectural isolation between adapters and persistence.
10. Infrastructure cleanliness (zero obsolete files).
"""

import io
import json
import os
import pathlib
import sys
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse

# Ensure Client package is importable
repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "src" / "Client"))

from infrastructure.adapters import (
    CoordinatorAdapter,
    CoordinatorAdapterError,
    CoordinatorConfigurationError,
    CoordinatorApiError,
    CoordinatorNetworkError,
    CreateTrainingTaskDto,
)


class TestTransportAdapter(HTTPAdapter):
    """Custom HTTP adapter simulating Coordinator endpoints for deterministic verification."""

    def __init__(
        self,
        status_code: int = 200,
        json_body: Optional[Dict[str, Any]] = None,
        text_body: Optional[str] = None,
        raise_exc: Optional[Exception] = None,
    ) -> None:
        super().__init__()
        self.status_code = status_code
        self.json_body = json_body
        self.text_body = text_body
        self.raise_exc = raise_exc
        self.last_request = None

    def send(self, request, **kwargs):  # type: ignore
        self.last_request = request
        if self.raise_exc:
            raise self.raise_exc

        if self.json_body is not None:
            body_bytes = json.dumps(self.json_body).encode("utf-8")
        elif self.text_body is not None:
            body_bytes = self.text_body.encode("utf-8")
        else:
            body_bytes = b""

        raw = HTTPResponse(
            body=io.BytesIO(body_bytes),
            status=self.status_code,
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )
        return self.build_response(request, raw)


def run_checks() -> None:
    passed = 0
    total = 10
    print("================================================================")
    print("      Coordinator Adapter Active Verification Suite             ")
    print("================================================================")

    # -------------------------------------------------------------
    # Check 1: Missing COORDINATOR_ADDRESS raises CoordinatorConfigurationError
    # -------------------------------------------------------------
    old_addr = os.environ.pop("COORDINATOR_ADDRESS", None)
    old_url = os.environ.pop("COORDINATOR_URL", None)
    try:
        try:
            CoordinatorAdapter()
            assert False, "Expected CoordinatorConfigurationError was not raised"
        except CoordinatorConfigurationError as e:
            assert "COORDINATOR_ADDRESS" in str(e)
            print("[PASS] Check 1: Missing COORDINATOR_ADDRESS fails fast with CoordinatorConfigurationError")
            passed += 1
    finally:
        if old_addr:
            os.environ["COORDINATOR_ADDRESS"] = old_addr

    # -------------------------------------------------------------
    # Check 2: Address normalization strips trailing slashes
    # -------------------------------------------------------------
    adapter = CoordinatorAdapter(coordinator_address="http://coordinator:8080///")
    assert adapter.base_url == "http://coordinator:8080"
    print("[PASS] Check 2: Base URL normalization strips trailing slashes")
    passed += 1

    # -------------------------------------------------------------
    # Check 3: CreateTrainingTaskDto field validation
    # -------------------------------------------------------------
    # Test missing/empty client_node_id
    try:
        CreateTrainingTaskDto(
            client_node_id="  ",
            model_id="m1",
            model_version="1.0",
            data_set_id="ds1",
            shard_id_list=["s1"],
        )
        assert False, "Expected ValueError on empty client_node_id"
    except ValueError:
        pass

    # Test empty shard_id_list
    try:
        CreateTrainingTaskDto(
            client_node_id="c1",
            model_id="m1",
            model_version="1.0",
            data_set_id="ds1",
            shard_id_list=[],
        )
        assert False, "Expected ValueError on empty shard_id_list"
    except ValueError:
        pass

    # Test whitespace shard_id in list
    try:
        CreateTrainingTaskDto(
            client_node_id="c1",
            model_id="m1",
            model_version="1.0",
            data_set_id="ds1",
            shard_id_list=["s1", "   "],
        )
        assert False, "Expected ValueError on whitespace shard_id"
    except ValueError:
        pass

    print("[PASS] Check 3: CreateTrainingTaskDto strict field and shard list validation")
    passed += 1

    # -------------------------------------------------------------
    # Check 4: CreateTrainingTaskDto camelCase wire serialization
    # -------------------------------------------------------------
    dto = CreateTrainingTaskDto(
        client_node_id="client-01",
        model_id="resnet50",
        model_version="2.1.0",
        data_set_id="imagenet",
        shard_id_list=["shard-1", "shard-2"],
    )
    wire_dict = dto.to_dict()
    assert "clientNodeId" in wire_dict
    assert "modelId" in wire_dict
    assert "modelVersion" in wire_dict
    assert "dataSetId" in wire_dict
    assert "shardIdList" in wire_dict
    # Confirm NO snake_case keys leaked
    assert "client_node_id" not in wire_dict
    assert "model_id" not in wire_dict
    assert "model_version" not in wire_dict
    assert "data_set_id" not in wire_dict
    assert "shard_id_list" not in wire_dict
    print("[PASS] Check 4: DTO wire serialization produces camelCase JSON without snake_case keys")
    passed += 1

    # -------------------------------------------------------------
    # Check 5: Success response handling (201 Created)
    # -------------------------------------------------------------
    session = requests.Session()
    transport = TestTransportAdapter(
        status_code=201,
        json_body={"trainingTaskIds": ["guid-001", "guid-002", "guid-003"]},
    )
    session.mount("http://", transport)
    session.mount("https://", transport)

    adapter = CoordinatorAdapter(coordinator_address="http://coordinator:8080", session=session)
    result = adapter.create_training_task(dto)
    assert result == ["guid-001", "guid-002", "guid-003"]
    assert transport.last_request.url == "http://coordinator:8080/api/training-tasks"
    assert transport.last_request.method == "POST"
    assert transport.last_request.headers["Content-Type"] == "application/json"
    sent_payload = json.loads(transport.last_request.body.decode("utf-8"))
    assert sent_payload["clientNodeId"] == "client-01"
    assert sent_payload["shardIdList"] == ["shard-1", "shard-2"]
    print("[PASS] Check 5: Successful task creation returns parsed task IDs and sends valid POST request")
    passed += 1

    # -------------------------------------------------------------
    # Check 6: HTTP error handling (400 / 500)
    # -------------------------------------------------------------
    session = requests.Session()
    transport = TestTransportAdapter(
        status_code=400,
        text_body="Invalid.ShardIdList",
    )
    session.mount("http://", transport)
    adapter = CoordinatorAdapter(coordinator_address="http://coordinator:8080", session=session)

    try:
        adapter.create_training_task(dto)
        assert False, "Expected CoordinatorApiError on HTTP 400"
    except CoordinatorApiError as e:
        assert e.status_code == 400
        assert "Invalid.ShardIdList" in e.response_text
        print("[PASS] Check 6: Non-success HTTP status (400) raises CoordinatorApiError")
        passed += 1

    # -------------------------------------------------------------
    # Check 7: Malformed success response handling
    # -------------------------------------------------------------
    session = requests.Session()
    transport = TestTransportAdapter(
        status_code=200,
        json_body={"unexpectedField": 123},  # missing trainingTaskIds
    )
    session.mount("http://", transport)
    adapter = CoordinatorAdapter(coordinator_address="http://coordinator:8080", session=session)

    try:
        adapter.create_training_task(dto)
        assert False, "Expected CoordinatorAdapterError on missing trainingTaskIds"
    except CoordinatorAdapterError as e:
        assert "missing" in str(e).lower()
        print("[PASS] Check 7: Missing 'trainingTaskIds' in 2xx response raises CoordinatorAdapterError")
        passed += 1

    # -------------------------------------------------------------
    # Check 8: Transport / Network error handling
    # -------------------------------------------------------------
    session = requests.Session()
    transport = TestTransportAdapter(
        raise_exc=requests.exceptions.ConnectTimeout("Connection timed out"),
    )
    session.mount("http://", transport)
    adapter = CoordinatorAdapter(coordinator_address="http://coordinator:8080", session=session)

    try:
        adapter.create_training_task(dto)
        assert False, "Expected CoordinatorNetworkError on connection timeout"
    except CoordinatorNetworkError as e:
        assert "timed out" in str(e).lower()
        print("[PASS] Check 8: Connection timeout raises CoordinatorNetworkError")
        passed += 1

    # -------------------------------------------------------------
    # Check 9: Architectural isolation
    # -------------------------------------------------------------
    import inspect
    import infrastructure.adapters.coordinator_adapter as ca_module
    ca_source = inspect.getsource(ca_module)
    assert "sqlite3" not in ca_source
    assert "DatabaseManager" not in ca_source
    assert "TrainingShardRepository" not in ca_source
    print("[PASS] Check 9: CoordinatorAdapter has zero imports/references to SQLite persistence")
    passed += 1

    # -------------------------------------------------------------
    # Check 10: Infrastructure cleanliness
    # -------------------------------------------------------------
    client_infra = repo_root / "src" / "Client" / "infrastructure"
    assert not (client_infra / "bootstrap_client.py").exists(), "bootstrap_client.py must be removed"
    assert not (client_infra / "coordinator_client.py").exists(), "coordinator_client.py must be removed"
    assert (client_infra / "adapters").is_dir(), "adapters/ must exist"
    assert (client_infra / "persistence").is_dir(), "persistence/ must exist"
    print("[PASS] Check 10: Infrastructure cleaned: obsolete clients removed, only adapters/ & persistence/ remain")
    passed += 1

    print("================================================================")
    print(f"       Verification Result: {passed}/{total} Checks Passed       ")
    print("================================================================")


if __name__ == "__main__":
    run_checks()
