"""Future lab, life graph, and cross-plan checks stay deterministic."""

from fastapi.testclient import TestClient

from shadow.api.app import create_app
from shadow.futures.conflicts import cross_plan_conflicts

TRIP = "Move my NYC trip to Friday and make sure everything still works."


def _analyzed() -> tuple[TestClient, str]:
    client = TestClient(create_app())
    created = client.post("/api/plans", json={"text": TRIP, "scenario_id": "travel", "seed": 7}).json()
    client.post(f"/api/plans/{created['id']}/analyze")
    return client, created["id"]


def test_life_graph_keeps_commitment_status() -> None:
    client, plan_id = _analyzed()
    life = client.get(f"/api/plans/{plan_id}").json()["life"]
    dinner = next(node for node in life["nodes"] if "dinner" in node["label"].lower())
    assert dinner["epistemic_status"]
    link = next(edge for edge in life["edges"] if edge["target"] == dinner["id"])
    assert link["epistemic_status"] == "INFERRED"
    assert link["relation"] == "HAS_COMMITMENT"


def test_future_lab_is_local_and_reports_the_boundary() -> None:
    client, plan_id = _analyzed()
    controls = client.get(f"/api/plans/{plan_id}/lab").json()
    assert {item["id"] for item in controls["variables"]} >= {"flight_delay_min", "traffic_extra_min"}
    held = client.post(f"/api/plans/{plan_id}/lab", json={"overrides": {"flight_delay_min": 20}}).json()
    assert held["holds"] is True
    assert held["simulation"] is True
    broken = client.post(
        f"/api/plans/{plan_id}/lab",
        json={"overrides": {"flight_delay_min": 180, "traffic_extra_min": 150, "not_a_variable": 9}},
    ).json()
    assert broken["holds"] is False
    assert "not_a_variable" not in broken["overrides"]
    assert broken["violated_labels"]


def test_nearest_failure_uses_the_stored_search() -> None:
    client, plan_id = _analyzed()
    body = client.post(f"/api/plans/{plan_id}/lab/nearest", json={}).json()
    assert body["message"] == "This is the nearest failure Shadow discovered under the modeled ranges."
    assert body["holds"] is False
    assert body["overrides"]


def test_futures_list_and_cross_plan_disagreement() -> None:
    client, plan_id = _analyzed()
    listed = client.get("/api/futures").json()
    assert listed["futures"][0]["plan_id"] == plan_id
    assert listed["futures"][0]["status"] == "FRAGILE"
    assert listed["conflicts"] == []
    found = cross_plan_conflicts(
        [
            {"future_id": "a", "effects": {"flight_departure_min": 680}},
            {"future_id": "b", "effects": {"flight_departure_min": 880}},
        ]
    )
    assert found[0]["shared_resource"] == "flight_departure_min"
    assert found[0]["repairable"] is True


def test_receipt_before_execution_is_honest() -> None:
    client, plan_id = _analyzed()
    receipt = client.get(f"/api/plans/{plan_id}/receipt").json()
    assert receipt["approved"] == "b1120"
    assert receipt["executed"] == []
    assert receipt["matched"] is None
