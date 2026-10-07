"""Semantic authorization. API scopes are not enough."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shadow.core.models import ActionDef, FutureContract, Scenario
from shadow.simulation.engine import bind, evaluate_constraints
from shadow.world.loader import action_map


class AuthorizationDenied(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def authorize(contract: FutureContract, action: ActionDef, world: dict[str, Any] | None = None) -> None:
    scenario = _scenario(world)
    _check_expiry(contract, world or {})
    if contract.status in {"STALE", "HALTED"}:
        raise AuthorizationDenied("Future no longer valid")
    if contract.status not in {"ACTIVE", "REAFFIRMED", "COMPLETED"}:
        raise AuthorizationDenied("contract is not active")
    if action.id in contract.forbidden_actions:
        raise AuthorizationDenied("Blocked: action is outside the approved future.")
    match = next(
        (
            allowed
            for allowed in contract.allowed_actions
            if allowed.action_id == action.id
            and allowed.action_type == action.action_type
            and allowed.resource == action.resource
        ),
        None,
    )
    if match is None or action.resource not in contract.resource_scopes:
        raise AuthorizationDenied("Blocked: action is outside the approved future.")
    if action.cost > contract.spending_limit + 1e-9 or action.cost > match.max_cost + 1e-9:
        raise AuthorizationDenied("Blocked: cost is outside the approved future.")
    _check_assumptions(contract, scenario)
    _check_invariants(contract, scenario, action)


def _scenario(world: dict[str, Any] | None) -> Scenario:
    if not isinstance(world, dict) or not isinstance(world.get("scenario"), Scenario):
        raise AuthorizationDenied("missing material state")
    return world["scenario"]


def _check_expiry(contract: FutureContract, world: dict[str, Any]) -> None:
    now = world.get("now")
    if not isinstance(now, datetime):
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        expires = datetime.strptime(contract.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise AuthorizationDenied("contract is expired") from None
    if now >= expires:
        raise AuthorizationDenied("contract is expired")


def _check_assumptions(contract: FutureContract, scenario: Scenario) -> None:
    baselines = {var.id: var.baseline for var in scenario.variables}
    for assumption in contract.assumptions:
        if assumption.status == "invalidated" or not assumption.variable:
            raise AuthorizationDenied("stale assumption")
        if assumption.variable not in baselines:
            raise AuthorizationDenied("missing material state")
        if not _same(baselines[assumption.variable], assumption.expected):
            raise AuthorizationDenied("stale assumption")


def _check_invariants(contract: FutureContract, scenario: Scenario, action: ActionDef) -> None:
    known = {item.id: item for item in scenario.constraints}
    if any(item not in known for item in contract.invariants):
        raise AuthorizationDenied("missing material state")
    mapping = action_map(scenario)
    effects: dict[str, Any] = {}
    for allowed in contract.allowed_actions:
        if allowed.action_id not in mapping:
            raise AuthorizationDenied("missing material state")
        effects.update(mapping[allowed.action_id].effects)
    for key, value in action.effects.items():
        if not _same(effects.get(key), value):
            raise AuthorizationDenied("action violates a hard invariant")
    env = bind(scenario, effects=effects)
    results = evaluate_constraints(scenario, env)
    for invariant_id in contract.invariants:
        constraint = known[invariant_id]
        if constraint.hardness != "hard":
            continue
        value = results.get(invariant_id)
        if value is None or value is False:
            raise AuthorizationDenied("action violates a hard invariant")


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool):
        return abs(float(left) - float(right)) <= 1e-9
    return left == right
