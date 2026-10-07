"""Deterministic future simulation. No model call."""

from __future__ import annotations

from typing import Any

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
        "simulation": True,
    }


def nearest_failure(scenario: Scenario, repair: RepairMetrics) -> dict[str, Any]:
    failure = repair.failures[0] if repair.failures else None
    overrides = {item.variable: item.value for item in failure.perturbations} if failure else {}
    result = simulate(scenario, repair.action_ids, overrides)
    result["message"] = NEAREST_MESSAGE if failure else describe_failure(scenario, None)
    result["failure"] = None if failure is None else failure.model_dump(mode="json")
    return result
