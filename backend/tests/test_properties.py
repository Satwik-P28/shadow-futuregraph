from hypothesis import given, settings
from hypothesis import strategies as st

from shadow.core.models import ActionDef, ContractAction, FutureContract
from shadow.failures.search import search_failures
from shadow.llm.budget import BudgetLedger
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.simulation.engine import bind
from shadow.world.loader import effects_for, load_scenario


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=1, max_value=10_000))
def test_same_seed_same_failure(seed: int):
    scenario = load_scenario("travel")
    left, _ = search_failures(scenario, ["set_flight_1440", "set_ride_1440", "confirm_friday"], seed=seed)
    right, _ = search_failures(scenario, ["set_flight_1440", "set_ride_1440", "confirm_friday"], seed=seed)
    assert [item.model_dump() for item in left] == [item.model_dump() for item in right]


@settings(max_examples=15, deadline=None)
@given(st.lists(st.sampled_from(["flight_delay_min", "traffic_extra_min"]), min_size=1, max_size=2, unique=True))
def test_removing_a_required_perturbation_stops_the_known_failure(names: list[str]):
    scenario = load_scenario("travel")
    failures, _ = search_failures(scenario, ["set_flight_1440", "set_ride_1440", "confirm_friday"], seed=7)
    dinner = next(item for item in failures if "c_dinner" in item.violated_constraints)
    if not dinner.perturbations:
        return
    effects = effects_for(scenario, ["set_flight_1440", "set_ride_1440", "confirm_friday"])
    point = {item.variable: item.value for item in dinner.perturbations}
    for name in names:
        if name not in point:
            continue
        reduced = dict(point)
        reduced[name] = 0
        env = bind(scenario, effects, reduced)
        arrival = env["dinner_arrival_min"]
        if len(dinner.perturbations) == 2 and set(point) == {"flight_delay_min", "traffic_extra_min"}:
            assert arrival <= env["dinner_deadline_min"]


def test_repaired_future_with_hard_violation_is_not_valid():
    from shadow.repair.evaluate import evaluate_repairs

    scenario = load_scenario("travel")
    scored = evaluate_repairs(scenario, [("bad", "bad", ["set_flight_1710", "set_ride_1710", "confirm_friday", "move_dinner"], "model")], seed=1)
    assert scored[0].feasible is False
    assert scored[0].recommended is False


def test_broker_never_authorizes_outside_resource(tmp_path):
    contract = FutureContract(
        contract_id="c",
        plan_id="p",
        approved_future_id="r",
        created_at="t",
        expires_at="t",
        goals=[],
        invariants=[],
        assumptions=[],
        allowed_actions=[ContractAction(action_id="a", action_type="calendar.update_event", resource="cal_trip", max_cost=0)],
        resource_scopes=["cal_trip"],
        spending_limit=10,
        forbidden_actions=["other"],
        verification_requirements=[],
        compensation_actions=[],
        provenance="test",
    )
    action = ActionDef(id="other", action_type="calendar.update_event", label="exam", resource="cal_exam")
    try:
        authorize(contract, action, {})
        raise AssertionError("authorized an outside resource")
    except AuthorizationDenied:
        pass
    ledger = BudgetLedger(tmp_path / "b.json")
    assert ledger.remaining_repo() >= 0
    assert ledger.remaining_overall() >= 0
