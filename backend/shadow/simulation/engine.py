"""Bind actions and exogenous samples, then evaluate typed constraints."""

from __future__ import annotations

from typing import Any

import networkx as nx

from shadow.core.expr import UNKNOWN, evaluate, references
from shadow.core.models import Constraint, Scenario, Variable


class FormulaCycle(ValueError):
    pass


def derived_variables(scenario: Scenario) -> list[Variable]:
    derived = [var for var in scenario.variables if var.role == "derived"]
    graph = nx.DiGraph()
    derived_ids = {var.id for var in derived}
    for var in derived:
        graph.add_node(var.id)
        if var.formula is None:
            raise ValueError(f"derived variable {var.id} has no formula")
        for ref in references(var.formula):
            if ref in derived_ids:
                graph.add_edge(ref, var.id)
    if not nx.is_directed_acyclic_graph(graph):
        raise FormulaCycle("derived formulas contain a cycle")
    by_id = {var.id: var for var in derived}
    return [by_id[node] for node in nx.topological_sort(graph)]


def sampled_exogenous(scenario: Scenario) -> list[Variable]:
    return [
        var
        for var in scenario.variables
        if var.role == "exogenous" and var.distribution == "uniform" and var.vtype == "number"
    ]


def bind(
    scenario: Scenario,
    effects: dict[str, Any] | None = None,
    exogenous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply action effects, then exogenous overrides, then derived formulas."""
    effects = effects or {}
    exogenous = exogenous or {}
    env: dict[str, Any] = {}
    for var in scenario.variables:
        if var.role == "derived":
            continue
        if var.id in effects:
            env[var.id] = effects[var.id]
        elif var.id in exogenous:
            env[var.id] = exogenous[var.id]
        else:
            env[var.id] = var.baseline
    for var in derived_variables(scenario):
        assert var.formula is not None
        value = evaluate(var.formula, env)
        env[var.id] = None if value is UNKNOWN else value
    return env


def evaluate_constraints(scenario: Scenario, env: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for constraint in scenario.constraints:
        value = evaluate(constraint.expr, env)
        results[constraint.id] = None if value is UNKNOWN else bool(value) if isinstance(value, bool) else value
    return results


def hard_status(scenario: Scenario, results: dict[str, Any]) -> tuple[int, int, list[str]]:
    violations: list[str] = []
    unresolved: list[str] = []
    for constraint in scenario.constraints:
        if constraint.hardness != "hard":
            continue
        value = results.get(constraint.id)
        if value is None:
            unresolved.append(constraint.id)
        elif value is False:
            violations.append(constraint.id)
    return len(violations), len(unresolved), violations


def constraint_by_id(scenario: Scenario) -> dict[str, Constraint]:
    return {constraint.id: constraint for constraint in scenario.constraints}


def upstream_vars(scenario: Scenario, constraint: Constraint) -> list[str]:
    """Causal parents of a constraint, derived variables expanded."""
    by_id = {var.id: var for var in scenario.variables}
    seen: list[str] = []
    stack = list(references(constraint.expr))
    while stack:
        ref = stack.pop()
        if ref in seen:
            continue
        seen.append(ref)
        var = by_id.get(ref)
        if var and var.formula is not None:
            for parent in references(var.formula):
                if parent not in seen:
                    stack.append(parent)
    return seen
