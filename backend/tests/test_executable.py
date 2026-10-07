"""Acceptance cases for worlds compiled without fixture formulas."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from shadow.core.models import ActionDef, EpistemicStatus, PlanSpec
from shadow.integrations.sandbox import SandboxProviders
from shadow.pipeline import PlanService, _contract
from shadow.repair.evaluate import evaluate_repairs
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.runtime.events import EventLog
from shadow.runtime.execute import execute_bundle
from shadow.simulation.engine import bind, evaluate_constraints
from shadow.watcher.models import WorldEvent
from shadow.world.executable import (
    ExecutableProposal,
    FormulaIR,
    VariableIR,
    compile_primitives,
    validate_proposal,
)
from shadow.world.loader import effects_for


def _chain() -> list[dict[str, str]]:
    return [
        {"id": "gate", "text": "Harbor gate ends at 9:00 AM.", "observed_at": "2026-10-01T00:00:00Z"},
        {"id": "walk", "text": "Harbor gate to badge queue takes 20-40 minutes.", "observed_at": "2026-10-01T00:00:00Z"},
        {"id": "line", "text": "Badge queue to clinic intake takes 10-30 minutes.", "observed_at": "2026-10-01T00:00:00Z"},
        {"id": "clinic", "text": "Clinic intake starts at 10:00 AM and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
        {"id": "exam", "text": "Board exam starts at 11:00 AM and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
    ]


def test_unfamiliar_schedule_is_executable_without_a_fixture() -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain()[:4])
    assert compiled.status == "READY"
    assert compiled.scenario is not None
    assert compiled.scenario.metadata["route"] == "independent"
    assert compiled.scenario.id == "compiled"
    env = bind(compiled.scenario, {}, {})
    assert evaluate_constraints(compiled.scenario, env)["c_arrive_clinic_intake"] is True
    high = {
        "harbor_gate_badge_queue_duration": 40.0,
        "badge_queue_clinic_intake_duration": 30.0,
    }
    failed = bind(compiled.scenario, {}, high)
    assert evaluate_constraints(compiled.scenario, failed)["c_arrive_clinic_intake"] is False


def test_shared_budget_is_one_combined_constraint() -> None:
    compiled = compile_primitives(
        "Can I buy both?",
        [
            {"id": "cam", "text": "Camera body costs $400.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "lens", "text": "Spare lens costs $250.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "cap", "text": "Available budget is at most $600.", "observed_at": "2026-10-01T00:00:00Z"},
        ],
    )
    assert compiled.status == "READY"
    assert compiled.scenario is not None
    env = bind(compiled.scenario, {}, {})
    assert env["total_cost"] == 650
    assert evaluate_constraints(compiled.scenario, env)["c_budget"] is False
    dropped = bind(compiled.scenario, effects_for(compiled.scenario, ["drop_camera_body"]), {})
    assert evaluate_constraints(compiled.scenario, dropped)["c_budget"] is True


def test_missing_duration_abstains() -> None:
    compiled = compile_primitives(
        "Can I arrive in time?",
        [
            {"id": "flight", "text": "Ferry arrives at 5:05 PM.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "meal", "text": "Supper starts at 7:00 PM and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
        ],
    )
    assert compiled.status == "NEEDS_INFORMATION"
    assert compiled.scenario is None
    assert any("duration" in item for item in compiled.missing)


def test_conflict_is_not_silently_resolved() -> None:
    records = [
        {"id": "cal", "text": "Supper starts at 7:00 PM and cannot move.", "observed_at": "2026-10-01T00:00:00Z"},
        {"id": "mail", "text": "Supper starts at 8:00 PM.", "observed_at": "2026-10-02T00:00:00Z"},
    ]
    compiled = compile_primitives("Which time is protected?", records)
    assert compiled.status == "CONTRADICTORY"
    later = compile_primitives(
        "Which time is protected?",
        [records[0], {**records[1], "supersedes": "cal"}],
    )
    assert later.status != "CONTRADICTORY"


def test_search_finds_a_combined_range_failure() -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain()[:4])
    assert compiled.scenario is not None
    scored = evaluate_repairs(
        compiled.scenario,
        [(bundle.id, bundle.label, bundle.action_ids, "catalog") for bundle in compiled.scenario.bundles],
        seed=7,
    )
    keep = next(item for item in scored if item.id == "keep")
    assert keep.hard_violations == 0
    assert keep.failures
    assert keep.failure_radius is not None


def test_locked_budget_has_no_feasible_future() -> None:
    compiled = compile_primitives(
        "Can I buy both?",
        [
            {"id": "cam", "text": "Camera body costs $400 and cannot cancel.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "lens", "text": "Spare lens costs $280 and cannot cancel.", "observed_at": "2026-10-01T00:00:00Z"},
            {"id": "cap", "text": "Available budget is at most $600.", "observed_at": "2026-10-01T00:00:00Z"},
        ],
    )
    assert compiled.scenario is not None
    service = PlanService(EventLog("sqlite://"))
    view = service.open_compiled("Can I buy both?", compiled.scenario, seed=7)
    assert view["status"] == "NO_FEASIBLE_FUTURE"
    assert view["recommended_repair_id"] is None


def test_broker_rejects_an_unapproved_commitment() -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain())
    assert compiled.scenario is not None
    service = PlanService(EventLog("sqlite://"))
    view = service.open_compiled("Can I arrive in time?", compiled.scenario, seed=7)
    service.approve(view["id"], view["recommended_repair_id"])
    denied = service.attempt(view["id"], "keep")
    assert denied["authorized"] is True
    extra = ActionDef(id="move_board_exam", action_type="calendar.update", label="Move the exam", resource="board_exam")
    with pytest.raises(AuthorizationDenied):
        authorize(service.plans[view["id"]]["contract"], extra, {"scenario": compiled.scenario})


def test_provider_lie_on_a_compiled_action_is_not_success() -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain()[:4])
    assert compiled.scenario is not None
    scenario = compiled.scenario
    scenario.actions.append(
        ActionDef(
            id="stamp",
            action_type="plan.select_option",
            label="Stamp the badge",
            resource="badge",
            effects={"state_token": "moved"},
        )
    )
    spec = PlanSpec(goals=[], hard_constraints=[])
    repair = SimpleNamespace(id="stamp", action_ids=["stamp"], additional_cost=0)
    contract = _contract("plan", scenario, repair, spec)
    providers = SandboxProviders()
    providers.state["badge"] = {"state_token": "old"}
    providers.lie_next = "badge"
    result = execute_bundle(
        scenario=scenario,
        contract=contract,
        providers=providers,
        events=EventLog("sqlite://"),
        plan_id="plan",
    )
    assert result["status"] == "halted"
    assert result["decision"] == "verify_mismatch"


def test_material_update_revokes_authority() -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain()[:4])
    assert compiled.scenario is not None
    service = PlanService(EventLog("sqlite://"))
    view = service.open_compiled("Can I arrive in time?", compiled.scenario, seed=7)
    service.approve(view["id"], "keep")
    event = WorldEvent(
        event_id="clinic_moved",
        source="record",
        event_type="update",
        observed_at="2026-10-07T12:00:00Z",
        affected_entities=["clinic_intake_start"],
        payload={"set_baseline": {"clinic_intake_start": 550}},
        epistemic_status="COMPUTED",
        provenance="test-record",
    )
    drifts = service.watcher.process_event(event, view["id"])
    assert drifts[0].new_status == "INVALID"
    assert service.plans[view["id"]]["contract"].status == "STALE"


def test_approved_future_survives_restart_for_its_session(tmp_path) -> None:
    compiled = compile_primitives("Can I arrive in time?", _chain()[:4])
    assert compiled.scenario is not None
    url = f"sqlite:///{tmp_path / 'shadow.db'}"
    first = PlanService(EventLog(url), session_id="alpha")
    view = first.open_compiled("Can I arrive in time?", compiled.scenario, seed=7)
    first.approve(view["id"], "keep")
    second = PlanService(EventLog(url), session_id="alpha")
    assert view["id"] in second.plans
    assert second.plans[view["id"]]["contract"].status == "ACTIVE"
    other = PlanService(EventLog(url), session_id="beta")
    assert view["id"] not in other.plans
    second.reset_demo()
    third = PlanService(EventLog(url), session_id="alpha")
    assert view["id"] not in third.plans


def test_model_proposal_cannot_invent_a_number_or_a_cycle() -> None:
    records = [{"id": "s", "text": "Supper starts at 7:00 PM.", "observed_at": "2026-10-01T00:00:00Z"}]
    invented = ExecutableProposal(
        variables=[
            VariableIR(
                id="invented",
                label="Invented",
                unit="minutes",
                role="fixed",
                value=999,
                source_ids=["s"],
                epistemic_status=EpistemicStatus.VERIFIED,
            )
        ]
    )
    rejected = validate_proposal(invented, records)
    assert rejected.status == "UNSUPPORTED"
    assert rejected.scenario is None
    cycle = ExecutableProposal(
        variables=[
            VariableIR(
                id="left",
                label="Left",
                unit="minutes",
                role="derived",
                formula=FormulaIR(op="var", ref="right"),
                source_ids=["s"],
            ),
            VariableIR(
                id="right",
                label="Right",
                unit="minutes",
                role="derived",
                formula=FormulaIR(op="var", ref="left"),
                source_ids=["s"],
            ),
        ]
    )
    assert validate_proposal(cycle, records).status == "UNSUPPORTED"
    with pytest.raises(ValidationError):
        ExecutableProposal.model_validate(
            {"actions": [{"id": "x", "action_type": "shell.exec", "label": "x", "resource": "x"}]}
        )
