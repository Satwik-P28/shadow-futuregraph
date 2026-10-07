"""Typed executable worlds from grounded records.

Nemotron may propose this schema. It may not propose code. Numbers must appear
in a cited record, as a clock or as a literal. Missing durations stay missing.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

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
from shadow.simulation.engine import FormulaCycle, derived_variables

ALLOWED_OPS = {"var", "const", "add", "sub"}
ALLOWED_RELATIONS = {"<=", ">=", "<", ">", "==", "!="}
ALLOWED_ACTION_TYPES = {"plan.keep", "plan.drop_purchase", "plan.select_option"}
_RELATION_OP = {"<=": "lte", ">=": "gte", "<": "lt", ">": "gt", "==": "eq", "!=": "neq"}
_CLOCK = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])m\b", re.IGNORECASE)
_DURATION = re.compile(
    r"(\d+)\s*(?:to|–|-|—)\s*(\d+)\s+minutes\b|\b(\d+)\s+minutes\b",
    re.IGNORECASE,
)


class FormulaIR(BaseModel):
    op: Literal["var", "const", "add", "sub"]
    ref: str | None = None
    value: float | None = None
    args: list[FormulaIR] = Field(default_factory=list)
    unit: Literal["minutes", "usd", "count"] | None = None


class VariableIR(BaseModel):
    id: str
    label: str
    unit: Literal["minutes", "usd", "count"]
    role: Literal["fixed", "exogenous", "derived", "controllable"]
    value: float | None = None
    lower: float | None = None
    upper: float | None = None
    formula: FormulaIR | None = None
    source_ids: list[str] = Field(default_factory=list)
    epistemic_status: EpistemicStatus = EpistemicStatus.INFERRED


class ConstraintIR(BaseModel):
    id: str
    label: str
    hardness: Literal["hard", "soft"]
    left: FormulaIR
    operator: Literal["<=", ">=", "<", ">", "==", "!="]
    right: FormulaIR
    source_ids: list[str] = Field(default_factory=list)
    epistemic_status: EpistemicStatus = EpistemicStatus.INFERRED


class ActionIR(BaseModel):
    id: str
    action_type: Literal["plan.keep", "plan.drop_purchase", "plan.select_option"]
    label: str
    resource: str
    effects: dict[str, float] = Field(default_factory=dict)
    cost: float = 0
    reversible: bool = True
    source_ids: list[str] = Field(default_factory=list)


class ExecutableProposal(BaseModel):
    variables: list[VariableIR] = Field(default_factory=list)
    constraints: list[ConstraintIR] = Field(default_factory=list)
    actions: list[ActionIR] = Field(default_factory=list)


class Compilation(BaseModel):
    status: Literal["READY", "NEEDS_INFORMATION", "UNSUPPORTED", "CONTRADICTORY"]
    reason: str
    missing: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    scenario: Scenario | None = None
    constraint_labels: list[str] = Field(default_factory=list)
    dependency_labels: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)


def compile_primitives(plan: str, records: list[dict[str, Any]] | None = None) -> Compilation:
    """Compile the supported sentence forms. Does not read fixture worlds."""
    rows = list(records or [])
    if not rows and plan.strip():
        rows = [{"id": "user_plan", "text": plan, "observed_at": ""}]
    claims, links, costs, cap, rejected = _read_records(rows)
    if rejected:
        return Compilation(status="CONTRADICTORY", reason=rejected[0], contradictions=rejected)
    if cap is not None or costs:
        return _compile_budget(plan, costs, cap, rows)
    if links or claims:
        return _compile_temporal(plan, claims, links, rows)
    return Compilation(
        status="UNSUPPORTED",
        reason="No grounded time, duration, or budget sentence was found.",
    )


def validate_proposal(proposal: ExecutableProposal, records: list[dict[str, Any]]) -> Compilation:
    """Accept a model proposal only when every number and identifier is grounded."""
    sources = {str(row.get("id")): _prepare(str(row.get("text") or "")) for row in records}
    problems: list[str] = []
    known = {item.id for item in proposal.variables}
    for item in proposal.variables:
        problems.extend(_ground_variable(item, sources, known))
    for item in proposal.constraints:
        problems.extend(_ground_formula(item.left, sources, item.source_ids, known))
        problems.extend(_ground_formula(item.right, sources, item.source_ids, known))
        if item.operator not in ALLOWED_RELATIONS:
            problems.append(f"unsupported operator {item.operator}")
    for item in proposal.actions:
        if item.action_type not in ALLOWED_ACTION_TYPES:
            problems.append(f"unsupported action {item.action_type}")
        if any(key not in known for key in item.effects):
            problems.append(f"action {item.id} names an unknown variable")
        if any(source not in sources for source in item.source_ids):
            problems.append(f"action {item.id} cites an unknown source")
        cited = " ".join(sources[source] for source in item.source_ids if source in sources)
        if item.action_type == "plan.drop_purchase" and any(value != 0 for value in item.effects.values()):
            problems.append(f"action {item.id} may only set a purchase to zero")
        if item.action_type == "plan.select_option":
            for value in item.effects.values():
                if not _number_supported(cited, value):
                    problems.append(f"action {item.id} uses a number that is not in its cited records")
    if problems:
        return Compilation(status="UNSUPPORTED", reason=problems[0], rejected=problems)
    try:
        scenario = _scenario_from_ir(proposal, records, plan="")
        derived_variables(scenario)
    except (FormulaCycle, ValueError, ValidationError) as exc:
        return Compilation(status="UNSUPPORTED", reason=str(exc), rejected=[str(exc)])
    return Compilation(
        status="READY",
        reason="The proposal is grounded and executable.",
        scenario=scenario,
        constraint_labels=[item.label for item in proposal.constraints],
        dependency_labels=[item.id for item in proposal.variables if item.role == "derived"],
    )


def _compile_budget(
    plan: str,
    costs: list[dict[str, Any]],
    cap: dict[str, Any] | None,
    rows: list[dict[str, Any]],
) -> Compilation:
    if cap is None:
        return Compilation(
            status="NEEDS_INFORMATION",
            reason="Purchase amounts are present, but no budget limit is stated.",
            missing=["available budget"],
        )
    if not costs:
        return Compilation(
            status="NEEDS_INFORMATION",
            reason="A budget is stated, but no purchase amounts are stated.",
            missing=["purchase amounts"],
        )
    variables: list[VariableIR] = []
    actions: list[ActionIR] = [
        ActionIR(id="keep", action_type="plan.keep", label="Keep the stated purchases", resource="plan", source_ids=[])
    ]
    for item in costs:
        variables.append(
            VariableIR(
                id=item["id"],
                label=item["label"],
                unit="usd",
                role="fixed" if item["locked"] else "controllable",
                value=item["amount"],
                source_ids=[item["source"]],
                epistemic_status=EpistemicStatus.COMPUTED,
            )
        )
        if not item["locked"]:
            actions.append(
                ActionIR(
                    id=f"drop_{item['id']}",
                    action_type="plan.drop_purchase",
                    label=f"Drop {item['label']}",
                    resource=item["id"],
                    effects={item["id"]: 0},
                    source_ids=[item["source"]],
                )
            )
    total = FormulaIR(op="add", unit="usd", args=[FormulaIR(op="var", ref=item["id"], unit="usd") for item in costs])
    variables.append(
        VariableIR(
            id="total_cost",
            label="Combined stated cost",
            unit="usd",
            role="derived",
            formula=total,
            source_ids=[item["source"] for item in costs],
            epistemic_status=EpistemicStatus.COMPUTED,
        )
    )
    variables.append(
        VariableIR(
            id="budget_cap",
            label="Available budget",
            unit="usd",
            role="fixed",
            value=cap["amount"],
            source_ids=[cap["source"]],
            epistemic_status=EpistemicStatus.COMPUTED,
        )
    )
    constraint = ConstraintIR(
        id="c_budget",
        label="Combined cost stays within the stated budget",
        hardness="hard",
        left=FormulaIR(op="var", ref="total_cost", unit="usd"),
        operator="<=",
        right=FormulaIR(op="var", ref="budget_cap", unit="usd"),
        source_ids=[cap["source"], *[item["source"] for item in costs]],
        epistemic_status=EpistemicStatus.COMPUTED,
    )
    proposal = ExecutableProposal(variables=variables, constraints=[constraint], actions=actions)
    scenario = _scenario_from_ir(proposal, rows, plan)
    return Compilation(
        status="READY",
        reason="Purchase amounts and a budget limit are both stated.",
        scenario=scenario,
        constraint_labels=[constraint.label],
        dependency_labels=["total_cost"],
    )


def _compile_temporal(
    plan: str,
    claims: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> Compilation:
    missing: list[str] = []
    variables: list[VariableIR] = []
    constraints: list[ConstraintIR] = []
    actions: list[ActionIR] = [
        ActionIR(id="keep", action_type="plan.keep", label="Keep the stated times", resource="plan", source_ids=[])
    ]
    built: set[str] = set()
    graph: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        graph.setdefault(link["origin"], []).append(link)
    for origin, claim in claims.items():
        clock = claim.get("end", claim.get("arrives"))
        if clock is None:
            continue
        for path in _paths(origin, graph, claims, depth=3):
            dest = path[-1]["dest"]
            deadline = claims.get(dest, {}).get("start")
            if deadline is None:
                missing.append(f"start time of {dest}")
                continue
            arrival_id = _chain(path, claims, clock, variables, built)
            constraint_id = f"c_arrive_{_slug(dest)}"
            if constraint_id in {item.id for item in constraints}:
                continue
            constraints.append(
                ConstraintIR(
                    id=constraint_id,
                    label=f"Arrival at {dest} is at or before its start",
                    hardness="hard" if claims[dest].get("hard", True) else "soft",
                    left=FormulaIR(op="var", ref=arrival_id, unit="minutes"),
                    operator="<=",
                    right=FormulaIR(op="var", ref=f"{_slug(dest)}_start", unit="minutes"),
                    source_ids=sorted({*(row["source"] for row in path), claims[dest]["source"], claim["source"]}),
                    epistemic_status=EpistemicStatus.COMPUTED,
                )
            )
            _ensure_fixed(variables, built, f"{_slug(dest)}_start", f"{dest} start", deadline, claims[dest]["source"])
    for name, claim in claims.items():
        alternate = claim.get("alternate")
        if alternate is None or claim.get("protected"):
            continue
        target = f"{_slug(name)}_start"
        if target not in built:
            _ensure_fixed(variables, built, target, f"{name} start", claim.get("start"), claim["source"])
        if target not in built:
            continue
        actions.append(
            ActionIR(
                id=f"move_{_slug(name)}",
                action_type="plan.select_option",
                label=f"Use the stated alternate time for {name}",
                resource=_slug(name),
                effects={target: alternate},
                source_ids=[claim["source"]],
            )
        )
    if constraints:
        proposal = ExecutableProposal(variables=variables, constraints=constraints, actions=actions)
        scenario = _scenario_from_ir(proposal, rows, plan)
        return Compilation(
            status="READY",
            reason="Timed endpoints and stated durations form an executable chain.",
            scenario=scenario,
            constraint_labels=[item.label for item in constraints],
            dependency_labels=[item.id for item in variables if item.role == "derived"],
        )
    if _asks_connection(plan, claims) or links or len(claims) >= 2:
        if not links:
            missing.append("a stated duration between the timed events")
        missing = list(dict.fromkeys(missing)) or ["a duration that connects the stated events"]
        return Compilation(
            status="NEEDS_INFORMATION",
            reason="Feasibility is not established. A required duration or endpoint is absent.",
            missing=missing,
        )
    return Compilation(
        status="UNSUPPORTED",
        reason="The records do not state a closed time or budget constraint.",
    )


def _chain(
    path: list[dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    origin_clock: float,
    variables: list[VariableIR],
    built: set[str],
) -> str:
    origin = path[0]["origin"]
    cursor = f"{_slug(origin)}_depart"
    _ensure_fixed(variables, built, cursor, f"{origin} departure", origin_clock, claims[origin]["source"])
    arrival = cursor
    for link in path:
        duration_id = f"{_slug(link['origin'])}_{_slug(link['dest'])}_duration"
        high = link["high"]
        if duration_id not in built:
            variables.append(
                VariableIR(
                    id=duration_id,
                    label=f"{link['origin']} to {link['dest']}",
                    unit="minutes",
                    role="exogenous" if high is not None else "fixed",
                    value=link["low"],
                    lower=link["low"],
                    upper=high if high is not None else link["low"],
                    source_ids=[link["source"]],
                    epistemic_status=EpistemicStatus.ESTIMATED if high is not None else EpistemicStatus.COMPUTED,
                )
            )
            built.add(duration_id)
        arrival = f"{_slug(link['dest'])}_arrival"
        if arrival not in built:
            variables.append(
                VariableIR(
                    id=arrival,
                    label=f"Arrival at {link['dest']}",
                    unit="minutes",
                    role="derived",
                    formula=FormulaIR(
                        op="add",
                        unit="minutes",
                        args=[
                            FormulaIR(op="var", ref=cursor, unit="minutes"),
                            FormulaIR(op="var", ref=duration_id, unit="minutes"),
                        ],
                    ),
                    source_ids=[link["source"]],
                    epistemic_status=EpistemicStatus.COMPUTED,
                )
            )
            built.add(arrival)
        cursor = arrival
    return arrival


def _ensure_fixed(
    variables: list[VariableIR],
    built: set[str],
    ident: str,
    label: str,
    value: float | None,
    source: str,
) -> None:
    if ident in built or value is None:
        return
    variables.append(
        VariableIR(
            id=ident,
            label=label,
            unit="minutes",
            role="fixed",
            value=value,
            source_ids=[source],
            epistemic_status=EpistemicStatus.COMPUTED,
        )
    )
    built.add(ident)


def _paths(
    origin: str,
    graph: dict[str, list[dict[str, Any]]],
    claims: dict[str, dict[str, Any]],
    depth: int,
) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []

    def walk(node: str, acc: list[dict[str, Any]]) -> None:
        if len(acc) >= depth:
            return
        for link in graph.get(node, []):
            step = [*acc, link]
            dest = link["dest"]
            if dest in claims and claims[dest].get("start") is not None:
                found.append(step)
            walk(dest, step)

    walk(origin, [])
    return found


def _scenario_from_ir(proposal: ExecutableProposal, records: list[dict[str, Any]], plan: str) -> Scenario:
    variables = [_variable(item) for item in proposal.variables]
    constraints = [_constraint(item) for item in proposal.constraints]
    actions = [_action(item) for item in proposal.actions] or [
        ActionDef(id="keep", action_type="plan.keep", label="Keep the stated plan", resource="plan")
    ]
    if not any(item.id == "keep" for item in actions):
        actions.insert(0, ActionDef(id="keep", action_type="plan.keep", label="Keep the stated plan", resource="plan"))
    bundles = [Bundle(id="keep", label="Keep the stated plan", action_ids=["keep"], rationale="No composed change.")]
    drops = [item.id for item in actions if item.action_type == "plan.drop_purchase"]
    moves = [item.id for item in actions if item.action_type == "plan.select_option"]
    for ident in drops + moves:
        action = next(item for item in actions if item.id == ident)
        bundles.append(Bundle(id=ident, label=action.label, action_ids=[ident], rationale="Single recorded option."))
    if len(drops) == 2:
        bundles.append(
            Bundle(
                id="drop_both",
                label="Drop both stated purchases",
                action_ids=drops,
                rationale="Bounded composition of two recorded drop actions.",
            )
        )
    facts = []
    for row in records:
        text = str(row.get("text") or "")
        if not text:
            continue
        facts.append(
            WorldFact(
                id=str(row.get("id") or f"fact_{len(facts)}"),
                subject="record",
                predicate="states",
                value=text[:240],
                observed_at=str(row.get("observed_at") or "1970-01-01T00:00:00Z"),
                source_type="record",
                source_id=str(row.get("id") or "record"),
                epistemic_status=EpistemicStatus.INFERRED,
                text=text,
                tags=["support"],
            )
        )
    return Scenario(
        id="compiled",
        title=plan[:80] or "Compiled plan",
        domain="compiled",
        plan_prompt=plan,
        variables=variables,
        constraints=constraints,
        actions=actions,
        bundles=bundles,
        facts=facts,
        metadata={"compiled_from": "executable primitive compiler", "route": "independent"},
    )


def _variable(item: VariableIR) -> Variable:
    high = item.upper if item.upper is not None else item.value
    low = item.lower if item.lower is not None else item.value
    scale = None
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        scale = float(high) - float(low) or 1.0
    distribution: Literal["point", "uniform", "unknown"] = "point"
    if item.role == "exogenous" and item.lower is not None and item.upper is not None and item.upper != item.lower:
        distribution = "uniform"
    status = item.epistemic_status
    if status == EpistemicStatus.VERIFIED:
        status = EpistemicStatus.INFERRED
    return Variable(
        id=item.id,
        label=item.label,
        role=item.role,
        vtype="number",
        baseline=item.value,
        lower=None if low is None else float(low),
        upper=None if high is None else float(high),
        scale=scale,
        unit=item.unit,
        epistemic_status=status,
        distribution=distribution,
        formula=None if item.formula is None else _expr(item.formula),
    )


def _constraint(item: ConstraintIR) -> Constraint:
    return Constraint(
        id=item.id,
        label=item.label,
        kind="numeric" if item.left.unit == "usd" or item.right.unit == "usd" else "temporal",
        hardness=item.hardness,
        expr=Expr(op=_RELATION_OP[item.operator], args=[_expr(item.left), _expr(item.right)]),
        description=item.label,
    )


def _action(item: ActionIR) -> ActionDef:
    return ActionDef(
        id=item.id,
        action_type=item.action_type,
        label=item.label,
        resource=item.resource,
        effects=dict(item.effects),
        cost=item.cost,
        reversible=item.reversible,
        compensatable=item.reversible,
        irreversible=not item.reversible,
    )


def _expr(formula: FormulaIR) -> Expr:
    if formula.op not in ALLOWED_OPS:
        raise ValueError(f"unsupported expression op: {formula.op}")
    return Expr(
        op=formula.op,
        ref=formula.ref,
        value=formula.value,
        args=[_expr(arg) for arg in formula.args],
    )


def _ground_variable(item: VariableIR, sources: dict[str, str], known: set[str]) -> list[str]:
    problems = []
    if any(source not in sources for source in item.source_ids):
        problems.append(f"{item.id} cites an unknown source")
    cited = " ".join(sources[source] for source in item.source_ids if source in sources)
    if item.value is not None and not _number_supported(cited, item.value):
        problems.append(f"{item.id} uses a number that is not in its cited records")
    if item.formula is not None:
        problems.extend(_ground_formula(item.formula, sources, item.source_ids, known))
    if item.role == "derived" and item.formula is None:
        problems.append(f"{item.id} is derived without a formula")
    return problems


def _ground_formula(formula: FormulaIR, sources: dict[str, str], source_ids: list[str], known: set[str]) -> list[str]:
    problems: list[str] = []
    if formula.op not in ALLOWED_OPS:
        return [f"unsupported expression op: {formula.op}"]
    if formula.op == "var" and formula.ref not in known:
        problems.append(f"undefined variable {formula.ref}")
    if formula.op == "const":
        cited = " ".join(sources[source] for source in source_ids if source in sources)
        if formula.value is None or not _number_supported(cited, formula.value):
            problems.append("a constant is not present in the cited records")
    units = [arg.unit for arg in formula.args if arg.unit]
    if formula.op in {"add", "sub"} and len(set(units)) > 1:
        problems.append("a formula mixes units")
    for arg in formula.args:
        problems.extend(_ground_formula(arg, sources, source_ids, known))
    return problems


def _number_supported(text: str, value: float) -> bool:
    if re.search(rf"(?<![\d.]){re.escape(_trim(value))}(?![\d.])", text):
        return True
    for match in _CLOCK.finditer(text):
        if _clock_minutes(match) == value:
            return True
    return False


def _read_records(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    claims: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    costs: list[dict[str, Any]] = []
    cap: dict[str, Any] | None = None
    seen: dict[tuple[str, str], tuple[str, float]] = {}
    conflicts: list[str] = []
    order = sorted(rows, key=lambda row: str(row.get("observed_at") or ""))
    superseded = {str(row.get("supersedes")) for row in order if row.get("supersedes")}
    for row in order:
        source = str(row.get("id") or "record")
        if source in superseded:
            continue
        for piece in _pieces(str(row.get("text") or "")):
            conflict = _absorb(piece, source, claims, links, costs, seen)
            if conflict:
                conflicts.append(conflict)
            found = _cap(piece, source)
            if found:
                cap = found
    return claims, links, costs, cap, conflicts


def _absorb(
    piece: str,
    source: str,
    claims: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    costs: list[dict[str, Any]],
    seen: dict[tuple[str, str], tuple[str, float]],
) -> str | None:
    protected = bool(re.search(r"cannot move|can't move|must not move|do not move", piece, re.IGNORECASE))
    locked = bool(re.search(r"cannot cancel|can't cancel|required", piece, re.IGNORECASE))
    soft = bool(re.search(r"prefer|ideally", piece, re.IGNORECASE))
    piece = re.sub(
        r"\s+and\s+(?:cannot move|can't move|must not move|do not move|cannot cancel|can't cancel|required)$",
        "",
        piece,
        flags=re.IGNORECASE,
    ).strip()
    alternate = re.search(
        r"^(?P<name>.+?) can start at (?P<clock>\d{1,2}(?::\d{2})?\s*[ap]m) instead$",
        piece,
        re.IGNORECASE,
    )
    if alternate:
        name = _norm(alternate.group("name"))
        value = _clock_minutes(_CLOCK.search(alternate.group("clock")))
        return _put(claims, seen, name, "alternate", value, source, protected, soft)
    travel = re.search(
        r"^(?:the )?(.+?) to (?:the )?(.+?) takes (\d+)(?:\s*(?:to|–|-|—)\s*(\d+))? minutes$",
        piece,
        re.IGNORECASE,
    )
    if travel:
        low = float(travel.group(3))
        high = float(travel.group(4)) if travel.group(4) else None
        links.append(
            {
                "origin": _norm(travel.group(1)),
                "dest": _norm(travel.group(2)),
                "low": low,
                "high": high,
                "source": source,
            }
        )
        return None
    timed = re.search(
        r"^(?:the )?(.+?) (starts|ends|arrives) at (\d{1,2}(?::\d{2})?\s*[ap]m)$",
        piece,
        re.IGNORECASE,
    )
    if timed:
        name = _norm(timed.group(1))
        kind = {"starts": "start", "ends": "end", "arrives": "arrives"}[timed.group(2).lower()]
        value = _clock_minutes(_CLOCK.search(timed.group(3)))
        return _put(claims, seen, name, kind, value, source, protected, soft)
    priced = re.search(r"^(?:the )?(.+?) costs \$(\d+(?:\.\d+)?)$", piece, re.IGNORECASE)
    if priced:
        costs.append(
            {
                "id": _slug(priced.group(1)),
                "label": _norm(priced.group(1)),
                "amount": float(priced.group(2)),
                "locked": locked,
                "source": source,
            }
        )
    return None


def _put(
    claims: dict[str, dict[str, Any]],
    seen: dict[tuple[str, str], tuple[str, float]],
    name: str,
    kind: str,
    value: float,
    source: str,
    protected: bool,
    soft: bool,
) -> str | None:
    key = (name, kind)
    previous = seen.get(key)
    if previous and previous[1] != value:
        return f"{name} has conflicting {kind} values ({_trim(previous[1])} and {_trim(value)})"
    seen[key] = (source, value)
    claim = claims.setdefault(name, {"source": source, "hard": True, "protected": False})
    claim[kind] = value
    claim["source"] = source
    claim["protected"] = claim["protected"] or protected
    claim["hard"] = False if soft else claim["hard"]
    return None


def _cap(piece: str, source: str) -> dict[str, Any] | None:
    match = re.search(
        r"(?:available budget is at most|budget is at most|no more than) \$(\d+(?:\.\d+)?)",
        piece,
        re.IGNORECASE,
    )
    if not match:
        return None
    return {"amount": float(match.group(1)), "source": source}


def _asks_connection(plan: str, claims: dict[str, dict[str, Any]]) -> bool:
    if len(claims) < 2:
        return False
    return bool(re.search(r"before|after|in time|make it|arrive|catch|reach|feasib", plan, re.IGNORECASE))


def _pieces(text: str) -> list[str]:
    prepared = _prepare(text)
    return [part.strip(" .") for part in re.split(r"[\n;]+|\.\s+", prepared) if part.strip(" .")]


def _prepare(text: str) -> str:
    return re.sub(r"\b([ap])\.m\.", r"\1m", text, flags=re.IGNORECASE)


def _norm(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.lower()).strip(" .")
    return re.sub(r"^(the|a|an)\s+", "", cleaned)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _norm(text)).strip("_")
    return slug[:48] or "item"


def _clock_minutes(match: re.Match[str] | None) -> float:
    if match is None:
        raise ValueError("clock time is missing")
    hour = int(match.group(1)) % 12
    minute = int(match.group(2) or 0)
    if match.group(3).lower().startswith("p"):
        hour += 12
    return float(hour * 60 + minute)


def _trim(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


FormulaIR.model_rebuild()
