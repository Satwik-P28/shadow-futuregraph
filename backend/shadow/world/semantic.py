"""Ground a model-proposed semantic world. The model does not evaluate it.

Quotes must appear in a cited record. Numbers are parsed from those quotes.
A missing duration stays missing. A conflict is not given a winner.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

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

Status = Literal[
    "EXECUTABLE",
    "PARTIALLY_EXECUTABLE",
    "NEEDS_INFORMATION",
    "CONTRADICTORY",
    "UNSUPPORTED",
    "INVALID_MODEL_OUTPUT",
]


class SemanticFact(BaseModel):
    id: str = ""
    kind: str = "event"
    name: str = ""
    quote: str = ""
    value: str | None = None
    unit: str = "unspecified"
    hardness: str = "unknown"
    source_id: str = "user"
    optional: bool = False


class SemanticLink(BaseModel):
    id: str = ""
    relation: str = ""
    inputs: list[str] = Field(default_factory=list)
    deadline: str | None = None
    hardness: str = "hard"
    quote: str = ""
    source_id: str = "user"


class SemanticWorld(BaseModel):
    facts: list[SemanticFact] = Field(default_factory=list)
    links: list[SemanticLink] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class Grounding(BaseModel):
    status: Status
    reason: str
    missing: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    scenario: Scenario | None = None
    shown: list[dict[str, str]] = Field(default_factory=list)


def coerce_semantic(payload: dict[str, Any]) -> dict[str, Any]:
    """Map the shapes the exploratory pass actually returned. Do not invent values."""
    facts_in = payload.get("facts") or payload.get("variables") or payload.get("entities") or []
    links_in = payload.get("links") or payload.get("constraints") or payload.get("dependencies") or []
    facts = []
    for index, item in enumerate(facts_in if isinstance(facts_in, list) else []):
        if isinstance(item, str):
            item = {"name": item, "quote": item}
        if not isinstance(item, dict):
            continue
        value = item.get("value", item.get("value_text", item.get("time")))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        quote = str(item.get("quote") or item.get("evidence") or item.get("text") or "")
        facts.append(
            {
                "id": str(item.get("id") or item.get("name") or f"f{index}"),
                "kind": str(item.get("kind") or item.get("type") or "event"),
                "name": str(item.get("name") or item.get("label") or item.get("id") or f"f{index}"),
                "quote": quote,
                "value": None if value is None else str(value),
                "unit": str(item.get("unit") or "unspecified"),
                "hardness": str(item.get("hardness") or "unknown"),
                "source_id": str(item.get("source_id") or item.get("source") or "user"),
                "optional": bool(item.get("optional", False)),
            }
        )
    links = []
    for index, item in enumerate(links_in if isinstance(links_in, list) else []):
        if not isinstance(item, dict):
            continue
        inputs = item.get("inputs") or item.get("args") or item.get("variables") or []
        if isinstance(inputs, str):
            inputs = [inputs]
        links.append(
            {
                "id": str(item.get("id") or f"l{index}"),
                "relation": str(item.get("relation") or item.get("op") or item.get("operator") or ""),
                "inputs": [str(part) for part in inputs],
                "deadline": None if item.get("deadline") is None else str(item.get("deadline")),
                "hardness": str(item.get("hardness") or "hard"),
                "quote": str(item.get("quote") or ""),
                "source_id": str(item.get("source_id") or item.get("source") or "user"),
            }
        )
    unknowns = payload.get("unknowns") or []
    contradictions = payload.get("contradictions") or []
    return {
        "facts": facts,
        "links": links,
        "unknowns": [_unknown_text(item) for item in unknowns] if isinstance(unknowns, list) else [],
        "contradictions": [str(item) for item in contradictions] if isinstance(contradictions, list) else [],
    }


def ground_semantic(world: SemanticWorld, records: list[dict[str, Any]], plan: str = "") -> Grounding:
    sources = {str(row.get("id") or "user"): str(row.get("text") or "") for row in records}
    blob = "\n".join(sources.values())
    rejected: list[str] = []
    parsed: dict[str, dict[str, Any]] = {}
    shown: list[dict[str, str]] = []
    for fact in world.facts:
        source = sources.get(fact.source_id) or blob
        quote = fact.quote.strip() or (fact.value or "")
        if not quote or not _contains(source, quote):
            rejected.append(f"{fact.name or fact.id} is not in a cited record")
            continue
        if fact.value and not _contains(source, fact.value) and not _contains(quote, fact.value):
            rejected.append(f"{fact.name or fact.id} uses a value that is not in its quote")
            continue
        reading = _read(fact.value or quote)
        if reading is None:
            parsed[fact.id] = {"unknown": True, "name": fact.name}
            shown.append({"source": quote, "extracted": f"{fact.name}: unparsed", "role": "unknown"})
            continue
        reading["name"] = fact.name or fact.id
        reading["quote"] = quote
        reading["optional"] = fact.optional or "considering" in quote.lower()
        reading["locked"] = bool(re.search(r"committed|cannot be moved|cannot move", quote, re.IGNORECASE))
        parsed[fact.id] = reading
        parsed[_key(fact.name)] = reading
        shown.append({"source": quote, "extracted": _show(reading), "role": reading["kind"]})
    if rejected and not parsed:
        return Grounding(status="INVALID_MODEL_OUTPUT", reason=rejected[0], rejected=rejected, shown=shown)
    conflicts = list(world.contradictions)
    conflicts.extend(_same_name_conflicts(world.facts, parsed))
    if conflicts:
        return Grounding(
            status="CONTRADICTORY",
            reason=conflicts[0],
            contradictions=conflicts,
            rejected=rejected,
            shown=shown,
        )
    variables: list[Variable] = []
    constraints: list[Constraint] = []
    actions: list[ActionDef] = [ActionDef(id="keep", action_type="plan.keep", label="Keep the stated plan", resource="plan")]
    missing = [item for item in world.unknowns if item]
    built: set[str] = set()
    for link in world.links:
        if link.relation in {"contradicts", "contradiction"}:
            conflicts.append(link.quote or link.id or "The records conflict.")
            continue
        if link.quote and not _contains(blob, link.quote):
            rejected.append(f"link {link.id} quote is not verbatim; the link is kept because its facts are")
        error = _apply_link(link, parsed, variables, constraints, actions, built, missing)
        if error:
            missing.append(error)
    if conflicts:
        return Grounding(status="CONTRADICTORY", reason=conflicts[0], contradictions=conflicts, rejected=rejected, shown=shown)
    if constraints and missing:
        status: Status = "PARTIALLY_EXECUTABLE"
        reason = "Some grounded constraints can be evaluated. Material facts are still missing."
    elif constraints:
        status = "EXECUTABLE"
        reason = "The grounded links are executable."
    elif missing or any(item.get("unknown") for item in parsed.values()):
        status = "NEEDS_INFORMATION"
        reason = "A material fact is missing or unparsed."
        if not missing:
            missing = [item["name"] for item in parsed.values() if item.get("unknown") and item.get("name")]
    else:
        status = "UNSUPPORTED"
        reason = "The proposal did not yield a grounded constraint."
    scenario = None
    if constraints:
        scenario = _scenario(plan, variables, constraints, actions, records, status)
    return Grounding(
        status=status,
        reason=reason,
        missing=list(dict.fromkeys(missing)),
        rejected=rejected,
        scenario=scenario,
        shown=shown,
    )


def _apply_link(
    link: SemanticLink,
    parsed: dict[str, dict[str, Any]],
    variables: list[Variable],
    constraints: list[Constraint],
    actions: list[ActionDef],
    built: set[str],
    missing: list[str],
) -> str | None:
    relation = link.relation.lower().replace(" ", "_")
    if relation in {"<=", "before", "sum_before", "at_or_before"}:
        return _sum_before(link, parsed, variables, constraints, built, missing)
    if relation in {"sum_at_most", "<=_budget", "at_most"}:
        return _budget(link, parsed, variables, constraints, actions, built, missing)
    if relation in {"overlaps", "overlap", "during"}:
        return _overlap(link, parsed, variables, constraints, built, missing)
    return f"unsupported relation {link.relation}"


def _sum_before(
    link: SemanticLink,
    parsed: dict[str, dict[str, Any]],
    variables: list[Variable],
    constraints: list[Constraint],
    built: set[str],
    missing: list[str],
) -> str | None:
    parts = [_lookup(parsed, item) for item in link.inputs]
    deadline = _lookup(parsed, link.deadline or "")
    if any(part is None or part.get("unknown") for part in parts) or deadline is None or deadline.get("unknown"):
        return "a sum is missing an endpoint or a duration"
    if deadline.get("point") is None:
        return "the deadline has no time"
    expr: Expr | None = None
    for part in parts:
        assert part is not None
        ident = _ensure_number(part, variables, built)
        if ident is None:
            return f"{part.get('name')} has no usable number"
        piece = Expr(op="var", ref=ident)
        expr = piece if expr is None else Expr(op="add", args=[expr, piece])
    deadline_id = _ensure_number(deadline, variables, built)
    if expr is None or deadline_id is None:
        return "the sum could not be built"
    constraints.append(
        Constraint(
            id=f"c_{_key(link.id or 'arrive')}",
            label=link.quote or "Stated arrival is at or before the stated deadline",
            kind="temporal",
            hardness="soft" if deadline.get("soft") or deadline.get("unknown") else "hard",
            expr=Expr(op="lte", args=[expr, Expr(op="var", ref=deadline_id)]),
            description=link.quote or "arrival before deadline",
        )
    )
    return None


def _budget(
    link: SemanticLink,
    parsed: dict[str, dict[str, Any]],
    variables: list[Variable],
    constraints: list[Constraint],
    actions: list[ActionDef],
    built: set[str],
    missing: list[str],
) -> str | None:
    del missing
    spends = [_lookup(parsed, item) for item in link.inputs]
    cap = _lookup(parsed, link.deadline or "")
    if any(item is None or item.get("point") is None for item in spends) or cap is None or cap.get("point") is None:
        return "a budget term is missing"
    expr: Expr | None = None
    for item in spends:
        assert item is not None
        ident = _ensure_number(item, variables, built)
        assert ident is not None
        piece = Expr(op="var", ref=ident)
        expr = piece if expr is None else Expr(op="add", args=[expr, piece])
        if item.get("optional"):
            actions.append(
                ActionDef(
                    id=f"drop_{ident}",
                    action_type="plan.drop_purchase",
                    label=f"Drop {item.get('name')}",
                    resource=ident,
                    effects={ident: 0},
                )
            )
    cap_id = _ensure_number(cap, variables, built)
    if expr is None or cap_id is None:
        return "the budget sum could not be built"
    constraints.append(
        Constraint(
            id="c_budget",
            label="Stated spending stays within the stated limit",
            kind="numeric",
            hardness="hard",
            expr=Expr(op="lte", args=[expr, Expr(op="var", ref=cap_id)]),
            description="budget",
        )
    )
    return None


def _overlap(
    link: SemanticLink,
    parsed: dict[str, dict[str, Any]],
    variables: list[Variable],
    constraints: list[Constraint],
    built: set[str],
    missing: list[str],
) -> str | None:
    del missing
    items = [_lookup(parsed, item) for item in link.inputs]
    if any(item is None for item in items):
        return "an overlap endpoint is missing"
    window = next((item for item in items if item and item.get("end") is not None), None)
    point = next((item for item in items if item and item.get("point") is not None and item is not window), None)
    if window is None or point is None or point.get("point") is None:
        return "overlap needs an interval and a time"
    start_id = _ensure_bound(window, "start", variables, built)
    end_id = _ensure_bound(window, "end", variables, built)
    point_id = _ensure_number(point, variables, built)
    if not start_id or not end_id or not point_id:
        return "overlap could not be built"
    inside = Expr(
        op="and",
        args=[
            Expr(op="gte", args=[Expr(op="var", ref=point_id), Expr(op="var", ref=start_id)]),
            Expr(op="lt", args=[Expr(op="var", ref=point_id), Expr(op="var", ref=end_id)]),
        ],
    )
    constraints.append(
        Constraint(
            id=f"c_{_key(link.id or 'overlap')}",
            label=link.quote or "The stated use falls outside the occupied interval",
            kind="temporal",
            hardness="hard",
            expr=Expr(op="not", args=[inside]),
            description="exclusivity",
        )
    )
    return None


def _ensure_number(reading: dict[str, Any], variables: list[Variable], built: set[str]) -> str | None:
    if reading.get("low") is not None and reading.get("high") is not None and reading["high"] != reading["low"]:
        return _add_var(reading, variables, built, "span")
    if reading.get("point") is None:
        return None
    return _add_var(reading, variables, built, "point")


def _ensure_bound(reading: dict[str, Any], bound: str, variables: list[Variable], built: set[str]) -> str | None:
    if reading.get(bound) is None:
        return None
    clone = dict(reading)
    clone["point"] = reading[bound]
    clone["low"] = reading[bound]
    clone["high"] = reading[bound]
    clone["name"] = f"{reading.get('name')} {bound}"
    return _add_var(clone, variables, built, "point")


def _add_var(reading: dict[str, Any], variables: list[Variable], built: set[str], mode: str) -> str:
    ident = _key(str(reading.get("name") or "value"))
    if mode == "span":
        ident = f"{ident}_span"
    if ident in built:
        return ident
    low = float(reading["low"] if reading.get("low") is not None else reading["point"])
    high = float(reading["high"] if reading.get("high") is not None else reading["point"])
    span = high != low
    variables.append(
        Variable(
            id=ident,
            label=str(reading.get("name") or ident),
            role="exogenous" if span else "controllable" if reading.get("optional") else "fixed",
            vtype="number",
            baseline=low,
            lower=low,
            upper=high,
            scale=high - low or 1.0,
            unit="usd" if reading.get("kind") == "money" else "minutes",
            epistemic_status=EpistemicStatus.ESTIMATED if reading.get("assumed_meridiem") else EpistemicStatus.COMPUTED,
            distribution="uniform" if span else "point",
        )
    )
    built.add(ident)
    return ident


def _scenario(
    plan: str,
    variables: list[Variable],
    constraints: list[Constraint],
    actions: list[ActionDef],
    records: list[dict[str, Any]],
    status: str,
) -> Scenario:
    bundles = [Bundle(id="keep", label="Keep the stated plan", action_ids=["keep"], rationale="No extra action was grounded.")]
    for action in actions:
        if action.id != "keep":
            bundles.append(Bundle(id=action.id, label=action.label, action_ids=[action.id], rationale="The cited spend was optional."))
    facts = [
        WorldFact(
            id=str(row.get("id") or f"r{index}"),
            subject="record",
            predicate="states",
            value=str(row.get("text") or "")[:240],
            observed_at=str(row.get("observed_at") or "1970-01-01T00:00:00Z"),
            source_type="record",
            source_id=str(row.get("id") or "user"),
            epistemic_status=EpistemicStatus.INFERRED,
            text=str(row.get("text") or ""),
            tags=["support"],
        )
        for index, row in enumerate(records)
        if row.get("text")
    ]
    return Scenario(
        id="semantic",
        title=plan[:80] or "Semantic plan",
        domain="semantic",
        plan_prompt=plan,
        variables=variables,
        constraints=constraints,
        actions=actions,
        bundles=bundles,
        facts=facts,
        metadata={"compiled_from": "semantic compiler", "route": "nemotron", "executable_status": status},
    )


def _unknown_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("description") or item.get("id") or "unknown")
    return str(item)


def _read(text: str) -> dict[str, Any] | None:
    raw = " ".join(text.lower().split())
    money = re.search(r"\$(\d+(?:\.\d+)?)", text)
    if money:
        amount = float(money.group(1))
        return {"kind": "money", "point": amount, "low": amount, "high": amount}
    if re.search(r"half an hour|half hour", raw):
        return {"kind": "duration", "point": 30.0, "low": 30.0, "high": 30.0}
    quarter = re.search(r"quarter past ([a-z0-9]+)", raw)
    if quarter:
        hour = _hour_word(quarter.group(1))
        if hour is not None:
            found = _clock(f"{hour}:15")
            if found:
                return {"kind": "time", "point": found[0], "low": found[0], "high": found[0], "assumed_meridiem": found[1]}
    spoken = re.search(r"([a-z]+)\s+minutes?\s+to\s+([a-z]+)", raw)
    if spoken:
        low, high = _hour_word(spoken.group(1)), _hour_word(spoken.group(2))
        if low is not None and high is not None:
            return {"kind": "duration", "point": float(low), "low": float(low), "high": float(high)}
    duration = re.search(r"(\d+)\s*(?:to|–|-|—)\s*(\d+)\s*minutes", raw)
    if duration:
        low, high = float(duration.group(1)), float(duration.group(2))
        return {"kind": "duration", "point": low, "low": low, "high": high}
    single = re.search(r"(\d+)\s*minutes", raw)
    if single and "at " not in raw:
        value = float(single.group(1))
        return {"kind": "duration", "point": value, "low": value, "high": value}
    interval = re.search(r"from\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:until|to)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", raw)
    if interval:
        start = _clock(interval.group(1))
        end = _clock(interval.group(2))
        if start is None or end is None:
            return None
        return {"kind": "interval", "start": start[0], "end": end[0], "assumed_meridiem": start[1] or end[1]}
    named = re.search(
        r"\b(?:at|by|until)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
        raw,
    )
    if named:
        hour = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }[named.group(1)]
        found = _clock(str(hour))
        if found is not None:
            return {"kind": "time", "point": found[0], "low": found[0], "high": found[0], "assumed_meridiem": found[1]}
    found = _clock(raw)
    if found is not None:
        return {"kind": "time", "point": found[0], "low": found[0], "high": found[0], "assumed_meridiem": found[1]}
    if re.search(r"\baround\b|\babout\b|\bhasn't confirmed\b|not sure|unconfirmed|never written|no idea|have not|hasn't said|not told|don't know|do not know", raw):
        return {"kind": "unknown", "unknown": True, "soft": True}
    return None


def _hour_word(text: str) -> int | None:
    words = {
        "five": 5,
        "ten": 10,
        "fifteen": 15,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "forty-five": 45,
        "four": 4,
        "three": 3,
        "two": 2,
        "one": 1,
        "six": 6,
        "seven": 7,
    }
    return words.get(text.lower().strip())


def _clock(text: str) -> tuple[float, bool] | None:
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)?", text, re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if minute > 59 or hour > 12 and not match.group(3):
        return None
    marker = (match.group(3) or "").lower()
    assumed = False
    if marker.startswith("p"):
        hour = hour % 12 + 12
    elif marker.startswith("a"):
        hour = hour % 12
    elif hour < 8:
        hour += 12
        assumed = True
    elif hour == 12:
        hour = 12
    return float(hour * 60 + minute), assumed


def _lookup(parsed: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    if not name:
        return None
    if name in parsed:
        return parsed[name]
    return parsed.get(_key(name))


def _same_name_conflicts(facts: list[SemanticFact], parsed: dict[str, dict[str, Any]]) -> list[str]:
    seen: dict[str, float] = {}
    conflicts = []
    for fact in facts:
        reading = parsed.get(fact.id)
        if not reading or reading.get("point") is None or reading.get("kind") == "duration":
            continue
        key = _key(fact.name)
        point = float(reading["point"])
        if key in seen and seen[key] != point:
            conflicts.append(f"{fact.name} has conflicting times")
        seen[key] = point
    return conflicts


def _contains(haystack: str, needle: str) -> bool:
    folded = " ".join(haystack.lower().split())
    return " ".join(needle.lower().split()) in folded


def _show(reading: dict[str, Any]) -> str:
    name = reading.get("name") or "value"
    if reading.get("unknown"):
        return f"{name} is unknown"
    if reading.get("end") is not None:
        return f"{name} from {reading['start']} to {reading['end']} minutes"
    if reading.get("high") not in {None, reading.get("low")}:
        return f"{name} in [{reading['low']}, {reading['high']}]"
    return f"{name} = {reading.get('point')}"


def _key(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48] or "item"
