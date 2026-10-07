"""Frozen heterogeneous worlds for the live pilot. The oracle is not model context."""

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
from shadow.repair.evaluate import select_naive
from shadow.simulation.engine import bind, evaluate_constraints, hard_status, sampled_exogenous
from shadow.world.loader import bundle_cost, effects_for

STRUCTURES = (
    "robust_nominal",
    "single_variable",
    "two_variable",
    "three_variable",
    "irrelevant_axes",
    "multiple_valid",
    "cheapest_best",
    "cheapest_not_best",
    "impossible",
    "unknown_material",
    "stale_fact",
    "repair_tradeoff",
    "hidden_downstream",
    "no_change",
    "distractors",
)
DOMAINS = ("travel", "scheduling", "purchase")
PLANS = {
    "travel": "Book the trip so the fixed commitment still holds.",
    "scheduling": "Schedule the commitment so it still holds.",
    "purchase": "Place the order so the commitment still holds.",
}
HIDDEN_PLANS = {
    "travel": "Pick the lowest fare for the trip.",
    "scheduling": "Pick the cheapest open slot.",
    "purchase": "Compare the sticker prices and place the order.",
}


def generate_world(index: int) -> tuple[Scenario, dict[str, Any]]:
    if index < 0 or index > 29:
        raise ValueError("live pilot index must be 0..29")
    structure = STRUCTURES[index % len(STRUCTURES)]
    copy = index // len(STRUCTURES)
    domain = DOMAINS[(index % len(STRUCTURES) + copy) % len(DOMAINS)]
    shift = 0.02 * copy
    scenario, oracle = _build(index, structure, domain, shift)
    oracle["index"] = index
    oracle["copy"] = copy
    _assert_structure(scenario, oracle)
    return scenario, oracle


def assess(scenario: Scenario, action_ids: list[str]) -> dict[str, Any]:
    env = bind(scenario, effects_for(scenario, action_ids), {})
    violations, unresolved, _ = hard_status(scenario, evaluate_constraints(scenario, env))
    exo = sampled_exogenous(scenario)
    probe_fails = 0
    if not violations and not unresolved and exo:
        for point in _probes(len(exo)):
            sample = {
                var.id: _scale(var, float(point[pos]))
                for pos, var in enumerate(exo)
            }
            probed = bind(scenario, effects_for(scenario, action_ids), sample)
            hit, pending, _ = hard_status(scenario, evaluate_constraints(scenario, probed))
            if hit or pending:
                probe_fails += 1
    return {
        "safe": not violations and not unresolved and probe_fails == 0,
        "nominal_violations": violations,
        "unresolved": unresolved,
        "probe_fails": probe_fails,
        "cost": bundle_cost(scenario, action_ids),
    }


def optimal_bundle(scenario: Scenario) -> str | None:
    best: tuple[float, str] | None = None
    for bundle in scenario.bundles:
        view = assess(scenario, bundle.action_ids)
        if not view["safe"]:
            continue
        if best is None or view["cost"] < best[0]:
            best = (view["cost"], bundle.id)
    return None if best is None else best[1]


def pilot_context(scenario: Scenario) -> dict[str, Any]:
    """Shared evidence. No formulas, bounds, or oracle fields."""
    costs = {bundle.id: bundle_cost(scenario, bundle.action_ids) for bundle in scenario.bundles}
    unknowns = [var.id for var in scenario.variables if var.epistemic_status == EpistemicStatus.UNKNOWN]
    facts = []
    for fact in scenario.facts:
        facts.append(
            {
                "id": fact.id,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "value": fact.value,
                "epistemic_status": fact.epistemic_status.value,
                "text": fact.text[:140],
            }
        )
    conflicts = _conflict_ids(scenario.facts)
    return {
        "domain": scenario.domain,
        "plan": scenario.plan_prompt,
        "bundles": [
            {
                "id": bundle.id,
                "label": bundle.label,
                "action_ids": bundle.action_ids,
                "cost": costs[bundle.id],
            }
            for bundle in scenario.bundles
        ],
        "constraints": [
            {"id": item.id, "hardness": item.hardness, "description": item.description}
            for item in scenario.constraints
        ],
        "unknowns": unknowns,
        "facts": facts,
        "conflicting_fact_ids": conflicts,
    }


def _build(index: int, structure: str, domain: str, shift: float) -> tuple[Scenario, dict[str, Any]]:
    fragile = round(0.18 + shift, 3)
    robust = round(1.22 + shift, 3)
    prompt = HIDDEN_PLANS[domain] if structure == "hidden_downstream" else PLANS[domain]
    if structure == "impossible":
        return _impossible(index, domain, prompt)
    if structure == "unknown_material":
        return _unknown(index, domain, prompt)
    if structure == "repair_tradeoff":
        return _tradeoff(index, domain, prompt, fragile, robust)
    penalty, shocks, cut = _penalty(structure)
    options = _options(structure, fragile, robust)
    if structure == "no_change":
        variables = [_margin(robust)]
    else:
        variables = [_margin(0)]
    variables.extend(shocks)
    variables.append(_slack(penalty))
    actions, bundles = _bundles(options)
    facts = _facts(structure, domain, index)
    scenario = _scenario(index, domain, prompt, variables, _slack_constraints(), actions, bundles, facts)
    oracle = {
        "structure": structure,
        "domain": domain,
        "optimal": None,
        "minimal_cut": cut,
        "material_edges": cut,
    }
    oracle["optimal"] = optimal_bundle(scenario)
    return scenario, oracle


def _penalty(structure: str) -> tuple[Expr, list[Variable], list[str]]:
    if structure in {"two_variable"}:
        shocks = [_shock("x0"), _shock("x1")]
        total = Expr(op="add", args=[Expr(op="var", ref="x0"), Expr(op="var", ref="x1")])
        penalty = Expr(op="max", args=[Expr(op="const", value=0), Expr(op="sub", args=[total, Expr(op="const", value=1)])])
        return penalty, shocks, ["x0", "x1"]
    if structure == "three_variable":
        shocks = [_shock("x0"), _shock("x1"), _shock("x2")]
        total = Expr(
            op="add",
            args=[Expr(op="var", ref="x0"), Expr(op="var", ref="x1"), Expr(op="var", ref="x2")],
        )
        penalty = Expr(op="max", args=[Expr(op="const", value=0), Expr(op="sub", args=[total, Expr(op="const", value=2)])])
        return penalty, shocks, ["x0", "x1", "x2"]
    shocks = [_shock("x0")]
    if structure == "irrelevant_axes":
        shocks.extend([_shock("noise_a"), _shock("noise_b")])
    return Expr(op="var", ref="x0"), shocks, ["x0"]


def _options(structure: str, fragile: float, robust: float) -> list[tuple[str, str, float, float]]:
    if structure == "robust_nominal":
        return [
            ("opt_a", "Option A", robust, 12),
            ("opt_b", "Option B", robust + 0.05, 28),
            ("opt_c", "Option C", robust + 0.08, 46),
        ]
    if structure == "multiple_valid":
        return [
            ("opt_a", "Option A", fragile, 11),
            ("opt_b", "Option B", robust, 34),
            ("opt_c", "Option C", robust + 0.08, 61),
        ]
    if structure == "cheapest_best":
        return [
            ("opt_a", "Option A", robust, 9),
            ("opt_b", "Option B", robust + 0.04, 39),
            ("opt_c", "Option C", fragile, 22),
        ]
    if structure == "no_change":
        return [
            ("opt_keep", "Keep the current commitment", robust, 20),
            ("opt_cheaper", "Switch to the cheaper commitment", fragile, 6),
        ]
    return [
        ("opt_a", "Option A", fragile, 10),
        ("opt_b", "Option B", round((fragile + robust) / 2, 3), 27),
        ("opt_c", "Option C", robust, 58),
    ]


def _tradeoff(index: int, domain: str, prompt: str, fragile: float, robust: float) -> tuple[Scenario, dict[str, Any]]:
    del fragile
    variables = [
        _level("a_level"),
        _level("b_level"),
        _shock("x0"),
        Variable(
            id="slack_a",
            label="First slack",
            role="derived",
            vtype="number",
            epistemic_status=EpistemicStatus.COMPUTED,
            formula=Expr(op="sub", args=[Expr(op="var", ref="a_level"), Expr(op="var", ref="x0")]),
        ),
        Variable(
            id="slack_b",
            label="Second slack",
            role="derived",
            vtype="number",
            epistemic_status=EpistemicStatus.COMPUTED,
            formula=Expr(op="sub", args=[Expr(op="var", ref="b_level"), Expr(op="var", ref="x0")]),
        ),
    ]
    actions, bundles = _bundles(
        [
            ("opt_patch", "Patch the first commitment", 0, 16),
            ("opt_align", "Align both commitments", 0, 48),
            ("opt_cheap", "Take the cheaper commitment", 0, 9),
        ],
        effects={
            "opt_patch": {"a_level": robust, "b_level": 0.2},
            "opt_align": {"a_level": robust, "b_level": robust},
            "opt_cheap": {"a_level": 0.2, "b_level": 0.2},
        },
    )
    constraints = [
        Constraint(
            id="c_first",
            label="First commitment",
            kind="numeric",
            hardness="hard",
            description="The first downstream commitment stays non-negative inside the declared range.",
            expr=Expr(op="gte", args=[Expr(op="var", ref="slack_a"), Expr(op="const", value=0)]),
        ),
        Constraint(
            id="c_second",
            label="Second commitment",
            kind="numeric",
            hardness="hard",
            description="The second downstream commitment stays non-negative inside the declared range.",
            expr=Expr(op="gte", args=[Expr(op="var", ref="slack_b"), Expr(op="const", value=0)]),
        ),
    ]
    scenario = _scenario(index, domain, prompt, variables, constraints, actions, bundles, _facts("repair_tradeoff", domain, index))
    return scenario, {
        "structure": "repair_tradeoff",
        "domain": domain,
        "optimal": optimal_bundle(scenario),
        "minimal_cut": ["x0"],
        "material_edges": ["x0"],
    }


def _impossible(index: int, domain: str, prompt: str) -> tuple[Scenario, dict[str, Any]]:
    variables = [_margin(0)]
    constraints = [
        Constraint(
            id="c_high",
            label="High floor",
            kind="numeric",
            hardness="hard",
            description="The commitment level must be at least 5.",
            expr=Expr(op="gte", args=[Expr(op="var", ref="margin"), Expr(op="const", value=5)]),
        ),
        Constraint(
            id="c_low",
            label="Low ceiling",
            kind="numeric",
            hardness="hard",
            description="The commitment level must be at most 1.",
            expr=Expr(op="lte", args=[Expr(op="var", ref="margin"), Expr(op="const", value=1)]),
        ),
    ]
    actions, bundles = _bundles(
        [("opt_a", "Option A", 0, 10), ("opt_b", "Option B", 1, 20), ("opt_c", "Option C", 3, 30)]
    )
    scenario = _scenario(index, domain, prompt, variables, constraints, actions, bundles, _facts("impossible", domain, index))
    return scenario, {
        "structure": "impossible",
        "domain": domain,
        "optimal": optimal_bundle(scenario),
        "minimal_cut": [],
        "material_edges": [],
    }


def _unknown(index: int, domain: str, prompt: str) -> tuple[Scenario, dict[str, Any]]:
    variables = [
        _margin(1.3),
        Variable(
            id="vendor_confirm",
            label="Vendor confirmation",
            role="exogenous",
            vtype="category",
            baseline=None,
            distribution="unknown",
            epistemic_status=EpistemicStatus.UNKNOWN,
        ),
    ]
    constraints = [
        Constraint(
            id="c_vendor",
            label="Vendor confirmation",
            kind="equality",
            hardness="hard",
            description="The vendor confirmation is unresolved, so the commitment cannot be treated as closed.",
            expr=Expr(op="eq", args=[Expr(op="var", ref="vendor_confirm"), Expr(op="const", value="yes")]),
        )
    ]
    actions, bundles = _bundles(
        [("opt_a", "Option A", 1.3, 12), ("opt_b", "Option B", 1.3, 30)],
        effects={"opt_a": {"margin": 1.3}, "opt_b": {"margin": 1.3}},
    )
    facts = _facts("unknown_material", domain, index)
    facts.append(
        _fact(
            "f_unknown",
            "vendor",
            "confirmation",
            None,
            "Vendor confirmation has not arrived.",
            EpistemicStatus.UNKNOWN,
        )
    )
    scenario = _scenario(index, domain, prompt, variables, constraints, actions, bundles, facts)
    return scenario, {
        "structure": "unknown_material",
        "domain": domain,
        "optimal": optimal_bundle(scenario),
        "minimal_cut": [],
        "material_edges": ["vendor_confirm"],
        "unknown": "vendor_confirm",
    }


def _assert_structure(scenario: Scenario, oracle: dict[str, Any]) -> None:
    views = {bundle.id: assess(scenario, bundle.action_ids) for bundle in scenario.bundles}
    safe = [bundle_id for bundle_id, view in views.items() if view["safe"]]
    naive = select_naive(scenario)
    structure = oracle["structure"]
    if structure == "impossible":
        if oracle["optimal"] is not None or safe or naive is not None:
            raise AssertionError("impossible world has a feasible bundle")
        return
    if structure == "unknown_material":
        if oracle["optimal"] is not None or any(view["unresolved"] == 0 for view in views.values()):
            raise AssertionError("unknown world resolved a material unknown")
        return
    if oracle["optimal"] not in safe:
        raise AssertionError(f"{structure} optimal is not safe")
    if structure in {"robust_nominal", "cheapest_best"}:
        if naive != oracle["optimal"]:
            raise AssertionError(f"{structure} naive plan should be optimal")
        if any(not view["safe"] for view in views.values() if structure == "robust_nominal"):
            raise AssertionError("robust nominal world contains an unsafe bundle")
    if structure in {"single_variable", "two_variable", "three_variable", "irrelevant_axes", "cheapest_not_best", "hidden_downstream", "stale_fact", "distractors", "no_change"}:
        if naive is None or views[naive]["safe"] or naive == oracle["optimal"]:
            raise AssertionError(f"{structure} should have an unsafe cheaper nominal plan")
    if structure == "multiple_valid":
        if len(safe) < 2 or naive == oracle["optimal"] or naive is None or views[naive]["safe"]:
            raise AssertionError("multiple valid repairs were not both safe and cheaper-than-naive")
    if structure == "repair_tradeoff":
        if "opt_align" not in safe or "opt_patch" in safe or naive == "opt_align":
            raise AssertionError("tradeoff repair was not rejected")
    if structure == "stale_fact" and len(_conflict_ids(scenario.facts)) < 2:
        raise AssertionError("stale world has no conflicting facts")
    if structure == "distractors" and len(scenario.facts) < 5:
        raise AssertionError("distractor world is missing irrelevant facts")
    if structure == "no_change" and oracle["optimal"] != "opt_keep":
        raise AssertionError("no-change world did not keep the current commitment")
    if structure == "hidden_downstream" and "fare" not in scenario.plan_prompt and "price" not in scenario.plan_prompt and "sticker" not in scenario.plan_prompt and "slot" not in scenario.plan_prompt:
        raise AssertionError("hidden world prompt mentions the downstream failure")


def _bundles(
    options: list[tuple[str, str, float, float]],
    effects: dict[str, dict[str, float]] | None = None,
) -> tuple[list[ActionDef], list[Bundle]]:
    actions = []
    bundles = []
    for bundle_id, label, margin, cost in options:
        action_id = f"set_{bundle_id}"
        payload = {"margin": margin} if effects is None else effects[bundle_id]
        actions.append(
            ActionDef(
                id=action_id,
                action_type="plan.commit",
                label=label,
                resource="plan",
                cost=cost,
                effects=payload,
            )
        )
        bundles.append(Bundle(id=bundle_id, label=label, action_ids=[action_id]))
    return actions, bundles


def _scenario(
    index: int,
    domain: str,
    prompt: str,
    variables: list[Variable],
    constraints: list[Constraint],
    actions: list[ActionDef],
    bundles: list[Bundle],
    facts: list[WorldFact],
) -> Scenario:
    return Scenario(
        id=f"live-{index:02d}",
        title=f"{domain} pilot {index:02d}",
        domain=domain,
        plan_prompt=prompt,
        variables=variables,
        constraints=constraints,
        actions=actions,
        bundles=bundles,
        facts=facts,
    )


def _slack_constraints() -> list[Constraint]:
    return [
        Constraint(
            id="c_slack",
            label="Commitment slack",
            kind="numeric",
            hardness="hard",
            description="The commitment stays non-negative when the declared exogenous inputs move inside their ranges.",
            expr=Expr(op="gte", args=[Expr(op="var", ref="slack"), Expr(op="const", value=0)]),
        )
    ]


def _slack(penalty: Expr) -> Variable:
    return Variable(
        id="slack",
        label="Slack",
        role="derived",
        vtype="number",
        epistemic_status=EpistemicStatus.COMPUTED,
        formula=Expr(op="sub", args=[Expr(op="var", ref="margin"), penalty]),
    )


def _margin(baseline: float) -> Variable:
    return Variable(
        id="margin",
        label="Commitment level",
        role="controllable",
        vtype="number",
        baseline=baseline,
        epistemic_status=EpistemicStatus.VERIFIED,
        show_in_diff=True,
    )


def _level(var_id: str) -> Variable:
    return Variable(
        id=var_id,
        label=var_id,
        role="controllable",
        vtype="number",
        baseline=0,
        epistemic_status=EpistemicStatus.VERIFIED,
        show_in_diff=True,
    )


def _shock(var_id: str) -> Variable:
    return Variable(
        id=var_id,
        label=var_id,
        role="exogenous",
        vtype="number",
        baseline=0,
        lower=0,
        upper=1,
        scale=1,
        distribution="uniform",
        epistemic_status=EpistemicStatus.ESTIMATED,
    )


def _facts(structure: str, domain: str, index: int) -> list[WorldFact]:
    rows = [
        _fact(
            "f_price",
            "offer",
            "note",
            domain,
            f"The {domain} options differ in sticker price.",
            EpistemicStatus.VERIFIED,
        )
    ]
    if structure == "stale_fact":
        rows.append(_fact("f_stale", "commitment", "status", "safe", "The cheaper option still clears the commitment.", EpistemicStatus.ESTIMATED))
        rows.append(
            _fact(
                "f_current",
                "commitment",
                "status",
                "exposed",
                "A movement inside the declared range can miss the commitment.",
                EpistemicStatus.VERIFIED,
            )
        )
    if structure == "distractors":
        for item, text in enumerate(
            (
                "The office snack order is unrelated.",
                "A newsletter draft is waiting and does not affect this commitment.",
                "Parking on a different day is not part of this plan.",
                "A closed museum exhibit is irrelevant to the commitment.",
            )
        ):
            rows.append(_fact(f"f_noise_{item}", f"noise_{item}", "note", text, text, EpistemicStatus.VERIFIED))
    if structure == "unknown_material":
        return rows
    rows.append(
        _fact(
            "f_range",
            "range",
            "declared",
            index,
            "Exogenous inputs are declared as ranges. No probability is given.",
            EpistemicStatus.ESTIMATED,
        )
    )
    return rows


def _fact(fact_id: str, subject: str, predicate: str, value: Any, text: str, status: EpistemicStatus) -> WorldFact:
    return WorldFact(
        id=fact_id,
        subject=subject,
        predicate=predicate,
        value=value,
        observed_at="2026-10-07T12:00:00Z",
        source_type="pilot",
        source_id=fact_id,
        epistemic_status=status,
        tags=["support"],
        text=text,
    )


def _conflict_ids(facts: list[WorldFact]) -> list[str]:
    grouped: dict[str, list[WorldFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.subject, []).append(fact)
    ids: list[str] = []
    for group in grouped.values():
        if len({repr(fact.value) for fact in group}) > 1:
            ids.extend(fact.id for fact in group)
    return ids


def _probes(dimensions: int) -> np.ndarray:
    sampler = qmc.Sobol(d=dimensions, scramble=True, seed=11)
    points = sampler.random(64)
    corners = []
    for mask in range(2**dimensions):
        corners.append([float((mask >> bit) & 1) for bit in range(dimensions)])
    return np.vstack([points, np.array(corners, dtype=float)])


def _scale(var: Variable, unit: float) -> float:
    lower = 0.0 if var.lower is None else float(var.lower)
    upper = 1.0 if var.upper is None else float(var.upper)
    return lower + unit * (upper - lower)
