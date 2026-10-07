from shadow.core.models import ActionDef, Assumption, ContractAction, FutureContract
from shadow.integrations.sandbox import SandboxProviders
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.runtime.events import EventLog
from shadow.runtime.execute import compensation_decision, execute_bundle
from shadow.world.loader import load_scenario


def _contract(action_ids: list[str]) -> FutureContract:
    scenario = load_scenario("travel")
    actions = {item.id: item for item in scenario.actions}
    allowed = [
        ContractAction(
            action_id=action_id,
            action_type=actions[action_id].action_type,
            resource=actions[action_id].resource,
            max_cost=max(actions[action_id].cost, 0),
        )
        for action_id in action_ids
    ]
    return FutureContract(
        contract_id="c1",
        plan_id="p1",
        approved_future_id="b1120",
        created_at="2026-10-07T12:00:00Z",
        expires_at="2026-10-08T00:00:00Z",
        goals=["move"],
        invariants=["c_dinner"],
        assumptions=[],
        allowed_actions=allowed,
        resource_scopes=[item.resource for item in allowed],
        spending_limit=100,
        forbidden_actions=["update_exam"],
        verification_requirements=[],
        compensation_actions=[],
        provenance="test",
    )


def test_broker_rejects_unrelated_event():
    scenario = load_scenario("travel")
    exam = next(item for item in scenario.actions if item.id == "update_exam")
    with __import__("pytest").raises(AuthorizationDenied):
        authorize(_contract(["set_flight_1120", "set_ride_1120", "confirm_friday"]), exam, {})


def test_duplicate_execution_does_not_double_apply():
    scenario = load_scenario("travel")
    providers = SandboxProviders()
    events = EventLog("sqlite://")
    result = execute_bundle(
        scenario=scenario,
        contract=_contract(["set_flight_1120", "set_ride_1120", "confirm_friday"]),
        providers=providers,
        events=events,
        plan_id="p1",
    )
    assert result["status"] == "verified"
    mutations = providers.mutations
    again = execute_bundle(
        scenario=scenario,
        contract=_contract(["set_flight_1120", "set_ride_1120", "confirm_friday"]),
        providers=providers,
        events=events,
        plan_id="p1",
    )
    assert again["status"] == "verified"
    assert providers.mutations == mutations
    replay = events.replay_resources("p1")
    assert "bk_nyc" in replay


def test_timeout_then_retry_is_idempotent():
    scenario = load_scenario("travel")
    providers = SandboxProviders()
    providers.fail_next = "timeout"
    events = EventLog("sqlite://")
    # First action in sorted order may not be the flight. Force the timeout on the first execute.
    result = execute_bundle(
        scenario=scenario,
        contract=_contract(["set_flight_1120"]),
        providers=providers,
        events=events,
        plan_id="p2",
    )
    # Timeout is raised after commit, then retry uses the same key and verifies.
    assert result["status"] == "verified"
    assert providers.mutations == 1


def test_calendar_failure_does_not_compensate_flight():
    flight = ActionDef(id="f", action_type="travel.change_flight", label="f", resource="bk", compensatable=True)
    calendar = ActionDef(id="c", action_type="calendar.update_event", label="c", resource="cal", retryable=True)
    assert compensation_decision(calendar, [flight]) == "retry"


def test_failed_flight_compensates_completed_calendar_step():
    scenario = load_scenario("travel")
    providers = SandboxProviders()
    providers.fail_next = "flight"
    events = EventLog("sqlite://")
    result = execute_bundle(
        scenario=scenario,
        contract=_contract(["confirm_friday", "set_flight_1120"]),
        providers=providers,
        events=events,
        plan_id="p4",
    )
    # confirm_friday sorts first and commits. The flight then fails closed.
    assert result["status"] == "halted"
    assert any(item.event_type == "COMPENSATION_EXECUTED" for item in events.list_for("p4"))


def test_provider_lie_halts():
    scenario = load_scenario("travel")
    providers = SandboxProviders()
    providers.lie_next = "bk_nyc"
    events = EventLog("sqlite://")
    result = execute_bundle(
        scenario=scenario,
        contract=_contract(["set_flight_1120"]),
        providers=providers,
        events=events,
        plan_id="p3",
    )
    assert result["status"] == "halted"
    assert result["decision"] == "verify_mismatch"


def _flight(scenario, action_id: str):
    return next(item for item in scenario.actions if item.id == action_id)


def _world(scenario, when: str = "2026-10-07T18:00:00Z"):
    from datetime import datetime, timezone

    return {
        "scenario": scenario,
        "now": datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc),
    }


def test_broker_blocks_expired_stale_unrelated_cost_and_missing_state():
    scenario = load_scenario("travel")
    flight = _flight(scenario, "set_flight_1120")
    later = _flight(scenario, "set_flight_1440")
    contract = _contract(["set_flight_1120"])
    contract.invariants = ["c_dinner"]
    authorize(contract, flight, _world(scenario))
    with __import__("pytest").raises(AuthorizationDenied, match="expired"):
        authorize(contract, flight, _world(scenario, "2026-10-09T00:00:00Z"))
    stale = contract.model_copy(deep=True)
    stale.assumptions = [
        Assumption(id="asm-delay", description="delay", variable="flight_delay_min", expected=0)
    ]
    shifted = scenario.model_copy(deep=True)
    for var in shifted.variables:
        if var.id == "flight_delay_min":
            var.baseline = 74
    with __import__("pytest").raises(AuthorizationDenied, match="stale assumption"):
        authorize(stale, flight, _world(shifted))
    exam = next(item for item in scenario.actions if item.id == "update_exam")
    with __import__("pytest").raises(AuthorizationDenied, match="outside the approved future"):
        authorize(contract, exam, _world(scenario))
    with __import__("pytest").raises(AuthorizationDenied, match="outside the approved future"):
        authorize(contract, later, _world(scenario))
    pricey = flight.model_copy(update={"cost": 500})
    with __import__("pytest").raises(AuthorizationDenied, match="cost"):
        authorize(contract, pricey, _world(scenario))
    with __import__("pytest").raises(AuthorizationDenied, match="missing material state"):
        authorize(contract, flight, None)
    missing = contract.model_copy(deep=True)
    missing.assumptions = [Assumption(id="asm-x", description="missing", variable="not_a_var", expected=1)]
    with __import__("pytest").raises(AuthorizationDenied, match="missing material state"):
        authorize(missing, flight, _world(scenario))
