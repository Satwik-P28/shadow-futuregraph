"""Detect when two futures cannot both keep the same resource."""

from __future__ import annotations

from typing import Any


def cross_plan_conflicts(futures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for index, left in enumerate(futures):
        for right in futures[index + 1 :]:
            if left["future_id"] == right["future_id"]:
                continue
            shared = set(left.get("effects") or {}) & set(right.get("effects") or {})
            for resource in sorted(shared):
                if left["effects"][resource] == right["effects"][resource]:
                    continue
                found.append(
                    {
                        "future_ids": [left["future_id"], right["future_id"]],
                        "shared_resource": resource,
                        "constraint": "The two futures set this resource to different values.",
                        "causal_path": [resource],
                        "severity": "hard",
                        "repairable": True,
                    }
                )
    return found
