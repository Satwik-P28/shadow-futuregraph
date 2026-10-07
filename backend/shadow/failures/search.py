"""Nearest discovered failure and minimal failure sets.

The radius is the smallest normalized L2 perturbation this search actually
found. It is not a probability and not a proof that nothing closer exists.
Perturbations live on exogenous numeric variables declared by the scenario.

Search, per hard constraint:
- seeded Sobol samples, with ray-shrinking of the cheapest failures
- directional refinement on each variable and each pair
- greedy cut-set reduction, then an exact subset check when the set is small
"""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import combinations

from scipy.stats import qmc

from shadow.core.models import MinimalFailureSet, Perturbation, Scenario, Variable
from shadow.simulation.engine import bind, evaluate_constraints, sampled_exogenous, upstream_vars
from shadow.world.loader import effects_for

MAX_WORLDS = 1024
_SOBOL = 128
_BISECT = 8

FailFn = Callable[[dict[str, float]], bool]


class EvalBudget:
    def __init__(self, limit: int = MAX_WORLDS) -> None:
        self.limit = limit
        self.used = 0

    @property
    def open(self) -> bool:
        return self.used < self.limit

    def charge(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def search_failures(
    scenario: Scenario,
    action_ids: list[str],
    *,
    seed: int = 7,
) -> tuple[list[MinimalFailureSet], int]:
    effects = effects_for(scenario, action_ids)
    variables = sampled_exogenous(scenario)
    budget = EvalBudget()
    base = {var.id: float(var.baseline or 0) for var in variables}
    bundle = "+".join(action_ids)
    found: list[MinimalFailureSet] = []

    for index, constraint in enumerate(c for c in scenario.constraints if c.hardness == "hard"):
        def truth(overrides: dict[str, float], constraint_id: str = constraint.id) -> bool:
            env = bind(scenario, effects, overrides)
            return evaluate_constraints(scenario, env).get(constraint_id) is False

        def fails(overrides: dict[str, float]) -> bool:
            if not budget.charge():
                return False
            return truth(overrides)

        exo_ids = {var.id for var in variables}
        depends_on_sample = bool(set(upstream_vars(scenario, constraint)) & exo_ids)
        if fails(base):
            found.append(_record(scenario, bundle, constraint.id, base, [], 0.0, index))
            continue
        if not depends_on_sample:
            continue
        point = _nearest(scenario, variables, base, fails, seed + index, budget)
        if point is None:
            continue
        active = _minimal_subset(variables, point, base, truth)
        found.append(
            _record(
                scenario,
                bundle,
                constraint.id,
                point,
                active,
                _cost(variables, base, point),
                index,
            )
        )
    found.sort(key=lambda item: (item.normalized_distance, item.id))
    return _dedupe(found), budget.used


def _nearest(
    scenario: Scenario,
    variables: list[Variable],
    base: dict[str, float],
    fails: FailFn,
    seed: int,
    budget: EvalBudget,
) -> dict[str, float] | None:
    del scenario
    if not variables or not budget.open:
        return None
    candidates = _sobol_points(variables, base, fails, seed, budget)
    candidates.extend(_directional_points(variables, base, fails, budget))
    best: dict[str, float] | None = None
    best_cost = math.inf
    for point in candidates:
        cost = _cost(variables, base, point)
        if cost < best_cost:
            best = point
            best_cost = cost
    return best


def _sobol_points(
    variables: list[Variable],
    base: dict[str, float],
    fails: FailFn,
    seed: int,
    budget: EvalBudget,
) -> list[dict[str, float]]:
    count = 1 << int(math.floor(math.log2(_SOBOL)))
    sampler = qmc.Sobol(d=len(variables), scramble=True, seed=seed)
    failing: list[tuple[float, dict[str, float]]] = []
    for row in sampler.random(count):
        if not budget.open:
            break
        point = dict(base)
        for var, unit in zip(variables, row, strict=True):
            lower = float(var.lower if var.lower is not None else base[var.id])
            upper = float(var.upper if var.upper is not None else lower)
            point[var.id] = lower + float(unit) * (upper - lower)
        if fails(point):
            failing.append((_cost(variables, base, point), point))
    failing.sort(key=lambda item: item[0])
    shrunk: list[dict[str, float]] = []
    for _, point in failing[:6]:
        boundary = _ray_shrink(base, point, fails, budget)
        if boundary is not None:
            shrunk.append(boundary)
    corner = dict(base)
    for var in variables:
        corner[var.id] = float(var.upper if var.upper is not None else base[var.id])
    if budget.open and fails(corner):
        boundary = _ray_shrink(base, corner, fails, budget)
        if boundary is not None:
            shrunk.append(boundary)
    return shrunk


def _directional_points(
    variables: list[Variable],
    base: dict[str, float],
    fails: FailFn,
    budget: EvalBudget,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    pairs = list(combinations(range(len(variables)), 2))
    steps = 12 if len(pairs) <= 1 else 8 if len(pairs) <= 3 else 4
    axes = [(index,) for index in range(len(variables))]
    groups = axes + pairs
    for group in groups:
        for step in range(1, steps + 1):
            if not budget.open:
                return points
            weights = _direction_weights(len(group), step, steps)
            point = _boundary_along(variables, base, group, weights, fails, budget)
            if point is not None:
                points.append(point)
    return points


def _direction_weights(size: int, step: int, steps: int) -> list[float]:
    if size == 1:
        return [1.0]
    theta = (math.pi / 2) * step / (steps + 1)
    return [math.cos(theta), math.sin(theta)]


def _boundary_along(
    variables: list[Variable],
    base: dict[str, float],
    indexes: tuple[int, ...],
    weights: list[float],
    fails: FailFn,
    budget: EvalBudget,
) -> dict[str, float] | None:
    def at(radius: float) -> dict[str, float]:
        point = dict(base)
        for offset, index in enumerate(indexes):
            var = variables[index]
            scale = float(var.scale or 1)
            lower = float(var.lower if var.lower is not None else base[var.id])
            upper = float(var.upper if var.upper is not None else base[var.id] + scale)
            point[var.id] = min(upper, max(lower, base[var.id] + radius * weights[offset] * scale))
        return point

    if not budget.open:
        return None
    if fails(at(0.0)):
        return at(0.0)
    if not fails(at(1.75)):
        return None
    low = 0.0
    high = 1.75
    for _ in range(_BISECT):
        if not budget.open:
            break
        mid = (low + high) / 2
        if fails(at(mid)):
            high = mid
        else:
            low = mid
    return at(high)


def _ray_shrink(
    base: dict[str, float],
    point: dict[str, float],
    fails: FailFn,
    budget: EvalBudget,
) -> dict[str, float] | None:
    def at(scale: float) -> dict[str, float]:
        return {
            key: origin + scale * (float(point.get(key, origin)) - origin) for key, origin in base.items()
        }

    if not budget.open or not fails(at(1.0)):
        return None
    if fails(at(0.0)):
        return at(0.0)
    low = 0.0
    high = 1.0
    for _ in range(_BISECT):
        if not budget.open:
            break
        mid = (low + high) / 2
        if fails(at(mid)):
            high = mid
        else:
            low = mid
    return at(high)


def _minimal_subset(
    variables: list[Variable],
    point: dict[str, float],
    base: dict[str, float],
    fails: FailFn,
) -> list[Variable]:
    active = [var for var in variables if abs(point.get(var.id, base[var.id]) - base[var.id]) > 1e-6]
    ids = [var.id for var in active]

    def project(keep: set[str]) -> dict[str, float]:
        projected = dict(base)
        for var_id in keep:
            projected[var_id] = point[var_id]
        return projected

    if len(ids) <= 8:
        exact = _exact_minimal(ids, project, fails)
        if exact is not None:
            chosen = set(exact)
            return [var for var in active if var.id in chosen]

    current = set(ids)
    changed = True
    while changed:
        changed = False
        for var_id in list(current):
            if fails(project(current - {var_id})):
                current.remove(var_id)
                changed = True
                break
    return [var for var in active if var.id in current]


def _exact_minimal(
    ids: list[str],
    project: Callable[[set[str]], dict[str, float]],
    fails: FailFn,
) -> tuple[str, ...] | None:
    best: tuple[str, ...] | None = None
    for mask in range(1 << len(ids)):
        subset = tuple(var_id for bit, var_id in enumerate(ids) if mask & (1 << bit))
        if best is not None and len(subset) >= len(best):
            continue
        if not fails(project(set(subset))):
            continue
        if all(not fails(project(set(subset) - {item})) for item in subset):
            best = subset
    return best


def _cost(variables: list[Variable], base: dict[str, float], point: dict[str, float]) -> float:
    total = 0.0
    for var in variables:
        scale = float(var.scale or 1) or 1.0
        delta = float(point.get(var.id, base[var.id])) - base[var.id]
        total += (delta / scale) ** 2
    return math.sqrt(total)


def _record(
    scenario: Scenario,
    bundle: str,
    constraint_id: str,
    point: dict[str, float],
    active: list[Variable],
    distance: float,
    index: int,
) -> MinimalFailureSet:
    by_id = {var.id: var for var in scenario.variables}
    perturbations = []
    for var in active:
        scale = float(var.scale or 1) or 1.0
        base = float(var.baseline or 0)
        value = float(point.get(var.id, base))
        perturbations.append(
            Perturbation(
                variable=var.id,
                label=var.label,
                baseline=base,
                value=value,
                normalized_magnitude=abs(value - base) / scale,
                provenance=var.distribution,
                controllability="exogenous",
            )
        )
    constraint = next(item for item in scenario.constraints if item.id == constraint_id)
    trace = upstream_vars(scenario, constraint)
    trace_labels = [by_id[item].label for item in trace if item in by_id]
    return MinimalFailureSet(
        id=f"fail-{index}-{constraint_id}",
        bundle_id=bundle,
        perturbations=perturbations,
        violated_constraints=[constraint_id],
        severity="hard",
        normalized_distance=distance,
        causal_trace=trace_labels,
        repairable=True,
        probability=None,
    )


def _dedupe(items: list[MinimalFailureSet]) -> list[MinimalFailureSet]:
    kept: list[MinimalFailureSet] = []
    for item in items:
        signature = (tuple(sorted(p.variable for p in item.perturbations)), tuple(item.violated_constraints))
        if any(
            tuple(sorted(p.variable for p in other.perturbations)) == signature[0]
            and tuple(other.violated_constraints) == signature[1]
            and other.normalized_distance <= item.normalized_distance + 1e-9
            for other in kept
        ):
            continue
        kept.append(item)
    return kept


def failure_radius(failures: list[MinimalFailureSet]) -> float | None:
    if not failures:
        return None
    return min(item.normalized_distance for item in failures)


def describe_failure(scenario: Scenario, failure: MinimalFailureSet | None) -> str:
    if failure is None:
        return "No discovered failure inside the modeled ranges."
    constraint = next(item.label for item in scenario.constraints if item.id == failure.violated_constraints[0])
    if not failure.perturbations:
        return f"Already violates {constraint} with no exogenous perturbation."
    parts = []
    for item in failure.perturbations:
        unit = next(var.unit for var in scenario.variables if var.id == item.variable)
        parts.append(f"{item.label} {item.baseline:.0f}→{item.value:.0f}{unit}")
    return f"Nearest discovered failure: {', '.join(parts)} violates {constraint}."
