"""Deterministic future simulation. No model call."""

from __future__ import annotations

from typing import Any

from shadow.core.expr import UNKNOWN, Expr, evaluate
from shadow.core.models import RepairMetrics, Scenario
from shadow.failures.search import describe_failure
from shadow.simulation.engine import (
    bind,
    evaluate_constraints,
    hard_status,
    sampled_exogenous,
    upstream_vars,
)
from shadow.world.loader import effects_for

NEAREST_MESSAGE = "This is the nearest failure Shadow discovered under the modeled ranges."


def material_controls(scenario: Scenario) -> list[dict[str, Any]]:
    exogenous = {var.id: var for var in sampled_exogenous(scenario)}
    used: set[str] = set()
    for constraint in scenario.constraints:
        if constraint.hardness != "hard":
            continue
        for ref in upstream_vars(scenario, constraint):
            if ref in exogenous:
                used.add(ref)
    controls = []
    for var_id in sorted(used):
        var = exogenous[var_id]
        controls.append(
            {
                "id": var.id,
                "label": var.label,
                "lower": var.lower if var.lower is not None else 0,
                "upper": var.upper if var.upper is not None else var.baseline,
                "baseline": var.baseline,
                "unit": var.unit,
            }
        )
    return controls


def simulate(scenario: Scenario, action_ids: list[str], overrides: dict[str, Any]) -> dict[str, Any]:
    allowed = {item["id"]: item for item in material_controls(scenario)}
    clean: dict[str, float] = {}
    for key, value in overrides.items():
        spec = allowed.get(key)
        if spec is None:
            continue
        number = float(value)
        clean[key] = min(float(spec["upper"]), max(float(spec["lower"]), number))
    env = bind(scenario, effects_for(scenario, action_ids), clean)
    results = evaluate_constraints(scenario, env)
    violations, unresolved, names = hard_status(scenario, results)
    labels = [next(item.label for item in scenario.constraints if item.id == name) for name in names]
    perturbations = [
        {
            "variable": key,
            "label": next(item["label"] for item in allowed.values() if item["id"] == key),
            "baseline": item["baseline"],
            "value": value,
        }
        for key, value in clean.items()
        for item in [allowed[key]]
    ]
    highlight = [f"con:{name}" for name in names] + [f"var:{key}" for key in clean]
    if violations == 0 and unresolved == 0:
        message = "Hard constraints hold under this simulation."
    elif labels:
        message = f"Hard constraint no longer holds: {', '.join(labels)}."
    else:
        message = "A hard constraint is unresolved under this simulation."
    return {
        "overrides": clean,
        "holds": violations == 0 and unresolved == 0,
        "violated": names,
        "violated_labels": labels,
        "unresolved": unresolved,
        "highlight": highlight,
        "message": message,
        "perturbations": perturbations,
        "evaluated_action_ids": list(action_ids),
        "simulation": True,
    }


def nearest_failure(scenario: Scenario, repair: RepairMetrics) -> dict[str, Any]:
    failure = repair.failures[0] if repair.failures else None
    overrides = {item.variable: item.value for item in failure.perturbations} if failure else {}
    result = simulate(scenario, repair.action_ids, overrides)
    result["message"] = NEAREST_MESSAGE if failure else describe_failure(scenario, None)
    result["failure"] = None if failure is None else failure.model_dump(mode="json")
    return result


def batch_simulate(
    scenario: Scenario,
    action_ids: list[str],
    *,
    points_per_variable: int = 16,
) -> dict[str, Any]:
    """Evaluate a bounded Cartesian grid using the same deterministic evaluator."""
    return _evaluate_option(scenario, action_ids, _grid(scenario, points_per_variable))


def compare_simulations(
    scenario: Scenario,
    options: list[dict[str, Any]],
    *,
    points_per_variable: int = 16,
) -> dict[str, Any]:
    cases = _grid(scenario, points_per_variable)
    comparisons = [_evaluate_option(scenario, option["action_ids"], cases) | {
        "id": option["id"],
        "label": option["label"],
        "source": option.get("source", "catalog"),
        "cost": option.get("cost", 0),
    } for option in options]
    ranked = sorted(
        comparisons,
        key=lambda item: (
            not item["overall_feasible"],
            -item["worst_tested_constraint_margin"],
            item["cost"],
            item["id"],
        ),
    )
    winner = ranked[0]["id"] if ranked and ranked[0]["overall_feasible"] else None
    for item in comparisons:
        item["recommended"] = item["id"] == winner
    return {
        "evaluated_per_option": len(cases),
        "variables": [spec["id"] for spec in material_controls(scenario)],
        "objective": "hard constraints first; then maximize worst tested hard-constraint margin; then minimize added cost",
        "options": comparisons,
        "recommended_id": winner,
        "simulation": True,
    }


def _grid(scenario: Scenario, points_per_variable: int) -> list[dict[str, float]]:
    controls = material_controls(scenario)
    if not controls:
        return [{}]
    if points_per_variable < 2:
        raise ValueError("points_per_variable must be at least 2")
    axes = [
        [
            float(spec["lower"])
            + (float(spec["upper"]) - float(spec["lower"])) * index / (points_per_variable - 1)
            for index in range(points_per_variable)
        ]
        for spec in controls
    ]
    cases: list[dict[str, float]] = [{}]
    for spec, values in zip(controls, axes):
        cases = [{**case, spec["id"]: value} for case in cases for value in values]
    return cases


def _evaluate_option(
    scenario: Scenario,
    action_ids: list[str],
    cases: list[dict[str, float]],
) -> dict[str, Any]:
    feasible = 0
    nominal_holds = False
    worst_margin = float("inf")
    failures: list[dict[str, Any]] = []
    successes: list[dict[str, Any]] = []
    for index, overrides in enumerate(cases):
        result = simulate(scenario, action_ids, overrides)
        if index == 0:
            nominal_holds = result["holds"]
        env = bind(scenario, effects_for(scenario, action_ids), overrides)
        margin = _hard_margin(scenario, env)
        if margin is not None:
            worst_margin = min(worst_margin, margin)
        case = {
            "overrides": result["overrides"],
            "holds": result["holds"],
            "violated": result["violated"],
            "violated_labels": result["violated_labels"],
        }
        if result["holds"]:
            feasible += 1
            if len(successes) < 3:
                successes.append(case)
        elif len(failures) < 5:
            failures.append(case)
    return {
        "evaluated": len(cases),
        "feasible": feasible,
        "failing": len(cases) - feasible,
        "action_ids": action_ids,
        "variables": [spec["id"] for spec in material_controls(scenario)],
        "representative_failures": failures,
        "representative_successes": successes,
        "hard_constraint_failures": len(cases) - feasible,
        "worst_tested_constraint_margin": 0 if worst_margin == float("inf") else worst_margin,
        "overall_feasible": nominal_holds,
        "simulation": True,
    }


def _hard_margin(scenario: Scenario, env: dict[str, Any]) -> float | None:
    margins: list[float] = []
    for constraint in scenario.constraints:
        if constraint.hardness != "hard":
            continue
        margin = _constraint_margin(constraint.expr, env)
        if margin is not None:
            margins.append(margin)
    return min(margins) if margins else None


def _constraint_margin(expr: Expr, env: dict[str, Any]) -> float | None:
    if expr.op in {"lte", "lt", "gte", "gt", "eq"} and len(expr.args) == 2:
        left = evaluate(expr.args[0], env)
        right = evaluate(expr.args[1], env)
        if left is UNKNOWN or right is UNKNOWN or not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        if expr.op in {"lte", "lt"}:
            return float(right - left)
        if expr.op in {"gte", "gt"}:
            return float(left - right)
        return float(-abs(left - right))
    margins = [_constraint_margin(arg, env) for arg in expr.args]
    values = [value for value in margins if value is not None]
    return min(values) if values else None
