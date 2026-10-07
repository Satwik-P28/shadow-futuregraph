"""Deterministic conflicts across saved futures. No model call."""

from __future__ import annotations

from typing import Any


def cross_plan_conflicts(futures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, left in enumerate(futures):
        for right in futures[index + 1 :]:
            if left.get("future_id") == right.get("future_id"):
                continue
            for conflict in _pair(left, right):
                key = (conflict["conflict_type"], conflict["resource_id"], tuple(sorted(conflict["future_ids"])).__str__())
                if key in seen:
                    continue
                seen.add(key)
                found.append(conflict)
    return found


def _pair(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    found.extend(_value_conflicts(left, right))
    found.extend(_time_conflicts(left, right))
    found.extend(_budget_conflicts(left, right))
    found.extend(_protected_conflicts(left, right))
    found.extend(_asset_conflicts(left, right))
    return found


def _value_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    shared = set(left.get("effects") or {}) & set(right.get("effects") or {})
    for resource in sorted(shared):
        if left["effects"][resource] == right["effects"][resource]:
            continue
        found.append(
            _conflict(
                "VALUE_CONFLICT",
                left,
                right,
                resource,
                "variable",
                "The two futures set this resource to different values.",
                "effects disagree",
                [resource],
                "effect comparison",
            )
        )
    return found


def _time_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for claim in left.get("claims") or []:
        if claim.get("resource_type") != "person" or claim.get("start") is None or claim.get("end") is None:
            continue
        for other in right.get("claims") or []:
            if other.get("resource_id") != claim.get("resource_id") or other.get("resource_type") != "person":
                continue
            if other.get("start") is None or other.get("end") is None:
                continue
            if not _overlaps(claim, other):
                continue
            if claim.get("protected") or other.get("protected"):
                continue
            found.append(
                _conflict(
                    "TIME_OVERLAP",
                    left,
                    right,
                    str(claim["resource_id"]),
                    "person",
                    "These futures are individually valid but incompatible together.",
                    f"{claim.get('label')} overlaps {other.get('label')}",
                    [str(claim.get("label")), str(other.get("label"))],
                    "interval overlap",
                )
            )
    return found


def _budget_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for claim in left.get("claims") or []:
        if claim.get("resource_type") != "budget":
            continue
        for other in right.get("claims") or []:
            if other.get("resource_type") != "budget" or other.get("resource_id") != claim.get("resource_id"):
                continue
            cap = claim.get("cap") if claim.get("cap") is not None else other.get("cap")
            if cap is None or claim.get("cost") is None or other.get("cost") is None:
                continue
            if float(claim["cost"]) <= float(cap) and float(other["cost"]) <= float(cap) and float(claim["cost"]) + float(other["cost"]) > float(cap):
                found.append(
                    _conflict(
                        "BUDGET_CONFLICT",
                        left,
                        right,
                        str(claim["resource_id"]),
                        "budget",
                        "Each future fits the shared budget. Together they do not.",
                        f"shared cap {cap}",
                        [str(claim["resource_id"])],
                        "shared budget cap",
                    )
                )
    return found


def _protected_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for owner, other in ((left, right), (right, left)):
        for claim in owner.get("claims") or []:
            if not claim.get("protected"):
                continue
            resource = str(claim.get("resource_id"))
            if resource in (other.get("effects") or {}) and other["effects"][resource] != claim.get("state", False):
                found.append(
                    _conflict(
                        "PROTECTED_RESOURCE",
                        owner,
                        other,
                        resource,
                        "commitment",
                        "One future changes a resource the other keeps fixed.",
                        str(claim.get("label") or resource),
                        [resource],
                        "protected claim",
                    )
                )
            for window in other.get("claims") or []:
                if window.get("resource_type") == "person" and claim.get("resource_type") == "person" and window.get("resource_id") == claim.get("resource_id") and _overlaps(claim, window):
                    found.append(
                        _conflict(
                            "PROTECTED_RESOURCE",
                            owner,
                            other,
                            str(claim["resource_id"]),
                            "person",
                            "These futures are individually valid but incompatible together.",
                            f"{claim.get('label')} is protected and overlaps {window.get('label')}",
                            [str(claim.get("label")), str(window.get("label"))],
                            "protected interval",
                        )
                    )
    return found


def _asset_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for claim in left.get("claims") or []:
        if claim.get("resource_type") not in {"reservation", "asset"} or claim.get("state") is None:
            continue
        for other in right.get("claims") or []:
            if other.get("resource_id") != claim.get("resource_id") or other.get("resource_type") != claim.get("resource_type"):
                continue
            if other.get("state") is None or other.get("state") == claim.get("state"):
                continue
            found.append(
                _conflict(
                    "ASSET_STATE_CONFLICT",
                    left,
                    right,
                    str(claim["resource_id"]),
                    str(claim["resource_type"]),
                    "The same reservation cannot be in both states.",
                    f"{claim.get('state')} vs {other.get('state')}",
                    [str(claim.get("state")), str(other.get("state"))],
                    "reservation state",
                )
            )
    return found


def _overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("start") is None or left.get("end") is None or right.get("start") is None or right.get("end") is None:
        return False
    return float(left["start"]) < float(right["end"]) and float(right["start"]) < float(left["end"])


def _conflict(
    kind: str,
    left: dict[str, Any],
    right: dict[str, Any],
    resource: str,
    resource_type: str,
    description: str,
    constraint: str,
    path: list[str],
    provenance: str,
) -> dict[str, Any]:
    ids = [str(left.get("future_id")), str(right.get("future_id"))]
    return {
        "conflict_id": f"{kind}:{resource}:{ids[0]}:{ids[1]}",
        "future_ids": ids,
        "future_names": [str(left.get("name") or ids[0]), str(right.get("name") or ids[1])],
        "conflict_type": kind,
        "resource_id": resource,
        "resource_type": resource_type,
        "description": description,
        "violated_constraint": constraint,
        "causal_path": path,
        "severity": "hard",
        "epistemic_status": "COMPUTED",
        "repairable": True,
        "provenance": provenance,
        "shared_resource": resource,
        "constraint": constraint,
    }


def demo_pair() -> list[dict[str, Any]]:
    """Fictional Alex futures. The overlap is data, not a UI branch."""
    return [
        {
            "future_id": "demo-airport",
            "plan_id": "demo-airport",
            "name": "NYC airport window",
            "status": "HEALTHY",
            "material_unknowns": 0,
            "nearest_failure": "No discovered failure inside the modeled ranges.",
            "scenario_id": "demo",
            "effects": {},
            "linked_entities": [],
            "life": {"nodes": [], "edges": []},
            "claims": [
                {
                    "resource_id": "alex",
                    "resource_type": "person",
                    "start": 840,
                    "end": 1020,
                    "protected": False,
                    "label": "Airport travel 2:00–5:00 PM",
                }
            ],
        },
        {
            "future_id": "demo-opening",
            "plan_id": "demo-opening",
            "name": "Gallery opening",
            "status": "HEALTHY",
            "material_unknowns": 0,
            "nearest_failure": "No discovered failure inside the modeled ranges.",
            "scenario_id": "demo",
            "effects": {},
            "linked_entities": [],
            "life": {"nodes": [], "edges": []},
            "claims": [
                {
                    "resource_id": "alex",
                    "resource_type": "person",
                    "start": 900,
                    "end": 960,
                    "protected": True,
                    "label": "Gallery opening 3:00–4:00 PM",
                }
            ],
        },
    ]
