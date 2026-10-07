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
    assert any(item["plan_id"] == plan_id and item["status"] == "FRAGILE" for item in listed["futures"])
    assert any(item["conflict_type"] == "PROTECTED_RESOURCE" for item in listed["conflicts"])
    found = cross_plan_conflicts(
        [
            {"future_id": "a", "effects": {"flight_departure_min": 680}},
            {"future_id": "b", "effects": {"flight_departure_min": 880}},
        ]
    )
    assert found[0]["shared_resource"] == "flight_departure_min"
    assert found[0]["repairable"] is True


def test_cross_plan_rules_cover_time_budget_protection_and_assets() -> None:
    opening = {
        "future_id": "opening",
        "name": "Gallery opening",
        "effects": {},
        "claims": [{"resource_id": "alex", "resource_type": "person", "start": 900, "end": 960, "protected": True, "label": "Gallery opening"}],
    }
    airport = {
        "future_id": "airport",
        "name": "NYC airport window",
        "effects": {},
        "claims": [{"resource_id": "alex", "resource_type": "person", "start": 840, "end": 1020, "protected": False, "label": "Airport travel"}],
    }
    later = {
        "future_id": "later",
        "name": "Evening dinner",
        "effects": {},
        "claims": [{"resource_id": "alex", "resource_type": "person", "start": 1140, "end": 1260, "protected": False, "label": "Dinner"}],
    }
    assert cross_plan_conflicts([airport, opening])[0]["conflict_type"] == "PROTECTED_RESOURCE"
    movable = {
        "future_id": "movable",
        "name": "Movable review",
        "effects": {},
        "claims": [{"resource_id": "alex", "resource_type": "person", "start": 900, "end": 960, "protected": False, "label": "Review"}],
    }
    assert cross_plan_conflicts([airport, movable])[0]["conflict_type"] == "TIME_OVERLAP"
    assert cross_plan_conflicts([later, opening]) == []
    budget = cross_plan_conflicts(
        [
            {"future_id": "a", "name": "A", "effects": {}, "claims": [{"resource_id": "cash", "resource_type": "budget", "cost": 60, "cap": 100}]},
            {"future_id": "b", "name": "B", "effects": {}, "claims": [{"resource_id": "cash", "resource_type": "budget", "cost": 50, "cap": 100}]},
        ]
    )
    assert budget[0]["conflict_type"] == "BUDGET_CONFLICT"
    protected = cross_plan_conflicts(
        [
            {"future_id": "trip", "name": "Trip", "effects": {"review_changed": True}, "claims": []},
            {"future_id": "review", "name": "Review", "effects": {}, "claims": [{"resource_id": "review_changed", "resource_type": "commitment", "protected": True, "state": False, "label": "Design review"}]},
        ]
    )
    assert protected[0]["conflict_type"] == "PROTECTED_RESOURCE"
    asset = cross_plan_conflicts(
        [
            {"future_id": "a", "name": "A", "effects": {}, "claims": [{"resource_id": "bk_nyc", "resource_type": "reservation", "state": "friday"}]},
            {"future_id": "b", "name": "B", "effects": {}, "claims": [{"resource_id": "bk_nyc", "resource_type": "reservation", "state": "thursday"}]},
        ]
    )
    assert asset[0]["conflict_type"] == "ASSET_STATE_CONFLICT"


def test_reset_demo_restores_the_cross_plan_pair() -> None:
    client = TestClient(create_app())
    first = client.post("/api/plans/freeform", json={"text": TRIP, "demo_context_id": "travel", "seed": 7})
    assert first.status_code == 200
    reset = client.post("/api/demo/reset")
    assert reset.status_code == 200
    listed = client.get("/api/futures")
    assert listed.status_code == 200
    body = listed.json()
    names = {item["name"] for item in body["futures"]}
    assert "NYC airport window" in names
    assert "Gallery opening" in names
    assert any(item["conflict_type"] == "PROTECTED_RESOURCE" for item in body["conflicts"])
    assert body["conflicts"][0]["description"]


def test_receipt_before_execution_is_honest() -> None:
    client, plan_id = _analyzed()
    receipt = client.get(f"/api/plans/{plan_id}/receipt").json()
    assert receipt["approved"] == "b1120"
    assert receipt["executed"] == []
    assert receipt["matched"] is None
