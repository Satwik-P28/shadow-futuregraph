"""Acceptance tests for the travel loop and the second domain."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from shadow.api.app import create_app
from shadow.pipeline import PlanService
from shadow.runtime.events import EventLog
from shadow.world.loader import load_scenario

ROOT = Path(__file__).resolve().parents[2]
CORE = [
    ROOT / "backend/shadow/failures/search.py",
    ROOT / "backend/shadow/repair/evaluate.py",
    ROOT / "backend/shadow/simulation/engine.py",
    ROOT / "backend/shadow/future_graph/build.py",
    ROOT / "backend/shadow/runtime/broker.py",
]


def _service() -> PlanService:
    return PlanService(EventLog("sqlite://"))


def test_core_is_not_travel_hardcoded():
    for path in CORE:
        text = path.read_text()
        assert "11:20" not in text
        assert "apartment" not in text
        assert "scenario ==" not in text


def test_travel_hero_discovers_fragile_afternoon_flight():
    service = _service()
    created = service.create("Move my NYC trip to Friday and make sure everything still works.", "travel", 7)
    view = service.analyze(created["id"])
    assert view["status"] == "READY"
    assert view["naive_repair_id"] == "b1440"
    assert view["recommended_repair_id"] == "b1120"
    naive = next(item for item in view["repairs"] if item["id"] == "b1440")
    early = next(item for item in view["repairs"] if item["id"] == "b1120")
    dinner = next(item for item in naive["failures"] if "c_dinner" in item["violated_constraints"])
    assert {item["variable"] for item in dinner["perturbations"]} == {"flight_delay_min", "traffic_extra_min"}
    assert dinner["normalized_distance"] > 0
    assert early["failure_radius"] is None or early["failure_radius"] > naive["failure_radius"] * 2
    rejected = next(item for item in view["repairs"] if item["id"] == "b_dinner")
    assert rejected["status"] == "infeasible"
    assert rejected["hard_violations"] >= 1
    assert view["diff"]["entries"]
    flight = next(item for item in view["diff"]["entries"] if item["id"] == "flight_departure_min")
    assert flight["before"] == "14:40"
    assert flight["after"] == "11:20"
    ride = next(item for item in view["diff"]["entries"] if item["id"] == "ride_pickup_min")
    assert ride["after"] == "8:45"
    assert view["coverage"]["summary"] == "1 material unknown remains"
    assert view["coverage"]["percentage"] is None
    assert "raw_body" not in str(view)
    graph = view["graph"]
    assert graph["nodes"]
    assert len(graph["nodes"]) <= 80
    assert len(graph["edges"]) <= 160


def test_approve_execute_block_and_inject():
    service = _service()
    created = service.create("Move my NYC trip to Friday and make sure everything still works.", "travel", 7)
    plan_id = created["id"]
    service.analyze(plan_id)
    contract = service.approve(plan_id, "b1120")
    assert "cal_exam" not in contract["resource_scopes"]
    blocked = service.attempt(plan_id, "update_exam")
    assert blocked["authorized"] is False
    assert "outside the approved future" in blocked["message"]
    executed = service.execute(plan_id)
    assert executed["status"] == "verified"
    view = service.view(plan_id)
    assert view["reconciliation"]["matched"] is True
    assert "matches approved future" in view["reconciliation"]["message"]
    mild = service.inject(plan_id, "delay_74")
    assert "flight_delay_min" in mild["invalidated"]
    assert mild["approved_future_holds"] is True
    assert mild["authority"] == "active"
    broken = service.inject(plan_id, "fare_increase")
    assert broken["approved_future_holds"] is False
    assert broken["authority"] == "revoked"
    assert broken["contract_status"] == "STALE"
    halted = service.execute(plan_id)
    assert halted["status"] == "halted"
    events = service.events.list_for(plan_id)
    assert any(item.event_type == "ACTION_BLOCKED" for item in events)
    assert any(item.event_type == "ASSUMPTION_INVALIDATED" for item in events)


def test_apartment_uses_same_engine():
    service = _service()
    created = service.create("I'm thinking about moving apartments next month. Does this plan actually work?", "apartment", 7)
    view = service.analyze(created["id"])
    assert view["naive_repair_id"] == "opt_sat"
    assert view["recommended_repair_id"] == "opt_align"
    naive = next(item for item in view["repairs"] if item["id"] == "opt_sat")
    assert naive["feasible"] is True
    assert any("c_pickup" in item["violated_constraints"] for item in naive["failures"])
    winner = next(item for item in view["repairs"] if item["id"] == "opt_align")
    assert winner["feasible"] is True
    assert winner["failure_radius"] is None or winner["failure_radius"] > naive["failure_radius"]


def test_impossible_and_unknown():
    service = _service()
    impossible = service.create("Be in two places.", "impossible", 3)
    view = service.analyze(impossible["id"])
    assert view["status"] == "NO_FEASIBLE_FUTURE"
    assert view["no_feasible_message"].startswith("No feasible future")
    assert view["solver"] == "unsat"
    unknown = service.create("Book the workshop.", "unknown", 3)
    pending = service.analyze(unknown["id"])
    assert pending["status"] == "NO_FEASIBLE_FUTURE"
    assert pending["coverage"]["unknown"] == 1
    assert pending["coverage"]["percentage"] is None
    resolved = service.inject(unknown["id"], "venue_yes")
    assert resolved["recommended_repair_id"] == "book_it"


def test_http_hero_and_graph_roundtrip():
    client = TestClient(create_app())
    created = client.post("/api/plans", json={"text": "Move my NYC trip to Friday and make sure everything still works.", "scenario_id": "travel", "seed": 7})
    assert created.status_code == 200
    plan_id = created.json()["id"]
    analyzed = client.post(f"/api/plans/{plan_id}/analyze")
    assert analyzed.status_code == 200
    body = analyzed.json()
    assert body["recommended_repair_id"] == "b1120"
    graph = client.get(f"/api/plans/{plan_id}/graph").json()
    from shadow.core.models import FutureGraph

    again = FutureGraph.model_validate(graph)
    assert len(again.nodes) == len(graph["nodes"])
    approved = client.post(f"/api/plans/{plan_id}/repairs/b1120/approve")
    assert approved.status_code == 200
    blocked = client.post(f"/api/plans/{plan_id}/actions/attempt", json={"action_id": "update_exam"})
    assert blocked.json()["authorized"] is False
    executed = client.post(f"/api/plans/{plan_id}/execute")
    assert executed.json()["status"] == "verified"
    assert client.get("/healthz").json()["status"] == "ok"
    load_scenario.cache_clear()
