"""Receding-horizon execution with idempotency and typed compensation."""

from __future__ import annotations

from shadow.core.models import ActionDef, FutureContract, Scenario
from shadow.integrations.sandbox import ProviderError, SandboxProviders
from shadow.runtime.broker import AuthorizationDenied, authorize
from shadow.runtime.events import EventLog
from shadow.world.loader import action_map


def order_actions(actions: list[ActionDef]) -> list[ActionDef]:
    def rank(action: ActionDef) -> tuple[int, str]:
        if action.reversible and not action.irreversible:
            return (0, action.id)
        if action.compensatable:
            return (1, action.id)
        return (2, action.id)

    return sorted(actions, key=rank)


def compensation_decision(failed: ActionDef, completed: list[ActionDef]) -> str:
    """Do not compensate when undoing a committed step would make the world worse."""
    if failed.retryable and failed.action_type.startswith("calendar"):
        return "retry"
    if failed.action_type.startswith("calendar") and any(item.action_type == "travel.change_flight" for item in completed):
        return "halt_keep"
    if failed.irreversible or not failed.compensatable:
        return "halt_keep"
    return "compensate"


def execute_bundle(
    *,
    scenario: Scenario,
    contract: FutureContract,
    providers: SandboxProviders,
    events: EventLog,
    plan_id: str,
) -> dict[str, object]:
    actions = action_map(scenario)
    ordered = order_actions([actions[item.action_id] for item in contract.allowed_actions])
    completed: list[ActionDef] = []
    results = []
    for action in ordered:
        try:
            authorize(contract, action, providers.state)
        except AuthorizationDenied as exc:
            events.append(plan_id, "ACTION_BLOCKED", {"action_id": action.id, "reason": exc.reason}, "broker")
            return {"status": "blocked", "reason": exc.reason, "results": results}
        preview = providers.preview(action)
        events.append(plan_id, "ACTION_PREVIEWED", {"action_id": action.id, "preview": preview}, "runtime")
        key = f"{contract.contract_id}:{action.id}"
        try:
            outcome = providers.execute(action, key)
        except ProviderError as exc:
            if key in providers.applied and providers.verify(action):
                completed.append(action)
                events.append(
                    plan_id,
                    "ACTION_VERIFIED",
                    {"action_id": action.id, "resource": action.resource, "reconciled": True},
                    "runtime",
                )
                results.append({"action_id": action.id, "status": "verified", "reconciled": True})
                continue
            decision = compensation_decision(action, completed)
            if decision == "retry":
                try:
                    outcome = providers.execute(action, key)
                except ProviderError:
                    decision = "halt_keep"
                else:
                    if not providers.verify(action):
                        decision = compensation_decision(action, completed)
                    else:
                        completed.append(action)
                        events.append(
                            plan_id,
                            "ACTION_VERIFIED",
                            {"action_id": action.id, "resource": action.resource},
                            "runtime",
                        )
                        results.append({"action_id": action.id, "status": "verified"})
                        continue
            if decision == "compensate":
                for done in reversed(completed):
                    if providers.supports_compensation(done):
                        providers.compensate(done, f"{contract.contract_id}:{done.id}")
                        events.append(
                            plan_id,
                            "COMPENSATION_EXECUTED",
                            {"action_id": done.id, "resource": done.resource},
                            "runtime",
                        )
            events.append(
                plan_id,
                "EXECUTION_HALTED",
                {"action_id": action.id, "decision": decision, "error": str(exc)},
                "runtime",
            )
            return {"status": "halted", "decision": decision, "results": results}
        if not providers.verify(action):
            events.append(
                plan_id,
                "EXECUTION_HALTED",
                {"action_id": action.id, "decision": "verify_mismatch"},
                "runtime",
            )
            return {"status": "halted", "decision": "verify_mismatch", "results": results}
        completed.append(action)
        events.append(
            plan_id,
            "ACTION_EXECUTED",
            {"action_id": action.id, "resource": action.resource, "effects": action.effects},
            "runtime",
        )
        events.append(plan_id, "ACTION_VERIFIED", {"action_id": action.id}, "runtime")
        results.append({"action_id": action.id, "status": "verified", "outcome": outcome})
    events.append(plan_id, "RECONCILIATION_COMPLETE", {"matched": True}, "runtime")
    return {"status": "verified", "results": results, "state": providers.state}
