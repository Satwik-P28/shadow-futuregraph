"""Deterministic providers for the synthetic Alex world."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from shadow.core.models import ActionDef


class ProviderError(RuntimeError):
    pass


class SandboxProviders:
    """Travel, calendar, mail, and search stand-ins. Never labeled live."""

    mode = "SANDBOX"

    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "bk_nyc": {"day": "thursday", "departure_min": 880, "status": "confirmed"},
            "ride_nyc": {"pickup_min": 725, "status": "confirmed"},
            "hotel_nyc": {"status": "confirmed"},
            "cal_trip": {"summary": "NYC trip", "day": "thursday"},
            "cal_dinner": {"summary": "Dinner with Jordan", "day": "friday", "time": "19:00"},
            "cal_review": {"summary": "Design review", "day": "friday", "time": "08:30"},
            "cal_exam": {"summary": "Algorithms exam", "day": "monday", "time": "10:00"},
            "drafts": [],
        }
        self.applied: dict[str, dict[str, Any]] = {}
        self.mutations = 0
        self.fail_next: str | None = None
        self.lie_next: str | None = None

    def preview(self, action: ActionDef) -> dict[str, Any]:
        return {"action_id": action.id, "resource": action.resource, "effects": action.effects, "mode": self.mode}

    def execute(self, action: ActionDef, idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self.applied:
            return deepcopy(self.applied[idempotency_key])
        if self.fail_next == "timeout":
            self.fail_next = None
            self._apply(action)
            self.applied[idempotency_key] = {"status": "executed", "resource": action.resource}
            raise ProviderError("timeout after the provider committed")
        if self.fail_next == "flight" and action.action_type == "travel.change_flight":
            self.fail_next = None
            raise ProviderError("provider rejected the change")
        if self.fail_next == "calendar" and action.action_type.startswith("calendar"):
            self.fail_next = None
            raise ProviderError("calendar update failed before commit")
        if self.lie_next == action.resource:
            self.lie_next = None
            self.applied[idempotency_key] = {"status": "executed", "resource": action.resource, "lied": True}
            return deepcopy(self.applied[idempotency_key])
        self._apply(action)
        result = {"status": "executed", "resource": action.resource, "mode": self.mode}
        self.applied[idempotency_key] = result
        return deepcopy(result)

    def verify(self, action: ActionDef) -> bool:
        resource = self.state.get(action.resource)
        if "state_token" in action.effects:
            return resource is not None and resource.get("state_token") == action.effects["state_token"]
        if resource is None:
            return action.resource == "workshop" or action.resource.startswith("move") or action.resource.startswith("lease")
        if action.resource == "bk_nyc" and "flight_departure_min" in action.effects:
            return resource.get("departure_min") == action.effects["flight_departure_min"]
        if action.resource == "ride_nyc" and "ride_pickup_min" in action.effects:
            return resource.get("pickup_min") == action.effects["ride_pickup_min"]
        if action.resource == "cal_trip":
            return resource.get("day") == "friday"
        if action.resource == "cal_exam":
            return False
        return True

    def compensate(self, action: ActionDef, idempotency_key: str) -> dict[str, Any]:
        key = idempotency_key + ":compensate"
        if key in self.applied:
            return deepcopy(self.applied[key])
        if action.resource == "bk_nyc":
            self.state["bk_nyc"] = {"day": "thursday", "departure_min": 880, "status": "confirmed"}
            self.mutations += 1
        result = {"status": "compensated", "resource": action.resource}
        self.applied[key] = result
        return result

    def supports_compensation(self, action: ActionDef) -> bool:
        return action.compensatable and not action.irreversible

    def search(self, query: str) -> list[dict[str, Any]]:
        return [
            {
                "query": query,
                "source": "fixture",
                "observed_at": "2026-10-07T12:00:00Z",
                "claim": "No active travel disruption is recorded in the sandbox feed.",
                "provenance": "fixture-search",
                "mode": self.mode,
            }
        ]

    def create_draft(self, subject: str, body: str) -> dict[str, Any]:
        draft = {"subject": subject, "body": body, "sent": False}
        self.state["drafts"].append(draft)
        return draft

    def _apply(self, action: ActionDef) -> None:
        self.mutations += 1
        if action.resource == "bk_nyc":
            self.state["bk_nyc"]["day"] = "friday"
            if "flight_departure_min" in action.effects:
                self.state["bk_nyc"]["departure_min"] = action.effects["flight_departure_min"]
        elif action.resource == "ride_nyc" and "ride_pickup_min" in action.effects:
            self.state["ride_nyc"]["pickup_min"] = action.effects["ride_pickup_min"]
        elif action.resource == "cal_trip":
            self.state["cal_trip"]["day"] = "friday"
        elif action.resource == "cal_dinner" and action.effects.get("dinner_fixed") is False:
            self.state["cal_dinner"]["time"] = "23:00"
        elif action.resource == "cal_exam":
            self.state["cal_exam"]["moved"] = True
        elif "state_token" in action.effects:
            bucket = self.state.setdefault(action.resource, {})
            if isinstance(bucket, dict):
                bucket["state_token"] = action.effects["state_token"]
