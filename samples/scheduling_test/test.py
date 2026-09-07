"""Comprehensive 12-Case Verification Suite for Coordinator Scheduler.

Tests fair model-level round-robin scheduling against active Coordinator service
using HTTP APIs with zero mocks.
"""

from __future__ import annotations
import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

PORT = int(os.environ.get("COORDINATOR_PORT", "5000"))
BASE_URL = os.environ.get("COORDINATOR_URL", f"http://localhost:{PORT}")

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def http_post(endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    """Send HTTP POST request with JSON payload and return parsed JSON."""
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def clear_all():
    """Clear all trainers and tasks, resetting in-memory scheduler cursor."""
    http_post("/api/trainers/clear")
    http_post("/api/training-tasks/clear")


def create_trainer(trainer_node_id: str, status: Optional[int] = None) -> Dict[str, Any]:
    """Connect a trainer node with optional status (0=UNCLEAR, 1=IDLE, 2=BUSY)."""
    payload = {"trainerNodeId": trainer_node_id}
    if status is not None:
        payload["status"] = status
    return http_post("/api/trainers/connect", payload)


def create_tasks(
    model_id: str,
    shard_ids: List[str],
    submit_time: Optional[str] = None,
    trainer_node_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create training tasks for a model."""
    payload = {
        "clientNodeId": "client-01",
        "modelId": model_id,
        "modelVersion": "1.0",
        "dataSetId": "dataset-01",
        "shardIdList": shard_ids
    }
    if submit_time:
        payload["submitTime"] = submit_time
    if trainer_node_id:
        payload["trainerNodeId"] = trainer_node_id
    if task_id:
        payload["trainingTaskId"] = task_id
    return http_post("/api/training-tasks", payload)


def assign_tasks() -> List[Dict[str, Any]]:
    """Trigger scheduler assign tasks API."""
    return http_post("/api/scheduler/assign")


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def record_pass(self, name: str, details: str):
        self.passed += 1
        print(f"  {GREEN}[PASS]{RESET} {BOLD}{name}{RESET}")
        print(f"         {details}")
        self.results.append((name, True, details))

    def record_fail(self, name: str, reason: str):
        self.failed += 1
        print(f"  {RED}[FAIL]{RESET} {BOLD}{name}{RESET}")
        print(f"         {reason}")
        self.results.append((name, False, reason))

    def print_summary(self):
        print("\n" + "=" * 80)
        print(f"{BOLD}Coordinator Scheduler Verification Summary{RESET}")
        print("=" * 80)
        for name, passed, details in self.results:
            status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
            print(f"  [{status_str}] {name} - {details}")
        print("-" * 80)
        total = self.passed + self.failed
        if self.failed == 0:
            print(f"{GREEN}{BOLD}ALL {total} TEST CASES PASSED! (100% SUCCESS){RESET}\n")
        else:
            print(f"{RED}{BOLD}{self.failed}/{total} TEST CASES FAILED.{RESET}\n")


runner = TestRunner()


# ------------------------------------------------------------------------------
# Test 1 - Single model
# ------------------------------------------------------------------------------
def test_1_single_model():
    name = "Test 1 - Single model"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:01:00")
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:02:00")

    assignments = assign_tasks()
    if len(assignments) != 2:
        runner.record_fail(name, f"Expected 2 assignments, got {len(assignments)}")
        return

    expected = [("T1", "shard-A1"), ("T2", "shard-A2")]
    actual = [(a["trainerNodeId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Assigned {actual}, shard-A3 remains unassigned.")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 2 - Basic model fairness
# ------------------------------------------------------------------------------
def test_2_basic_model_fairness():
    name = "Test 2 - Basic model fairness"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")
    create_trainer("T3")

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:01:00")
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:02:00")

    create_tasks("ModelB", ["shard-B1"], submit_time="2026-09-07T10:03:00")
    create_tasks("ModelB", ["shard-B2"], submit_time="2026-09-07T10:04:00")

    create_tasks("ModelC", ["shard-C1"], submit_time="2026-09-07T10:05:00")
    create_tasks("ModelC", ["shard-C2"], submit_time="2026-09-07T10:06:00")

    assignments = assign_tasks()
    expected = [("T1", "ModelA", "shard-A1"), ("T2", "ModelB", "shard-B1"), ("T3", "ModelC", "shard-C1")]
    actual = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Round-robin turn order satisfied: {actual}")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 3 - More trainers than models
# ------------------------------------------------------------------------------
def test_3_more_trainers_than_models():
    name = "Test 3 - More trainers than models"
    clear_all()
    for t in ["T1", "T2", "T3", "T4", "T5"]:
        create_trainer(t)

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:01:00")
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:02:00")
    create_tasks("ModelB", ["shard-B1"], submit_time="2026-09-07T10:03:00")

    assignments = assign_tasks()
    expected = [
        ("T1", "ModelA", "shard-A1"),
        ("T2", "ModelB", "shard-B1"),
        ("T3", "ModelA", "shard-A2"),
        ("T4", "ModelA", "shard-A3")
    ]
    actual = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Fully utilized 4 trainers, T5 left idle: {actual}")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 4 - Model with only one task & cursor continuity
# ------------------------------------------------------------------------------
def test_4_model_with_only_one_task():
    name = "Test 4 - Model with one task & cursor continuity"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")
    create_trainer("T3")

    create_tasks("ModelA", ["shard-A1"])
    create_tasks("ModelB", ["shard-B1"])
    create_tasks("ModelC", ["shard-C1"])
    create_tasks("ModelD", ["shard-D1"])

    # Round 1
    r1 = assign_tasks()
    expected_r1 = [("T1", "ModelA"), ("T2", "ModelB"), ("T3", "ModelC")]
    actual_r1 = [(a["trainerNodeId"], a["modelId"]) for a in r1]
    if actual_r1 != expected_r1:
        runner.record_fail(name, f"Round 1 mismatch: expected {expected_r1}, got {actual_r1}")
        return

    # Add 1 idle trainer for Round 2
    create_trainer("T4")
    r2 = assign_tasks()
    expected_r2 = [("T4", "ModelD")]
    actual_r2 = [(a["trainerNodeId"], a["modelId"]) for a in r2]
    if actual_r2 == expected_r2:
        runner.record_pass(name, f"Cursor persisted to ModelD: R1={actual_r1}, R2={actual_r2}")
    else:
        runner.record_fail(name, f"Cursor restarted or failed: expected {expected_r2}, got {actual_r2}")


# ------------------------------------------------------------------------------
# Test 5 - FIFO within a model
# ------------------------------------------------------------------------------
def test_5_fifo_within_a_model():
    name = "Test 5 - FIFO within a model"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:05:00")
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:10:00")
    create_tasks("ModelB", ["shard-B1"], submit_time="2026-09-07T10:01:00")

    r1 = assign_tasks()
    expected_r1 = [("T1", "shard-A1"), ("T2", "shard-B1")]
    actual_r1 = [(a["trainerNodeId"], a["shardId"]) for a in r1]
    if actual_r1 != expected_r1:
        runner.record_fail(name, f"Round 1 mismatch: expected {expected_r1}, got {actual_r1}")
        return

    # T3 becomes available
    create_trainer("T3")
    r2 = assign_tasks()
    expected_r2 = [("T3", "shard-A2")]
    actual_r2 = [(a["trainerNodeId"], a["shardId"]) for a in r2]
    if actual_r2 == expected_r2:
        runner.record_pass(name, f"FIFO preserved (shard-A1 before A2, A3 queued): {actual_r1 + actual_r2}")
    else:
        runner.record_fail(name, f"FIFO violated: expected {expected_r2}, got {actual_r2}")


# ------------------------------------------------------------------------------
# Test 6 - Large imbalance between models
# ------------------------------------------------------------------------------
def test_6_large_imbalance_between_models():
    name = "Test 6 - Large imbalance between models"
    clear_all()
    for t in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        create_trainer(t)

    for i in range(1, 11):
        create_tasks("ModelA", [f"shard-A{i}"], submit_time=f"2026-09-07T10:00:{i:02d}")
    create_tasks("ModelB", ["shard-B1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelC", ["shard-C1"], submit_time="2026-09-07T10:00:00")

    assignments = assign_tasks()
    expected = [
        ("T1", "ModelA", "shard-A1"),
        ("T2", "ModelB", "shard-B1"),
        ("T3", "ModelC", "shard-C1"),
        ("T4", "ModelA", "shard-A2"),
        ("T5", "ModelA", "shard-A3"),
        ("T6", "ModelA", "shard-A4")
    ]
    actual = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Starvation prevented: B1 and C1 received turns in first round: {actual}")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 7 - Trainer status filtering
# ------------------------------------------------------------------------------
def test_7_trainer_status():
    name = "Test 7 - Trainer status filtering"
    clear_all()
    create_trainer("T1", status=2)  # BUSY
    create_trainer("T2", status=0)  # UNCLEAR
    create_trainer("T3", status=1)  # IDLE
    create_trainer("T4", status=1)  # IDLE

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:01:00")
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:02:00")

    assignments = assign_tasks()
    expected = [("T3", "shard-A1"), ("T4", "shard-A2")]
    actual = [(a["trainerNodeId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Only IDLE trainers assigned (T3, T4); BUSY/UNCLEAR ignored: {actual}")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 8 - No tasks
# ------------------------------------------------------------------------------
def test_8_no_tasks():
    name = "Test 8 - No tasks"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")

    assignments = assign_tasks()
    if len(assignments) == 0:
        runner.record_pass(name, "Zero assignments returned; trainers remain IDLE.")
    else:
        runner.record_fail(name, f"Expected 0 assignments, got {len(assignments)}")


# ------------------------------------------------------------------------------
# Test 9 - No idle trainers
# ------------------------------------------------------------------------------
def test_9_no_idle_trainers():
    name = "Test 9 - No idle trainers"
    clear_all()
    create_trainer("T1", status=2)  # BUSY
    create_trainer("T2", status=2)  # BUSY
    create_trainer("T3", status=0)  # UNCLEAR

    create_tasks("ModelA", ["shard-A1"])
    create_tasks("ModelB", ["shard-B1"])

    assignments = assign_tasks()
    if len(assignments) == 0:
        runner.record_pass(name, "Zero assignments made when all trainers BUSY/UNCLEAR.")
    else:
        runner.record_fail(name, f"Expected 0 assignments, got {len(assignments)}")


# ------------------------------------------------------------------------------
# Test 10 - Already assigned tasks must be ignored
# ------------------------------------------------------------------------------
def test_10_already_assigned_tasks():
    name = "Test 10 - Already assigned tasks must be ignored"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")

    create_tasks("ModelA", ["shard-A1"], trainer_node_id="")
    create_tasks("ModelA", ["shard-A2"], trainer_node_id="T99")  # Pre-assigned
    create_tasks("ModelB", ["shard-B1"], trainer_node_id="")

    assignments = assign_tasks()
    expected = [("T1", "ModelA", "shard-A1"), ("T2", "ModelB", "shard-B1")]
    actual = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in assignments]
    if actual == expected:
        runner.record_pass(name, f"Pre-assigned task A2 untouched; assigned unassigned tasks: {actual}")
    else:
        runner.record_fail(name, f"Expected {expected}, got {actual}")


# ------------------------------------------------------------------------------
# Test 11 - Model disappears from rotation
# ------------------------------------------------------------------------------
def test_11_model_disappears_from_rotation():
    name = "Test 11 - Model disappears from rotation"
    clear_all()
    for t in ["T1", "T2", "T3", "T4"]:
        create_trainer(t)

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00")
    create_tasks("ModelB", ["shard-B1"], submit_time="2026-09-07T10:01:00")
    create_tasks("ModelB", ["shard-B2"], submit_time="2026-09-07T10:02:00")
    create_tasks("ModelC", ["shard-C1"], submit_time="2026-09-07T10:03:00")
    create_tasks("ModelC", ["shard-C2"], submit_time="2026-09-07T10:04:00")
    create_tasks("ModelC", ["shard-C3"], submit_time="2026-09-07T10:05:00")

    # Round 1
    r1 = assign_tasks()
    expected_r1 = [
        ("T1", "ModelA", "shard-A1"),
        ("T2", "ModelB", "shard-B1"),
        ("T3", "ModelC", "shard-C1"),
        ("T4", "ModelB", "shard-B2")
    ]
    actual_r1 = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in r1]
    if actual_r1 != expected_r1:
        runner.record_fail(name, f"Round 1 mismatch: expected {expected_r1}, got {actual_r1}")
        return

    # Add T5, T6
    create_trainer("T5")
    create_trainer("T6")
    r2 = assign_tasks()
    expected_r2 = [
        ("T5", "ModelC", "shard-C2"),
        ("T6", "ModelC", "shard-C3")
    ]
    actual_r2 = [(a["trainerNodeId"], a["modelId"], a["shardId"]) for a in r2]
    if actual_r2 == expected_r2:
        runner.record_pass(name, f"Exhausted models pruned; remaining capacity allocated to C: {actual_r2}")
    else:
        runner.record_fail(name, f"Expected {expected_r2}, got {actual_r2}")


# ------------------------------------------------------------------------------
# Test 12 - Deterministic ordering for equal SubmitTime
# ------------------------------------------------------------------------------
def test_12_deterministic_ordering_for_equal_submittime():
    name = "Test 12 - Deterministic tie-breaking on equal SubmitTime"
    clear_all()
    create_trainer("T1")
    create_trainer("T2")
    create_trainer("T3")

    # All share exact same timestamp, but have distinct TrainingTaskId
    id1 = "11111111-1111-1111-1111-111111111111"
    id2 = "22222222-2222-2222-2222-222222222222"
    id3 = "33333333-3333-3333-3333-333333333333"

    create_tasks("ModelA", ["shard-A1"], submit_time="2026-09-07T10:00:00", task_id=id1)
    create_tasks("ModelA", ["shard-A2"], submit_time="2026-09-07T10:00:00", task_id=id2)
    create_tasks("ModelA", ["shard-A3"], submit_time="2026-09-07T10:00:00", task_id=id3)

    assignments = assign_tasks()
    expected_ids = [id1, id2, id3]
    actual_ids = [a["trainingTaskId"] for a in assignments]
    if actual_ids == expected_ids:
        runner.record_pass(name, f"Tie-break by TrainingTaskId ASC satisfied: {actual_ids}")
    else:
        runner.record_fail(name, f"Expected {expected_ids}, got {actual_ids}")


def main():
    print(f"\n{BOLD}{CYAN}=== TrainSwarm Coordinator Scheduler Test Suite ==={RESET}\n")
    print(f"Target Base URL: {BASE_URL}\n")

    # Verify coordinator health before starting
    try:
        req = urllib.request.Request(f"{BASE_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                print(f"{RED}[ERROR] Coordinator /health returned status {resp.status}{RESET}")
                sys.exit(1)
    except Exception as e:
        print(f"{RED}[ERROR] Cannot connect to Coordinator at {BASE_URL}: {e}{RESET}")
        print(f"{YELLOW}Hint: Start the coordinator in a separate command line using: python setup.py{RESET}")
        sys.exit(1)

    test_1_single_model()
    test_2_basic_model_fairness()
    test_3_more_trainers_than_models()
    test_4_model_with_only_one_task()
    test_5_fifo_within_a_model()
    test_6_large_imbalance_between_models()
    test_7_trainer_status()
    test_8_no_tasks()
    test_9_no_idle_trainers()
    test_10_already_assigned_tasks()
    test_11_model_disappears_from_rotation()
    test_12_deterministic_ordering_for_equal_submittime()

    # Final cleanup
    clear_all()

    runner.print_summary()
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()

