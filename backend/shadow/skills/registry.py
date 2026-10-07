"""Deterministic skill lookup. No model call."""

from __future__ import annotations

from shadow.skills.base import Skill
from shadow.skills.catalog import COORDINATE_SCHEDULE, HANDLE_DISRUPTION, RESCHEDULE_TRIP, SKILLS


class SkillRegistry:
    def __init__(self) -> None:
        self._skills = {item.id: item for item in SKILLS}

    def register(self, skill: Skill) -> None:
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Skill:
        return self._skills[skill_id]

    def list_skills(self) -> list[Skill]:
        return [self._skills[item.id] for item in SKILLS if item.id in self._skills]

    def available_for(self, text: str = "", event_type: str = "") -> Skill:
        blob = f"{text} {event_type}".lower()
        if any(token in blob for token in ("delay", "fare", "cancel", "disruption", "hotel")):
            return HANDLE_DISRUPTION
        if any(token in blob for token in ("coordinate", "schedule", "apartment", "meeting")):
            return COORDINATE_SCHEDULE
        if any(token in blob for token in ("trip", "flight", "travel", "nyc")):
            return RESCHEDULE_TRIP
        return COORDINATE_SCHEDULE
