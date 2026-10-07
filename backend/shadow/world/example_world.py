"""Example-only license table for the synthetic travel fixture.

This is not the generic compiler. It exists so the sandbox demo can keep the
pre-authored travel constraints when the fixture text supports them. A phrase
match here does not mean Shadow understood an arbitrary plan.
"""

from __future__ import annotations

from typing import Any

from shadow.core.models import EpistemicStatus
from shadow.world.compiler import CompiledWorld, _item, parsed_clock_minutes

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


def license_example_bundle(bundle: dict[str, Any]) -> CompiledWorld:
    records = list(bundle.get("records") or [])
    plan = str(bundle.get("plan_text") or "")
    texts = {str(item["id"]): str(item["text"]) for item in records}
    blob = " ".join([plan, *texts.values()]).lower()
    world = CompiledWorld()
    world.goals.append(
        _item("goal_plan", "goal", plan or "example plan", EpistemicStatus.INFERRED, ["user_plan"], "example fixture", bool(plan))
    )
    licensed: list[str] = []
    for tag, needles, constraint_ids in _LICENSES:
        if not all(needle in blob for needle in needles):
            continue
        sources = [key for key, text in texts.items() if all(needle in text.lower() for needle in needles)]
        if tag == "trip_friday" and "friday" in plan.lower():
            sources = ["user_plan", *sources]
        status = EpistemicStatus.INFERRED
        value = None
        if tag == "dinner_deadline":
            dinner_text = next((text for text in texts.values() if "dinner" in text.lower() and "7" in text), "")
            value = parsed_clock_minutes(dinner_text)
            status = EpistemicStatus.COMPUTED if value == 19 * 60 else EpistemicStatus.INFERRED
        if tag == "budget_cap":
            value = 100
            status = EpistemicStatus.COMPUTED
        if tag == "hotel_hold":
            status = EpistemicStatus.VERIFIED
        world.hard_constraints.append(
            _item(tag, "hard_constraint", tag.replace("_", " "), status, sources or ["user_plan"], "example fixture match", True, value)
        )
        licensed.extend(constraint_ids)
    if "street_closure" not in blob and "street closure" not in blob:
        world.unknowns.append(
            _item("street_closure", "unknown", "street_closure", EpistemicStatus.UNKNOWN, [], "no evidence in the example bundle", True)
        )
    world.licensed_constraint_ids = sorted(set(licensed))
    return world
