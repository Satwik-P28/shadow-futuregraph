"""Procedural worlds. The oracle is not passed to the evaluator."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import qmc

from shadow.core.expr import Expr
from shadow.core.models import (
    ActionDef,
    Bundle,
    Constraint,
    EpistemicStatus,
    Scenario,
    Variable,
    WorldFact,
)


def generate_world(seed: int, family: str) -> tuple[Scenario, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    weights = rng.uniform(0.45, 0.9, size=3)
    total = float(weights.sum())
    margins = {
        "cheap": round(float(rng.uniform(0.25, 0.45)), 3),
        "mid": round(float(total * 0.62), 3),
        "robust": round(total + 0.15, 3),
    }
    costs = {"cheap": 10.0, "mid": 28.0, "robust": 60.0}
    include_unknown = family == "purchase"
    variables = [
        Variable(
            id="margin",
            label="Safety margin",
            role="controllable",
            vtype="number",
            baseline=0,
            epistemic_status=EpistemicStatus.VERIFIED,
            show_in_diff=True,
        )
    ]
    for index, weight in enumerate(weights):
        variables.append(
            Variable(
                id=f"x{index}",
                label=f"Shock {index + 1}",
                role="exogenous",
                vtype="number",
                baseline=0,
                lower=0,
                upper=1,
                scale=1,
                distribution="uniform",
                epistemic_status=EpistemicStatus.ESTIMATED,
            )
        )
    if include_unknown:
        variables.append(
            Variable(
                id="vendor_note",
                label="Vendor note",
                role="exogenous",
                vtype="category",
                baseline=None,
                distribution="unknown",
                epistemic_status=EpistemicStatus.UNKNOWN,
            )
        )
    shock = Expr(
        op="add",
        args=[
            Expr(op="mul", args=[Expr(op="const", value=float(weights[i])), Expr(op="var", ref=f"x{i}")])
            for i in range(3)
        ],
    )
    variables.append(
        Variable(
            id="slack",
            label="Slack",
            role="derived",
            vtype="number",
            epistemic_status=EpistemicStatus.COMPUTED,
            formula=Expr(op="sub", args=[Expr(op="var", ref="margin"), shock]),
        )
    )
    actions = []
    bundles = []
    for name in ("cheap", "mid", "robust"):
        action_id = f"set_{name}"
        actions.append(
            ActionDef(
                id=action_id,
                action_type="plan.set_margin",
                label=f"Set {name} margin",
                resource="plan",
                cost=costs[name],
                effects={"margin": margins[name]},
            )
        )
        bundles.append(Bundle(id=name, label=f"{name} plan", action_ids=[action_id]))
    facts = [
        WorldFact(
            id="f1",
            subject="plan",
            predicate="observed",
            value=family,
            observed_at="2026-10-07T12:00:00Z",
            source_type="generator",
            source_id=f"{family}-{seed}",
            epistemic_status=EpistemicStatus.VERIFIED,
            tags=["support"],
            text=f"A {family} commitment with three exogenous shocks.",
        )
    ]
    scenario = Scenario(
        id=f"{family}-{seed}",
        title=f"{family} world {seed}",
        domain=family,
        plan_prompt=f"Commit to the {family} plan if it will still hold.",
        variables=variables,
        constraints=[
            Constraint(
                id="c_slack",
                label="Slack stays non-negative",
                kind="numeric",
                hardness="hard",
                description="Weighted shocks must stay inside the selected margin.",
                expr=Expr(op="gte", args=[Expr(op="var", ref="slack"), Expr(op="const", value=0)]),
            )
        ],
        actions=actions,
        bundles=bundles,
        facts=facts,
    )
    oracle = {
        "seed": seed,
        "family": family,
        "weights": [float(value) for value in weights],
        "margins": margins,
        "costs": costs,
        "optimal": _optimal(weights, margins, costs),
        "material_edges": [f"x{i}" for i in range(3)],
        "unknown": include_unknown,
    }
    return scenario, oracle


def _optimal(weights: np.ndarray, margins: dict[str, float], costs: dict[str, float]) -> str | None:
    probes = _probes(len(weights), 11)
    best: tuple[float, str] | None = None
    for name, margin in margins.items():
        if all(float(np.dot(weights, probe)) <= margin + 1e-9 for probe in probes):
            if best is None or costs[name] < best[0]:
                best = (costs[name], name)
    return None if best is None else best[1]


def _probes(dimensions: int, seed: int) -> np.ndarray:
    sampler = qmc.Sobol(d=dimensions, scramble=True, seed=seed)
    points = sampler.random(64)
    points = np.vstack([points, np.ones((1, dimensions))])
    return points


def probe_failures(oracle: dict[str, Any], margin: float) -> int:
    weights = np.array(oracle["weights"])
    probes = _probes(len(weights), 11)
    return int(sum(float(np.dot(weights, probe)) > margin + 1e-9 for probe in probes))
