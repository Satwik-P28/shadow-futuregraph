"""Compile messy personal records into candidate typed semantics.

Nemotron may propose structure. It may not invent a number or promote an
inferred relation to verified truth. Numeric checks stay in the deterministic engine.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from shadow.core.models import EpistemicStatus, Scenario
from shadow.paths import repo_root

ROOT = repo_root()

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
        _accept_model_proposal(bundle, world, proposal)
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


def attach_compiled(scenario: Scenario, proposal: SemanticProposal | None = None) -> tuple[Scenario, CompiledWorld | None]:
    bundle = load_bundle(scenario.id)
    if bundle is None:
        return scenario, None
    compiled = compile_bundle(bundle, proposal)
    return license_scenario(scenario, compiled), compiled


_HARD_MARKERS = ("cannot", "must", "maximum", "do not", "don't", "fixed", "at most", "no more than", "confirmed", "before")
_SOFT_MARKERS = ("prefer", "maybe", "might", "optional", "can move", "perhaps", "ideally", "like")
_UNKNOWN_CUES = ("unknown", "whether", "nobody has", "not said", "have not said", "unsure", "not confirmed", "maybe")
_NUMBER = re.compile(r"\d+")


def verify_proposal(bundle: dict[str, Any], proposal: SemanticProposal) -> CompiledWorld:
    """Drop model claims the cited records do not support. Never promotes a status."""
    records = {str(item["id"]): str(item["text"]) for item in bundle.get("records") or []}
    world = CompiledWorld()
    for index, row in enumerate(proposal.hard_constraints):
        label = str(row.get("label") or "")
        sources = _known_sources(row, records)
        if not label or not sources:
            continue
        if _numbers_unsupported(label, sources, records):
            continue
        cited = " ".join(records[item].lower() for item in sources)
        if any(marker in cited for marker in _HARD_MARKERS):
            world.hard_constraints.append(
                _item(f"vhard_{index}", "hard_constraint", label, EpistemicStatus.INFERRED, sources, "verifier", True)
            )
        elif any(marker in cited for marker in _SOFT_MARKERS):
            world.soft_preferences.append(
                _item(f"vsoft_{index}", "preference", label, EpistemicStatus.INFERRED, sources, "verifier", True)
            )
    for index, row in enumerate(proposal.dependencies):
        label = str(row.get("label") or "")
        sources = _known_sources(row, records)
        if label and sources and not _numbers_unsupported(label, sources, records):
            world.dependencies.append(
                _item(f"vdep_{index}", "dependency", label, EpistemicStatus.INFERRED, sources, "verifier", True)
            )
    for index, row in enumerate(proposal.unknowns):
        label = str(row.get("label") or "")
        sources = _known_sources(row, records)
        if label:
            world.unknowns.append(
                _item(f"vunk_{index}", "unknown", label, EpistemicStatus.UNKNOWN, sources, "verifier", True)
            )
    for source_id, text in records.items():
        lowered = text.lower()
        if any(cue in lowered for cue in _UNKNOWN_CUES):
            if not any(source_id in item.source_ids for item in world.unknowns):
                world.unknowns.append(
                    _item(f"vgap_{source_id}", "unknown", text, EpistemicStatus.UNKNOWN, [source_id], "verifier", True)
                )
            world.hard_constraints = [
                item
                for item in world.hard_constraints
                if source_id not in item.source_ids or any(marker in lowered for marker in _HARD_MARKERS)
            ]
    return world


def world_from_proposal(proposal: SemanticProposal) -> CompiledWorld:
    world = CompiledWorld()
    _merge_proposal(world, proposal)
    return world


def _known_sources(row: dict[str, Any], records: dict[str, str]) -> list[str]:
    return [str(item) for item in row.get("source_ids") or [] if str(item) in records]


def _numbers_unsupported(label: str, sources: list[str], records: dict[str, str]) -> bool:
    cited = " ".join(records[item] for item in sources)
    return any(number not in cited for number in _NUMBER.findall(label))


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


def frozen_route() -> str:
    path = ROOT / "shadowbench" / "routing" / "decision.json"
    if not path.exists():
        return "lightning"
    system = str(json.loads(path.read_text()).get("system") or "lightning")
    if system not in {"lightning", "super", "compiler_verifier"}:
        return "lightning"
    return system


def route_model() -> str:
    """Compile calls use the frozen route. Other purposes stay on Lightning."""
    if frozen_route() == "super":
        return "nvidia/nemotron-3-super-120b-a12b"
    return "nvidia/Nemotron-3_5-Lightning"


def _accept_model_proposal(bundle: dict[str, Any], world: CompiledWorld, proposal: SemanticProposal) -> None:
    if frozen_route() != "compiler_verifier":
        _merge_proposal(world, proposal)
        return
    verified = verify_proposal(bundle, proposal)
    existing = {item.label.lower() for item in world.items()}
    for bucket in (verified.hard_constraints, verified.soft_preferences, verified.dependencies, verified.unknowns):
        for item in bucket:
            if item.label.lower() in existing:
                continue
            existing.add(item.label.lower())
            getattr(world, _bucket_name(item.kind)).append(item)


def _bucket_name(kind: str) -> str:
    return {
        "hard_constraint": "hard_constraints",
        "preference": "soft_preferences",
        "dependency": "dependencies",
        "unknown": "unknowns",
    }.get(kind, "facts")


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


class AuditFinding(BaseModel):
    finding_type: str
    target_label: str = ""
    source_ids: list[str] = Field(default_factory=list)
    evidence: str = ""


class AuditReport(BaseModel):
    findings: list[AuditFinding] = Field(default_factory=list)


def merge_audit(world: CompiledWorld, report: AuditReport, records: dict[str, str]) -> CompiledWorld:
    """Apply an audit only when the cited record actually contains the evidence."""
    updated = world.model_copy(deep=True)
    for finding in report.findings:
        kind = finding.finding_type
        sources = [item for item in finding.source_ids if item in records]
        evidence = finding.evidence.strip()
        supported = bool(sources and evidence) and all(evidence.lower() in records[item].lower() for item in sources)
        label = finding.target_label.strip() or evidence
        if kind == "MISSED_CONSTRAINT" and supported and _supported_hard(evidence):
            _add_item(updated.hard_constraints, label, "hard_constraint", sources, EpistemicStatus.INFERRED)
        elif kind == "MISSED_DEPENDENCY" and supported:
            _add_item(updated.dependencies, label, "dependency", sources, EpistemicStatus.INFERRED)
        elif kind == "UNSUPPORTED_CONSTRAINT":
            updated.hard_constraints = [item for item in updated.hard_constraints if not _critic_can_remove(item, finding, records)]
        elif kind == "UNSUPPORTED_DEPENDENCY":
            updated.dependencies = [item for item in updated.dependencies if not _critic_can_remove(item, finding, records)]
        elif kind == "CONTRADICTION" and supported:
            _add_item(updated.unknowns, f"contradiction: {label}", "unknown", sources, EpistemicStatus.UNKNOWN)
        elif kind == "SHOULD_BE_UNKNOWN" and supported:
            _downgrade_unknown(updated, label, sources)
        elif kind == "PROVENANCE_MISSING":
            _downgrade_missing_provenance(updated, label)
    return updated


def _supported_hard(evidence: str) -> bool:
    lowered = evidence.lower()
    return any(marker in lowered for marker in _HARD_MARKERS)


def _critic_can_remove(item: CompiledItem, finding: AuditFinding, records: dict[str, str]) -> bool:
    if finding.target_label.lower() not in item.label.lower():
        return False
    if not item.source_ids:
        return True
    cited = " ".join(records.get(source, "") for source in item.source_ids).lower()
    return not any(marker in cited for marker in _HARD_MARKERS)


def _add_item(bucket: list[CompiledItem], label: str, kind: str, sources: list[str], status: EpistemicStatus) -> None:
    if not label or any(label.lower() == item.label.lower() for item in bucket):
        return
    bucket.append(_item(f"audit_{kind}_{len(bucket)}", kind, label, status, sources, "audit merge", status == EpistemicStatus.UNKNOWN))


def _downgrade_unknown(world: CompiledWorld, label: str, sources: list[str]) -> None:
    kept = []
    for item in world.hard_constraints:
        if label.lower() in item.label.lower():
            _add_item(world.unknowns, item.label, "unknown", sources or item.source_ids, EpistemicStatus.UNKNOWN)
        else:
            kept.append(item)
    world.hard_constraints = kept


def _downgrade_missing_provenance(world: CompiledWorld, label: str) -> None:
    kept = []
    for item in world.hard_constraints:
        if label.lower() in item.label.lower() and not item.source_ids:
            _add_item(world.unknowns, item.label, "unknown", [], EpistemicStatus.UNKNOWN)
        else:
            kept.append(item)
    world.hard_constraints = kept


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
