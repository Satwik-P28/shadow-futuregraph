"""Score repair bundles. The model may propose them. It does not score them."""

from __future__ import annotations

from typing import Any

from shadow.core.models import RepairMetrics, Scenario
from shadow.failures.search import failure_radius, search_failures
from shadow.simulation.engine import bind, evaluate_constraints, hard_status
from shadow.world.loader import action_map, bundle_cost, effects_for


def select_naive(scenario: Scenario) -> str | None:
    """Lowest sticker cost among bundles that pass every hard constraint at baseline."""
    best: tuple[float, str] | None = None
    for bundle in scenario.bundles:
        metrics = _nominal(scenario, bundle.action_ids)
        if metrics[0] or metrics[1]:
            continue
        cost = bundle_cost(scenario, bundle.action_ids)
        if best is None or cost < best[0]:
            best = (cost, bundle.id)
    return None if best is None else best[1]


def evaluate_repairs(
    scenario: Scenario,
    proposals: list[tuple[str, str, list[str], str]],
    *,
    seed: int = 7,
) -> list[RepairMetrics]:
    """proposals: (id, label, action_ids, source) with source catalog|model."""
    scored: list[RepairMetrics] = []
    seen: set[tuple[str, ...]] = set()
    for repair_id, label, action_ids, source in proposals:
        key = tuple(action_ids)
        if key in seen:
            continue
        seen.add(key)
        if any(action_id not in action_map(scenario) for action_id in action_ids):
            continue
        scored.append(_score(scenario, repair_id, label, action_ids, source, seed))
    _mark_pareto(scored)
    _recommend(scored)
    return scored


def _nominal(scenario: Scenario, action_ids: list[str]) -> tuple[int, int]:
    env = bind(scenario, effects_for(scenario, action_ids), {})
    violations, unresolved, _ = hard_status(scenario, evaluate_constraints(scenario, env))
    return violations, unresolved


def _score(
    scenario: Scenario,
    repair_id: str,
    label: str,
    action_ids: list[str],
    source: str,
    seed: int,
) -> RepairMetrics:
    violations, unresolved = _nominal(scenario, action_ids)
    failures, worlds = search_failures(scenario, action_ids, seed=seed)
    radius = failure_radius(failures)
    unknowns = [var.id for var in scenario.variables if var.epistemic_status.value == "UNKNOWN"]
    if violations:
        status = "infeasible"
    elif unresolved:
        status = "unresolved"
    else:
        status = "feasible"
    actions = action_map(scenario)
    chosen = [actions[item] for item in action_ids]
    reversible = sum(1 for item in chosen if item.reversible and not item.irreversible)
    reversibility = reversible / len(chosen) if chosen else 1.0
    baseline = bind(scenario, {}, {})
    repaired = bind(scenario, effects_for(scenario, action_ids), {})
    changed = sum(1 for key, value in repaired.items() if baseline.get(key) != value and not _derived(scenario, key))
    success_rate, basis = _success_rate(failures, status)
    return RepairMetrics(
        id=repair_id,
        label=label,
        action_ids=action_ids,
        source="model" if source == "model" else "catalog",
        hard_violations=violations,
        unresolved_hard=unresolved,
        soft_violations=0,
        failure_radius=radius,
        failure_radius_label=_radius_label(radius, status),
        modeled_success_rate=success_rate,
        success_rate_basis=basis,
        additional_cost=bundle_cost(scenario, action_ids),
        changed_items=changed,
        reversibility=reversibility,
        impact_on_others=sum(item.impacts_others for item in chosen),
        unresolved_unknowns=unknowns,
        feasible=status == "feasible",
        status=status,  # type: ignore[arg-type]
        failures=failures,
        worlds_simulated=worlds,
        rationale="",
        dominated=False,
        recommended=False,
    )


def _derived(scenario: Scenario, var_id: str) -> bool:
    return any(var.id == var_id and var.role == "derived" for var in scenario.variables)


def _radius_label(radius: float | None, status: str) -> str:
    if status == "unresolved":
        return "Unresolved hard constraint"
    if radius is None:
        return "No discovered failure inside the modeled ranges"
    if radius == 0:
        return "Fails with no exogenous perturbation"
    return "Nearest discovered failure"


def _success_rate(failures: list[Any], status: str) -> tuple[float | None, str]:
    if status != "feasible":
        return None, "not estimated"
    if not failures:
        return None, "no failing sample inside the modeled ranges; probability not invented"
    return None, "ranges are declared, but a success probability is not claimed from the nearest failure"


def _objectives(item: RepairMetrics) -> tuple[float, float, float, float]:
    radius = item.failure_radius if item.failure_radius is not None else 1e6
    return (item.hard_violations + item.unresolved_hard, -radius, item.additional_cost, item.changed_items)


def _mark_pareto(items: list[RepairMetrics]) -> None:
    for item in items:
        item.dominated = False
    for item in items:
        left = _objectives(item)
        for other in items:
            if other.id == item.id:
                continue
            right = _objectives(other)
            if _dominates(right, left):
                item.dominated = True
                break


def _dominates(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    better_or_equal = all(a <= b for a, b in zip(left, right, strict=True))
    strictly = any(a < b for a, b in zip(left, right, strict=True))
    return better_or_equal and strictly


def _recommend(items: list[RepairMetrics]) -> None:
    if not items:
        return

    def key(item: RepairMetrics) -> tuple[float, float, float, float, float, float]:
        radius = item.failure_radius if item.failure_radius is not None else 1e6
        return (
            float(item.hard_violations),
            float(item.unresolved_hard),
            -radius,
            float(item.changed_items),
            float(item.additional_cost),
            -item.reversibility,
        )

    winner = min(items, key=key)
    if winner.hard_violations == 0 and winner.unresolved_hard == 0:
        winner.recommended = True


def binding_for(scenario: Scenario, action_ids: list[str]) -> dict[str, Any]:
    return bind(scenario, effects_for(scenario, action_ids), {})
