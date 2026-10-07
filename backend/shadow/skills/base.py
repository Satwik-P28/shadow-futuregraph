"""Typed skill manifests. A skill declares capability. It does not grant authority."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Skill(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1"
    preconditions: list[str] = Field(default_factory=list)
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
    possible_effects: list[str] = Field(default_factory=list)
    irreversible_effects: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    compensation_actions: list[str] = Field(default_factory=list)
    risk_dimensions: list[str] = Field(default_factory=list)

    def grants_authority(self) -> bool:
        return False
