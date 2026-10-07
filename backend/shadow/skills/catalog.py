"""The three reusable skills. They do not choose a future or authorize an action."""

from __future__ import annotations

from shadow.skills.base import Skill

RESCHEDULE_TRIP = Skill(
    id="reschedule_trip",
    name="Reschedule Trip",
    description="Reads the trip, calendar, ride, hard commitments, preferences, and budget, then asks the future engine for a repair.",
    preconditions=["a travel plan exists"],
    reads=["travel reservation", "calendar", "ride", "hard commitments", "preferences", "budget"],
    writes=["flight", "ride", "travel calendar block"],
    available_actions=["change flight", "update ride", "update travel calendar block"],
    possible_effects=["reservation moves", "ride moves", "trip block moves"],
    irreversible_effects=["ticketed flight change"],
    required_tools=["travel", "calendar"],
    verification_steps=[
        "reservation matches approved future",
        "ride matches approved future",
        "calendar matches approved future",
        "protected events unchanged",
    ],
    compensation_actions=["restore prior booking where the provider supports it"],
    risk_dimensions=["cost", "schedule", "other people"],
)

HANDLE_DISRUPTION = Skill(
    id="handle_trip_disruption",
    name="Handle Trip Disruption",
    description="A world event arrived. Re-check the approved trip future and propose a repair. Do not execute it.",
    preconditions=["an approved trip future exists", "a world event names a trip dependency"],
    reads=["approved trip future", "disruption", "dependent commitments", "alternatives"],
    writes=[],
    available_actions=["propose repair"],
    possible_effects=["contract reaffirmed", "contract marked stale", "repair proposed"],
    irreversible_effects=[],
    required_tools=["travel"],
    verification_steps=["approved future re-evaluated", "no consequential action runs before approval"],
    compensation_actions=[],
    risk_dimensions=["stale authority", "missed commitment"],
)

COORDINATE_SCHEDULE = Skill(
    id="coordinate_schedule",
    name="Coordinate Schedule",
    description="Reads people, availability, fixed commitments, and preferences for a schedule change outside a single trip.",
    preconditions=["a scheduling plan exists"],
    reads=["people", "events", "availability", "fixed commitments", "preferences"],
    writes=["calendar block", "coordination draft"],
    available_actions=["move approved event", "create or update calendar block", "draft coordination message"],
    possible_effects=["an approved event moves", "a calendar block changes", "a draft is stored"],
    irreversible_effects=[],
    required_tools=["calendar", "mail"],
    verification_steps=["fixed commitments unchanged", "moved event matches the approved future"],
    compensation_actions=["restore the previous calendar block"],
    risk_dimensions=["other people", "fixed commitments"],
)

SKILLS = (RESCHEDULE_TRIP, HANDLE_DISRUPTION, COORDINATE_SCHEDULE)
