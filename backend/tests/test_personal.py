"""Watcher, persisted contracts, and the three typed skills."""

from shadow.pipeline import PlanService
from shadow.runtime.events import EventLog
from shadow.skills.registry import SkillRegistry
from shadow.watcher.models import WorldEvent


def _approved() -> tuple[PlanService, str]:
    service = PlanService(EventLog("sqlite://"))
    created = service.create("Move my NYC trip to Friday and make sure everything still works.", "travel", 7)
    view = service.analyze(created["id"])
    service.approve(created["id"], view["recommended_repair_id"])
    return service, created["id"]


def test_unrelated_event_leaves_the_contract():
    service, plan_id = _approved()
    before = service.plans[plan_id]["contract"].status
    drifts = service.watcher.process_event(
        WorldEvent(
            event_id="cat",
            source="note",
            event_type="note",
            observed_at="2026-10-07T12:00:00Z",
            affected_entities=["cat_birthday"],
        ),
        plan_id,
    )
    assert drifts[0].new_status == "UNCHANGED"
    assert service.plans[plan_id]["contract"].status == before


def test_delay_keeps_authority_and_fare_or_cancel_revokes_it():
    service, plan_id = _approved()
    mild = service.inject(plan_id, "delay_74")
    assert "flight_delay_min" in mild["invalidated"]
    assert mild["approved_future_holds"] is True
    assert mild["authority"] == "active"
    assert mild["drift_status"] == "DEGRADED"
    canceled = service.inject(plan_id, "hotel_canceled")
    assert canceled["authority"] == "revoked"
    assert canceled["contract_status"] == "STALE"
    blocked = service.attempt(plan_id, "confirm_friday")
    assert blocked["authorized"] is False


def test_fare_increase_stales_the_contract():
    service, plan_id = _approved()
    broken = service.inject(plan_id, "fare_increase")
    assert broken["drift_status"] == "INVALID"
    assert broken["authority"] == "revoked"
    assert service.plans[plan_id]["contract"].status == "STALE"


def test_unknown_event_does_not_execute_or_revoke():
    service, plan_id = _approved()
    drifts = service.watcher.process_event(
        WorldEvent(
            event_id="rumor",
            source="mail",
            event_type="rumor",
            observed_at="2026-10-07T12:00:00Z",
            affected_entities=["flight_delay_min"],
            epistemic_status="UNKNOWN",
        ),
        plan_id,
    )
    assert drifts[0].new_status == "UNKNOWN"
    assert drifts[0].still_feasible is None
    assert service.plans[plan_id]["contract"].status == "ACTIVE"


def test_restart_can_monitor_the_saved_contract():
    events = EventLog("sqlite://")
    service = PlanService(events)
    created = service.create("Move my NYC trip to Friday and make sure everything still works.", "travel", 7)
    view = service.analyze(created["id"])
    service.approve(created["id"], view["recommended_repair_id"])
    restarted = PlanService(events)
    assert created["id"] in restarted.plans
    mild = restarted.inject(created["id"], "delay_74")
    assert mild["authority"] == "active"


def test_registry_has_three_skills_and_does_not_authorize():
    registry = SkillRegistry()
    names = [item.id for item in registry.list_skills()]
    assert names == ["reschedule_trip", "handle_trip_disruption", "coordinate_schedule"]
    trip = registry.available_for("Move my NYC trip to Friday")
    disruption = registry.available_for("Flight delayed", "fare_increase")
    schedule = registry.available_for("Coordinate the Thursday meeting")
    assert trip.id == "reschedule_trip"
    assert disruption.id == "handle_trip_disruption"
    assert schedule.id == "coordinate_schedule"
    assert registry.available_for("hello") is None
    assert trip.grants_authority() is False
    assert trip.required_tools
    assert trip.verification_steps
    assert trip.compensation_actions
    service, _plan_id = _approved()
    assert service.plans[_plan_id]["skill_id"] == "reschedule_trip"
    status = service.personal_status()
    assert status["skills"] == ["Reschedule Trip", "Handle Trip Disruption", "Coordinate Schedule"]
    assert status["privacy"]["raw_source_bodies_sent_to_model"] is False
    assert status["connected_tools"]["search"] == "OFF"
