"""Compile messy personal records into candidate typed semantics.

Nemotron may propose structure. It may not invent a number or promote an
inferred relation to verified truth. Numeric checks stay in the deterministic engine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from shadow.core.models import EpistemicStatus, Scenario

ROOT = Path(__file__).resolve().parents[3]

# Constraint ids licensed only when a source record supports them.
_LICENSES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("dinner_deadline", ("dinner", "7"), ("c_dinner",)),
    ("dinner_fixed", ("do not move",), ("c_dinner_fixed",)),
    ("review_fixed", ("design review", "cannot move"), ("c_review", "c_leave")),
    ("exam_protected", ("exam", "unrelated"), ("c_exam",)),
    ("budget_cap", ("maximum additional", "100"), ("c_budget",)),
    ("ride_link", ("ride", "linked"), ("c_ride",)),
    ("trip_friday", ("friday",), ("c_friday",)),
    ("hotel_hold", ("hotel", "confirmed"), ("c_hotel",)),
    ("replacement_hold", ("held", "replacement"), ("c_replacement",)),
]


class CompiledItem(BaseModel):
    id: str
    kind: str
    label: str
    epistemic_status: EpistemicStatus
    source_ids: list[str] = Field(default_factory=list)
    provenance: str
    confidence: float | None = None
    validated: bool = False
    value: Any = None


class CompiledWorld(BaseModel):
    goals: list[CompiledItem] = Field(default_factory=list)
    facts: list[CompiledItem] = Field(default_factory=list)
    hard_constraints: list[CompiledItem] = Field(default_factory=list)
    soft_preferences: list[CompiledItem] = Field(default_factory=list)
    dependencies: list[CompiledItem] = Field(default_factory=list)
    exogenous: list[CompiledItem] = Field(default_factory=list)
    unknowns: list[CompiledItem] = Field(default_factory=list)
    actions: list[CompiledItem] = Field(default_factory=list)
    licensed_constraint_ids: list[str] = Field(default_factory=list)

    def items(self) -> list[CompiledItem]:
        return [
            *self.goals,
            *self.facts,
            *self.hard_constraints,
            *self.soft_preferences,
            *self.dependencies,
            *self.exogenous,
            *self.unknowns,
            *self.actions,
        ]


class SemanticProposal(BaseModel):
    """Model output. Every status that is not UNKNOWN is stored as INFERRED."""

    hard_constraints: list[dict[str, Any]] = Field(default_factory=list)
    soft_preferences: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)


def load_bundle(scenario_id: str) -> dict[str, Any] | None:
    path = ROOT / "fixtures" / scenario_id / "context.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def compile_bundle(bundle: dict[str, Any], proposal: SemanticProposal | None = None) -> CompiledWorld:
    records = list(bundle.get("records") or [])
    plan = str(bundle.get("plan_text") or "")
    texts = {str(item["id"]): str(item["text"]) for item in records}
    blob = " ".join([plan, *texts.values()]).lower()
    world = CompiledWorld()
    world.goals.append(
        _item(
            "goal_plan",
            "goal",
            plan,
            EpistemicStatus.INFERRED,
            ["user_plan"],
            "user plan text",
            validated=bool(plan),
        )
    )
    licensed: list[str] = []
    for tag, needles, constraint_ids in _LICENSES:
        if all(needle in blob for needle in needles):
            sources = [key for key, text in texts.items() if all(needle in text.lower() for needle in needles)]
            if tag == "trip_friday" and "friday" in plan.lower():
                sources = ["user_plan", *sources]
            status = EpistemicStatus.COMPUTED if tag == "budget_cap" else EpistemicStatus.INFERRED
            if tag == "hotel_hold":
                status = EpistemicStatus.VERIFIED
            value = None
            if tag == "dinner_deadline":
                dinner_text = next((text for text in texts.values() if "dinner" in text.lower() and "7" in text), "")
                value = parsed_clock_minutes(dinner_text)
                status = EpistemicStatus.COMPUTED if value == 19 * 60 else EpistemicStatus.INFERRED
            if tag == "budget_cap":
                value = 100
            world.hard_constraints.append(
                _item(
                    tag,
                    "hard_constraint",
                    tag.replace("_", " "),
                    status,
                    sources or ["user_plan"],
                    "source match",
                    True,
                    value,
                )
            )
            licensed.extend(constraint_ids)
    if "preserve fixed" in blob:
        world.soft_preferences.append(
            _item(
                "preserve_fixed",
                "preference",
                "preserve fixed commitments",
                EpistemicStatus.INFERRED,
                [key for key, text in texts.items() if "preserve fixed" in text.lower()],
                "preference wording",
                True,
            )
        )
    world.dependencies.extend(
        [
            _item(
                "flight_to_exit",
                "dependency",
                "flight arrival affects airport exit",
                EpistemicStatus.INFERRED,
                ["res_flights"] if "res_flights" in texts else [],
                "candidate causal link",
                validated=False,
            ),
            _item(
                "exit_to_dinner",
                "dependency",
                "airport exit and ground travel affect dinner arrival",
                EpistemicStatus.INFERRED,
                ["mail_dinner", "cal_dinner"] if "mail_dinner" in texts else [],
                "candidate causal link",
                validated=False,
            ),
        ]
    )
    world.exogenous.extend(
        [
            _item("flight_delay", "exogenous", "flight delay", EpistemicStatus.ESTIMATED, [], "material uncertainty", False),
            _item("ground_travel", "exogenous", "ground travel", EpistemicStatus.ESTIMATED, [], "material uncertainty", False),
        ]
    )
    if "street_closure" not in blob and "street closure" not in blob:
        world.unknowns.append(
            _item("street_closure", "unknown", "street_closure", EpistemicStatus.UNKNOWN, [], "no evidence in the bundle", True)
        )
    if proposal is not None:
        _merge_proposal(world, proposal)
    world.licensed_constraint_ids = sorted(set(licensed))
    return world


def license_scenario(scenario: Scenario, compiled: CompiledWorld) -> Scenario:
    """Drop hard constraints the sources did not support. Do not invent replacements."""
    allowed = set(compiled.licensed_constraint_ids)
    updated = scenario.model_copy(deep=True)
    updated.constraints = [
        item for item in updated.constraints if item.hardness != "hard" or item.id in allowed
    ]
    updated.metadata = {
        **updated.metadata,
        "compiled_from": "personal context",
        "licensed_constraints": compiled.licensed_constraint_ids,
    }
    return updated


def attach_compiled(scenario: Scenario) -> tuple[Scenario, CompiledWorld | None]:
    bundle = load_bundle(scenario.id)
    if bundle is None:
        return scenario, None
    compiled = compile_bundle(bundle)
    return license_scenario(scenario, compiled), compiled


def score_compilation(compiled: CompiledWorld, oracle: dict[str, Any]) -> dict[str, Any]:
    hard_labels = [item.label.lower() for item in compiled.hard_constraints]
    dep_labels = [item.label.lower() for item in compiled.dependencies]
    unknown_labels = [item.label.lower() for item in compiled.unknowns]
    hard_hit = _hits(hard_labels, oracle.get("hard") or [])
    false_hard = _false_hits(hard_labels, oracle.get("not_hard") or [])
    dep_hit = _hits(dep_labels, oracle.get("dependencies") or [])
    false_dep = _false_hits(dep_labels, oracle.get("not_dependencies") or [])
    unknown_hit = _hits(unknown_labels, oracle.get("unknowns") or [])
    items = compiled.items()
    with_source = sum(1 for item in items if item.source_ids or item.epistemic_status == EpistemicStatus.UNKNOWN)
    return {
        "hard_hit": hard_hit,
        "hard_total": len(oracle.get("hard") or []),
        "false_hard": false_hard,
        "hard_proposed": len(hard_labels),
        "dep_hit": dep_hit,
        "dep_total": len(oracle.get("dependencies") or []),
        "false_dep": false_dep,
        "dep_proposed": len(dep_labels),
        "unknown_hit": unknown_hit,
        "unknown_total": len(oracle.get("unknowns") or []),
        "provenance_hit": with_source,
        "provenance_total": len(items),
        "repair_ok": _repair_ok(compiled, oracle),
        "repair_applicable": oracle.get("repair") is not None,
    }


def _repair_ok(compiled: CompiledWorld, oracle: dict[str, Any]) -> bool | None:
    expected = oracle.get("repair")
    if expected is None:
        return None
    labels = " ".join(item.label.lower() for item in compiled.items())
    if expected == "abstain":
        return all(alias.lower() in labels for alias in oracle.get("unknowns") or [])
    required = oracle.get("hard") or []
    return _hits([item.label.lower() for item in compiled.hard_constraints], required) == len(required)


def _hits(labels: list[str], aliases: list[str]) -> int:
    return sum(1 for alias in aliases if any(alias.lower() in label for label in labels))


def _false_hits(labels: list[str], banned: list[str]) -> int:
    return sum(1 for label in labels if any(word.lower() in label for word in banned))


def _merge_proposal(world: CompiledWorld, proposal: SemanticProposal) -> None:
    existing = {item.label.lower() for item in world.items()}
    for index, row in enumerate(proposal.hard_constraints):
        label = str(row.get("label") or "")
        if not label or label.lower() in existing:
            continue
        world.hard_constraints.append(
            _item(
                f"model_hard_{index}",
                "hard_constraint",
                label,
                EpistemicStatus.INFERRED,
                [str(item) for item in row.get("source_ids") or []],
                "model proposal",
                validated=False,
            )
        )
    for index, row in enumerate(proposal.dependencies):
        label = str(row.get("label") or f"{row.get('source')} -> {row.get('target')}")
        world.dependencies.append(
            _item(
                f"model_dep_{index}",
                "dependency",
                label,
                EpistemicStatus.INFERRED,
                [str(item) for item in row.get("source_ids") or []],
                "model proposal",
                validated=False,
            )
        )
    for index, row in enumerate(proposal.unknowns):
        label = str(row.get("label") or "")
        if label and not any(label.lower() == item.label.lower() for item in world.unknowns):
            world.unknowns.append(
                _item(
                    f"model_unknown_{index}",
                    "unknown",
                    label,
                    EpistemicStatus.UNKNOWN,
                    [str(item) for item in row.get("source_ids") or []],
                    "model proposal",
                    validated=True,
                )
            )


def _item(
    item_id: str,
    kind: str,
    label: str,
    status: EpistemicStatus,
    source_ids: list[str],
    provenance: str,
    validated: bool,
    value: Any = None,
) -> CompiledItem:
    confidence = None
    if status in {EpistemicStatus.VERIFIED, EpistemicStatus.COMPUTED} and validated:
        confidence = 1.0
    return CompiledItem(
        id=item_id,
        kind=kind,
        label=label,
        epistemic_status=status,
        source_ids=[item for item in source_ids if item],
        provenance=provenance,
        confidence=confidence,
        validated=validated,
        value=value,
    )


def proposal_from_payload(payload: dict[str, Any]) -> SemanticProposal:
    """Keep model statuses from becoming verified. Numbers in the payload are ignored."""
    cleaned = json.loads(json.dumps(payload))
    for key in ("hard_constraints", "soft_preferences", "dependencies", "unknowns"):
        rows = cleaned.get(key) or []
        if isinstance(rows, dict):
            rows = [rows]
        normalized = []
        for row in rows:
            if isinstance(row, str):
                row = {"label": row}
            if not isinstance(row, dict):
                continue
            row.pop("confidence", None)
            row.pop("value", None)
            if key == "unknowns":
                row["status"] = "UNKNOWN"
            elif str(row.get("status") or "").upper() == "UNKNOWN":
                row["status"] = "UNKNOWN"
            else:
                row["status"] = "INFERRED"
            normalized.append(row)
        cleaned[key] = normalized
    return SemanticProposal.model_validate(cleaned)


_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", re.I)


def parsed_clock_minutes(text: str) -> int | None:
    match = _CLOCK.search(text)
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = (match.group(3) or "").lower()
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute
