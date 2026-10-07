"""Map a world event onto the contracts that actually depend on it."""

from __future__ import annotations

from typing import Any

from shadow.core.models import FutureContract, Scenario
from shadow.watcher.models import FutureDrift, WorldEvent


def depends_on(contract: FutureContract, scenario: Scenario, event: WorldEvent) -> bool:
    names = set(event.affected_entities) | set((event.payload.get("set_baseline") or {}))
    if not names:
        return False
    assumed = {item.variable for item in contract.assumptions if item.variable}
    variables = {var.id for var in scenario.variables}
    return bool(names & (assumed | variables))


def unchanged(contract: FutureContract | None, explanation: str) -> FutureDrift:
    status = "none" if contract is None else contract.status
    return FutureDrift(
        contract_id=None if contract is None else contract.contract_id,
        previous_status=status,
        new_status="UNCHANGED",
        still_feasible=True if contract and contract.status in {"ACTIVE", "REAFFIRMED", "COMPLETED"} else None,
        repair_required=False,
        explanation=explanation,
        provenance="watcher",
    )


def unknown_drift(contract: FutureContract | None) -> FutureDrift:
    return FutureDrift(
        contract_id=None if contract is None else contract.contract_id,
        previous_status="none" if contract is None else contract.status,
        new_status="UNKNOWN",
        still_feasible=None,
        repair_required=False,
        explanation="The world event is incomplete. Shadow will not treat the approved future as safe or unsafe.",
        provenance="watcher",
    )


def affected_constraints(scenario: Scenario, repairs: list[Any], approved_id: str | None) -> list[str]:
    approved = next((item for item in repairs if item.id == approved_id), None)
    if approved is None:
        return []
    names: list[str] = []
    for failure in approved.failures:
        names.extend(failure.violated_constraints)
    return sorted(set(names))
