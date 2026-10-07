"""Semantic authorization. API scopes are not enough."""

from __future__ import annotations

from typing import Any

from shadow.core.models import ActionDef, FutureContract


class AuthorizationDenied(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def authorize(contract: FutureContract, action: ActionDef, world: dict[str, Any] | None = None) -> None:
    del world
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
            if allowed.action_type == action.action_type and allowed.resource == action.resource
        ),
        None,
    )
    if match is None or action.resource not in contract.resource_scopes:
        raise AuthorizationDenied("Blocked: action is outside the approved future.")
    if action.cost > contract.spending_limit + 1e-9 or action.cost > match.max_cost + 1e-9:
        raise AuthorizationDenied("Blocked: cost is outside the approved future.")
