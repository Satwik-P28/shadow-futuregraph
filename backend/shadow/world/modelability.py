"""Decide whether a freeform plan has enough grounded structure to simulate.

The compiler may propose structure. This module does not invent a world and does not
choose the travel or apartment demo unless the caller passed that context explicitly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from shadow.skills.registry import SkillRegistry
from shadow.world.compiler import compile_bundle, load_bundle
from shadow.world.example_world import license_example_bundle

_LIFE = ("marry", "married", "soulmate", "meaning of life", "be happy", "fall in love")
_TRIP = ("trip", "flight", "flights", "travel", "nyc")
_SCHEDULE = ("appointment", "dentist", "class", "meeting", "schedule", "calendar", "coordinate")
_DISRUPTION = ("delay", "delayed", "fare", "canceled", "cancelled", "disruption")
_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "tomorrow")


class ModelabilityResult(BaseModel):
    status: Literal["SUPPORTED", "NEEDS_INFORMATION", "UNSUPPORTED"]
    reason: str
    missing_information: list[str] = Field(default_factory=list)
    compiled_constraints: list[str] = Field(default_factory=list)
    compiled_dependencies: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
    selected_skill: str | None = None
    provenance: str


def assess_freeform(text: str, demo_context_id: str | None = None) -> ModelabilityResult:
    cleaned = " ".join(text.split())
    lowered = cleaned.lower()
    registry = SkillRegistry()
    if demo_context_id in {"travel", "apartment"}:
        skill = registry.available_for(cleaned)
        compiled = _compiled_labels(demo_context_id, cleaned)
        return ModelabilityResult(
            status="SUPPORTED",
            reason="An example context supplies the grounded records for this plan.",
            compiled_constraints=compiled[0],
            compiled_dependencies=compiled[1],
            available_actions=skill.available_actions,
            selected_skill=skill.name,
            provenance="world compiler plus explicit example context",
        )
    if any(token in lowered for token in _LIFE) or _skill_name(lowered) is None:
        return ModelabilityResult(
            status="UNSUPPORTED",
            reason="I don't have enough grounded information or executable structure to model this as a future.",
            provenance="world compiler",
        )
    skill = registry.get(_skill_name(lowered) or "coordinate_schedule")
    compiled = _compiled_labels(None, cleaned)
    missing = _missing(lowered, skill.id)
    return ModelabilityResult(
        status="NEEDS_INFORMATION",
        reason="I can model this plan, but I need more grounded information first.",
        missing_information=missing,
        compiled_constraints=compiled[0],
        compiled_dependencies=compiled[1],
        available_actions=skill.available_actions,
        selected_skill=skill.name,
        provenance="world compiler",
    )


def _skill_name(lowered: str) -> str | None:
    if any(token in lowered for token in _DISRUPTION):
        return "handle_trip_disruption"
    if any(token in lowered for token in _TRIP):
        return "reschedule_trip"
    if any(token in lowered for token in _SCHEDULE):
        return "coordinate_schedule"
    return None


def _missing(lowered: str, skill_id: str) -> list[str]:
    missing: list[str] = []
    if skill_id == "reschedule_trip":
        if not any(day in lowered for day in _DAYS):
            missing.append("which day you want to travel")
        if not any(token in lowered for token in ("$", "budget", "at most", "cap")):
            missing.append("your maximum extra budget")
        if not any(token in lowered for token in ("cannot move", "can move", "fixed", "dinner")):
            missing.append("whether dinner or other fixed commitments can move")
        missing.append("the reservation and calendar records this change would affect")
    elif skill_id == "coordinate_schedule":
        if not any(day in lowered for day in _DAYS):
            missing.append("which day the event should move to")
        if not any(token in lowered for token in ("class", "fixed", "cannot", "interfere")):
            missing.append("which commitments must stay where they are")
        missing.append("the times of the commitments that must not be disturbed")
        missing.append("the calendar record for the event you want to move")
    else:
        missing.append("which approved trip this change refers to")
        missing.append("the new fact that changed, with its source")
    return missing


def _compiled_labels(demo_context_id: str | None, text: str) -> tuple[list[str], list[str]]:
    bundle = load_bundle(demo_context_id) if demo_context_id else None
    if demo_context_id == "travel" and bundle is not None:
        compiled = license_example_bundle(bundle)
    else:
        if bundle is None:
            bundle = {"plan_text": text, "records": [{"id": "user_plan", "kind": "note", "text": text}]}
        compiled = compile_bundle(bundle)
    constraints = [item.label for item in compiled.hard_constraints]
    dependencies = [item.label for item in compiled.dependencies]
    return constraints, dependencies
