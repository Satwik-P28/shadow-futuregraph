"""Typed world events and the drift they cause. The watcher does not execute repairs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorldEvent(BaseModel):
    event_id: str
    source: str
    event_type: str
    observed_at: str
    affected_entities: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    epistemic_status: Literal["VERIFIED", "COMPUTED", "ESTIMATED", "INFERRED", "UNKNOWN"] = "VERIFIED"
    provenance: str = "world-event"


class FutureDrift(BaseModel):
    contract_id: str | None
    affected_assumptions: list[str] = Field(default_factory=list)
    affected_constraints: list[str] = Field(default_factory=list)
    previous_status: str
    new_status: Literal["UNCHANGED", "DEGRADED", "INVALID", "UNKNOWN"]
    still_feasible: bool | None
    repair_required: bool
    explanation: str
    provenance: str
